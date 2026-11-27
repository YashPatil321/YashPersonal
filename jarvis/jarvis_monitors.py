"""
Moving windows between screens by voice.

  "move spotify to the other screen"        next screen over (wraps around)
  "send this to the jarvis screen"          "this" = the window you were last using (not Atlas's own windows)
  "put chrome on the left monitor"          left / right of where it is now
  "move discord to the main screen"         main / primary
  "throw this to monitor 2"                 by number, left to right
  "bring spotify here"                      to the screen your mouse is on
  "move everything to the main screen"      every window
It keeps the window's size and spot relative to the screen, and keeps it maximized if it was.
"""

import re
import threading
import time
import sys

IS_WIN = sys.platform == "win32"
MINE = ("atlas", "jarvis desk", "atlas space", "jarvis hologram")   # Atlas's own windows are never "this"
LAST = {"hwnd": None}


def _log(msg):
    print(time.strftime("[%H:%M:%S] ") + "screens: " + str(msg), flush=True)


def screens():
    """[(x, y, w, h, primary, work_rect)] left to right."""
    if not IS_WIN:
        return []
    import ctypes
    from ctypes import wintypes
    u, out = ctypes.windll.user32, []

    class MI(ctypes.Structure):
        _fields_ = [("cbSize", wintypes.DWORD), ("rcMonitor", wintypes.RECT), ("rcWork", wintypes.RECT), ("dwFlags", wintypes.DWORD)]

    @ctypes.WINFUNCTYPE(wintypes.BOOL, wintypes.HMONITOR, wintypes.HDC, ctypes.POINTER(wintypes.RECT), wintypes.LPARAM)
    def cb(hm, hdc, rc, lp):
        mi = MI(cbSize=ctypes.sizeof(MI))
        u.GetMonitorInfoW(hm, ctypes.byref(mi))
        r, wk = mi.rcMonitor, mi.rcWork
        out.append((r.left, r.top, r.right - r.left, r.bottom - r.top, bool(mi.dwFlags & 1),
                    (wk.left, wk.top, wk.right - wk.left, wk.bottom - wk.top)))
        return True
    u.EnumDisplayMonitors(0, 0, cb, 0)
    return sorted(out, key=lambda m: (m[0], m[1]))


def screen_of(rect, mons):
    """Index of the screen that holds most of rect (x, y, w, h)."""
    x, y, w, h = rect
    best, area = 0, -1
    for i, m in enumerate(mons):
        ix = max(0, min(x + w, m[0] + m[2]) - max(x, m[0]))
        iy = max(0, min(y + h, m[1] + m[3]) - max(y, m[1]))
        if ix * iy > area:
            best, area = i, ix * iy
    return best


def target_index(where, cur, mons, jarvis=None, cursor=None):
    """Which screen 'where' means, from the screen the window is on now."""
    n = len(mons)
    w = where.strip().lower()
    if n < 2 and w not in ("main", "primary"):
        return None
    if w in ("other", "next", "another", "second", "the other"):
        return (cur + 1) % n if w != "second" or n < 2 else 1
    if w in ("previous", "last"):
        return (cur - 1) % n
    if w == "left":
        return max(0, cur - 1) if cur > 0 else None
    if w == "right":
        return min(n - 1, cur + 1) if cur < n - 1 else None
    if w in ("main", "primary", "first"):
        return next((i for i, m in enumerate(mons) if m[4]), 0)
    if w in ("jarvis", "atlas", "projector", "desk", "glass") and jarvis:
        return next((i for i, m in enumerate(mons) if tuple(m[:4]) == tuple(jarvis[:4])), None)
    if w in ("here", "this") and cursor:
        return screen_of((cursor[0], cursor[1], 1, 1), mons)
    words = {"1": 0, "2": 1, "3": 2, "4": 3, "one": 0, "two": 1, "three": 2, "four": 3, "third": 2, "fourth": 3}
    if w in words and words[w] < n:
        return words[w]
    return None


def rect_of(hwnd):
    import ctypes
    from ctypes import wintypes
    r = wintypes.RECT()
    ctypes.windll.user32.GetWindowRect(hwnd, ctypes.byref(r))
    return (r.left, r.top, r.right - r.left, r.bottom - r.top)


def move(hwnd, where, jarvis=None, screen=None):
    """Moves one window. Returns the target screen index, or None if 'where' made no sense."""
    import ctypes
    u = ctypes.windll.user32
    mons = screens()
    if not mons:
        return None
    zoomed = bool(u.IsZoomed(hwnd))
    if u.IsIconic(hwnd):
        u.ShowWindow(hwnd, 9)
        time.sleep(0.05)
    rect = rect_of(hwnd)
    cur = screen_of(rect, mons)
    try:
        from ctypes import wintypes
        pt = wintypes.POINT()
        u.GetCursorPos(ctypes.byref(pt))
        cursor = (pt.x, pt.y)
    except Exception:
        cursor = None
    t = target_index(where, cur, mons, jarvis, cursor)
    if t is None:
        return None
    a, b = mons[cur][5], mons[t][5]
    # same spot and size relative to the screen
    fx, fy = (rect[0] - a[0]) / max(1, a[2]), (rect[1] - a[1]) / max(1, a[3])
    fw, fh = rect[2] / max(1, a[2]), rect[3] / max(1, a[3])
    nw, nh = min(b[2], int(fw * b[2])), min(b[3], int(fh * b[3]))
    nx = b[0] + max(0, min(b[2] - nw, int(fx * b[2])))
    ny = b[1] + max(0, min(b[3] - nh, int(fy * b[3])))
    if zoomed:
        u.ShowWindow(hwnd, 9)
        time.sleep(0.05)
    (screen.place if screen else lambda h, r: u.MoveWindow(h, *r, True))(hwnd, (nx, ny, nw, nh))
    if zoomed:
        time.sleep(0.05)
        u.ShowWindow(hwnd, 3)
    return t


def track_last(windows_fn, every=0.4):
    """Remembers the last window you used that isn't Atlas's own, so 'move this' means that window."""
    def loop():
        import ctypes
        u = ctypes.windll.user32
        while True:
            time.sleep(every)
            try:
                h = u.GetForegroundWindow()
                if not h:
                    continue
                buf = ctypes.create_unicode_buffer(256)
                u.GetWindowTextW(h, buf, 256)
                t = buf.value.lower()
                if t and not any(t.startswith(m) for m in MINE) and "administrator: atlas" not in t and t not in ("atlas",):
                    LAST["hwnd"] = h
            except Exception:
                pass
    if IS_WIN:
        threading.Thread(target=loop, daemon=True).start()


WHERE = r"(other|next|another|previous|left|right|main|primary|first|second|third|fourth|jarvis|atlas|projector|desk|glass|[1-4]|one|two|three|four)"


def route_monitors(t):
    m = re.fullmatch(r"(?:move|send|put|throw|take|shift|push) (.+?) (?:to|on|onto|over to) (?:the |my )?" + WHERE +
                     r"(?: (?:screen|monitor|display))?", t) or \
        re.fullmatch(r"(?:move|send|put|throw|take|shift|push) (.+?) (?:to|on|onto) (?:the |my )?(?:screen|monitor|display) " + WHERE, t)
    if m:
        return ("monitor_move", (m.group(1).strip(), m.group(2)))
    m = re.fullmatch(r"(?:bring|pull) (.+?) (?:here|over here|to this screen|to me)", t)
    if m:
        return ("monitor_move", (m.group(1).strip(), "here"))
    m = re.fullmatch(r"(?:move|send|throw|put) (?:this|it|that)(?: window)? over", t)
    if m:
        return ("monitor_move", ("this", "other"))
    return None


def find(name, windows):
    """The window you mean: 'this' = the last one you used, else by app name or title."""
    n = name.lower().strip()
    n = re.sub(r"^(?:the|my)\s+", "", n)
    n = re.sub(r"\s+(?:window|app)$", "", n)
    if n in ("this", "it", "that", "this window", "that window", "the window", "current"):
        return LAST["hwnd"]
    if n in ("everything", "all", "all windows", "every window"):
        return "all"
    import jarvis_trust
    hits = [h for h, exe, title in windows if jarvis_trust._matches(n, exe, title)]
    return hits[0] if hits else None
