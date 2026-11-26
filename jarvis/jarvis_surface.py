"""
The whole mat is a touchscreen. Windows extends the desktop onto the projector, and whatever is projected (any app,
any website) can be touched, dragged, scrolled and zoomed, because Atlas turns your fingers into real Windows touch
input (the same thing a touchscreen laptop sends), not fake mouse clicks.

Two ways to sense touch:

  camera (works now, one normal camera looking down)
      point with your index finger      the cursor follows your fingertip, so you see where you'll touch
      hold the fingertip still ~0.4 s   tap
      pinch thumb + index               finger down; move while pinched = drag (move windows, select text, sliders)
      two fingers together, move        scroll / pan (two real touch points, so Windows scrolls natively)
      pinch with both hands             zoom, spread apart or push together
    A camera looking straight down can't see height, so it can't tell "touching" from "hovering" by itself. That's
    why tap is hold still and drag is pinch.

  laser (real touch: tap, drag, multi finger, like a phone)
      an infrared line laser lays an invisible sheet of light a few millimeters over the mat. A finger that touches
      the mat breaks the sheet and lights up as a bright dot for an infrared camera. Every dot is a real touch point.
      Parts: 850 nm line laser module with a 90 to 120 degree line lens, and a USB camera with an 850 nm filter (no
      IR cut filter). Calibrate by touching the 4 dots it projects.

Settings (local_settings.py): DESK_MODE = "screen" (the default: touch your actual Windows desktop on the projector)
or "panels" (Atlas's own desk page), DESK_TOUCH = "camera" or "laser".
"""

import math
import sys
import time

IS_WIN = sys.platform == "win32"

DWELL_TAP = 0.42          # seconds a pointing fingertip holds still to tap
STILL = 0.012             # how far (share of the mat) a fingertip can wobble and still count as still
LASER_LEVEL = 200         # 0..255 brightness a laser dot has to reach in the IR picture
LASER_MIN_AREA = 12       # pixels: smaller is noise


# ================= smoothing: the One Euro filter (steady when slow, quick when fast) =================
class OneEuro:
    def __init__(self, min_cutoff=1.2, beta=12.0, d_cutoff=1.0):
        self.min_cutoff, self.beta, self.d_cutoff = min_cutoff, beta, d_cutoff
        self.x = self.dx = self.t = None

    @staticmethod
    def _a(cutoff, dt):
        r = 2 * math.pi * cutoff * dt
        return r / (r + 1)

    def __call__(self, x, t):
        if self.x is None:
            self.x, self.dx, self.t = x, 0.0, t
            return x
        dt = max(1e-3, t - self.t)
        dx = (x - self.x) / dt
        self.dx += self._a(self.d_cutoff, dt) * (dx - self.dx)
        cutoff = self.min_cutoff + self.beta * abs(self.dx)
        self.x += self._a(cutoff, dt) * (x - self.x)
        self.t = t
        return self.x


class Point2:
    def __init__(self):
        self.fx, self.fy = OneEuro(), OneEuro()

    def __call__(self, x, y, t):
        return self.fx(x, t), self.fy(y, t)


# ================= hand shapes from the 21 hand points =================
def _d(a, b):
    return math.hypot(a[0] - b[0], a[1] - b[1])


def extended(lm, tip, pip):
    """A finger is out when its tip is farther from the wrist than its middle joint (with some margin)."""
    return _d(lm[tip], lm[0]) > _d(lm[pip], lm[0]) * 1.12


def shape(lm):
    """'pinch', 'two', 'point', 'open' or 'other' for one hand (camera coordinates 0..1)."""
    palm = _d(lm[5], lm[17]) or 1e-6
    if _d(lm[4], lm[8]) < palm * 0.38:
        return "pinch"
    idx, mid, ring, pinky = extended(lm, 8, 6), extended(lm, 12, 10), extended(lm, 16, 14), extended(lm, 20, 18)
    if idx and mid and not ring and not pinky:
        return "two"
    if idx and not mid and not ring and not pinky:
        return "point"
    if idx and mid and ring and pinky:
        return "open"
    return "other"


# ================= sending touch to Windows =================
class Injector:
    """Real Windows touch input (InjectTouchInput), up to 10 fingers. Falls back to the mouse if Windows says no."""
    def __init__(self, screen):
        self.screen = screen            # (x, y, w, h) of the projector in desktop pixels
        self.ok = False
        self.down = {}                  # contact id -> (px, py)
        if not IS_WIN:
            return
        try:
            import ctypes
            from ctypes import wintypes
            self.ct, self.u = ctypes, ctypes.windll.user32

            class POINTER_INFO(ctypes.Structure):
                _fields_ = [("pointerType", ctypes.c_uint32), ("pointerId", ctypes.c_uint32), ("frameId", ctypes.c_uint32),
                            ("pointerFlags", ctypes.c_uint32), ("sourceDevice", wintypes.HANDLE), ("hwndTarget", wintypes.HWND),
                            ("ptPixelLocation", wintypes.POINT), ("ptHimetricLocation", wintypes.POINT),
                            ("ptPixelLocationRaw", wintypes.POINT), ("ptHimetricLocationRaw", wintypes.POINT),
                            ("dwTime", wintypes.DWORD), ("historyCount", ctypes.c_uint32), ("InputData", ctypes.c_int32),
                            ("dwKeyStates", wintypes.DWORD), ("PerformanceCount", ctypes.c_uint64), ("ButtonChangeType", ctypes.c_int)]

            class POINTER_TOUCH_INFO(ctypes.Structure):
                _fields_ = [("pointerInfo", POINTER_INFO), ("touchFlags", ctypes.c_uint32), ("touchMask", ctypes.c_uint32),
                            ("rcContact", wintypes.RECT), ("rcContactRaw", wintypes.RECT), ("orientation", ctypes.c_uint32),
                            ("pressure", ctypes.c_uint32)]
            self.PTI = POINTER_TOUCH_INFO
            self.ok = bool(self.u.InitializeTouchInjection(10, 1))   # 1 = show the usual touch feedback circles
        except Exception:
            self.ok = False

    def px(self, x, y):
        sx, sy, w, h = self.screen
        return int(sx + min(1.0, max(0.0, x)) * (w - 1)), int(sy + min(1.0, max(0.0, y)) * (h - 1))

    def frame(self, contacts):
        """contacts: {id: (x, y)} in mat coordinates 0..1, the fingers touching right now. Sends downs, moves and ups."""
        now = {i: self.px(*p) for i, p in contacts.items()}
        if not IS_WIN:
            self.down = now
            return
        if not self.ok:
            return self._mouse(now)
        items = []
        for i, (x, y) in now.items():
            flags = (0x20000 if i in self.down else 0x10000) | 0x2 | 0x4     # UPDATE or DOWN, INRANGE, INCONTACT
            items.append((i, x, y, flags))
        for i, (x, y) in self.down.items():
            if i not in now:
                items.append((i, x, y, 0x40000))                              # UP
        if items:
            arr = (self.PTI * len(items))()
            for k, (i, x, y, flags) in enumerate(items):
                t = arr[k]
                t.pointerInfo.pointerType = 2          # touch
                t.pointerInfo.pointerId = i
                t.pointerInfo.pointerFlags = flags
                t.pointerInfo.ptPixelLocation.x, t.pointerInfo.ptPixelLocation.y = x, y
                t.touchMask = 0x1 | 0x2 | 0x4
                t.rcContact.left, t.rcContact.right, t.rcContact.top, t.rcContact.bottom = x - 4, x + 4, y - 4, y + 4
                t.orientation, t.pressure = 90, 32000
            if not self.u.InjectTouchInput(len(items), arr):
                self.ok = False   # some setups refuse touch injection: use the mouse from now on
                return self._mouse(now)
        self.down = now

    def _mouse(self, now):
        """One finger = the mouse: down, move, up."""
        u = getattr(self, "u", None)
        first = sorted(now.items())[:1]
        if u is None:
            return
        if first:
            _, (x, y) = first[0]
            u.SetCursorPos(x, y)
            if not self.down:
                u.mouse_event(0x0002, 0, 0, 0, 0)
        elif self.down:
            u.mouse_event(0x0004, 0, 0, 0, 0)
        self.down = dict(first)

    def hover(self, x, y):
        """Moves the cursor without touching, so you can see where your finger points."""
        if IS_WIN and not self.down:
            try:
                self.ct.windll.user32.SetCursorPos(*self.px(x, y))
            except Exception:
                pass

    def tap(self, x, y, frame=None):
        self.frame({1: (x, y)})
        time.sleep(0.05)
        self.frame({})

    def release(self):
        if self.down:
            self.frame({})


# ================= camera only: gestures -> touches =================
class CameraTouch:
    """Hands seen from above -> touch contacts. feed() once per camera frame."""
    def __init__(self, inject, clock=time.time):
        self.inject, self.clock = inject, clock
        self.filters = {}
        self.dwell = None              # (x, y, since) for the pointing finger
        self.tapped_at = None
        self.mode = None
        self.zoom0 = None

    def _smooth(self, key, x, y, t):
        f = self.filters.setdefault(key, Point2())
        return f(x, y, t)

    def feed(self, hands):
        """hands: [(landmarks in camera 0..1, to_mat(point) -> (x, y) or None)]. Returns what it's doing, for the overlay."""
        t = self.clock()
        seen = []
        for k, (lm, to_mat) in enumerate(hands):
            s = shape(lm)
            tip = to_mat(lm[8])
            if not tip:
                continue
            if s == "pinch":   # the point between thumb and index is where the "finger" touches
                m = to_mat(((lm[4][0] + lm[8][0]) / 2, (lm[4][1] + lm[8][1]) / 2)) or tip
                tip = m
            if s == "two":
                mid = to_mat(lm[12]) or tip
                tip = ((tip[0] + mid[0]) / 2, (tip[1] + mid[1]) / 2)
            x, y = self._smooth(k, tip[0], tip[1], t)
            seen.append((s, x, y))
        pinches = [(x, y) for s, x, y in seen if s == "pinch"]
        contacts, state = {}, "idle"
        if len(pinches) >= 2:                      # both hands pinching: zoom
            (ax, ay), (bx, by) = pinches[:2]
            contacts, state = {1: (ax, ay), 2: (bx, by)}, "zoom"
            self.dwell = None
        elif pinches:                              # pinch = finger down, move = drag
            contacts, state = {1: pinches[0]}, "drag"
            self.dwell = None
        else:
            two = [(x, y) for s, x, y in seen if s == "two"]
            if two:                                # two fingers: two touch points side by side, Windows scrolls
                x, y = two[0]
                contacts, state = {1: (x - 0.012, y), 2: (x + 0.012, y)}, "scroll"
                self.dwell = None
            else:
                point = [(x, y) for s, x, y in seen if s == "point"]
                if point:
                    x, y = point[0]
                    self.inject.hover(x, y)
                    state = "point"
                    if self.dwell and math.hypot(x - self.dwell[0], y - self.dwell[1]) < STILL:
                        if t - self.dwell[2] >= DWELL_TAP and not self.dwell[3]:
                            self.inject.release()
                            self.inject.tap(self.dwell[0], self.dwell[1])
                            self.dwell = (self.dwell[0], self.dwell[1], self.dwell[2], True)   # one tap per hold
                            state = "tap"
                    else:
                        self.dwell = (x, y, t, False)
                else:
                    self.dwell = None
        if state not in ("tap", "point"):
            self.inject.frame(contacts)
        elif self.inject.down:
            self.inject.release()
        prog = 0.0
        if self.dwell and not self.dwell[3]:
            prog = min(1.0, (t - self.dwell[2]) / DWELL_TAP)
        return {"state": state, "fingers": [{"x": x, "y": y, "shape": s} for s, x, y in seen], "dwell": prog}


# ================= laser: bright dots in the infrared picture -> touches =================
def laser_dots(gray, level=None, min_area=None):
    """Centers (camera pixels) of the bright spots where fingers break the laser sheet."""
    import cv2
    _, bw = cv2.threshold(gray, level or LASER_LEVEL, 255, cv2.THRESH_BINARY)
    bw = cv2.morphologyEx(bw, cv2.MORPH_OPEN, cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (3, 3)))
    n, _, stats, cents = cv2.connectedComponentsWithStats(bw)
    out = []
    for i in range(1, n):
        if stats[i, cv2.CC_STAT_AREA] >= (min_area or LASER_MIN_AREA):
            out.append((float(cents[i][0]), float(cents[i][1]), int(stats[i, cv2.CC_STAT_AREA])))
    return sorted(out, key=lambda d: -d[2])[:10]


class LaserTouch:
    """Laser dots -> touch contacts that keep their ids while a finger stays down."""
    def __init__(self, inject, clock=time.time):
        self.inject, self.clock = inject, clock
        self.tracks = {}   # id -> (x, y, filter)
        self.next_id = 1
        self.gone = {}

    def feed(self, points):
        """points: mat coordinates of every finger touching right now."""
        t = self.clock()
        new = {}
        free = dict(self.tracks)
        for x, y in points:
            best = min(free.items(), key=lambda kv: math.hypot(kv[1][0] - x, kv[1][1] - y), default=None)
            if best and math.hypot(best[1][0] - x, best[1][1] - y) < 0.08:
                i, (_, _, f) = best
                del free[i]
            else:
                i, f = self.next_id, Point2()
                self.next_id = self.next_id % 9 + 1
            sx, sy = f(x, y, t)
            new[i] = (sx, sy, f)
        # a finger that blinks out for a frame (laser flicker) isn't lifted yet
        for i, v in free.items():
            if t - self.gone.setdefault(i, t) < 0.06:
                new[i] = v
        self.gone = {i: g for i, g in self.gone.items() if i in free}
        self.tracks = new
        self.inject.frame({i: (x, y) for i, (x, y, _) in new.items()})
        return {"state": "touch" if new else "idle", "fingers": [{"x": x, "y": y, "shape": "touch"} for x, y, _ in new.values()], "dwell": 0}


class TouchCalibration:
    """For the laser camera (it can't see the projected picture): touch 4 projected dots in turn."""
    TARGETS = ((0.1, 0.12), (0.9, 0.12), (0.9, 0.88), (0.1, 0.88))

    def __init__(self, clock=time.time):
        self.clock, self.i, self.got, self.hold = clock, 0, [], None

    def target(self):
        return self.TARGETS[self.i] if self.i < len(self.TARGETS) else None

    def feed(self, dots):
        """dots: camera pixel centers. Returns the 4 camera points once done, else None."""
        if self.i >= len(self.TARGETS):
            return self.got
        t = self.clock()
        if len(dots) == 1:
            x, y = dots[0][:2]
            if self.hold and math.hypot(x - self.hold[0], y - self.hold[1]) < 12:
                if t - self.hold[2] > 0.6:
                    self.got.append((x, y))
                    self.i += 1
                    self.hold = None
                    self.wait_lift = True
            elif not getattr(self, "wait_lift", False):
                self.hold = (x, y, t)
        elif not dots:
            self.hold, self.wait_lift = None, False
        return self.got if self.i >= len(self.TARGETS) else None
