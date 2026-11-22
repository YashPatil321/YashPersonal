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
DESK_CAMERA_INDEX = 1        # the downward camera. The monitor webcam is usually 0
DESK_CAMERA_SIZE = (1280, 720)
DESK_DISPLAY = None          # which screen is the projector (0, 1, 2 ...). None = the smallest screen that isn't the main one
DWELL_SECONDS = 0.6
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
        _DET = cv2.aruco.ArucoDetector(d, cv2.aruco.DetectorParameters())
    return _DET


def find_markers(gray):
    """{id: (center_xy, angle_degrees)} in camera pixels."""
    corners, ids, _ = detector().detectMarkers(gray)
    out = {}
    if ids is None:
        return out
    for c, i in zip(corners, ids.ravel()):
        pts = c.reshape(4, 2)
        cx, cy = float(pts[:, 0].mean()), float(pts[:, 1].mean())
        ang = math.degrees(math.atan2(pts[1][1] - pts[0][1], pts[1][0] - pts[0][0]))
        out[int(i)] = ((cx, cy), ang)
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

    # ---- camera loop ----
    def start(self):
        if not self.running:
            self.running = True
            threading.Thread(target=self._run, daemon=True).start()

    def stop(self):
        self.running = False

    def calibrate(self, done=None):
        self.calibrating, self.cal_done = True, done
        self.live["calibrating"] = True
        self.start()

    def _run(self):
        try:
            import cv2
            import jarvis_vision
            det = jarvis_vision.Detectors(hands=True, faces=False)
        except Exception as e:
            _log(f"desk camera off: {e}")
            self.running = False
            return
        cap = cv2.VideoCapture(DESK_CAMERA_INDEX, cv2.CAP_DSHOW if IS_WIN else 0)
        cap.set(cv2.CAP_PROP_FRAME_WIDTH, DESK_CAMERA_SIZE[0])
        cap.set(cv2.CAP_PROP_FRAME_HEIGHT, DESK_CAMERA_SIZE[1])
        if not cap.isOpened():
            _log(f"no desk camera at index {DESK_CAMERA_INDEX}")
            self.say("I can't find the desk camera. Plug it in, or set DESK CAMERA INDEX.")
            self.running = False
            return
        _log("desk camera on")
        n = 0
        while self.running:
            good, frame = cap.read()
            if not good:
                time.sleep(0.1)
                continue
            n += 1
            try:
                self.step(frame, det, n)
            except Exception as e:
                _log(f"frame: {e}")
                time.sleep(0.3)
        cap.release()

    def step(self, frame, det, n=0, now_ms=None):
        import cv2
        h, w = frame.shape[:2]
        gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
        if self.calibrating:
            ms = find_markers(gray)
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
        rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
        hands = det.hands_all(rgb, now_ms if now_ms is not None else time.time() * 1000)
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


def projector_screen(mons=None):
    mons = monitors() if mons is None else mons
    if DESK_DISPLAY is not None and DESK_DISPLAY < len(mons):
        return mons[DESK_DISPLAY]
    others = [m for m in mons if not m[4]]
    return min(others, key=lambda m: m[2] * m[3]) if others else None


def route_desk(t):
    import re
    if re.fullmatch(r"(?:turn on |start |wake (?:up )?|activate )?(?:the )?desk(?: mode| ui| display)?(?: on)?|projector (?:on|mode)", t):
        return ("desk", True)
    if re.fullmatch(r"(?:turn off |stop |close )(?:the )?desk(?: mode| ui)?|desk (?:mode )?off|projector off", t):
        return ("desk", False)
    if re.fullmatch(r"(?:calibrate|recalibrate|line up|align) (?:the |my )?(?:desk|projector)", t):
        return ("desk_cal", None)
    if re.fullmatch(r"(?:print|show|open) (?:my |the )?(?:desk )?cards", t):
        return ("desk_cards", None)
    if re.fullmatch(r"(?:hologram|holo)(?: mode)?|(?:open|show|start) (?:the )?hologram", t):
        return ("holo", None)
    return None
