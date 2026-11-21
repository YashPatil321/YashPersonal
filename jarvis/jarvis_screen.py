"""
Screen control by voice, from an allow list. Windows only (prints what it would do elsewhere).

  "put chrome on the left"            snap a window into a zone
  "move spotify to the right third"   zones: left, right, left third, center third, right third,
                                      left quarter, right quarter, center, full
  "maximize chrome", "minimize discord", "show desktop"
  "switch to claude", "focus vs code"  bring an app to the front
  "room layout", "coding layout", "focus layout", "school layout"
  "type see you at practice"           types into whatever window is active
  "press enter", "new tab", "close tab", "copy", "paste", "undo", "save", "refresh"
  "start dictation"                    starts Wispr Flow hands free (Ctrl+Win+Space)

Nothing here can delete files, run programs it wasn't told about, or type a key that isn't on the list.
"""

import re
import sys
import time

IS_WIN = sys.platform == "win32"

# spoken name -> process names that count as that app
APPS = {
    "chrome": ["chrome.exe"], "browser": ["chrome.exe", "msedge.exe"], "edge": ["msedge.exe"],
    "spotify": ["spotify.exe"], "claude": ["claude.exe"], "vs code": ["code.exe"], "vscode": ["code.exe"], "code": ["code.exe"],
    "discord": ["discord.exe"], "terminal": ["windowsterminal.exe"], "explorer": ["explorer.exe"], "files": ["explorer.exe"],
    "steam": ["steam.exe"], "notepad": ["notepad.exe"], "hq": ["chrome.exe", "msedge.exe"],
}

# zones as fractions of the screen's work area: (x, y, w, h)
ZONES = {
    "left": (0, 0, .5, 1), "right": (.5, 0, .5, 1), "full": (0, 0, 1, 1),
    "left third": (0, 0, 1 / 3, 1), "center third": (1 / 3, 0, 1 / 3, 1), "middle third": (1 / 3, 0, 1 / 3, 1), "right third": (2 / 3, 0, 1 / 3, 1),
    "left quarter": (0, 0, .25, 1), "right quarter": (.75, 0, .25, 1), "center": (.25, 0, .5, 1), "middle": (.25, 0, .5, 1),
    "top left": (0, 0, .5, .5), "top right": (.5, 0, .5, .5), "bottom left": (0, .5, .5, .5), "bottom right": (.5, .5, .5, .5),
}

# layouts for the 5120x1440 ultrawide: app -> zone. Apps that aren't open get launched by the caller.
LAYOUTS = {
    "room": [("claude", "left quarter"), ("hq", "center"), ("spotify", "right quarter")],
    "coding": [("claude", "left quarter"), ("vs code", "center"), ("chrome", "right quarter")],
    "school": [("chrome", "left"), ("claude", "right")],
    "focus": "focus",   # the active window goes center, everything else minimizes
}

KEYS = {   # spoken -> virtual key chord
    "enter": ["RETURN"], "tab": ["TAB"], "escape": ["ESCAPE"], "backspace": ["BACK"], "space": ["SPACE"],
    "copy": ["CONTROL", "C"], "paste": ["CONTROL", "V"], "cut": ["CONTROL", "X"], "undo": ["CONTROL", "Z"], "redo": ["CONTROL", "Y"],
    "select all": ["CONTROL", "A"], "save": ["CONTROL", "S"], "find": ["CONTROL", "F"],
    "new tab": ["CONTROL", "T"], "close tab": ["CONTROL", "W"], "reopen tab": ["CONTROL", "SHIFT", "T"],
    "next tab": ["CONTROL", "TAB"], "previous tab": ["CONTROL", "SHIFT", "TAB"], "refresh": ["F5"],
    "scroll down": ["NEXT"], "page down": ["NEXT"], "scroll up": ["PRIOR"], "page up": ["PRIOR"],
    "screenshot": ["LWIN", "SHIFT", "S"], "show desktop": ["LWIN", "D"], "task view": ["LWIN", "TAB"],
    "dictation": ["CONTROL", "LWIN", "SPACE"],   # Wispr Flow hands free
}
VK = {"RETURN": 0x0D, "TAB": 0x09, "ESCAPE": 0x1B, "BACK": 0x08, "SPACE": 0x20, "CONTROL": 0x11, "SHIFT": 0x10, "MENU": 0x12,
      "LWIN": 0x5B, "F5": 0x74, "NEXT": 0x22, "PRIOR": 0x21}


def _norm(t):
    return re.sub(r"\s+", " ", re.sub(r"^(the|my)\s+", "", t.strip().lower()))


def route_screen(t):
    """t is the normalized lowercase line. Returns (action, arg) or None."""
    m = re.fullmatch(r"(?:switch|go|change) to (?:the )?(.+?) layout|(?:the )?(.+?) layout|layout (.+)", t)
    if m:
        name = (m.group(1) or m.group(2) or m.group(3)).strip()
        if name in LAYOUTS:
            return ("layout", name)
    m = re.fullmatch(r"(?:put|move|snap|send) (.+?) (?:on|to|into) (?:the )?(.+?)(?: side| half| of the screen)?", t)
    if m and _norm(m.group(1)) in APPS and m.group(2).strip() in ZONES:
        return ("snap", (_norm(m.group(1)), m.group(2).strip()))
    m = re.fullmatch(r"(maximize|minimize|full screen|fullscreen) (.+)", t)
    if m and _norm(m.group(2)) in APPS:
        return ("maximize" if m.group(1) != "minimize" else "minimize", _norm(m.group(2)))
    m = re.fullmatch(r"(?:switch to|focus|focus on|bring up|show me) (.+)", t)
    if m and _norm(m.group(1)) in APPS:
        return ("focus", _norm(m.group(1)))
    if re.fullmatch(r"(?:show (?:the )?desktop|minimize everything|hide everything)", t):
        return ("keys", "show desktop")
    if re.fullmatch(r"(?:start|stop|toggle) dictation|dictate", t):
        return ("keys", "dictation")
    m = re.fullmatch(r"(?:press|hit|do a?) (.+)|(.+)", t)
    key = (m.group(1) or m.group(2)).strip() if m else ""
    if key in KEYS and (m.group(1) or key in ("new tab", "close tab", "reopen tab", "next tab", "previous tab", "copy", "paste", "undo", "redo", "select all", "screenshot", "scroll down", "scroll up", "refresh")):
        return ("keys", key)
    m = re.fullmatch(r"(?:type out|type) (.+)", t)
    if m:
        return ("type", m.group(1))
    return None


class Screen:
    """Talks to Windows through user32. Swapped for a recorder in tests."""
    def __init__(self):
        self.log = []

    # ---- windows ----
    def windows(self):
        """Visible top level windows: [(hwnd, exe, title)]."""
        if not IS_WIN:
            return []
        import ctypes
        from ctypes import wintypes
        u, k = ctypes.windll.user32, ctypes.windll.kernel32
        out = []

        @ctypes.WINFUNCTYPE(wintypes.BOOL, wintypes.HWND, wintypes.LPARAM)
        def cb(h, _):
            if not u.IsWindowVisible(h) or u.GetWindowTextLengthW(h) == 0:
                return True
            buf = ctypes.create_unicode_buffer(512)
            u.GetWindowTextW(h, buf, 512)
            pid = wintypes.DWORD()
            u.GetWindowThreadProcessId(h, ctypes.byref(pid))
            exe = ""
            hp = k.OpenProcess(0x1000, False, pid.value)   # query limited information
            if hp:
                name = ctypes.create_unicode_buffer(512)
                size = wintypes.DWORD(512)
                if k.QueryFullProcessImageNameW(hp, 0, name, ctypes.byref(size)):
                    exe = name.value.split("\\")[-1].lower()
                k.CloseHandle(hp)
            out.append((h, exe, buf.value))
            return True
        u.EnumWindows(cb, 0)
        return out

    def find(self, app):
        exes = APPS.get(app, [app + ".exe"])
        wins = [w for w in self.windows() if w[1] in exes]
        if app == "hq":
            wins = [w for w in wins if "yash hq" in w[2].lower()] or wins
        return wins[0][0] if wins else None

    def work_area(self):
        if not IS_WIN:
            return (0, 0, 5120, 1400)
        import ctypes
        from ctypes import wintypes
        r = wintypes.RECT()
        ctypes.windll.user32.SystemParametersInfoW(0x0030, 0, ctypes.byref(r), 0)   # SPI_GETWORKAREA
        return (r.left, r.top, r.right - r.left, r.bottom - r.top)

    def place(self, hwnd, rect):
        self.log.append(("place", hwnd, rect))
        if not IS_WIN:
            return
        import ctypes
        u = ctypes.windll.user32
        u.ShowWindow(hwnd, 9)   # restore if maximized
        x, y, w, h = rect
        u.SetWindowPos(hwnd, 0, int(x), int(y), int(w), int(h), 0x0040)   # SWP_SHOWWINDOW

    def show(self, hwnd, cmd):
        self.log.append(("show", hwnd, cmd))
        if IS_WIN:
            import ctypes
            ctypes.windll.user32.ShowWindow(hwnd, {"max": 3, "min": 6, "restore": 9}[cmd])

    def focus(self, hwnd):
        self.log.append(("focus", hwnd))
        if IS_WIN:
            import ctypes
            u = ctypes.windll.user32
            u.ShowWindow(hwnd, 9)
            u.keybd_event(0x12, 0, 0, 0)    # a tap of Alt lets Windows hand over focus
            u.keybd_event(0x12, 0, 2, 0)
            u.SetForegroundWindow(hwnd)

    def foreground(self):
        if not IS_WIN:
            return None
        import ctypes
        return ctypes.windll.user32.GetForegroundWindow()

    # ---- keyboard ----
    def chord(self, names):
        self.log.append(("chord", tuple(names)))
        if not IS_WIN:
            return
        import ctypes
        u = ctypes.windll.user32
        codes = [VK[n] if n in VK else ord(n) for n in names]
        for c in codes:
            u.keybd_event(c, 0, 0, 0)
        for c in reversed(codes):
            u.keybd_event(c, 0, 2, 0)

    def type_text(self, text):
        """Types unicode text into the active window, one character at a time (no shortcuts can fire)."""
        self.log.append(("type", text))
        if not IS_WIN:
            return
        import ctypes
        from ctypes import wintypes

        class KI(ctypes.Structure):
            _fields_ = [("wVk", wintypes.WORD), ("wScan", wintypes.WORD), ("dwFlags", wintypes.DWORD), ("time", wintypes.DWORD), ("dwExtraInfo", ctypes.POINTER(wintypes.ULONG))]

        class INPUT(ctypes.Structure):
            class _U(ctypes.Union):
                _fields_ = [("ki", KI), ("pad", ctypes.c_byte * 32)]
            _anonymous_ = ("u",)
            _fields_ = [("type", wintypes.DWORD), ("u", _U)]

        for ch in text:
            for flags in (0x0004, 0x0004 | 0x0002):   # KEYEVENTF_UNICODE, then key up
                inp = INPUT(type=1)
                inp.ki = KI(0, ord(ch), flags, 0, None)
                ctypes.windll.user32.SendInput(1, ctypes.byref(inp), ctypes.sizeof(INPUT))
            time.sleep(0.004)


def zone_rect(area, zone):
    x0, y0, W, H = area
    fx, fy, fw, fh = ZONES[zone]
    return (x0 + fx * W, y0 + fy * H, fw * W, fh * H)


def clean_typing(text):
    """What you said, as you'd type it: first letter capital, spoken punctuation turned into marks."""
    t = text.strip()
    for w, mark in ((" comma", ","), (" period", "."), (" full stop", "."), (" question mark", "?"), (" exclamation mark", "!"), (" new line", "\n")):
        t = t.replace(w, mark)
    return t[:1].upper() + t[1:] if t else t


class ScreenControl:
    def __init__(self, say, launch, screen=None):
        self.say, self.launch, self.s = say, launch, screen or Screen()

    def _win(self, app, open_if_missing=False):
        h = self.s.find(app)
        if not h and open_if_missing:
            target = {"hq": None, "vs code": "code", "vscode": "code", "browser": "chrome"}.get(app, app)
            if target:
                self.launch("spotify:" if target == "spotify" else target)
                for _ in range(20):
                    time.sleep(0.5)
                    h = self.s.find(app)
                    if h:
                        break
        return h

    def handle(self, action, arg):
        area = self.s.work_area()
        if action == "snap":
            app, zone = arg
            h = self._win(app, True)
            if not h:
                return self.say(f"I can't find {app}.")
            self.s.place(h, zone_rect(area, zone))
        elif action in ("maximize", "minimize"):
            h = self._win(arg)
            if not h:
                return self.say(f"{arg} isn't open.")
            self.s.show(h, "max" if action == "maximize" else "min")
        elif action == "focus":
            h = self._win(arg, True)
            if not h:
                return self.say(f"I can't find {arg}.")
            self.s.focus(h)
        elif action == "layout":
            lay = LAYOUTS[arg]
            if lay == "focus":
                fg = self.s.foreground()
                for h, exe, _ in self.s.windows():
                    if h != fg and exe not in ("explorer.exe",):
                        self.s.show(h, "min")
                if fg:
                    self.s.place(fg, zone_rect(area, "center"))
                return self.say("Focus mode.")
            missing = []
            for app, zone in lay:
                h = self._win(app, True)
                if h:
                    self.s.place(h, zone_rect(area, zone))
                else:
                    missing.append(app)
            self.say(arg.capitalize() + " layout." + (" Couldn't open " + ", ".join(missing) + "." if missing else ""))
        elif action == "keys":
            self.s.chord(KEYS[arg])
        elif action == "type":
            self.s.type_text(clean_typing(arg))
