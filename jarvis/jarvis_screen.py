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

if IS_WIN:
    # Work in real pixels. Without this, Windows display scaling makes windows land in the wrong place and size.
    try:
        import ctypes
        ctypes.windll.user32.SetProcessDpiAwarenessContext(ctypes.c_void_p(-4))   # per monitor v2
    except Exception:
        try:
            ctypes.windll.shcore.SetProcessDpiAwareness(2)
        except Exception:
            pass

# spoken name -> process names that count as that app
APPS = {
    "chrome": ["chrome.exe"], "browser": ["chrome.exe", "msedge.exe"], "edge": ["msedge.exe"],
    "spotify": ["spotify.exe"], "claude": ["claude.exe"], "vs code": ["code.exe"], "vscode": ["code.exe"], "code": ["code.exe"],
    "discord": ["discord.exe"], "terminal": ["windowsterminal.exe"], "explorer": ["explorer.exe"], "files": ["explorer.exe"],
    "steam": ["steam.exe"], "notepad": ["notepad.exe"], "hq": ["chrome.exe", "msedge.exe"],
    "whatsapp": ["whatsapp.exe", "whatsapp.root.exe"],
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
        self.problems = []   # what Windows refused, in plain words

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

    def work_area(self, hwnd=None):
        """Work area (screen minus taskbar) of the monitor the window is on, or the primary one."""
        if not IS_WIN:
            return (0, 0, 5120, 1400)
        import ctypes
        from ctypes import wintypes

        class MI(ctypes.Structure):
            _fields_ = [("cbSize", wintypes.DWORD), ("rcMonitor", wintypes.RECT), ("rcWork", wintypes.RECT), ("dwFlags", wintypes.DWORD)]
        u = ctypes.windll.user32
        mon = u.MonitorFromWindow(hwnd, 2) if hwnd else u.MonitorFromPoint(wintypes.POINT(0, 0), 1)
        mi = MI(cbSize=ctypes.sizeof(MI))
        if mon and u.GetMonitorInfoW(mon, ctypes.byref(mi)):
            r = mi.rcWork
            return (r.left, r.top, r.right - r.left, r.bottom - r.top)
        r = wintypes.RECT()
        u.SystemParametersInfoW(0x0030, 0, ctypes.byref(r), 0)
        return (r.left, r.top, r.right - r.left, r.bottom - r.top)

    def place(self, hwnd, rect):
        """Moves a window so its VISIBLE edges land exactly on the zone. Windows 10/11 windows have an invisible
        resize border (about 7 px) that SetWindowPos counts, which is what leaves gaps and overlaps."""
        self.log.append(("place", hwnd, rect))
        if not IS_WIN:
            return
        import ctypes
        from ctypes import wintypes
        u = ctypes.windll.user32
        if u.IsIconic(hwnd) or u.IsZoomed(hwnd):
            u.ShowWindow(hwnd, 9)   # restore first, a maximized window ignores moves
            time.sleep(0.05)
        x, y, w, h = (int(round(v)) for v in rect)
        outer, vis = wintypes.RECT(), wintypes.RECT()
        u.GetWindowRect(hwnd, ctypes.byref(outer))
        l = t = r = b = 0
        if ctypes.windll.dwmapi.DwmGetWindowAttribute(hwnd, 9, ctypes.byref(vis), ctypes.sizeof(vis)) == 0:   # DWMWA_EXTENDED_FRAME_BOUNDS
            l, t, r, b = vis.left - outer.left, vis.top - outer.top, outer.right - vis.right, outer.bottom - vis.bottom
        if not u.SetWindowPos(hwnd, 0, x - l, y - t, w + l + r, h + t + b, 0x0004 | 0x0040):   # no z order change, show
            self._blocked("move", ctypes.windll.kernel32.GetLastError())

    def show(self, hwnd, cmd):
        self.log.append(("show", hwnd, cmd))
        if IS_WIN:
            import ctypes
            ctypes.windll.user32.ShowWindow(hwnd, {"max": 3, "min": 6, "restore": 9}[cmd])

    def focus(self, hwnd):
        """Brings a window to the front. Windows blocks this for background apps, so borrow the foreground thread's input."""
        self.log.append(("focus", hwnd))
        if not IS_WIN:
            return
        import ctypes
        u, k = ctypes.windll.user32, ctypes.windll.kernel32
        if u.IsIconic(hwnd):
            u.ShowWindow(hwnd, 9)
        fg = u.GetForegroundWindow()
        a, b = u.GetWindowThreadProcessId(fg, None), k.GetCurrentThreadId()
        if a and a != b:
            u.AttachThreadInput(b, a, True)
        u.keybd_event(0x12, 0, 0, 0)
        u.keybd_event(0x12, 0, 2, 0)
        u.BringWindowToTop(hwnd)
        u.SetForegroundWindow(hwnd)
        u.SetFocus(hwnd)
        if a and a != b:
            u.AttachThreadInput(b, a, False)
        if u.GetForegroundWindow() != hwnd:
            # Windows' focus lock said no. Minimizing and restoring a window always brings it to the front.
            u.ShowWindow(hwnd, 6)
            time.sleep(0.08)
            u.ShowWindow(hwnd, 9)
            time.sleep(0.12)
            u.SetForegroundWindow(hwnd)
        if u.GetForegroundWindow() != hwnd:
            self._blocked("focus", 0)
            return False
        return True

    def _blocked(self, what, err):
        msg = {5: "Windows blocked it. That window is probably running as administrator, so Jarvis has to run as administrator too.",
               1400: "that window closed before I could move it."}.get(err, f"Windows refused to {what} that window (error {err}).")
        self.problems.append(msg)

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
                if not ctypes.windll.user32.SendInput(1, ctypes.byref(inp), ctypes.sizeof(INPUT)):
                    self._blocked("type into", ctypes.windll.kernel32.GetLastError() or 5)
                    return False
            time.sleep(0.004)
        return True


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
    def __init__(self, say, launch, screen=None, open_url=None):
        self.say, self.launch, self.s, self.open_url = say, launch, screen or Screen(), open_url

    def _win(self, app, open_if_missing=False):
        h = self.s.find(app)
        if not h and open_if_missing:
            target = {"hq": None, "vs code": "code", "vscode": "code", "browser": "chrome"}.get(app, app)
            if target in ("chrome", "msedge", "edge") and self.open_url:
                self.open_url("about:blank", app_window=None)
            elif target:
                self.launch("spotify:" if target == "spotify" else target)
                for _ in range(20):
                    time.sleep(0.5)
                    h = self.s.find(app)
                    if h:
                        break
        return h

    def handle(self, action, arg):
        self.s.problems = []
        try:
            return self._handle(action, arg)
        finally:
            if self.s.problems:
                self.say(self.s.problems[0])

    def _handle(self, action, arg):
        area = self.s.work_area()
        if action == "snap":
            app, zone = arg
            h = self._win(app, True)
            if not h:
                return self.say(f"I can't find {app}.")
            self.s.place(h, zone_rect(self.s.work_area(h) if self.s.work_area.__code__.co_argcount > 1 else area, zone))
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


# ================= self test =================
def selftest(log=print, launch=None):
    """Checks every piece of computer control on this PC and says what to fix. python jarvis.py --test-pc"""
    import os
    results = []

    def check(name, ok, fix=""):
        results.append((name, ok, fix))
        log(("PASS  " if ok else "FAIL  ") + name + ("" if ok or not fix else "\n        fix: " + fix))

    if not IS_WIN:
        log("This only runs on Windows.")
        return results
    import ctypes
    from ctypes import wintypes
    u, k = ctypes.windll.user32, ctypes.windll.kernel32
    admin = bool(ctypes.windll.shell32.IsUserAnAdmin())
    log(f"user {os.environ.get('USERNAME')}, running as admin: {admin}")
    sid = wintypes.DWORD()
    k.ProcessIdToSessionId(k.GetCurrentProcessId(), ctypes.byref(sid))
    check("Jarvis runs on your desktop (not in the background session)", sid.value != 0,
          "the startup task is set to 'Run whether user is logged on or not'. In Task Scheduler, set it to 'Run only when user is logged on'.")
    try:
        aw = u.GetAwarenessFromDpiAwarenessContext(u.GetThreadDpiAwarenessContext())
        check("DPI aware (windows land in the right place with display scaling)", aw == 2, "update Jarvis, jarvis_screen.py sets this")
    except Exception:
        pass
    sc = Screen()
    wins = sc.windows()
    check(f"can see open windows ({len(wins)} found)", len(wins) > 0, "nothing visible, see the desktop session check above")
    area = sc.work_area()
    log(f"main screen work area: {area}")
    # a test window we own: Notepad
    before = {h for h, _, _ in wins}
    (launch or (lambda t: os.startfile(t)))("notepad")
    h = None
    for _ in range(30):
        time.sleep(0.3)
        for hh, exe, title in sc.windows():
            if exe == "notepad.exe" and hh not in before:
                h = hh
                break
        if h:
            break
    h = h or sc.find("notepad")
    check("open an app (Notepad)", bool(h), "Notepad didn't open")
    if not h:
        return results
    time.sleep(0.6)
    sc.problems = []
    sc.place(h, zone_rect(area, "left"))
    time.sleep(0.3)
    r = wintypes.RECT()
    u.GetWindowRect(h, ctypes.byref(r))
    want = zone_rect(area, "left")
    moved = abs(r.left - want[0]) < 40 and abs((r.right - r.left) - want[2]) < 60
    check("move and resize a window (Notepad to the left half)", moved and not sc.problems, sc.problems[0] if sc.problems else "it didn't land where it should")
    sc.place(h, zone_rect(area, "right"))
    focused = sc.focus(h)
    check("bring a window to the front", bool(focused), "Windows' focus lock blocked it. Try: run Jarvis as administrator, or turn off Focus Assist")
    time.sleep(0.3)
    typed = sc.type_text("Jarvis test, you can close this without saving.")
    check("type text into the active window", bool(typed), sc.problems[-1] if sc.problems else "")
    sc.chord(["CONTROL", "A"])
    check("send a keyboard shortcut (Ctrl+A)", not sc.problems, sc.problems[-1] if sc.problems else "")
    # an admin window we can't touch?
    elevated = []
    for hh, exe, title in sc.windows():
        if not exe and title:
            elevated.append(title[:40])
    if elevated and not admin:
        log("windows Jarvis can't read (probably running as admin): " + ", ".join(elevated[:5]))
        log("        Jarvis can't move or type into those unless it runs as administrator too.")
    bad = [n for n, ok, _ in results if not ok]
    log("")
    log("All computer control works." if not bad else f"{len(bad)} problem(s). The fixes are listed above.")
    log("Close the Notepad window without saving.")
    return results
