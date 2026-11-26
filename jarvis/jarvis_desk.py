"""
The projected desk: a projector pointing down at your desk, a camera next to it looking down,
and your desk becomes a Jarvis touch surface.

  Touch      hold a fingertip still on something for half a second, or pinch over it, to press it
  Move       pinch and hold on a panel's title, then move your hand, to put that panel anywhere
  Cards      printed marker cards are physical controls (print them with "print my desk cards"):
               FOCUS card: put it down = focus session, pick it up = done
               MUSIC card: put it down = play, pick it up = pause
               VOLUME knob: turn the card like a dial
               TIMER dial: turn it to set minutes, pick it up to start the timer
               STUDY card = study mode, PARTY card = house party protocol, GAME card = hype me up
  Calibrate  "calibrate the desk": it projects 4 markers, the camera finds them, done. Redo it if you move anything

The hologram: /holo is a 4 view Jarvis core for a Pepper's ghost pyramid on the iPad or a monitor,
and /holo?single=1 is one view for a holographic LED fan or a transparent screen.

Voice: "desk mode", "desk off", "calibrate the desk", "print my desk cards", "hologram mode".
"""

import json
import math
import os
import sys
import threading
import time

IS_WIN = sys.platform == "win32"
HERE = os.path.dirname(os.path.abspath(__file__))

# ---------------- settings (override in local_settings.py) ----------------
DESK = True                  # the desk only runs when you say "desk mode", this just allows it
DESK_CAMERA_NAME = ""        # part of the desk camera's name, e.g. "Brio". Beats the number, which Windows can shuffle
DESK_CAMERA_INDEX = 1        # the downward camera. The monitor webcam is usually 0
DESK_CAMERA_SIZE = (1280, 720)
DESK_DISPLAY = None          # which screen is the projector (0, 1, 2 ...). None = the smallest screen that isn't the main one
DWELL_SECONDS = 0.6
DESK_MODE = "screen"         # "screen": the projector is a Windows touchscreen (touch any app). "panels": Atlas's desk page
DESK_TOUCH = "camera"        # "camera": hand tracking from the down camera. "laser": an IR line laser + IR camera, real touch
DESK_EXPOSURE = None         # None keeps what the camera picked. -7 or -8 = sharper fast fingers if the room is bright enough
DESK_OVERLAY = True          # rings under your fingertips on the projector, over every app (click-through)
DESK_LOCK_CAMERA = True      # freeze focus, exposure and white balance once the camera settles
DESK_GLOW = 12               # 0 = pure black desk. A little glow lets the down camera see your hand in a dark room
CALIB_FILE = os.path.join(HERE, ".cache", "desk_calib.json")
# ArUco 4x4 marker ids printed on the cards
CARDS = {0: "focus", 1: "music", 2: "volume", 3: "timer", 4: "study", 5: "party", 6: "game"}
# 9 calibration markers in a 3 x 3 grid, row by row. Each of the 4 cells gets its own correction, which
# straightens out the bend a wide angle camera lens puts near the edges (a low mounted camera needs a wide lens).
_GX, _GY = (0.1, 0.5, 0.9), (0.12, 0.5, 0.88)
CAL_IDS = tuple(range(40, 49))
CAL_POS = tuple((x, y) for y in _GY for x in _GX)
CELLS = ((0, 1, 4, 3), (1, 2, 5, 4), (3, 4, 7, 6), (4, 5, 8, 7))   # corner indexes of each cell, clockwise
# ---------------------------------------------------------------------------


def _log(msg):
    print(time.strftime("[%H:%M:%S] ") + "desk: " + str(msg), flush=True)


# ================= calibration: camera pixels -> projector 0..1 =================
def homography(src, dst):
    """3x3 matrix mapping src points onto dst points (4 or more pairs). Plain numpy, least squares."""
    import numpy as np
    A = []
    for (x, y), (u, v) in zip(src, dst):
        A.append([-x, -y, -1, 0, 0, 0, x * u, y * u, u])
        A.append([0, 0, 0, -x, -y, -1, x * v, y * v, v])
    _, _, vt = np.linalg.svd(np.asarray(A, dtype=float))
    H = vt[-1].reshape(3, 3)
    return H / H[2, 2]


def apply(H, pt):
    x, y = pt
    d = H[2][0] * x + H[2][1] * y + H[2][2]
    return ((H[0][0] * x + H[0][1] * y + H[0][2]) / d, (H[1][0] * x + H[1][1] * y + H[1][2]) / d)


def inside(pt, quad):
    """Is pt inside the convex quad (4 points in order)?"""
    sign = 0
    for i in range(4):
        (x1, y1), (x2, y2) = quad[i], quad[(i + 1) % 4]
        c = (x2 - x1) * (pt[1] - y1) - (y2 - y1) * (pt[0] - x1)
        if c:
            if sign and (c > 0) != (sign > 0):
                return False
            sign = c
    return True


class Calibration:
    def __init__(self, path=None):
        self.path = path or CALIB_FILE
        self.H = None
        self.cells = []   # [(camera quad, H)] for the 3 x 3 grid
        try:
            with open(self.path) as f:
                d = json.load(f)
            self.H, self.cells = d["H"], [(c["quad"], c["H"]) for c in d.get("cells", [])]
        except Exception:
            pass

    @property
    def ready(self):
        return self.H is not None

    def fit(self, cam_pts, proj_pts):
        self.H = homography(cam_pts, proj_pts).tolist()   # one overall fit, used outside the grid
        self.cells = []
        if len(cam_pts) == 9:
            for cell in CELLS:
                quad = [list(map(float, cam_pts[i])) for i in cell]
                self.cells.append((quad, homography(quad, [proj_pts[i] for i in cell]).tolist()))
        os.makedirs(os.path.dirname(self.path), exist_ok=True)
        with open(self.path, "w") as f:
            json.dump({"H": self.H, "cells": [{"quad": q, "H": h} for q, h in self.cells], "when": time.strftime("%Y-%m-%d %H:%M")}, f)

    def to_desk(self, pt):
        if not self.H:
            return None
        for quad, h in self.cells:
            if inside(pt, quad):
                return apply(h, pt)
        return apply(self.H, pt)


# ================= markers =================
_DET = None


def detector():
    global _DET
    if _DET is None:
        import cv2
        d = cv2.aruco.getPredefinedDictionary(cv2.aruco.DICT_4X4_50)
        p = cv2.aruco.DetectorParameters()
        # projected markers are small, soft and washed out: look harder than the defaults do
        p.adaptiveThreshWinSizeMin, p.adaptiveThreshWinSizeMax, p.adaptiveThreshWinSizeStep = 3, 53, 6
        p.minMarkerPerimeterRate = 0.015
        p.polygonalApproxAccuracyRate = 0.06
        p.errorCorrectionRate = 0.8
        p.minOtsuStdDev = 2.0
        p.perspectiveRemoveIgnoredMarginPerCell = 0.2
        p.cornerRefinementMethod = cv2.aruco.CORNER_REFINE_SUBPIX
        _DET = cv2.aruco.ArucoDetector(d, p)
    return _DET


def _detect(gray, scale=1.0):
    corners, ids, _ = detector().detectMarkers(gray)
    out = {}
    if ids is None:
        return out
    for c, i in zip(corners, ids.ravel()):
        pts = c.reshape(4, 2) / scale
        cx, cy = float(pts[:, 0].mean()), float(pts[:, 1].mean())
        ang = math.degrees(math.atan2(pts[1][1] - pts[0][1], pts[1][0] - pts[0][0]))
        out[int(i)] = ((cx, cy), ang)
    return out


def find_markers(gray, thorough=False):
    """{id: (center_xy, angle_degrees)} in camera pixels. thorough: also try a contrast boosted, a darkened (for a
    bright, washed out projection) and a 2x enlarged copy, and keep everything any of them finds."""
    out = _detect(gray)
    if not thorough:
        return out
    import cv2
    import numpy as np
    clahe = cv2.createCLAHE(clipLimit=3.0, tileGridSize=(8, 8)).apply(gray)
    lut = np.array([((i / 255.0) ** 2.2) * 255 for i in range(256)], np.uint8)   # pull washed out whites apart
    dark = cv2.LUT(gray, lut)
    sharp = cv2.addWeighted(gray, 1.8, cv2.GaussianBlur(gray, (0, 0), 3), -0.8, 0)
    for img in (clahe, dark, sharp):
        for k, v in _detect(img).items():
            out.setdefault(k, v)
    if len(out) < 9:
        big = cv2.resize(clahe, None, fx=2, fy=2, interpolation=cv2.INTER_CUBIC)
        for k, v in _detect(big, 2.0).items():
            out.setdefault(k, v)
    return out


def marker_png(mid, size=300):
    import cv2
    import numpy as np
    d = cv2.aruco.getPredefinedDictionary(cv2.aruco.DICT_4X4_50)
    img = cv2.aruco.generateImageMarker(d, int(mid), size)
    pad = size // 6
    img = np.pad(img, pad, constant_values=255)   # markers need a white border
    return cv2.imencode(".png", img)[1].tobytes()


# ================= touch on the desk =================
class Taps:
    """Fingertips in desk coordinates (0..1) -> taps. A tap is a still fingertip for DWELL_SECONDS, or a pinch."""
    def __init__(self, clock=time.time, dwell=None):
        self.clock, self.dwell = clock, DWELL_SECONDS if dwell is None else dwell
        self.tracks = []   # dicts: x, y, since, armed, pinch

    def feed(self, fingers):
        """fingers: [(x, y, pinching)]. Returns (fingers with dwell progress, taps)."""
        now, taps, new = self.clock(), [], []
        for x, y, pinch in fingers:
            tr = min(self.tracks, key=lambda t: math.hypot(t["x"] - x, t["y"] - y), default=None)
            if tr and math.hypot(tr["x"] - x, tr["y"] - y) < 0.08:
                self.tracks.remove(tr)
                moved = math.hypot(tr["ax"] - x, tr["ay"] - y)
                if moved > 0.015:   # moved: restart the dwell from here
                    tr.update(ax=x, ay=y, since=now)
                    if moved > 0.03:
                        tr["armed"] = True
                tr.update(x=x, y=y)
            else:
                tr = {"x": x, "y": y, "ax": x, "ay": y, "since": now, "armed": True, "pinch": False}
            if pinch and not tr["pinch"]:
                taps.append((x, y, "pinch"))
                tr["armed"] = False
            elif tr["armed"] and now - tr["since"] >= self.dwell and not pinch:
                taps.append((x, y, "dwell"))
                tr["armed"] = False
            tr["pinch"] = pinch
            new.append(tr)
        self.tracks = new
        prog = [{"x": t["x"], "y": t["y"], "pinch": t["pinch"],
                 "dwell": min(1.0, (now - t["since"]) / self.dwell) if t["armed"] else 0.0} for t in self.tracks]
        return prog, taps


class Tangibles:
    """Marker cards on the desk -> place / remove / turn events."""
    def __init__(self, clock=time.time, gone_after=1.5):
        self.clock, self.gone_after = clock, gone_after
        self.on = {}   # name -> {"t": last seen, "ang": angle, "acc": accumulated turn}

    def feed(self, cards):
        """cards: {name: angle}. Returns events: ("place", name) ("remove", name, total_turn) ("turn", name, delta)."""
        now, ev = self.clock(), []
        for name, ang in cards.items():
            if name not in self.on:
                self.on[name] = {"t": now, "ang": ang, "acc": 0.0}
                ev.append(("place", name))
                continue
            st = self.on[name]
            d = (ang - st["ang"] + 180) % 360 - 180
            if abs(d) >= 4:
                st["acc"] += d
                st["ang"] = ang
                ev.append(("turn", name, d))
            st["t"] = now
        for name in list(self.on):
            if name not in cards and now - self.on[name]["t"] > self.gone_after:   # hands cover cards, so wait a bit
                ev.append(("remove", name, self.on.pop(name)["acc"]))
        return ev


def timer_minutes(turn_deg):
    """The timer dial: every 30 degrees clockwise is 5 minutes, 5 to 90."""
    return int(max(5, min(90, 5 * round(turn_deg / 30) + 5)))


# ================= the desk =================
def fast_camera(cap):
    """Highest frame rate the camera can do: MJPG over USB, no frame queue, 60 fps at 720p if it can, else 1080p."""
    import cv2
    import jarvis_vision
    cap.set(cv2.CAP_PROP_FOURCC, cv2.VideoWriter_fourcc(*"MJPG"))
    cap.set(cv2.CAP_PROP_BUFFERSIZE, 1)
    best = None
    for w, h in ((1280, 720), tuple(DESK_CAMERA_SIZE), (1920, 1080)):
        cap.set(cv2.CAP_PROP_FRAME_WIDTH, w)
        cap.set(cv2.CAP_PROP_FRAME_HEIGHT, h)
        cap.set(cv2.CAP_PROP_FPS, 60)
        fps, size = jarvis_vision._measure(cap)
        _log(f"desk camera {size[0]}x{size[1]}: {fps:.0f} fps")
        if best is None or fps > best[0] * 1.2:
            best = (fps, w, h)
        if fps >= 50:
            break
    if best:
        cap.set(cv2.CAP_PROP_FRAME_WIDTH, best[1])
        cap.set(cv2.CAP_PROP_FRAME_HEIGHT, best[2])
        cap.set(cv2.CAP_PROP_FPS, 60)


def lock_camera(cap, settle=3.0):
    """Once the camera has adjusted to the room, freeze focus and white balance (and exposure only if you set
    DESK_EXPOSURE), so it stops re-adjusting every time the projected picture changes."""
    import cv2
    time.sleep(settle)
    try:
        cap.set(cv2.CAP_PROP_AUTOFOCUS, 0)
        cap.set(cv2.CAP_PROP_AUTO_WB, 0)
        if DESK_EXPOSURE is not None:
            cap.set(cv2.CAP_PROP_AUTO_EXPOSURE, 0.25)
            cap.set(cv2.CAP_PROP_EXPOSURE, DESK_EXPOSURE)
        _log("desk camera focus and color locked")
    except Exception as e:
        _log(f"camera lock: {e}")


def camera_names():
    """Every camera's name, in the order Windows (DirectShow) numbers them. Empty if it can't tell."""
    if not IS_WIN:
        return []
    try:
        from pygrabber.dshow_graph import FilterGraph
    except ImportError:
        import subprocess
        subprocess.run([sys.executable, "-m", "pip", "install", "-q", "pygrabber"], timeout=300)
        try:
            from pygrabber.dshow_graph import FilterGraph
        except ImportError:
            return []
    try:
        return list(FilterGraph().get_input_devices())
    except Exception as e:
        _log(f"camera names: {e}")
        return []


_NAME_CACHE = {}


def desk_index():
    """The desk camera's number right now: found by DESK_CAMERA_NAME when that's set, else DESK_CAMERA_INDEX."""
    if DESK_CAMERA_NAME:
        if DESK_CAMERA_NAME not in _NAME_CACHE or time.time() - _NAME_CACHE[DESK_CAMERA_NAME][1] > 30:
            names = camera_names()
            hit = next((i for i, n in enumerate(names) if DESK_CAMERA_NAME.lower() in n.lower()), None)
            _NAME_CACHE[DESK_CAMERA_NAME] = (hit, time.time())
            if hit is None:
                _log(f"no camera named like '{DESK_CAMERA_NAME}' (have: {', '.join(names) or 'none'})")
        hit = _NAME_CACHE[DESK_CAMERA_NAME][0]
        if hit is not None:
            return hit
    return DESK_CAMERA_INDEX


def save_setting(name, value):
    path = os.path.join(HERE, "local_settings.py")
    try:
        lines = open(path, encoding="utf-8").read().splitlines()
    except OSError:
        lines = []
    import re
    lines = [l for l in lines if not re.match(rf"\s*{name}\s*=", l)] + [f"{name} = {value!r}"]
    with open(path, "w", encoding="utf-8") as f:
        f.write("\n".join(lines) + "\n")
    globals()[name] = value


def camera_auto(cap, be):
    """Back to automatic exposure, focus and white balance. Cameras remember settings between uses, so one that was
    left on a bad manual exposure stays black until something turns auto back on."""
    import cv2
    try:
        cap.set(cv2.CAP_PROP_AUTO_EXPOSURE, 0.75 if be == cv2.CAP_DSHOW else 1)
        cap.set(cv2.CAP_PROP_AUTOFOCUS, 1)
        cap.set(cv2.CAP_PROP_AUTO_WB, 1)
    except Exception:
        pass


def open_desk_camera(index=None, log=_log):
    """Opens exactly the desk camera and finds a mode that gives a real picture: compressed (MJPG) first, so a
    high resolution camera fits through USB at a high frame rate, then the camera's own format. Returns (cap, text)."""
    import cv2
    import jarvis_vision
    by_name = index is None and bool(DESK_CAMERA_NAME)
    index = desk_index() if index is None else index
    # numbers from names follow DirectShow's order, and the other driver can number cameras differently
    backends = ([cv2.CAP_DSHOW] if by_name else [cv2.CAP_DSHOW, cv2.CAP_MSMF]) if IS_WIN else [cv2.CAP_ANY]
    modes = [("MJPG", 1280, 720, 60), ("MJPG", 1920, 1080, 60), ("MJPG", 1280, 720, 30), (None, 1280, 720, 30),
             (None, 640, 480, 30), (None, 0, 0, 0)]
    for be in backends:
        cap = cv2.VideoCapture(index, be)
        if not cap.isOpened():
            cap.release()
            continue
        camera_auto(cap, be)
        cap.set(cv2.CAP_PROP_BUFFERSIZE, 1)
        for fourcc, w, h, fps in modes:
            if fourcc:
                cap.set(cv2.CAP_PROP_FOURCC, cv2.VideoWriter_fourcc(*fourcc))
            if w:
                cap.set(cv2.CAP_PROP_FRAME_WIDTH, w)
                cap.set(cv2.CAP_PROP_FRAME_HEIGHT, h)
                cap.set(cv2.CAP_PROP_FPS, fps)
            bright, frame = 0.0, None
            for _ in range(40):   # auto exposure needs a moment to open up
                ok, f = cap.read()
                if ok:
                    frame, bright = f, float(f.mean())
                    if bright > 4:
                        break
            if frame is not None and bright > 4:
                got, size = jarvis_vision._measure(cap)
                name = "DirectShow" if be == cv2.CAP_DSHOW else "Media Foundation" if IS_WIN else "default"
                text = f"camera {index}: {size[0]}x{size[1]} at {got:.0f} fps ({fourcc or 'native'}, {name})"
                log(text)
                return cap, text
        log(f"camera {index} opened but only gave black through " + ("DirectShow" if be == cv2.CAP_DSHOW else "the other driver"))
        cap.release()
    return None, f"camera {index} gives no picture. Is its shutter or lens cap open, and is nothing else using it?"


class Desk:
    def __init__(self, ask, key, state=None, say=None):
        """ask(phrase) runs it like you said it. key(name, times) presses media keys. state() -> dict for the panels."""
        self.ask, self.key, self.state_fn, self.say = ask, key, state or (lambda: {}), say or (lambda *_: None)
        self.cal = Calibration()
        self.taps, self.cards = Taps(), Tangibles()
        self.live = {"fingers": [], "hands": [], "taps": [], "cards": [], "calibrating": False, "calibrated": self.cal.ready, "seq": 0}
        self.running = False
        self.calibrating = False
        self.cal_done = None
        self.timer_turn = 0.0
        self.vol_turn = 0.0
        self.pending_taps = []
        self.surface = None          # touch -> Windows, built once calibrated (see jarvis_surface)
        self.touchcal = None
        self.mode = DESK_MODE
        import jarvis_surface
        self.stats = jarvis_surface.Stats()

    # ---- camera loop ----
    def start(self):
        fresh = Calibration()   # pick up a calibration saved from the preview tool
        if fresh.ready:
            self.cal = fresh
            self.live["calibrated"] = True
        if not self.running:
            self.running = True
            threading.Thread(target=self._run, daemon=True).start()

    def stop(self):
        self.running = False
        if self.surface is not None:
            try:
                self.surface.inject.release()
            except Exception:
                pass
        if getattr(self, "overlay", None):
            self.overlay.close()
            self.overlay = None

    def calibrate(self, done=None):
        self.calibrating, self.cal_done = True, done
        self.live["calibrating"] = True
        if DESK_TOUCH == "laser":
            import jarvis_surface
            self.touchcal = jarvis_surface.TouchCalibration()
            self.live["touchcal"] = list(self.touchcal.target())
        self.start()

    def _surface(self):
        if self.surface is None:
            import jarvis_surface
            scr = projector_screen(or_main=True) or (0, 0, 1920, 1080, True)
            inj = jarvis_surface.Injector(scr[:4])
            self.surface = jarvis_surface.LaserTouch(inj) if DESK_TOUCH == "laser" else jarvis_surface.CameraTouch(inj)
            self.screen_rect = scr[:4]
            _log(f"touchscreen on the screen at {scr[:2]} ({scr[2]}x{scr[3]}), " +
                 ("real Windows touch" if inj.ok else "mouse input") + f", sensing: {DESK_TOUCH}")
        if DESK_OVERLAY and not getattr(self, "overlay", None):
            import jarvis_surface
            self.overlay = jarvis_surface.Overlay(self.screen_rect, lambda: self.live.get("touch"))
        return self.surface

    def _run(self):
        try:
            import cv2
            import jarvis_vision
            # the plain hand model (no gesture classifier on top): faster, and the desk reads shapes itself
            det = jarvis_vision.Detectors(hands=True, faces=False, gestures=False, confidence=0.5)
        except Exception as e:
            _log(f"desk camera off: {e}")
            self.running = False
            return
        import jarvis_vision
        mon = getattr(getattr(self, "vision", None), "camera_index", jarvis_vision.CAMERA_INDEX)
        cap, why = open_desk_camera()
        self.camera_text = why if cap else f"no desk camera ({why})"
        if not cap and mon != desk_index():   # not where it should be: any other camera that isn't Atlas's own
            cap, idx = jarvis_vision.open_camera(DESK_CAMERA_INDEX, avoid=mon)
            if cap:
                _log(f"{why} Using camera {idx} instead. Set DESK_CAMERA_INDEX = {idx} if that's right.")
                fast_camera(cap)
        grab = None
        if cap:
            grab = jarvis_vision.LatestFrame(cap)   # always the newest frame, never a queued old one
            if DESK_LOCK_CAMERA:
                threading.Thread(target=lock_camera, args=(cap,), daemon=True).start()
        shared = None
        if not cap:
            v = getattr(self, "vision", None)
            if v is not None and getattr(v, "ok", False):
                # only one camera on this PC and Atlas's camera already has it: share its pictures instead of fighting over it
                shared = v
                _log(f"one camera only: the desk shares camera {getattr(v, 'camera_index', '?')} with Atlas")
                self.camera_text = f"sharing Atlas's camera {getattr(v, 'camera_index', '?')}"
            else:
                _log(f"no desk camera at index {DESK_CAMERA_INDEX}")
                self.say("I can't find the desk camera. Plug it in, or set DESK CAMERA INDEX.")
                self.running = False
                return
        _log("desk camera on")
        n, last_t = 0, 0.0
        while self.running:
            if shared is not None:
                t = getattr(shared, "last_frame_t", 0)
                f = getattr(shared, "last_frame", None)
                if f is None or t == last_t:
                    time.sleep(0.02)
                    continue
                last_t, good, frame = t, True, cv2.flip(f, 1)   # Atlas mirrors its picture, the desk needs it straight
            else:
                frame = grab.next(timeout=1.0)
                good = frame is not None
            if not good:
                time.sleep(0.05)
                continue
            n += 1
            self.stats.tick(grab.t if grab else last_t)
            try:
                self.step(frame, det, n)
            except Exception as e:
                _log(f"frame: {e}")
                time.sleep(0.3)
        if grab:
            grab.close()
            time.sleep(0.1)
        if cap:
            cap.release()

    def step(self, frame, det, n=0, now_ms=None):
        import cv2
        h, w = frame.shape[:2]
        gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
        if DESK_TOUCH == "laser":
            return self._laser_step(gray)
        if self.calibrating:
            ms = find_markers(gray, thorough=True)
            if all(i in ms for i in CAL_IDS):
                self.cal.fit([ms[i][0] for i in CAL_IDS], list(CAL_POS))
                self.calibrating = False
                self.live.update(calibrating=False, calibrated=True)
                _log("calibrated")
                if self.cal_done:
                    self.cal_done(True)
            return
        if not self.cal.ready:
            return
        # cards (every 3rd frame is plenty)
        if n % 3 == 0:
            seen = {}
            shown = []
            for mid, (c, ang) in find_markers(gray).items():
                name = CARDS.get(mid)
                if name:
                    seen[name] = ang
                    dx, dy = self.cal.to_desk(c)
                    shown.append({"name": name, "x": dx, "y": dy, "angle": ang})
            for e in self.cards.feed(seen):
                self.card_event(e)
            for c in shown:
                c["value"] = timer_minutes(self.timer_turn) if c["name"] == "timer" else None
            self.live["cards"] = shown
        # fingertips
        small = frame if w <= 1280 else cv2.resize(frame, (1280, int(h * 1280 / w)), interpolation=cv2.INTER_AREA)
        rgb = cv2.cvtColor(small, cv2.COLOR_BGR2RGB)   # the hand model runs on a smaller copy (fast); tips are refined at full size
        hands = det.hands_all(rgb, now_ms if now_ms is not None else time.time() * 1000)
        if self.mode == "screen":   # the whole projected desktop is the touchscreen
            import jarvis_surface
            to_mat = lambda p: self.cal.to_desk((p[0] * w, p[1] * h))
            hands = [jarvis_surface.refine_tips(frame, lm) for lm in hands]   # pixel exact fingertips
            self.live["touch"] = self._surface().feed([(lm, to_mat) for lm in hands])
            self.live["fps"], self.live["lag_ms"] = round(self.stats.fps), round(self.stats.lag * 1000)
            if n % 600 == 0:
                _log(f"hand tracking at {self.stats.fps:.0f} fps, {self.stats.lag * 1000:.0f} ms behind")
            return
        import jarvis_touch
        fingers, outlines = [], []
        for lm in hands:
            pts = [self.cal.to_desk((x * w, y * h)) for x, y in lm]
            outlines.append([[round(px, 4), round(py, 4)] for px, py in pts])   # the whole hand, so the desk can black it out
            tip = lm[8]
            d = self.cal.to_desk((tip[0] * w, tip[1] * h))
            if d and -0.05 <= d[0] <= 1.05 and -0.05 <= d[1] <= 1.05:
                fingers.append((d[0], d[1], jarvis_touch.Pinch(8).feed(lm)))
        prog, taps = self.taps.feed(fingers)
        self.live["fingers"] = prog
        self.live["hands"] = outlines
        if taps:
            self.live["seq"] += 1
            self.live["taps"] = [{"x": x, "y": y, "how": how, "seq": self.live["seq"]} for x, y, how in taps]

    def _laser_step(self, gray):
        import jarvis_surface
        dots = jarvis_surface.laser_dots(gray)
        if self.calibrating and self.touchcal:
            got = self.touchcal.feed(dots)
            tgt = self.touchcal.target()
            self.live["touchcal"] = list(tgt) if tgt else None
            if got:
                self.cal.fit(got, list(jarvis_surface.TouchCalibration.TARGETS))
                self.calibrating, self.touchcal = False, None
                self.live.update(calibrating=False, calibrated=True, touchcal=None)
                _log("calibrated by touch")
                if self.cal_done:
                    self.cal_done(True)
            return
        if not self.cal.ready:
            return
        pts = [p for p in (self.cal.to_desk((x, y)) for x, y, _ in dots) if p and -0.05 <= p[0] <= 1.05 and -0.05 <= p[1] <= 1.05]
        if self.mode == "screen":
            self.live["touch"] = self._surface().feed(pts)
        else:
            prog, taps = self.taps.feed([(x, y, False) for x, y in pts])
            self.live["fingers"] = prog
            if taps:
                self.live["seq"] += 1
                self.live["taps"] = [{"x": x, "y": y, "how": how, "seq": self.live["seq"]} for x, y, how in taps]

    def card_event(self, e):
        kind, name = e[0], e[1]
        _log(f"card {kind} {name}")
        go = lambda phrase: threading.Thread(target=self.ask, args=(phrase,), daemon=True).start()
        if name == "volume" and kind == "turn":
            self.vol_turn += e[2]
            while abs(self.vol_turn) >= 15:
                step = 1 if self.vol_turn > 0 else -1
                self.key("vol_up" if step > 0 else "vol_down", 1)
                self.vol_turn -= 15 * step
        elif name == "timer":
            if kind == "place":
                self.timer_turn = 0.0
            elif kind == "turn":
                self.timer_turn = max(0.0, self.timer_turn + e[2])
            elif kind == "remove":
                go(f"set a timer for {timer_minutes(self.timer_turn)} minutes")
        elif kind == "place":
            phrase = {"focus": "lock in for 50 minutes", "music": "play", "study": "study mode",
                      "party": "house party protocol", "game": "hype me up"}.get(name)
            if phrase:
                go(phrase)
        elif kind == "remove":
            phrase = {"focus": "stop focus", "music": "pause", "party": "back to normal"}.get(name)
            if phrase:
                go(phrase)

    def status(self):
        """Plain words: what the desk is doing and what's wrong, for 'desk status'."""
        l, tch = self.live, self.live.get("touch") or {}
        if not self.running:
            return "The desk is off. Type touchscreen mode to start it."
        bits = [getattr(self, "camera_text", "camera: unknown"),
                f"{self.stats.fps:.0f} frames a second",
                "calibrated" if self.cal.ready else "NOT calibrated, type calibrate the desk",
                f"mode {self.mode}"]
        if self.mode == "screen":
            hands = len(tch.get("fingers", []))
            bits.append(f"hands seen now: {hands}" + (f", doing: {tch.get('state')}" if hands else ""))
            if self.surface is not None:
                inj = self.surface.inject
                bits.append("sending real touch" if inj.ok else "sending mouse clicks")
                bits.append(f"touch area {inj.screen[2]}x{inj.screen[3]} at {inj.screen[0]},{inj.screen[1]}")
        return ". ".join(bits) + "."

    # ---- web pages ----
    def register(self, bridge):
        import jarvis_orb
        desk = self

        def send(h, code, body, ctype):
            if isinstance(body, str):
                body = body.encode("utf-8")
            h.send_response(code)
            h.send_header("Content-Type", ctype)
            h.send_header("Content-Length", str(len(body)))
            h.send_header("Cache-Control", "no-store")
            h.end_headers()
            h.wfile.write(body)

        def page(name):
            with open(os.path.join(HERE, name), encoding="utf-8") as f:
                return f.read()

        def stream(h, q):
            h.send_response(200)
            h.send_header("Content-Type", "text/event-stream")
            h.send_header("Cache-Control", "no-store")
            h.end_headers()
            last_seq = 0
            try:
                while True:
                    live = dict(desk.live, orb=jarvis_orb.LAST.get("state", "idle"))
                    if live["seq"] == last_seq:
                        live["taps"] = []
                    last_seq = live["seq"]
                    h.wfile.write(("data: " + json.dumps(live) + "\n\n").encode())
                    h.wfile.flush()
                    time.sleep(0.05)
            except Exception:
                return

        def act(h, q):
            phrase = (q.get("say") or "").strip()
            if not phrase:
                return send(h, 400, "nothing to do", "text/plain")
            if phrase in ("vol_up", "vol_down", "next", "prev", "play_pause", "mute"):
                desk.key(phrase, 2 if phrase.startswith("vol") else 1)
                return send(h, 200, "ok", "text/plain")
            threading.Thread(target=desk.ask, args=(phrase,), daemon=True).start()
            return send(h, 200, "ok", "text/plain")

        def state(h, q):
            try:
                st = desk.state_fn()
            except Exception as e:
                st = {"error": str(e)}
            st["orb"] = jarvis_orb.LAST.get("state", "idle")
            return send(h, 200, json.dumps(st), "application/json")

        def calib(h, q):
            desk.calibrate(lambda ok: desk.say("Desk calibrated."))
            return send(h, 200, "calibrating", "text/plain")

        bridge.routes.update({
            "/desk": lambda h, q: send(h, 200, page("desk.html").replace('?? 12)', f'?? {int(DESK_GLOW)})'), "text/html; charset=utf-8"),
            "/holo": lambda h, q: send(h, 200, page("holo.html"), "text/html; charset=utf-8"),
            "/desk/cards": lambda h, q: send(h, 200, page("desk-cards.html"), "text/html; charset=utf-8"),
            "/desk/stream": stream,
            "/desk/state": state,
            "/desk/act": act,
            "/desk/calibrate": calib,
            "/desk/marker.png": lambda h, q: send(h, 200, marker_png(int(q.get("id", 0)), int(q.get("size", 300))), "image/png"),
        })


# ================= projector screen =================
def monitors():
    """[(x, y, w, h, primary)] for every screen, Windows only."""
    if not IS_WIN:
        return []
    import ctypes
    from ctypes import wintypes
    u = ctypes.windll.user32
    out = []

    class MI(ctypes.Structure):
        _fields_ = [("cbSize", wintypes.DWORD), ("rcMonitor", wintypes.RECT), ("rcWork", wintypes.RECT), ("dwFlags", wintypes.DWORD)]

    @ctypes.WINFUNCTYPE(wintypes.BOOL, wintypes.HMONITOR, wintypes.HDC, ctypes.POINTER(wintypes.RECT), wintypes.LPARAM)
    def cb(hm, hdc, rc, lp):
        mi = MI()
        mi.cbSize = ctypes.sizeof(MI)
        u.GetMonitorInfoW(hm, ctypes.byref(mi))
        r = mi.rcMonitor
        out.append((r.left, r.top, r.right - r.left, r.bottom - r.top, bool(mi.dwFlags & 1)))
        return True
    u.EnumDisplayMonitors(0, 0, cb, 0)
    return out


def projector_screen(mons=None, or_main=False):
    """The projector: DESK_DISPLAY if set, else the smallest screen that isn't the main one. With or_main, the main
    screen when the projector is the only display (or Windows is mirroring)."""
    mons = monitors() if mons is None else mons
    if DESK_DISPLAY is not None and DESK_DISPLAY < len(mons):
        return mons[DESK_DISPLAY]
    others = [m for m in mons if not m[4]]
    if others:
        return min(others, key=lambda m: m[2] * m[3])
    return next((m for m in mons if m[4]), None) if or_main else None


def route_desk(t):
    import re
    if re.fullmatch(r"(?:turn on |start |activate )?(?:the )?(?:touch ?screen|touch) (?:mode|desk|mat)|(?:make )?(?:the )?(?:mat|desk|projector) (?:a )?touch ?screen", t):
        return ("desk", "screen")
    if re.fullmatch(r"(?:turn on |start |open )?(?:the )?desk (?:panels|page|dashboard)|panels mode", t):
        return ("desk", "panels")
    if re.fullmatch(r"(?:turn on |start |wake (?:up )?|activate )?(?:the )?desk(?: mode| ui| display)?(?: on)?|projector (?:on|mode)", t):
        return ("desk", True)
    if re.fullmatch(r"(?:turn off |stop |close )(?:the )?desk(?: mode| ui)?|desk (?:mode )?off|projector off", t):
        return ("desk", False)
    if re.fullmatch(r"(?:calibrate|recalibrate|line up|align) (?:the |my )?(?:desk|projector)", t):
        return ("desk_cal", None)
    if re.fullmatch(r"(?:desk|touch|touchscreen|touch screen) (?:status|check|test)|(?:is|why is) (?:the )?(?:touch ?screen|desk) (?:working|not working)", t):
        return ("desk_status", None)
    if re.fullmatch(r"(?:print|show|open) (?:my |the )?(?:desk )?cards", t):
        return ("desk_cards", None)
    if re.fullmatch(r"(?:hologram|holo)(?: mode)?|(?:open|show|start) (?:the )?hologram", t):
        return ("holo", None)
    return None


# ================= test it on its own: python jarvis_desk.py =================
def _browser():
    import shutil
    for p in (r"C:\Program Files\Google\Chrome\Application\chrome.exe", r"C:\Program Files (x86)\Google\Chrome\Application\chrome.exe",
              r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe", r"C:\Program Files\Microsoft\Edge\Application\msedge.exe"):
        if os.path.exists(p):
            return p
    return shutil.which("chrome") or shutil.which("msedge")


def open_on_projector(url):
    """Opens a page full screen on the projector (or the main screen if there's only one)."""
    import subprocess
    import webbrowser
    scr = projector_screen(or_main=True)
    exe = _browser()
    if exe and scr:
        x, y, w, h, _ = scr
        subprocess.Popen([exe, "--app=" + url, f"--window-position={x},{y}", f"--window-size={w},{h}", "--start-fullscreen",
                          "--user-data-dir=" + os.path.join(HERE, ".cache", "desk-browser")])
        return scr
    webbrowser.open(url)
    return None


def preview(index=None):
    """The down camera's picture with what it sees drawn on: calibration markers, cards, fingertips. Q to close."""
    import cv2
    import jarvis_vision
    _settings()
    idx = desk_index() if index is None else index
    cap, why = open_desk_camera(None if index is None else index, log=print)
    if not cap:
        print(why + "\nRun: python jarvis_desk.py --cameras  (and press the desk camera's number)")
        return
    det = jarvis_vision.Detectors(hands=True, faces=False, gestures=False, confidence=0.5)
    scr = projector_screen(or_main=True) or (0, 0, 1280, 720, True)
    board_win = "Atlas calibration squares"
    cv2.namedWindow(board_win, cv2.WINDOW_NORMAL)
    cv2.moveWindow(board_win, scr[0] + 20, scr[1] + 20)
    board = marker_board(scr[2], scr[3])
    main = next((m for m in monitors() if m[4]), None)
    separate = bool(main) and tuple(scr[:4]) != tuple(main[:4])
    cv2.imshow(board_win, board)
    cv2.waitKey(50)
    cv2.setWindowProperty(board_win, cv2.WND_PROP_FULLSCREEN, cv2.WINDOW_FULLSCREEN)
    cv2.waitKey(50)
    print(f"Camera {idx}. The squares are on the screen at {scr[:2]} ({scr[2]}x{scr[3]}).\n"
          "  If they're on the wrong screen, press Win+P and pick Extend, or set DESK_DISPLAY.\n"
          "  It saves the calibration by itself once the camera holds 9/9 for a second. Q = close")
    seen_since, saved = None, False
    while True:
        ok, frame = cap.read()
        if not ok:
            continue
        h, w = frame.shape[:2]
        gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
        ms = find_markers(gray, thorough=True)
        for mid, (c, _ang) in ms.items():
            cv2.circle(frame, (int(c[0]), int(c[1])), 10, (0, 220, 255), 2)
            cv2.putText(frame, CARDS.get(mid, str(mid)), (int(c[0]) + 12, int(c[1])), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 220, 255), 2)
        for lm in det.hands_all(cv2.cvtColor(frame, cv2.COLOR_BGR2RGB), time.time() * 1000):
            cv2.circle(frame, (int(lm[8][0] * w), int(lm[8][1] * h)), 9, (80, 255, 80), -1)
        cal = sum(i in ms for i in CAL_IDS)
        if cal == 9 and not saved:
            seen_since = seen_since or time.time()
            if time.time() - seen_since > 1.0:
                Calibration().fit([ms[i][0] for i in CAL_IDS], list(CAL_POS))
                saved = True
                print("Calibrated and saved. Close this (Q), start Atlas, and type touchscreen mode.")
        elif cal < 9:
            seen_since = None
        msg = f"camera {idx}   squares seen: {cal}/9" + ("   SAVED" if saved else "")
        cv2.putText(frame, msg, (14, 30), cv2.FONT_HERSHEY_SIMPLEX, 0.8, (80, 255, 80) if cal == 9 else (255, 255, 255), 2)
        if separate:   # the camera view goes on your monitor, the squares on the projector
            small = cv2.resize(frame, (960, int(frame.shape[0] * 960 / frame.shape[1])))
            cv2.imshow("Atlas desk camera (Q to close)", small)
        else:          # one screen (mirrored to the projector): nothing may cover the squares, so progress goes on the board
            b = board.copy()
            cv2.putText(b, f"squares seen {cal}/9" + ("  SAVED, press Q" if saved else "  (Q closes)"),
                        (int(scr[2] * 0.30), int(scr[3] * 0.32)), cv2.FONT_HERSHEY_SIMPLEX, scr[3] / 900, (0, 150, 0) if saved else (60, 60, 60), 2)
            cv2.imshow(board_win, b)
        k = cv2.waitKey(1) & 0xFF
        if k in (ord("q"), 27):
            break
    cap.release()
    cv2.destroyAllWindows()


def touch_test(index=None):
    """The touchscreen on its own, with everything visible: the camera picture with each hand's shape and where it
    lands on the mat, and real touches sent to Windows. Every tap, drag and scroll prints here. Q closes."""
    import cv2
    import jarvis_surface
    import jarvis_vision
    _settings()
    cal = Calibration()
    if not cal.ready:
        print("Not calibrated yet. Run: python jarvis_desk.py --preview  first.")
        return
    cap, why = open_desk_camera(index, log=print)
    if not cap:
        print(why)
        return
    det = jarvis_vision.Detectors(hands=True, faces=False, gestures=False, confidence=0.5)
    scr = projector_screen(or_main=True) or (0, 0, 1920, 1080, True)
    inj = jarvis_surface.Injector(scr[:4])
    touch = jarvis_surface.CameraTouch(inj)
    print(f"Touch area: {scr[2]}x{scr[3]} at {scr[0]},{scr[1]}. Sending " + ("real Windows touch." if inj.ok else "mouse clicks."))
    print("Point with your index finger and hold still to tap. Pinch to drag. Two fingers to scroll. Q closes.")
    cv2.namedWindow("Atlas touch test", cv2.WINDOW_NORMAL)
    cv2.resizeWindow("Atlas touch test", 640, 360)
    while True:
        ok, frame = cap.read()
        if not ok:
            continue
        h, w = frame.shape[:2]
        small = frame if w <= 1280 else cv2.resize(frame, (1280, int(h * 1280 / w)))
        hands = det.hands_all(cv2.cvtColor(small, cv2.COLOR_BGR2RGB), time.time() * 1000)
        hands = [jarvis_surface.refine_tips(frame, lm) for lm in hands]
        to_mat = lambda p: cal.to_desk((p[0] * w, p[1] * h))
        r = touch.feed([(lm, to_mat) for lm in hands])
        for lm in hands:
            for a, b in ((0, 5), (5, 8), (0, 9), (9, 12), (0, 13), (13, 16), (0, 17), (17, 20), (0, 1), (1, 4)):
                cv2.line(frame, (int(lm[a][0] * w), int(lm[a][1] * h)), (int(lm[b][0] * w), int(lm[b][1] * h)), (255, 200, 120), 2)
            cv2.circle(frame, (int(lm[8][0] * w), int(lm[8][1] * h)), 8, (80, 255, 80), -1)
            m = to_mat(lm[8])
            cv2.putText(frame, f"{jarvis_surface.shape(lm)}  mat {m[0]:.2f},{m[1]:.2f}" if m else jarvis_surface.shape(lm),
                        (int(lm[8][0] * w) + 12, int(lm[8][1] * h)), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (80, 255, 80), 2)
        cv2.putText(frame, f"hands {len(hands)}   {r['state']}" + (f"   tap {int(r['dwell'] * 100)}%" if r.get("dwell") else ""),
                    (14, 34), cv2.FONT_HERSHEY_SIMPLEX, 1.0, (255, 255, 255), 2)
        cv2.imshow("Atlas touch test", frame)
        if cv2.waitKey(1) & 0xFF in (ord("q"), 27):
            break
    inj.release()
    cap.release()
    cv2.destroyAllWindows()


def marker_board(w, h):
    """The 9 calibration squares, where the desk page puts them, as one picture for the projector."""
    import cv2
    import numpy as np
    board = np.full((h, w, 3), 255, np.uint8)
    size = int(min(w, h) * 0.17)
    d = cv2.aruco.getPredefinedDictionary(cv2.aruco.DICT_4X4_50)
    for mid, (x, y) in zip(CAL_IDS, CAL_POS):
        m = cv2.aruco.generateImageMarker(d, int(mid), size)
        pad = size // 6
        m = cv2.cvtColor(np.pad(m, pad, constant_values=255), cv2.COLOR_GRAY2BGR)
        s = m.shape[0]
        x0, y0 = int(x * w - s / 2), int(y * h - s / 2)
        x0, y0 = max(0, min(w - s, x0)), max(0, min(h - s, y0))
        board[y0:y0 + s, x0:x0 + s] = m
    return board


def _settings():
    """Run on its own (not inside Atlas): read the desk settings from local_settings.py."""
    try:
        sys.path.insert(0, HERE)
        import local_settings
        for k, v in vars(local_settings).items():
            if k.startswith("DESK") or k == "DWELL_SECONDS":
                globals()[k] = v
    except Exception:
        pass


def test():
    """The whole desk with no voice, no Claude: projector page, down camera, touches and cards. Type c to calibrate."""
    import jarvis_phone
    _settings()

    def ask(phrase):
        print(f"  >> desk asked for: {phrase}", flush=True)
        return "ok"
    desk = Desk(ask, lambda name, times=1: print(f"  >> key: {name} x{times}", flush=True),
                state=lambda: {"time": time.strftime("%I:%M %p").lstrip("0")}, say=lambda t: print("  atlas:", t, flush=True))
    bridge = jarvis_phone.Bridge(lambda text, speak=False: ask(text) or "ok", lambda name: "ok")
    desk.register(bridge)
    bridge.start()
    url = f"http://127.0.0.1:{jarvis_phone.PHONE_PORT}/desk?token={jarvis_phone.token()}"
    scr = open_on_projector(url)
    print("\nScreens:", monitors() or "(couldn't list them)")
    print("Desk page on", f"the screen at {scr[:2]}, {scr[2]}x{scr[3]}" if scr else "your browser (move it to the projector, press F11)")
    print("If it opened on the wrong screen, set DESK_DISPLAY = 0, 1 or 2 in local_settings.py and run this again.\n")
    desk.start()
    print("Commands:  c = calibrate   p = camera preview   s = status   q = quit")
    if not desk.cal.ready:
        print("Not calibrated yet. Keep your hands off the desk and type c.")
    last = 0
    while True:
        try:
            cmd = input("> ").strip().lower()
        except (EOFError, KeyboardInterrupt):
            break
        if cmd == "c":
            print("Calibrating: the projector shows 9 squares, the camera has to see all of them...")
            desk.calibrate(lambda ok: print("  calibrated. Hold a fingertip still on a button for half a second.", flush=True))
        elif cmd == "p":
            desk.stop()
            time.sleep(0.5)
            preview()
            desk.start()
        elif cmd == "s":
            l = desk.live
            print(f"  camera running: {desk.running}   calibrated: {desk.cal.ready}   calibrating: {desk.calibrating}   "
                  f"fingers on desk: {len(l['fingers'])}   cards: {[c['name'] for c in l['cards']]}")
        elif cmd == "q":
            break
    desk.stop()


def cameras():
    """Every camera's picture with its name. Press the number of the one looking at the desk and it's saved by
    name, so Windows renumbering cameras can't break it again."""
    import cv2
    import numpy as np
    names = camera_names()
    tiles, nums = [], []
    for i in range(max(len(names), 6) if not names else len(names)):
        img, how = None, ""
        for be in ([cv2.CAP_DSHOW] if IS_WIN else [0]):
            cap = cv2.VideoCapture(i, be)
            if cap.isOpened():
                camera_auto(cap, be)
                cap.set(cv2.CAP_PROP_FOURCC, cv2.VideoWriter_fourcc(*"MJPG"))
                for _ in range(40):
                    ok, f = cap.read()
                    if ok:
                        img, how = f, ("ok" if f.mean() > 4 else "black")
                        if how == "ok":
                            break
            cap.release()
        name = names[i] if i < len(names) else ""
        if img is None:
            print(f"  {i}  {name or '(nothing)'}   no picture (busy or unplugged)")
            img = np.zeros((270, 480, 3), np.uint8)
            how = "busy"
        print(f"  {i}  {name}   " + {"ok": "picture", "black": "only black (IR sensor, virtual camera, or shutter closed)",
                                    "busy": ""}[how])
        t = cv2.resize(img, (480, 270))
        cv2.rectangle(t, (0, 0), (480, 40), (0, 0, 0), -1)
        cv2.putText(t, f"{i}  {name[:28]}", (10, 28), cv2.FONT_HERSHEY_SIMPLEX, 0.75, (0, 220, 255), 2)
        tiles.append(t)
        nums.append(i)
    if not tiles:
        print("No cameras found.")
        return
    while len(tiles) % 2:
        tiles.append(np.zeros_like(tiles[0]))
    sheet = np.vstack([np.hstack(tiles[k:k + 2]) for k in range(0, len(tiles), 2)])
    print("\nClick the camera window, then press the NUMBER of the camera looking down at the desk (any other key: cancel).")
    cv2.imshow("Atlas cameras: press the desk camera's number", sheet)
    k = cv2.waitKey(0) & 0xFF
    cv2.destroyAllWindows()
    if ord("0") <= k <= ord("9") and k - ord("0") in nums:
        i = k - ord("0")
        if i < len(names):
            save_setting("DESK_CAMERA_NAME", names[i])
            print(f"Saved: the desk camera is '{names[i]}'. Atlas finds it by name from now on.")
        else:
            save_setting("DESK_CAMERA_INDEX", i)
            print(f"Saved: the desk camera is camera {i}.")


if __name__ == "__main__":
    if "--cameras" in sys.argv:
        cameras()
    elif "--touch" in sys.argv:
        touch_test()
    elif "--preview" in sys.argv:
        rest = sys.argv[sys.argv.index("--preview") + 1:]
        preview(int(rest[0]) if rest and rest[0].isdigit() else None)
    else:
        test()
