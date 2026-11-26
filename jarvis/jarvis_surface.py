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
LEAD_SECONDS = 0.035      # look ahead this far along the finger's motion, to cancel camera and processing lag
GRACE = 0.15              # a hand that drops out of tracking this long (motion blur) keeps its touch
PINCH_IN, PINCH_OUT = 0.36, 0.52   # pinch closes under the first gap (share of palm width) and opens over the second


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
    """Smoothed point, nudged ahead by its own speed so it lands where your finger is now, not a frame ago."""
    def __init__(self, lead=None):
        self.fx, self.fy = OneEuro(), OneEuro()
        self.lead = LEAD_SECONDS if lead is None else lead

    def __call__(self, x, y, t):
        sx, sy = self.fx(x, t), self.fy(y, t)
        if self.lead and self.fx.dx is not None:
            sx += max(-0.03, min(0.03, self.fx.dx * self.lead))
            sy += max(-0.03, min(0.03, self.fy.dx * self.lead))
        return sx, sy


# ================= hand shapes from the 21 hand points =================
def _d(a, b):
    return math.hypot(a[0] - b[0], a[1] - b[1])


def extended(lm, tip, pip):
    """A finger is out when its tip is farther from the wrist than its middle joint (with some margin)."""
    return _d(lm[tip], lm[0]) > _d(lm[pip], lm[0]) * 1.12


def shape(lm, was=None):
    """'pinch', 'two', 'point', 'open' or 'other' for one hand (camera coordinates 0..1). `was` is the last shape, so a
    pinch needs a clear opening to end (no dropped drags) and a clear closing to start (no accidental grabs)."""
    palm = _d(lm[5], lm[17]) or 1e-6
    gap = _d(lm[4], lm[8]) / palm
    if gap < (PINCH_OUT if was == "pinch" else PINCH_IN):
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
                t.orientation, t.pressure = 90, 512   # Windows takes 0 to 1024; anything over makes it refuse the touch
            if not self.u.InjectTouchInput(len(items), arr):
                err = self.ct.GetLastError()
                print(time.strftime("[%H:%M:%S] ") + f"surface: Windows refused touch input (error {err}), using the mouse instead", flush=True)
                self.ok = False   # some setups refuse touch injection: use the mouse from now on
                self.down = {}
                return self._mouse(now)
            self.sent = getattr(self, "sent", 0) + 1
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
class Hand:
    """One hand followed from frame to frame: its own smoothing, a shape that has to hold before it counts, and a
    short grace period when tracking blinks."""
    def __init__(self, wrist, t):
        self.wrist, self.seen = wrist, t
        self.f = Point2()
        self.shape, self.pending, self.pending_n = "other", None, 0
        self.x = self.y = None

    def update_shape(self, raw):
        if raw == self.shape:
            self.pending, self.pending_n = None, 0
            return self.shape
        need = 3 if self.shape == "pinch" else 2   # leaving a pinch has to be really meant
        if raw == self.pending:
            self.pending_n += 1
        else:
            self.pending, self.pending_n = raw, 1
        if self.pending_n >= need:
            self.shape, self.pending, self.pending_n = raw, None, 0
        return self.shape


class CameraTouch:
    """Hands seen from above -> touch contacts. feed() once per camera frame."""
    def __init__(self, inject, clock=time.time):
        self.inject, self.clock = inject, clock
        self.hands = []
        self.dwell = None              # (x, y, since, fired) for the pointing finger

    def _match(self, wrists, t):
        """Pairs this frame's hands with the ones already followed (closest wrist), so each keeps its own filter."""
        out, free = [], list(self.hands)
        for w in wrists:
            best = min(free, key=lambda h: _d(h.wrist, w), default=None)
            if best and _d(best.wrist, w) < 0.25:
                free.remove(best)
            else:
                best = Hand(w, t)
            best.wrist, best.seen = w, t
            out.append(best)
        kept = [h for h in free if t - h.seen < GRACE and h.x is not None]   # blinked out: hold on a moment
        self.hands = out + kept
        return out, kept

    def feed(self, hands):
        """hands: [(landmarks in camera 0..1, to_mat(point) -> (x, y) or None)]. Returns what it's doing, for the overlay."""
        t = self.clock()
        tracked, kept = self._match([lm[0] for lm, _ in hands], t)
        seen = []
        for hand, (lm, to_mat) in zip(tracked, hands):
            s = hand.update_shape(shape(lm, hand.shape))
            tip = to_mat(lm[8])
            if not tip:
                continue
            if s == "pinch":   # the point between thumb and index is where the "finger" touches
                tip = to_mat(((lm[4][0] + lm[8][0]) / 2, (lm[4][1] + lm[8][1]) / 2)) or tip
            if s == "two":
                mid = to_mat(lm[12]) or tip
                tip = ((tip[0] + mid[0]) / 2, (tip[1] + mid[1]) / 2)
            hand.x, hand.y = hand.f(tip[0], tip[1], t)
            seen.append((s, hand.x, hand.y))
        for hand in kept:
            seen.append((hand.shape, hand.x, hand.y))
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
        if state != getattr(self, "last_state", None) and state != "idle":
            print(time.strftime("[%H:%M:%S] ") + f"surface: {state}" + (f" at {seen[0][1]:.2f}, {seen[0][2]:.2f}" if seen else ""), flush=True)
        self.last_state = state
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


# ================= sharper fingertips =================
def refine_tips(frame, lm, tips=((7, 8), (11, 12)), max_reach=0.7, step=1.5, jump=38.0):
    """The hand model puts the fingertip roughly at the tip; the real edge of your finger can be a few pixels off,
    which on a projected mat is the difference between hitting a button and missing it. This walks out from the
    model's tip along the finger, in the full resolution picture, until the color stops looking like your finger,
    and puts the tip there. Returns new landmarks (camera 0..1)."""
    import numpy as np
    h, w = frame.shape[:2]
    out = list(lm)
    for a, b in tips:
        ax, ay, bx, by = lm[a][0] * w, lm[a][1] * h, lm[b][0] * w, lm[b][1] * h
        seg = math.hypot(bx - ax, by - ay)
        if seg < 4:
            continue
        ux, uy = (bx - ax) / seg, (by - ay) / seg
        # what this finger looks like: a few pixels between the last joint and the tip
        samples = []
        for k in (0.35, 0.5, 0.65):
            px, py = int(ax + (bx - ax) * k), int(ay + (by - ay) * k)
            if 0 <= px < w and 0 <= py < h:
                samples.append(frame[py, px].astype(np.float32))
        if not samples:
            continue
        skin = np.mean(samples, axis=0)
        # start a bit inside the tip, walk outward
        x, y = bx - ux * seg * 0.25, by - uy * seg * 0.25
        last = (bx, by)
        travelled, reach = 0.0, seg * (0.25 + max_reach)
        while travelled < reach:
            px, py = int(round(x)), int(round(y))
            if not (0 <= px < w and 0 <= py < h):
                break
            if float(np.linalg.norm(frame[py, px].astype(np.float32) - skin)) > jump:
                break
            last = (x, y)
            x, y, travelled = x + ux * step, y + uy * step, travelled + step
        out[b] = (last[0] / w, last[1] / h)
    return out


class Stats:
    """Frames per second and how far behind real time the picture is, for the overlay and the log."""
    def __init__(self):
        self.n, self.t0, self.fps, self.lag = 0, time.time(), 0.0, 0.0

    def tick(self, captured_at=None):
        self.n += 1
        now = time.time()
        if captured_at:
            self.lag = self.lag * 0.9 + (now - captured_at) * 0.1
        if now - self.t0 >= 2:
            self.fps, self.n, self.t0 = self.n / (now - self.t0), 0, now
        return self.fps


# ================= what you see on the mat: a see-through layer over every app =================
class Overlay:
    """A click-through, always-on-top layer on the projector: a ring under each fingertip that fills as a tap
    charges, a solid dot while you're touching (pinch or laser), two dots for scroll. get() -> desk.live["touch"]."""
    def __init__(self, screen, get):
        self.screen, self.get = screen, get
        self.alive = True
        import threading
        threading.Thread(target=self._run, daemon=True).start()

    def close(self):
        self.alive = False

    def _run(self):
        try:
            import tkinter as tk
        except Exception:
            return
        x, y, w, h = self.screen
        root = tk.Tk()
        root.overrideredirect(True)
        root.geometry(f"{w}x{h}+{x}+{y}")
        root.attributes("-topmost", True)
        key = "#010101"
        root.configure(bg=key)
        try:
            root.attributes("-transparentcolor", key)
        except Exception:
            pass
        cv = tk.Canvas(root, width=w, height=h, bg=key, highlightthickness=0)
        cv.pack()
        if IS_WIN:   # clicks and touches pass straight through to the app underneath
            try:
                import ctypes
                root.update_idletasks()
                hwnd = ctypes.windll.user32.GetParent(root.winfo_id())
                ex = ctypes.windll.user32.GetWindowLongW(hwnd, -20)
                ctypes.windll.user32.SetWindowLongW(hwnd, -20, ex | 0x80000 | 0x20 | 0x08000000)   # layered, transparent, no activate
            except Exception:
                pass
        ICE = "#9cd3ff"

        def draw():
            if not self.alive:
                root.destroy()
                return
            cv.delete("all")
            d = self.get() or {}
            state = d.get("state", "idle")
            for f in d.get("fingers", []):
                px, py = f["x"] * w, f["y"] * h
                if f.get("shape") in ("pinch", "touch") or state in ("drag", "zoom", "touch"):
                    cv.create_oval(px - 9, py - 9, px + 9, py + 9, fill=ICE, outline="")
                elif state == "scroll":
                    for dx in (-14, 14):
                        cv.create_oval(px + dx - 6, py - 6, px + dx + 6, py + 6, fill=ICE, outline="")
                else:
                    r = 16
                    cv.create_oval(px - r, py - r, px + r, py + r, outline=ICE, width=2)
                    prog = d.get("dwell", 0)
                    if prog > 0.05:
                        cv.create_arc(px - r - 5, py - r - 5, px + r + 5, py + r + 5, start=90, extent=-359.9 * prog,
                                      style="arc", outline=ICE, width=4)
            root.after(16, draw)
        root.after(16, draw)
        root.mainloop()
