"""
Touch mode: control the whole screen with your hands in the air, in front of the camera.

  move your hand          the cursor follows your knuckles (so pinching doesn't make it jump)
  pinch thumb + index     click.  Pinch twice fast = double click
  pinch and hold, move    drag (select text, move files, drag sliders)
  pinch thumb + middle    right click
  fist                    grab the window under the cursor and carry it. Open your hand to drop it
  fist, then fling        throw the window to the left or right half of the screen (snaps it)
  two fingers up, move    scroll up and down
  both hands pinching     pull apart to zoom in, push together to zoom out
  open palm held 2 s      leave touch mode

"touch mode" / "touch mode off" by voice. Uses the screen you're looking at, all of the 49 inch ultrawide.
"""

import math
import sys
import time

IS_WIN = sys.platform == "win32"

# ---------------- settings (override in local_settings.py) ----------------
TOUCH_REGION = (0.18, 0.15, 0.82, 0.80)   # the part of the camera picture that maps to the whole screen (x0, y0, x1, y1)
TOUCH_SMOOTH = 0.35          # 0 = raw and jittery, 0.8 = very smooth but laggy
SCROLL_SPEED = 2600          # wheel units per full camera height of hand movement
FLING_SPEED = 1.6            # screen widths per second that counts as throwing a window
# ---------------------------------------------------------------------------

WRIST, THUMB_TIP, INDEX_MCP, INDEX_TIP, MIDDLE_MCP, MIDDLE_TIP, RING_MCP, PINKY_MCP = 0, 4, 5, 8, 9, 12, 13, 17


def _d(a, b):
    return math.hypot(a[0] - b[0], a[1] - b[1])


def palm_size(lm):
    return _d(lm[INDEX_MCP], lm[PINKY_MCP]) or 1e-6


def anchor(lm):
    """A steady point to drive the cursor: the knuckles, which barely move when you pinch."""
    pts = (lm[INDEX_MCP], lm[MIDDLE_MCP], lm[RING_MCP], lm[WRIST])
    w = (0.35, 0.3, 0.2, 0.15)
    return (sum(p[0] * k for p, k in zip(pts, w)), sum(p[1] * k for p, k in zip(pts, w)))


def to_screen(pt, region=None):
    x0, y0, x1, y1 = region or TOUCH_REGION
    return (min(1.0, max(0.0, (pt[0] - x0) / (x1 - x0))), min(1.0, max(0.0, (pt[1] - y0) / (y1 - y0))))


class Pinch:
    """Thumb to a fingertip, with on/off hysteresis so it doesn't flicker."""
    def __init__(self, tip, on=0.33, off=0.5):
        self.tip, self.on, self.off, self.active = tip, on, off, False

    def feed(self, lm):
        r = _d(lm[THUMB_TIP], lm[self.tip]) / palm_size(lm)
        self.active = r < self.on if not self.active else r < self.off
        return self.active


def shape(lm):
    """'fist', 'two', 'palm' or 'other' (ignores the thumb)."""
    from jarvis_vision import fingers
    f = fingers(lm)
    n = sum(f[k] for k in ("index", "middle", "ring", "pinky"))
    if n == 0 and _d(lm[THUMB_TIP], lm[INDEX_TIP]) / palm_size(lm) > 0.25:
        return "fist"
    if f["index"] and f["middle"] and not f["ring"] and not f["pinky"] and _d(lm[THUMB_TIP], lm[INDEX_TIP]) / palm_size(lm) > 0.6 \
            and _d(lm[THUMB_TIP], lm[MIDDLE_TIP]) / palm_size(lm) > 0.6:
        return "two"   # thumb well away from both fingers, so it's never a pinch
    if n == 4:
        return "palm"
    return "other"


class TouchController:
    """Feed it the hands in one frame (list of 21 point landmark lists, 0 to 2 hands).
    Returns a list of actions for the executor, each a tuple:
      ("move", fx, fy)  fx, fy in 0..1 of the whole screen
      ("down",) ("up",) ("click",) ("double",) ("right",)
      ("scroll", wheel_units)  ("zoom", steps)
      ("grab", fx, fy) ("carry", fx, fy) ("drop",) ("snap", "left" | "right")
      ("exit",)
    """
    HOLD_FOR_DRAG = 0.30
    DOUBLE_GAP = 0.45

    def __init__(self, clock=time.time):
        self.clock = clock
        self.pos = None
        self.index_pinch, self.middle_pinch = Pinch(INDEX_TIP), Pinch(MIDDLE_TIP)
        self.pinch_at, self.dragging, self.last_click = None, False, -1e9
        self.mid_was = False
        self.grabbing, self.grab_track = False, []
        self.scroll_y = None
        self.zoom_d = None
        self.palm_since = None

    def _smooth(self, p):
        if self.pos is None:
            self.pos = p
        else:
            a = TOUCH_SMOOTH
            # move faster when the hand moves a lot, smoother when it's nearly still
            jump = _d(p, self.pos)
            a = a * 0.4 if jump > 0.05 else a
            self.pos = (self.pos[0] * a + p[0] * (1 - a), self.pos[1] * a + p[1] * (1 - a))
        return self.pos

    def feed(self, hands):
        now, out = self.clock(), []
        if not hands:
            if self.dragging:
                out.append(("up",))
            if self.grabbing:
                out.append(("drop",))
            self.dragging = self.grabbing = False
            self.pinch_at = self.scroll_y = self.zoom_d = self.palm_since = None
            self.pos = None
            return out

        # two hands pinching: zoom
        if len(hands) == 2:
            p = [_d(h[THUMB_TIP], h[INDEX_TIP]) / palm_size(h) < 0.35 for h in hands]
            if all(p):
                mid = [((h[THUMB_TIP][0] + h[INDEX_TIP][0]) / 2, (h[THUMB_TIP][1] + h[INDEX_TIP][1]) / 2) for h in hands]
                d = _d(*mid)
                if self.zoom_d is None:
                    self.zoom_d = d
                steps = int((d - self.zoom_d) / 0.05)
                if steps:
                    out.append(("zoom", steps))
                    self.zoom_d += steps * 0.05
                return out
            self.zoom_d = None

        lm = max(hands, key=palm_size)   # the closer hand drives
        pt = self._smooth(to_screen(anchor(lm)))
        sh = shape(lm)

        # open palm held: leave touch mode
        if sh == "palm" and not self.index_pinch.active:
            self.palm_since = self.palm_since or now
            if now - self.palm_since > 2.0:
                self.palm_since = None
                return out + [("exit",)]
        else:
            self.palm_since = None

        # fist: grab and carry the window
        if sh == "fist":
            if not self.grabbing:
                self.grabbing, self.grab_track = True, []
                out.append(("grab", pt[0], pt[1]))
            else:
                out.append(("carry", pt[0], pt[1]))
            self.grab_track = [(t, x) for t, x in self.grab_track if now - t < 0.25] + [(now, pt[0])]
            return out
        if self.grabbing:
            self.grabbing = False
            tr = self.grab_track
            speed = (tr[-1][1] - tr[0][1]) / (tr[-1][0] - tr[0][0]) if len(tr) >= 2 and tr[-1][0] > tr[0][0] else 0
            out.append(("snap", "right" if speed > 0 else "left") if abs(speed) >= FLING_SPEED else ("drop",))
            return out

        # two fingers: scroll
        if sh == "two":
            y = anchor(lm)[1]
            if self.scroll_y is None:
                self.scroll_y = y
            units = int((self.scroll_y - y) * SCROLL_SPEED)
            if abs(units) >= 120:
                out.append(("scroll", units))
                self.scroll_y = y
            return out
        self.scroll_y = None

        # right click: thumb to middle finger
        mid = self.middle_pinch.feed(lm)
        if mid and not self.mid_was and not self.index_pinch.active:
            out.append(("right",))
        self.mid_was = mid

        # index pinch: click, double click, drag
        pin = self.index_pinch.feed(lm) and not mid
        if pin and self.pinch_at is None:
            self.pinch_at = now
        elif pin and not self.dragging and now - self.pinch_at >= self.HOLD_FOR_DRAG:
            self.dragging = True
            out.append(("down",))
        elif not pin and self.pinch_at is not None:
            if self.dragging:
                out.append(("up",))
            elif now - self.last_click < self.DOUBLE_GAP:
                out.append(("double",))
                self.last_click = -1e9
            else:
                out.append(("click",))
                self.last_click = now
            self.pinch_at, self.dragging = None, False
        out.insert(0, ("move", pt[0], pt[1]))
        return out


class WindowsTouch:
    """Carries out TouchController actions with user32."""
    def __init__(self, on_exit=None):
        self.on_exit = on_exit
        self.grab = None   # (hwnd, offset_x, offset_y)
        if IS_WIN:
            import ctypes
            self.u = ctypes.windll.user32
            try:
                self.u.SetProcessDpiAwarenessContext(ctypes.c_void_p(-4))
            except Exception:
                pass

    def _screen(self):
        u = self.u
        return u.GetSystemMetrics(76), u.GetSystemMetrics(77), u.GetSystemMetrics(78), u.GetSystemMetrics(79)

    def _px(self, fx, fy):
        x0, y0, w, h = self._screen()
        return int(x0 + fx * (w - 1)), int(y0 + fy * (h - 1))

    def run(self, actions):
        if not IS_WIN:
            return
        import ctypes
        from ctypes import wintypes
        u = self.u
        for a in actions:
            k = a[0]
            if k == "move":
                u.SetCursorPos(*self._px(a[1], a[2]))
            elif k == "down":
                u.mouse_event(0x0002, 0, 0, 0, 0)
            elif k == "up":
                u.mouse_event(0x0004, 0, 0, 0, 0)
            elif k == "click":
                u.mouse_event(0x0002, 0, 0, 0, 0)
                u.mouse_event(0x0004, 0, 0, 0, 0)
            elif k == "double":
                for _ in range(2):
                    u.mouse_event(0x0002, 0, 0, 0, 0)
                    u.mouse_event(0x0004, 0, 0, 0, 0)
            elif k == "right":
                u.mouse_event(0x0008, 0, 0, 0, 0)
                u.mouse_event(0x0010, 0, 0, 0, 0)
            elif k == "scroll":
                u.mouse_event(0x0800, 0, 0, ctypes.c_uint32(int(a[1]) & 0xFFFFFFFF).value, 0)
            elif k == "zoom":
                u.keybd_event(0x11, 0, 0, 0)   # ctrl + wheel zooms in browsers, VS Code, Figma, Explorer
                u.mouse_event(0x0800, 0, 0, ctypes.c_uint32((120 * int(a[1])) & 0xFFFFFFFF).value, 0)
                u.keybd_event(0x11, 0, 2, 0)
            elif k == "grab":
                x, y = self._px(a[1], a[2])
                h = u.GetAncestor(u.WindowFromPoint(wintypes.POINT(x, y)), 2)
                if h and h != u.GetShellWindow() and h != u.GetDesktopWindow():
                    if u.IsZoomed(h):
                        u.ShowWindow(h, 9)
                    r = wintypes.RECT()
                    u.GetWindowRect(h, ctypes.byref(r))
                    self.grab = (h, x - r.left, y - r.top)
                    u.SetForegroundWindow(h)
            elif k == "carry" and self.grab:
                h, ox, oy = self.grab
                x, y = self._px(a[1], a[2])
                u.SetWindowPos(h, 0, x - ox, y - oy, 0, 0, 0x0001 | 0x0004 | 0x0010)   # no size, no z order, no activate
            elif k == "snap" and self.grab:
                h = self.grab[0]
                u.SetForegroundWindow(h)
                vk = 0x25 if a[1] == "left" else 0x27
                u.keybd_event(0x5B, 0, 0, 0)
                u.keybd_event(vk, 0, 0, 0)
                u.keybd_event(vk, 0, 2, 0)
                u.keybd_event(0x5B, 0, 2, 0)
                self.grab = None
            elif k == "drop":
                self.grab = None
            elif k == "exit" and self.on_exit:
                self.on_exit()


def route_touch(t):
    import re
    if re.fullmatch(r"(?:turn on |start |enable |activate )?(?:touch|hand|gesture) (?:mode|control)(?: on)?|(?:let me |i want to )?control (?:my |the )?screen with my hands?|air mouse(?: on)?", t):
        return ("touch", True)
    if re.fullmatch(r"(?:turn off |stop |disable |exit |end )(?:touch|hand|gesture) (?:mode|control)|(?:touch|hand|gesture) (?:mode|control) off|air mouse off", t):
        return ("touch", False)
    return None
