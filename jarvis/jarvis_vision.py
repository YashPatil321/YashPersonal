"""
Jarvis with eyes. A webcam on the monitor, MediaPipe on your PC. No picture is ever saved or sent anywhere.

  Presence   sees you sit down, so the welcome back happens without a clap or a keyboard.
  Gestures   peace sign = Jarvis starts listening (no wake word)
             open palm held = play or pause
             swipe right / left = next / previous song
             point up / point down held = volume up / down
             thumbs up = yes, to anything Jarvis asked you to confirm
             fist held = mute
             wave = wake the room
             air mouse (optional): index finger moves the cursor, pinch clicks
  Reps       "count my pushups" / "count my squats": counts out loud from your body pose, logs to Training.

Setup:  .venv\\Scripts\\pip install mediapipe opencv-python     then VISION = True in local_settings.py
Test:   python jarvis_vision.py --preview     (a window with what it sees and the gesture it reads)
"""

import math
import re
import os
import sys
import threading
import time
from collections import deque

IS_WIN = sys.platform == "win32"
# MediaPipe's engine prints a wall of INFO lines on start. Quiet it before it loads.
os.environ.setdefault("GLOG_minloglevel", "2")
os.environ.setdefault("TF_CPP_MIN_LOG_LEVEL", "3")
os.environ.setdefault("ABSL_MIN_LOG_LEVEL", "2")

# ---------------- settings (override in local_settings.py) ----------------
VISION = True                # on by default. No camera? It checks again every minute, so plugging one in just works
CAMERA_INDEX = 0             # the camera to try first. If it isn't there, Jarvis tries the others and uses the first that works
CAMERA_SIZE = (1920, 1080)    # asks for full HD (falls back to whatever the camera can do). More pixels = reads you from farther
GESTURES = True
AIR_MOUSE = False            # index finger drives the cursor, pinch clicks. Fun, but off by default
HOLD_SECONDS = 1.0           # how long a pose must be held before it counts
COOLDOWN_SECONDS = 2.5
ARM_SECONDS = 0.5            # a hand has to appear and hold still this long before any gesture counts
# Gestures only count when you hold your hand up toward the camera on purpose: big enough in the picture (close)
# and not down at the bottom edge (hands on the keyboard, scratching your face, waving at someone).
MIN_HAND = 0.045             # palm width as a share of the picture width (about arm's length from a normal webcam)
MAX_WRIST_Y = 0.80           # wrist above this line (0 top, 1 bottom): hand held up, not resting on the desk
PRESENCE_FROM_CAMERA = True
GESTURE_MODEL = True         # Google's trained gesture model on top of the hand points (much steadier than finger math)
VOTE_SECONDS = 0.35          # a shape has to win most of the frames in this window to count (kills flicker)
ZOOM = False                 # follow mode, off until you say "focus on me": it then zooms in on you (like a camera
                             # operator following you), so a small hand across the room still reads like a close one
ZOOM_WHEN_FACE_UNDER = 0.13  # zoom kicks in when your face is narrower than this share of the picture
HAND_VS_FACE = 0.38          # with your face in view: palm at least this share of your face width (held up toward the camera)
WRIST_BELOW_FACE = 2.4       # and wrist no more than this many face heights below your chin (not resting on the desk or lap)
GRACE_SECONDS = 0.3          # the hand can drop out of tracking this long (motion blur) without starting over
# ---------------------------------------------------------------------------

# MediaPipe hand landmark ids
WRIST, THUMB_TIP, THUMB_IP, THUMB_MCP = 0, 4, 3, 2
INDEX_MCP, INDEX_PIP, INDEX_TIP = 5, 6, 8
MIDDLE_MCP, MIDDLE_PIP, MIDDLE_TIP = 9, 10, 12
RING_PIP, RING_TIP = 14, 16
PINKY_MCP, PINKY_PIP, PINKY_TIP = 17, 18, 20


def _log(msg):
    print(time.strftime("[%H:%M:%S] ") + "vision: " + str(msg), flush=True)


def _d(a, b):
    return math.hypot(a[0] - b[0], a[1] - b[1])


# ================= gesture math (pure, tested) =================
def fingers(lm):
    """Which fingers are out: dict thumb/index/middle/ring/pinky -> bool. lm = 21 (x, y) points, y grows downward."""
    w = lm[WRIST]
    out = {}
    for name, tip, pip in (("index", INDEX_TIP, INDEX_PIP), ("middle", MIDDLE_TIP, MIDDLE_PIP),
                           ("ring", RING_TIP, RING_PIP), ("pinky", PINKY_TIP, PINKY_PIP)):
        out[name] = _d(lm[tip], w) > _d(lm[pip], w) * 1.15
    palm = _d(lm[INDEX_MCP], lm[PINKY_MCP]) or 1e-6
    # out = the thumb is straight and its tip is away from the index knuckle (tuned on real MediaPipe hands)
    out["thumb"] = angle(lm[1], lm[THUMB_MCP], lm[THUMB_TIP]) > 150 and _d(lm[THUMB_TIP], lm[INDEX_MCP]) > palm * 0.6
    return out


def pose_name(lm):
    """A held hand shape: palm, fist, peace, point_up, point_down, thumbs_up, or None."""
    f = fingers(lm)
    n4 = sum(f[k] for k in ("index", "middle", "ring", "pinky"))
    size = _d(lm[WRIST], lm[MIDDLE_MCP]) or 1e-6
    if n4 == 4 and f["thumb"]:
        return "palm"
    if n4 == 4:
        return "four"
    if f["index"] and f["middle"] and f["ring"] and not f["pinky"]:
        return "three"
    if n4 == 0 and f["thumb"] and lm[THUMB_TIP][1] < min(p[1] for i, p in enumerate(lm) if i > 4) - size * 0.05:
        return "thumbs_up"
    if n4 == 0 and not f["thumb"]:
        return "fist"
    if f["index"] and f["middle"] and not f["ring"] and not f["pinky"]:
        return "peace"
    if f["index"] and not f["middle"] and not f["ring"] and not f["pinky"]:
        dy = lm[INDEX_TIP][1] - lm[INDEX_MCP][1]
        dx = lm[INDEX_TIP][0] - lm[INDEX_MCP][0]
        if abs(dy) > abs(dx) * 1.3:
            return "point_up" if dy < 0 else "point_down"
    return None


MODEL_LABELS = {"Open_Palm": "palm", "Closed_Fist": "fist", "Victory": "peace", "Pointing_Up": "point_up",
                "Thumb_Up": "thumbs_up", "Thumb_Down": "thumbs_down", "ILoveYou": "rock", "None": ""}


def fuse(label, lm):
    """One frame's hand shape. The trained model decides when it has an opinion; the finger math fills in what it
    doesn't know (pointing down) and covers when the model isn't loaded."""
    mine = pose_name(lm)
    if label is None:
        return mine
    if mine in ("three", "four") and label in ("", "palm"):
        return mine   # the model has no three or four, it calls them palm or nothing
    if label == "point_up" and mine == "point_down":
        return "point_down"
    if label == "" and mine in ("point_down", "point_up"):
        return mine
    return label or None


def hand_size(lm):
    """How big the hand looks, the same whether it faces the camera or is turned edge on mid swipe.
    (Knuckle width shrinks to nothing when the hand turns sideways; palm length doesn't.)"""
    return max(_d(lm[INDEX_MCP], lm[PINKY_MCP]), _d(lm[WRIST], lm[MIDDLE_MCP]) * 0.85)


def pinching(lm):
    palm = _d(lm[INDEX_MCP], lm[PINKY_MCP]) or 1e-6
    return _d(lm[THUMB_TIP], lm[INDEX_TIP]) < palm * 0.35


class GestureReader:
    """Feed it one frame of landmarks at a time (or None for no hand). Returns a gesture name when one fires."""
    REPEATS = ("point_up", "point_down")   # these keep firing while held

    def __init__(self, hold=None, cooldown=None, clock=time.time):
        self.hold = HOLD_SECONDS if hold is None else hold
        self.cooldown = COOLDOWN_SECONDS if cooldown is None else cooldown
        self.clock = clock
        self.cur, self.since, self.last_fire, self.fired_cur = None, 0.0, -1e9, False
        self.track = deque()   # (t, x) of the open palm center, for swipes and waves
        self.arm_since = self.arm_pos = None
        self.why = ""
        self.votes = deque()
        self.mtrack = deque()
        self.dial, self.progress = None, 0.0
        self.ztrack, self.ctrack, self.last_push, self.last_circle = deque(), deque(), -1e9, -1e9
        self.swiped_at, self.last_swipe, self.last_wave, self.present_since = -1e9, None, -1e9, 0.0
        self.face = None
        self.seen_at = None
        self.palm = 0.08

    def feed(self, lm, label=None):
        """label: what the trained model says this frame ("palm", "fist", ..., "" for nothing), or None without it."""
        now = self.clock()
        self.progress = 0.0
        if lm is None and self.seen_at and now - self.seen_at < GRACE_SECONDS:
            return None   # lost the hand for a moment (fast move, blur): carry on where we were
        if lm is not None:
            self.seen_at = now
        self.why = "no hand" if lm is None else ""
        face = self.face if self.face and now - self.face[3] < 2.0 else None   # (width, chin y, height, when)
        if lm is not None:
            palm = hand_size(lm)
            if face:   # judged against your own face, so it works the same at any distance
                small = palm < max(0.012, face[0] * HAND_VS_FACE * 0.8)
                low = lm[WRIST][1] > face[1] + face[2] * WRIST_BELOW_FACE
                very_low = lm[WRIST][1] > face[1] + face[2] * WRIST_BELOW_FACE * 1.6
            else:
                small, low, very_low = palm < MIN_HAND * 0.8, lm[WRIST][1] > MAX_WRIST_Y, lm[WRIST][1] > 0.97
            if small:
                self.why, lm = "hand too small, hold it up toward the camera", None
            elif low:
                # a resting or fidgeting hand down low never counts. A real, deliberate sweep still does, as long as
                # it's clearly on purpose: longer, faster and flatter than a normal swipe.
                m = None if very_low else self._sweep(now, lm, label, strict=True)
                self.cur, self.fired_cur, self.arm_since = None, False, None
                self.votes.clear()
                self.why = "hand low: only a big deliberate swipe counts down there"
                return m
        if lm is not None:
            # swipes, waves and circles come first and skip arming: you raise your hand and go, no pause needed
            m = self._sweep(now, lm, label)
            if m:
                return m
            m = self._circle_feed(now, lm, label)
            if m:
                return m
        else:
            self.mtrack.clear()
        if lm is not None:
            # arming: the hand has to show up and hold fairly still for ARM_SECONDS before anything counts
            c = (lm[WRIST][0], lm[WRIST][1])
            if self.arm_since is None or self.arm_pos is None or (now - self.arm_since < ARM_SECONDS and _d(c, self.arm_pos) > 0.06):
                self.arm_since, self.arm_pos = now, c
            if now - self.arm_since < ARM_SECONDS:
                self.why = "hold still a moment"
                return None
        else:
            self.arm_since = self.arm_pos = None
        if lm is None:
            self.cur, self.fired_cur = None, False
            self.track.clear()
            self.votes.clear()
            self.seen_at = None
            return None
        # push: the hand moves toward the camera (looks a lot bigger, fast) without moving sideways, like pressing a button
        size = hand_size(lm)
        hx, hy = lm[MIDDLE_MCP]
        self.ztrack.append((now, size, hx, hy))
        while self.ztrack and now - self.ztrack[0][0] > 0.45:
            self.ztrack.popleft()
        zs = list(self.ztrack)
        if len(zs) >= 7 and now - self.last_push > 1.5 and sum(fingers(lm)[k] for k in ("index", "middle", "ring", "pinky")) >= 3:
            a, b = zs[:3], zs[-3:]
            s0, s1 = sum(z[1] for z in a) / 3, sum(z[1] for z in b) / 3
            x0, y0 = sum(z[2] for z in a) / 3, sum(z[3] for z in a) / 3
            steady_growth = sum(1 for p, q in zip(zs, zs[1:]) if q[1] >= p[1] * 0.97) >= len(zs) - 2
            if s1 > s0 * 1.35 and steady_growth and math.hypot(hx - x0, hy - y0) < s0 * 0.9:
                self.last_push = now
                self.ztrack.clear()
                self.cur, self.fired_cur = None, True
                return "push"
        # OK sign (thumb and index touching, other fingers up) then move up or down: a volume dial
        f = fingers(lm)
        if pinching(lm) and f["middle"] and f["ring"]:
            if self.dial is None:
                self.dial = [now, lm[WRIST][1], 0]
            elif now - self.dial[0] > 0.35:
                steps = int((self.dial[1] - lm[WRIST][1]) / (hand_size(lm) * 0.4))
                if steps != self.dial[2]:
                    up = steps > self.dial[2]
                    self.dial[2] += 1 if up else -1
                    self.why = "volume dial"
                    return "dial_up" if up else "dial_down"
            self.why = "OK sign: move up or down for volume"
            self.cur = None
            return None
        self.dial = None
        raw = fuse(label, lm)
        self.votes.append((now, raw))
        while self.votes and now - self.votes[0][0] > VOTE_SECONDS:
            self.votes.popleft()
        tally = {}
        for _, v in self.votes:
            tally[v] = tally.get(v, 0) + 1
        top, cnt = max(tally.items(), key=lambda kv: kv[1])
        n = len(self.votes)
        if cnt >= max(2, 0.6 * n):
            name = top
        elif self.cur is not None and tally.get(self.cur, 0) >= 0.45 * n:
            name = self.cur   # still mostly the same shape: keep the hold going
        else:
            name = None
        moving = len(self.mtrack) > 2 and abs(self.mtrack[-1][1] - self.mtrack[0][1]) > (self.mtrack[-1][4] or 0.05)
        self.why = "moving, watching for a swipe" if moving and not name else "reading: " + (name or "no clear shape")
        cx = sum(lm[i][0] for i in (WRIST, INDEX_MCP, PINKY_MCP)) / 3
        self.palm = _d(lm[INDEX_MCP], lm[PINKY_MCP])

        if raw == "palm" or (name == "palm" and raw is None):
            self.track.append((now, cx))
            while self.track and now - self.track[0][0] > 1.6:
                self.track.popleft()
        else:
            self.track.clear()
        if now - self.swiped_at < 0.8:
            self.cur, self.since = name, now   # just swiped: don't read the hand coming to rest as a held palm
            return None

        if name != self.cur:
            self.cur, self.since, self.fired_cur = name, now, False
            return None
        if name and not self.fired_cur and name not in self.REPEATS:
            self.progress = min(1.0, (now - self.since) / self.hold)   # the orb fills up as you hold
        if name is None or now - self.since < self.hold:
            return None
        if name == "palm" and self._moving():
            return None
        if self.fired_cur and name not in self.REPEATS:
            return None
        if name in self.REPEATS and len(self.ctrack) > 4:
            xs, ys = [p[1] for p in self.ctrack if now - p[0] < 0.5], [p[2] for p in self.ctrack if now - p[0] < 0.5]
            if xs and max(max(xs) - min(xs), max(ys) - min(ys)) > hand_size(lm) * 0.5:
                return None   # the finger is drawing, not holding
        gap = 0.45 if name in self.REPEATS else self.cooldown
        if now - self.last_fire < gap:
            return None
        self.last_fire, self.fired_cur = now, True
        return name

    def _circle_feed(self, now, lm, label):
        """Draw a circle in the air with your index finger."""
        if pose_name(lm) == "point_up" or label == "point_up":
            self.ctrack.append((now, lm[INDEX_TIP][0], lm[INDEX_TIP][1]))
            while self.ctrack and now - self.ctrack[0][0] > 1.8:
                self.ctrack.popleft()
            c = self._circle(hand_size(lm))
            if c and now - self.last_circle > 1.2:
                self.last_circle = now
                self.ctrack.clear()
                self.cur, self.fired_cur = None, True
                return c
        else:
            self.ctrack.clear()
        return None

    def _circle(self, size):
        """'circle_cw' or 'circle_ccw' once the fingertip has gone most of the way around a loop at least half a hand wide."""
        pts = list(self.ctrack)
        if len(pts) < 10:
            return None
        cx, cy = sum(p[1] for p in pts) / len(pts), sum(p[2] for p in pts) / len(pts)
        radii = [math.hypot(p[1] - cx, p[2] - cy) for p in pts]
        r = sorted(radii)[len(radii) // 2]
        if r < size * 0.35:
            return None
        ring = [p for p, rad in zip(pts, radii) if rad > r * 0.4]   # points near the middle (the start, a pause) don't count
        if len(ring) < 8:
            return None
        xr = max(p[1] for p in ring) - min(p[1] for p in ring)
        yr = max(p[2] for p in ring) - min(p[2] for p in ring)
        if min(xr, yr) < max(xr, yr) * 0.45:
            return None   # a line (wagging the finger), not a loop
        total, jumps = 0.0, 0
        for a, b in zip(ring, ring[1:]):
            d = math.atan2(b[2] - cy, b[1] - cx) - math.atan2(a[2] - cy, a[1] - cx)
            d = (d + math.pi) % (2 * math.pi) - math.pi
            if abs(d) > 1.4:
                jumps += 1   # cut straight across the middle: not going around
                continue
            total += d
        if jumps > len(ring) * 0.15:
            return None
        if abs(total) > math.radians(320):
            return "circle_cw" if total > 0 else "circle_ccw"   # picture y points down, so positive is clockwise
        return None

    def _sweep(self, now, lm, label, strict=False):
        """Swipe or wave from how the hand moves over the last ~0.7 s, whatever shape it blurs into on the way.
        Distances are in hand widths, so it's the same motion close up or across the room."""
        f = fingers(lm)
        # mid swipe the hand blurs and turns, so the model often can't name it. Anything but a clear fist counts.
        is_open = label != "fist" and (label in ("palm", "", None) or sum(f[k] for k in ("index", "middle", "ring", "pinky")) >= 2)
        cx = sum(lm[i][0] for i in (WRIST, INDEX_MCP, PINKY_MCP)) / 3
        cy = sum(lm[i][1] for i in (WRIST, INDEX_MCP, PINKY_MCP)) / 3
        palm = hand_size(lm) or 0.05
        if not self.mtrack:
            self.present_since = now
        self.mtrack.append((now, cx, cy, is_open, palm))
        while len(self.mtrack) > 1 and now - self.mtrack[0][0] > 0.9:
            self.mtrack.popleft()
        pts = list(self.mtrack)
        if len(pts) < 4 or sum(p[3] for p in pts) < 0.5 * len(pts):
            return None
        hw = sorted(p[4] for p in pts)[len(pts) // 2]   # typical hand width
        xs = [p[1] for p in pts]
        # wave: back and forth at least three times
        turns, direction = 0, 0
        for a, b in zip(xs, xs[1:]):
            d = b - a
            if abs(d) < hw * 0.15:
                continue
            sgn = 1 if d > 0 else -1
            if direction and sgn != direction:
                turns += 1
            direction = sgn
        if not strict and turns >= 3 and max(xs) - min(xs) > max(0.06, hw * 1.3) and now - self.last_wave > 3.0:
            self.last_wave = self.swiped_at = now
            self.mtrack.clear()
            return "wave"
        # swipe: one fast, mostly sideways sweep from where the hand was a moment ago
        # where the sweep began: the last moment the hand was at its far side
        lo = min(xs) if xs[-1] > xs[0] else max(xs)
        start = max(i for i, x in enumerate(xs) if abs(x - lo) < hw * 0.2)
        dx, dy = xs[-1] - pts[start][1], pts[-1][2] - pts[start][2]
        seg = xs[start:]
        back = max((abs(b - a) for a, b in zip(seg, seg[1:]) if (b - a) * dx < 0), default=0)
        settled = pts[start][0] - self.present_since >= 0.15   # hand was up before it moved (not someone passing by)
        quick = pts[-1][0] - pts[start][0] <= (0.45 if strict else 0.6)   # a flick, not slowly moving your hand over
        need, flat = (hw * 3.2, 0.45) if strict else (hw * 2.0, 0.7)
        if settled and quick and abs(dx) > max(0.09, need) and abs(dy) < abs(dx) * flat and back < hw * 0.5 and turns <= 1:
            way = "swipe_right" if dx > 0 else "swipe_left"
            opposite = self.last_swipe and self.last_swipe != way and now - self.swiped_at < 1.0   # the hand swinging back
            if now - self.swiped_at > 0.55 and not opposite:
                self.last_swipe, self.swiped_at = way, now
                self.mtrack.clear()
                return way
        return None

    def _moving(self):
        xs = [x for _, x in self.track]
        return len(xs) > 2 and max(xs) - min(xs) > 0.08

    def _motion(self, now):
        pts = list(self.track)
        if len(pts) < 4:
            return None
        xs = [x for _, x in pts]
        turns, direction = 0, 0
        for a, b in zip(xs, xs[1:]):
            d = b - a
            if abs(d) < 0.015:
                continue
            s = 1 if d > 0 else -1
            if direction and s != direction:
                turns += 1
            direction = s
        if turns >= 3 and max(xs) - min(xs) > max(0.08, self.palm * 1.3):
            return "wave"
        recent = [(t, x) for t, x in pts if now - t <= 0.5]
        if len(recent) >= 3:
            dx = recent[-1][1] - recent[0][1]
            if abs(dx) > max(0.16, self.palm * 2.6) and turns <= 1:   # about two and a half hand widths, any distance
                return "swipe_right" if dx > 0 else "swipe_left"
        return None


# ================= reps (pose) =================
def angle(a, b, c):
    """Angle at b, degrees."""
    ab = (a[0] - b[0], a[1] - b[1])
    cb = (c[0] - b[0], c[1] - b[1])
    dot = ab[0] * cb[0] + ab[1] * cb[1]
    n = (math.hypot(*ab) * math.hypot(*cb)) or 1e-6
    return math.degrees(math.acos(max(-1.0, min(1.0, dot / n))))


# MediaPipe pose ids
L_SHOULDER, R_SHOULDER, L_ELBOW, R_ELBOW, L_WRIST, R_WRIST = 11, 12, 13, 14, 15, 16
L_HIP, R_HIP, L_KNEE, R_KNEE, L_ANKLE, R_ANKLE = 23, 24, 25, 26, 27, 28
EXERCISES = {   # joint triple, down below this angle, up above this angle
    "pushups": ((L_SHOULDER, L_ELBOW, L_WRIST), (R_SHOULDER, R_ELBOW, R_WRIST), 95, 155),
    "squats": ((L_HIP, L_KNEE, L_ANKLE), (R_HIP, R_KNEE, R_ANKLE), 100, 160),
    "curls": ((L_SHOULDER, L_ELBOW, L_WRIST), (R_SHOULDER, R_ELBOW, R_WRIST), 50, 145),
}


class RepCounter:
    def __init__(self, exercise):
        self.ex = exercise
        self.left, self.right, self.down_at, self.up_at = EXERCISES[exercise]
        self.reps, self.down = 0, False

    def feed(self, pts):
        """pts: list of (x, y) pose landmarks. Returns True when a rep completes."""
        a = min(angle(*(pts[i] for i in self.left)), angle(*(pts[i] for i in self.right)))
        if a < self.down_at:
            self.down = True
        elif a > self.up_at and self.down:
            self.down = False
            self.reps += 1
            return True
        return False


# ================= the camera loop =================
MODEL_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), ".cache", "models")
MODELS = {
    "hand": "https://storage.googleapis.com/mediapipe-models/hand_landmarker/hand_landmarker/float16/latest/hand_landmarker.task",
    "gesture": "https://storage.googleapis.com/mediapipe-models/gesture_recognizer/gesture_recognizer/float16/latest/gesture_recognizer.task",
    "face": "https://storage.googleapis.com/mediapipe-models/face_detector/blaze_face_short_range/float16/latest/blaze_face_short_range.tflite",
    "pose": "https://storage.googleapis.com/mediapipe-models/pose_landmarker/pose_landmarker_lite/float16/latest/pose_landmarker_lite.task",
    "face_mesh": "https://storage.googleapis.com/mediapipe-models/face_landmarker/face_landmarker/float16/latest/face_landmarker.task",
    "objects": "https://storage.googleapis.com/mediapipe-models/object_detector/efficientdet_lite0/float16/latest/efficientdet_lite0.tflite",
}


def model_path(name):
    """Downloads a MediaPipe model the first time (a few MB, from Google's model store)."""
    os.makedirs(MODEL_DIR, exist_ok=True)
    path = os.path.join(MODEL_DIR, MODELS[name].rsplit("/", 1)[-1])
    if not os.path.exists(path):
        import urllib.request
        _log(f"downloading the {name} model")
        urllib.request.urlretrieve(MODELS[name], path + ".part")
        os.replace(path + ".part", path)
    return path


class Detectors:
    """MediaPipe Tasks (mediapipe 0.10.14 and newer). Each call takes an RGB numpy frame and a timestamp in ms."""
    def __init__(self, hands=True, faces=True):
        import mediapipe as mp
        from mediapipe.tasks.python import BaseOptions, vision
        self.mp, self.vision, self.Base = mp, vision, BaseOptions
        V = vision.RunningMode.VIDEO
        self.hands, self.recognizer, self.last_label, self._cache, self.last_all = None, None, None, (None, None), []
        if hands and GESTURE_MODEL:
            try:
                self.recognizer = vision.GestureRecognizer.create_from_options(vision.GestureRecognizerOptions(
                    base_options=BaseOptions(model_asset_path=model_path("gesture")), running_mode=V, num_hands=2,
                    min_hand_detection_confidence=0.6, min_hand_presence_confidence=0.6, min_tracking_confidence=0.6))
                self.hands = True
                _log("gesture model loaded")
            except Exception as e:
                _log(f"gesture model didn't load ({e}), using finger math")
        if hands and not self.recognizer:
            self.hands = vision.HandLandmarker.create_from_options(vision.HandLandmarkerOptions(
                base_options=BaseOptions(model_asset_path=model_path("hand")), running_mode=V, num_hands=2,
                min_hand_detection_confidence=0.6, min_hand_presence_confidence=0.6, min_tracking_confidence=0.6))
        self.hand_ts = 0
        self.faces = vision.FaceDetector.create_from_options(vision.FaceDetectorOptions(
            base_options=BaseOptions(model_asset_path=model_path("face")), running_mode=V, min_detection_confidence=0.5)) if faces else None
        self.pose = None
        self.last_ts = 0

    def _img(self, rgb):
        return self.mp.Image(image_format=self.mp.ImageFormat.SRGB, data=rgb)

    def _ts(self, ts):
        self.last_ts = max(int(ts), self.last_ts + 1)   # VIDEO mode needs strictly rising timestamps
        return self.last_ts

    def _hands(self, rgb, ts, roi=None):
        """[(points, label)] for each hand, one model run per frame however many times it's asked. roi = (x0, y0, x1, y1)
        as shares of the picture: look only there (zoomed in), points come back in whole picture coordinates."""
        if self._cache[0] is rgb:
            return self._cache[1]
        self.hand_ts = max(int(ts), self.hand_ts + 1)
        full, ox, oy, sx, sy = rgb, 0.0, 0.0, 1.0, 1.0
        if roi:
            import numpy as np
            H, W = rgb.shape[:2]
            x0, y0, x1, y1 = int(roi[0] * W), int(roi[1] * H), int(roi[2] * W), int(roi[3] * H)
            if x1 - x0 > 32 and y1 - y0 > 32:
                rgb = np.ascontiguousarray(rgb[y0:y1, x0:x1])
                ox, oy, sx, sy = x0 / W, y0 / H, (x1 - x0) / W, (y1 - y0) / H
        out = self._run_hands(rgb)
        out = [([(ox + x * sx, oy + y * sy) for x, y in pts], lab) for pts, lab in out]
        self._cache = (full, out)
        return out

    def _run_hands(self, rgb):
        if self.recognizer:
            r = self.recognizer.recognize_for_video(self._img(rgb), self.hand_ts)
            out = []
            for i, h in enumerate(r.hand_landmarks):
                g = r.gestures[i][0] if i < len(r.gestures) and r.gestures[i] else None
                label = MODEL_LABELS.get(g.category_name, "") if g is not None and g.score >= 0.55 else ""
                out.append(([(p.x, p.y) for p in h], label))
            return out
        r = self.hands.detect_for_video(self._img(rgb), self.hand_ts)
        return [([(p.x, p.y) for p in h], None) for h in r.hand_landmarks]

    def hands_all(self, rgb, ts):
        return [h for h, _ in self._hands(rgb, ts)]

    def hand(self, rgb, ts, roi=None, keep=None):
        """The biggest (closest) hand that `keep` accepts. Its model label is in self.last_label."""
        hs = self._hands(rgb, ts, roi)
        self.last_all = hs
        if keep:
            hs = [h for h in hs if keep(h[0])]
        if not hs:
            self.last_label = None
            return None
        lm, self.last_label = max(hs, key=lambda h: _d(h[0][INDEX_MCP], h[0][PINKY_MCP]))
        return lm

    def face(self, rgb, ts):
        return bool(self.faces.detect_for_video(self._img(rgb), self._ts(ts)).detections)

    def body(self, rgb, ts):
        if not self.pose:
            v = self.vision
            self.pose = v.PoseLandmarker.create_from_options(v.PoseLandmarkerOptions(
                base_options=self.Base(model_asset_path=model_path("pose")), running_mode=v.RunningMode.VIDEO))
        r = self.pose.detect_for_video(self._img(rgb), self._ts(ts))
        return [(p.x, p.y) for p in r.pose_landmarks[0]] if r.pose_landmarks else None


# ================= face gestures: nod, shake, wink, eyebrows (pure, tested) =================
FACE_GESTURES = True         # head nods and shakes answer yes or no; winks and raised eyebrows are yours to map


class HeadReader:
    """Feed it head angles (degrees) and face muscle scores (0 to 1, from MediaPipe's face mesh) about 15 times a
    second. Returns "nod", "shake", "wink", "brows" or "eyes_closed" when one happens."""
    def __init__(self, clock=time.time):
        self.clock = clock
        self.hist = deque()          # (t, yaw, pitch)
        self.last = {}               # event -> last time fired
        self.wink_since = self.brows_since = self.closed_since = None

    def _fire(self, name, now, gap):
        if now - self.last.get(name, -1e9) < gap:
            return None
        self.last[name] = now
        return name

    @staticmethod
    def _swings(vals, step):
        """How many times the movement reverses direction (ignoring wobbles smaller than step)."""
        turns, direction, anchor = 0, 0, vals[0]
        for v in vals[1:]:
            d = v - anchor
            if abs(d) < step:
                continue
            sgn = 1 if d > 0 else -1
            if direction and sgn != direction:
                turns += 1
            direction, anchor = sgn, v
        return turns

    def feed(self, yaw, pitch, b):
        now = self.clock()
        self.hist.append((now, yaw, pitch))
        while self.hist and now - self.hist[0][0] > 1.3:
            self.hist.popleft()
        ys, ps = [h[1] for h in self.hist], [h[2] for h in self.hist]
        if len(ys) >= 6:
            yr, pr = max(ys) - min(ys), max(ps) - min(ps)
            if pr > 9 and yr < pr * 0.6 and self._swings(ps, 3.0) >= 2:
                e = self._fire("nod", now, 1.6)
                if e:
                    self.hist.clear()
                    return e
            if yr > 12 and pr < yr * 0.6 and self._swings(ys, 4.0) >= 2:
                e = self._fire("shake", now, 1.6)
                if e:
                    self.hist.clear()
                    return e
        l, r = b.get("eyeBlinkLeft", 0), b.get("eyeBlinkRight", 0)
        if (l > 0.55 and r < 0.25) or (r > 0.55 and l < 0.25):
            self.wink_since = self.wink_since or now
        else:
            if self.wink_since and 0.18 <= now - self.wink_since <= 1.2:
                self.wink_since = None
                e = self._fire("wink", now, 1.5)
                if e:
                    return e
            self.wink_since = None
        if l > 0.6 and r > 0.6:
            self.closed_since = self.closed_since or now
            if now - self.closed_since > 4.0:
                e = self._fire("eyes_closed", now, 60)
                if e:
                    return e
        else:
            self.closed_since = None
        brow = max(b.get("browInnerUp", 0), (b.get("browOuterUpLeft", 0) + b.get("browOuterUpRight", 0)) / 2)
        if brow > 0.6:
            self.brows_since = self.brows_since or now
            if now - self.brows_since > 0.45:
                self.brows_since = now + 10   # once per raise
                e = self._fire("brows", now, 2.0)
                if e:
                    return e
        else:
            self.brows_since = None
        return None


def head_angles(matrix):
    """(yaw, pitch) in degrees from MediaPipe's 4x4 face transform."""
    m = [[matrix[i][j] for j in range(3)] for i in range(3)]
    pitch = math.degrees(math.atan2(m[2][1], m[2][2]))
    yaw = math.degrees(math.atan2(-m[2][0], math.hypot(m[2][1], m[2][2])))
    return yaw, pitch


class FaceSense:
    """MediaPipe's face mesh: 478 points, 52 muscle scores and head angle for the face it's following."""
    def __init__(self):
        import mediapipe as mp
        from mediapipe.tasks.python import BaseOptions, vision
        self.mp, self.ts = mp, 0
        self.lm = vision.FaceLandmarker.create_from_options(vision.FaceLandmarkerOptions(
            base_options=BaseOptions(model_asset_path=model_path("face_mesh")), running_mode=vision.RunningMode.VIDEO,
            num_faces=3, output_face_blendshapes=True, output_facial_transformation_matrixes=True,
            min_face_detection_confidence=0.5, min_face_presence_confidence=0.5, min_tracking_confidence=0.5))

    def read(self, rgb, near=None):
        """(yaw, pitch, scores) for the face closest to `near` (x, y shares of the picture, e.g. you), else the biggest."""
        self.ts = max(int(time.time() * 1000), self.ts + 1)
        r = self.lm.detect_for_video(self.mp.Image(image_format=self.mp.ImageFormat.SRGB, data=rgb), self.ts)
        if not r.face_landmarks:
            return None
        def center(i):
            pts = r.face_landmarks[i]
            xs, ys = [p.x for p in pts], [p.y for p in pts]
            return (sum(xs) / len(xs), sum(ys) / len(ys), max(xs) - min(xs))
        cs = [center(i) for i in range(len(r.face_landmarks))]
        if near:
            i = min(range(len(cs)), key=lambda k: (cs[k][0] - near[0]) ** 2 + (cs[k][1] - near[1]) ** 2)
        else:
            i = max(range(len(cs)), key=lambda k: cs[k][2])
        yaw, pitch = head_angles(r.facial_transformation_matrixes[i]) if r.facial_transformation_matrixes else (0.0, 0.0)
        scores = {c.category_name: c.score for c in r.face_blendshapes[i]} if r.face_blendshapes else {}
        return yaw, pitch, scores


class ObjectFinder:
    """Everyday objects in a picture (phone, cup, book, laptop, ...), COCO's 80 kinds."""
    def __init__(self, min_score=0.45):
        import mediapipe as mp
        from mediapipe.tasks.python import BaseOptions, vision
        self.mp = mp
        self.det = vision.ObjectDetector.create_from_options(vision.ObjectDetectorOptions(
            base_options=BaseOptions(model_asset_path=model_path("objects")), score_threshold=min_score, max_results=8))

    def labels(self, bgr):
        import cv2
        rgb = cv2.cvtColor(bgr, cv2.COLOR_BGR2RGB)
        r = self.det.detect(self.mp.Image(image_format=self.mp.ImageFormat.SRGB, data=rgb))
        return [d.categories[0].category_name for d in r.detections if d.categories]


class Vision:
    def __init__(self, on_gesture=None, on_face=None, say=None, on_people=None):
        self.on_gesture, self.on_face, self.say, self.on_people = on_gesture, on_face, say, on_people
        self.touch = None          # (TouchController, WindowsTouch) while touch mode is on
        self.cad = None            # CadHub while the CAD workshop is open: hands go to the 3D model, not the gestures
        self.faceid = None
        self.room = None
        self.enroll = None         # (name, feats list, until, done callback) while learning a face
        self.last_seen_names = []
        self.last_face = 0.0
        self.enabled = True
        self.reps = None          # RepCounter while counting
        self.reps_done = None     # callback(exercise, reps)
        self.reader = GestureReader()
        self.ok = False

    def snapshot(self, path):
        """Saves what the camera sees right now as a JPEG (for 'can you see me'). Returns the path, or None."""
        import cv2
        f = getattr(self, "last_frame", None)
        if f is None or time.time() - getattr(self, "last_frame_t", 0) > 3:
            return grab_frame(path)
        os.makedirs(os.path.dirname(path), exist_ok=True)
        cv2.imwrite(path, f)
        return path

    def seconds_since_face(self):
        return time.time() - self.last_face if self.last_face else 1e9

    def start(self):
        threading.Thread(target=self._run, daemon=True).start()
        return self

    def count(self, exercise, done):
        self.reps, self.reps_done = RepCounter(exercise), done

    def stop_count(self):
        rc, self.reps = self.reps, None
        if rc and self.reps_done:
            self.reps_done(rc.ex, rc.reps)
        return rc

    def _run(self):
        det = None
        for attempt in range(2):
            try:
                import cv2
                det = Detectors(hands=GESTURES, faces=PRESENCE_FROM_CAMERA)
                break
            except ImportError:
                if attempt == 0:
                    _log("camera packages missing, installing them now (a few minutes, once)")
                    import subprocess
                    import update
                    update.install_extras()
                    import importlib
                    importlib.invalidate_caches()
            except Exception as e:
                _log(f"camera models failed: {e}")
                return
        if det is None:
            _log("camera packages didn't install. Run: .venv\\Scripts\\python update.py --extras")
            return
        warned = False
        while True:
            cap, idx = open_camera(CAMERA_INDEX, avoid=desk_camera_index())
            if cap:
                self.camera_index = idx
                _log(f"camera {idx} works" + ("" if idx == CAMERA_INDEX else f" (camera {CAMERA_INDEX} didn't, set CAMERA_INDEX = {idx} to skip the search)"))
                break
            if not warned:
                _log("no working camera yet (tried 0 to 5). Is another app using it, or is it unplugged? Checking every minute")
                warned = True
            time.sleep(60)
        setup_capture(cap)
        grab = LatestFrame(cap)
        try:
            import jarvis_faces
            if jarvis_faces.FACES:
                self.faceid, self.room = jarvis_faces.FaceID(), jarvis_faces.Room()
                _log(f"face id on, knows: {', '.join(self.faceid.book.people) or 'nobody yet, say learn my face'}")
        except Exception as e:
            _log(f"face id off: {e}")
        self.ok = True
        _log(f"camera on, {grab.size()}")
        if self.faceid:
            threading.Thread(target=self._faces_loop, daemon=True).start()
        threading.Thread(target=self._phone_loop, daemon=True).start()
        if FACE_GESTURES:
            threading.Thread(target=self._head_loop, daemon=True).start()
        n, face_seen, pinch_was = 0, False, False
        while True:
            if not self.enabled:
                time.sleep(0.5)
                continue
            if getattr(self, "low_power", False):
                time.sleep(0.12)   # standby: a few frames a second is plenty to notice you walk in
            frame = grab.next(timeout=1.0)   # always the newest picture, never a stale one from the buffer
            if frame is None:
                continue
            self.fps_n = getattr(self, "fps_n", 0) + 1
            if time.time() - getattr(self, "fps_t", 0) >= 60:
                if getattr(self, "fps_t", 0):
                    self.fps = self.fps_n / (time.time() - self.fps_t)
                    _log(f"tracking at {self.fps:.0f} fps" + (", following you" if getattr(self, "zoom_on", ZOOM) else ""))
                self.fps_t, self.fps_n = time.time(), 0
            frame = cv2.flip(frame, 1)   # mirror, so your right is the screen's right
            self.last_frame, self.last_frame_t = frame, time.time()
            rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
            ts = time.time() * 1000
            n += 1
            try:
                if self.reps:
                    pts = det.body(rgb, ts)
                    if pts and self.reps.feed(pts) and self.say:
                        k = self.reps.reps
                        threading.Thread(target=self.say, args=(str(k) if k % 5 else f"{k}. Keep going.",), daemon=True).start()
                    continue
                if self.enroll:
                    self._enroll_step(frame)
                    continue
                if self.faceid:
                    pass   # faces run on their own thread, so hands never wait for them
                elif det.faces and not self.faceid and n % 10 == 0:   # faces about twice a second is plenty
                    seen = det.face(rgb, ts)
                    if seen:
                        self.last_face = time.time()
                    if seen != face_seen:
                        face_seen = seen
                        if self.on_face:
                            self.on_face(seen)
                if not det.hands or getattr(self, "low_power", False):
                    continue
                if self.cad and self.cad.active:
                    self.cad.set_hands(det.hands_all(rgb, ts))
                    continue
                if self.touch:
                    ctl, exe = self.touch
                    exe.run(ctl.feed(det.hands_all(rgb, ts)))
                    continue
                lm = det.hand(rgb, ts, self._zoom_roi(), keep=self.keep_hand)
                g2 = self._two_hands(det.last_all)
                if g2 and self.on_gesture:
                    threading.Thread(target=self.on_gesture, args=(g2,), daemon=True).start()
                    self._orb(g2)
            except Exception as e:
                _log(f"frame: {e}")
                time.sleep(0.5)
                continue
            if AIR_MOUSE and lm:
                self._mouse(lm)
                p = pinching(lm)
                if p and not pinch_was:
                    self._click()
                pinch_was = p
                continue
            g = self.reader.feed(lm, det.last_label if lm is not None else None)
            self._orb(g)
            if lm is not None and self.reader.why != getattr(self, "_why_logged", "") and time.time() - getattr(self, "_why_t", 0) > 8:
                self._why_logged, self._why_t = self.reader.why, time.time()
                _log("hand seen: " + self.reader.why)   # so you can see why a gesture didn't fire
            if g and self.on_gesture:
                threading.Thread(target=self.on_gesture, args=(g,), daemon=True).start()

    # ---- faces ----
    def learn_face(self, name, done, seconds=6.0):
        self.enroll = (name, [], time.time() + seconds, done)

    def _enroll_step(self, frame):
        name, feats, until, done = self.enroll
        if self.faceid:
            f = self.faceid.biggest_feature(frame)
            if f is not None and not _near_duplicate(f, feats):
                feats.append(f)
        if time.time() >= until or len(feats) >= 24:
            self.enroll = None
            saved = self.faceid.book.add(name, feats[2:] if len(feats) > 5 else feats) if self.faceid and feats else None
            done(saved, len(feats))

    def _two_hands(self, hands):
        """Both open palms up toward the camera, held for most of a second: "both_palms" (stop)."""
        now = time.time()
        both = len(hands) >= 2 and sum(1 for pts, lab in hands if (lab == "palm" or (lab is None and pose_name(pts) == "palm"))
                                       and self.keep_hand(pts)) >= 2
        if not both:
            self._both_since = None
            return None
        self._both_since = getattr(self, "_both_since", None) or now
        if now - self._both_since > 0.7 and now - getattr(self, "_both_fired", 0) > 3:
            self._both_fired = now
            self.reader.cur, self.reader.fired_cur = "palm", True   # so one palm doesn't also count as play/pause
            return "both_palms"
        return None

    def _orb(self, g):
        """Live feedback in the corner orb: it fills up while you hold a gesture and flashes when one fires."""
        try:
            import jarvis_orb
            now = time.time()
            if g:
                jarvis_orb.send("gesture:" + g)
                self._orb_t = now
            elif self.reader.progress > 0.05 and now - getattr(self, "_orb_t", 0) > 0.08:
                jarvis_orb.send(f"hold:{self.reader.progress:.2f}")
                self._orb_t = now
        except Exception:
            pass

    def _head_loop(self):
        """Face mesh about 15 times a second on your face only: nods, shakes, winks, raised eyebrows."""
        import cv2
        try:
            fs = FaceSense()
            _log("face mesh on (nod yes, shake no, wink, eyebrows)")
        except Exception as e:
            _log(f"face mesh off: {e}")
            return
        reader = HeadReader()
        while True:
            time.sleep(0.066)
            try:
                f = getattr(self, "last_frame", None)
                if f is None or not self.enabled or self.enroll or time.time() - getattr(self, "last_frame_t", 0) > 2 \
                        or self.seconds_since_face() > 10:
                    continue
                h, w = f.shape[:2]
                k = min(1.0, 960 / w)
                small = cv2.resize(f, (int(w * k), int(h * k))) if k < 1 else f
                me = self.owner_center()
                got = fs.read(cv2.cvtColor(small, cv2.COLOR_BGR2RGB), near=me)
                if got:
                    self.head = got
                    e = reader.feed(*got)
                    if e and self.on_gesture:
                        threading.Thread(target=self.on_gesture, args=(e,), daemon=True).start()
                        self._orb(e)
            except Exception as e:
                _log(f"face mesh: {e}")
                time.sleep(2)

    def owner_center(self):
        """Where your face is in the picture (x, y shares), when it knows you and sees you."""
        for cx, cy, w, name in getattr(self, "faces_norm", []):
            if name == getattr(self, "owner_name", "yash"):
                return (cx, cy)
        return None

    def keep_hand(self, pts):
        """With more than one person in view, only hands that belong to you count (the hand nearest your face).
        Until it knows your face, every hand counts."""
        fl = [f for f in getattr(self, "faces_norm", []) if time.time() - getattr(self, "faces_norm_t", 0) < 2]
        if len(fl) < 2 or not any(f[3] == getattr(self, "owner_name", "yash") for f in fl):
            return True
        wx, wy = pts[WRIST]
        owner_of = min(fl, key=lambda f: (abs(wx - f[0]) / max(f[2], 1e-3)) + 0.3 * max(0.0, f[1] - wy) / max(f[2], 1e-3))
        return owner_of[3] == getattr(self, "owner_name", "yash")

    phone_watch = None    # set by Jarvis: returns True while a focus session runs
    on_phone = None       # called with the number of seconds the phone has been out

    def _phone_loop(self):
        """During focus sessions, looks for a phone in your hands about once every two seconds (Google's object
        model, on your PC). Out for 20 seconds straight and Jarvis says something, at most every 5 minutes."""
        det, seen_since, last_nudge, misses = None, None, 0.0, 0
        while True:
            time.sleep(1.8)
            try:
                if not (self.phone_watch and self.phone_watch()) or not self.enabled:
                    seen_since, misses = None, 0
                    continue
                f = getattr(self, "last_frame", None)
                if f is None or time.time() - getattr(self, "last_frame_t", 0) > 3:
                    continue
                if det is None:
                    det = ObjectFinder()
                if "cell phone" in det.labels(f):
                    misses = 0
                    seen_since = seen_since or time.time()
                    out = time.time() - seen_since
                    if out >= 20 and time.time() - last_nudge > 300 and self.on_phone:
                        last_nudge = time.time()
                        threading.Thread(target=self.on_phone, args=(out,), daemon=True).start()
                else:
                    misses += 1
                    if misses >= 3:   # put down for about five seconds
                        seen_since = None
            except Exception as e:
                _log(f"phone check: {e}")
                time.sleep(30)

    def _zoom_roi(self):
        """Where to look for hands: a crop around you when you're far away, else the whole picture.
        The crop only moves when you do, so hand tracking stays locked on."""
        f = getattr(self, "focus", None)
        if not f or time.time() - f[4] > 2.0:
            self.reader.face = None
            self.roi = None
            return None
        x, y, w, h, _ = f
        self.reader.face = (w, y + h, h, f[4])
        if not getattr(self, "zoom_on", ZOOM) or w >= ZOOM_WHEN_FACE_UNDER:
            self.roi = None
            return None
        cx = x + w / 2
        want = (max(0.0, cx - w * 5.0), max(0.0, y - h * 1.2), min(1.0, cx + w * 5.0), min(1.0, y + h * 5.0))
        old = getattr(self, "roi", None)
        if old and abs((old[0] + old[2]) / 2 - (want[0] + want[2]) / 2) < w * 0.6 and abs(old[1] - want[1]) < h * 0.6 \
                and abs((old[2] - old[0]) - (want[2] - want[0])) < (want[2] - want[0]) * 0.25:
            return old
        self.roi = want
        return want

    def _faces_loop(self):
        """Who's here, about three times a second, on the newest frame."""
        while True:
            time.sleep(0.33)
            f = getattr(self, "last_frame", None)
            if f is None or self.enroll or not self.enabled or time.time() - getattr(self, "last_frame_t", 0) > 2:
                continue
            try:
                self._faces_step(f)
            except Exception as e:
                _log(f"faces: {e}")
                time.sleep(2)

    def _faces_step(self, frame):
        import jarvis_faces
        found = self.faceid.identify(frame)
        H, W = frame.shape[:2]
        trs = [t for t in getattr(self.faceid, "tracks", []) if time.time() - t["t"] < 1.0]
        t = None
        if trs:   # you if it knows you're here; in follow mode only ever you, else the closest face
            t = next((t for t in trs if t.get("name") == jarvis_faces.OWNER), None)
            if t is None and not (getattr(self, "zoom_on", ZOOM) and jarvis_faces.OWNER in self.faceid.book.people):
                t = max(trs, key=lambda t: t["w"])
        self.owner_name = jarvis_faces.OWNER
        self.faces_norm = [(x["cx"] / W, x["cy"] / H, x["w"] / W, x.get("name") if x.get("sure") else None) for x in trs]
        self.faces_norm_t = time.time()
        if t is not None:
            self.focus = ((t["cx"] - t["w"] / 2) / W, (t["cy"] - t["h"] / 2) / H, t["w"] / W, t["h"] / H, time.time())
        self.last_seen_names = [n for n, _, _ in found]
        owner_known = jarvis_faces.OWNER in self.faceid.book.people
        if found and (not owner_known or jarvis_faces.OWNER in self.last_seen_names):
            self.last_face = time.time()
        self.room.owner_known = owner_known
        arrived, left = self.room.feed(self.last_seen_names)
        if self.room.guests() != getattr(self, "_guests_was", False):
            self._guests_was = self.room.guests()
            arrived = arrived or {"?"}   # tell Jarvis so guest mode follows
        if (arrived or left) and self.on_people:
            threading.Thread(target=self.on_people, args=(arrived, left, self.room), daemon=True).start()
        if self.room.should_lock() and self.on_people:
            self.room.stranger_since = None
            threading.Thread(target=self.on_people, args=(set(), set(), self.room, True), daemon=True).start()

    def _mouse(self, lm):
        if not IS_WIN:
            return
        import ctypes
        u = ctypes.windll.user32
        w, h = u.GetSystemMetrics(78), u.GetSystemMetrics(79)   # whole virtual screen
        x0, y0 = u.GetSystemMetrics(76), u.GetSystemMetrics(77)
        tx, ty = lm[INDEX_TIP]
        # the middle 60 percent of the camera covers the whole screen
        fx, fy = min(1, max(0, (tx - 0.2) / 0.6)), min(1, max(0, (ty - 0.2) / 0.6))
        px, py = int(x0 + fx * w), int(y0 + fy * h)
        if not hasattr(self, "_m"):
            self._m = (px, py)
        self._m = (int(self._m[0] * 0.6 + px * 0.4), int(self._m[1] * 0.6 + py * 0.4))
        u.SetCursorPos(*self._m)

    def _click(self):
        if IS_WIN:
            import ctypes
            u = ctypes.windll.user32
            u.mouse_event(0x0002, 0, 0, 0, 0)
            u.mouse_event(0x0004, 0, 0, 0, 0)


def desk_camera_index():
    try:
        import jarvis_desk
        return jarvis_desk.DESK_CAMERA_INDEX
    except Exception:
        return None


def _near_duplicate(f, feats, limit=0.95):
    import numpy as np
    if not feats:
        return False
    a = np.asarray(f, dtype=np.float32).ravel()
    m = np.asarray(feats[-12:], dtype=np.float32).reshape(-1, a.size)
    sims = (m @ a) / ((np.linalg.norm(m, axis=1) + 1e-9) * (np.linalg.norm(a) + 1e-9))
    return float(sims.max()) > limit


CAMERA_FPS = 60              # ask for this; most webcams do 60 at 720p and 30 at 1080p
CAMERA_MODES = [(1920, 1080), (1280, 720)]   # tried in order; it keeps whichever actually runs fastest


def _measure(cap, n=24):
    t0, got, f = time.time(), 0, None
    for _ in range(n + 3):
        ok, fr = cap.read()
        if ok:
            got, f = got + 1, fr
            if got == 3:
                t0 = time.time()   # skip the first frames, they come out of a buffer
    if got <= 3 or f is None:
        return 0.0, (0, 0)
    return (got - 3) / max(1e-3, time.time() - t0), (f.shape[1], f.shape[0])


def setup_capture(cap):
    """Compressed (MJPG) so USB can carry high frame rates, no backlog of old frames, and the camera mode that gives
    the most frames per second (full HD wins a tie). Most of what makes hand tracking feel instant is frame rate."""
    import cv2
    try:
        cap.set(cv2.CAP_PROP_FOURCC, cv2.VideoWriter_fourcc(*"MJPG"))
        cap.set(cv2.CAP_PROP_BUFFERSIZE, 1)
        best, w, h = None, 0, 0
        modes = [tuple(CAMERA_SIZE)] + [m for m in CAMERA_MODES if m != tuple(CAMERA_SIZE)]
        for w, h in modes:
            cap.set(cv2.CAP_PROP_FRAME_WIDTH, w)
            cap.set(cv2.CAP_PROP_FRAME_HEIGHT, h)
            cap.set(cv2.CAP_PROP_FPS, CAMERA_FPS)
            fps, size = _measure(cap)
            _log(f"camera mode {size[0]}x{size[1]}: {fps:.0f} fps")
            if best is None or fps > best[0] * 1.25:
                best = (fps, w, h)
            if fps >= CAMERA_FPS * 0.85:
                break
        if best and (best[1], best[2]) != (w, h):
            cap.set(cv2.CAP_PROP_FRAME_WIDTH, best[1])
            cap.set(cv2.CAP_PROP_FRAME_HEIGHT, best[2])
            cap.set(cv2.CAP_PROP_FPS, CAMERA_FPS)
        cap.set(cv2.CAP_PROP_BUFFERSIZE, 1)
    except Exception as e:
        _log(f"camera setup: {e}")


class LatestFrame:
    """Reads the camera nonstop on its own thread and keeps only the newest frame, so what Jarvis sees is never
    behind what you're doing (cameras otherwise queue frames and the lag piles up)."""
    def __init__(self, cap):
        self.cap, self.frame, self.seq, self.taken = cap, None, 0, 0
        self.cond = threading.Condition()
        threading.Thread(target=self._pump, daemon=True).start()

    def _pump(self):
        fails = 0
        while True:
            ok, f = self.cap.read()
            if not ok:
                fails += 1
                time.sleep(0.05 if fails < 40 else 0.5)
                continue
            fails = 0
            with self.cond:
                self.frame, self.seq = f, self.seq + 1
                self.cond.notify_all()

    def next(self, timeout=1.0):
        with self.cond:
            if self.seq == self.taken:
                self.cond.wait(timeout)
            if self.seq == self.taken:
                return None
            self.taken = self.seq
            return self.frame

    def size(self):
        f = self.frame
        return f"{f.shape[1]}x{f.shape[0]}" if f is not None else "no picture yet"


def open_camera(first=0, avoid=None, tries=6):
    """The first camera that actually gives a picture: `first`, then 0 to 5, through both of Windows' camera drivers.
    Returns (capture, index) or (None, None). Skips `avoid` (the desk camera) unless it's the only one."""
    import cv2
    backends = [cv2.CAP_DSHOW, cv2.CAP_MSMF] if IS_WIN else [0]
    order = [first] + [i for i in range(tries) if i != first]
    order = [i for i in order if i != avoid] + ([avoid] if avoid is not None and avoid in order else [])
    for i in order:
        for be in backends:
            cap = cv2.VideoCapture(i, be)
            if cap.isOpened():
                ok = False
                for _ in range(5):   # opened isn't enough: it has to deliver a frame
                    ok, _f = cap.read()
                    if ok:
                        break
                    time.sleep(0.1)
                if ok:
                    return cap, i
            cap.release()
    return None, None


def grab_frame(path, index=None):
    """One picture from the webcam, when the camera loop isn't running. Returns the path, or None."""
    try:
        import cv2
    except ImportError:
        return None
    cap, _ = open_camera(CAMERA_INDEX if index is None else index, avoid=desk_camera_index())
    if not cap:
        return None
    try:
        frame = None
        for _ in range(8):   # the first frames are often dark while the camera adjusts
            ok, f = cap.read()
            if ok:
                frame = f
            time.sleep(0.05)
        if frame is None:
            return None
        os.makedirs(os.path.dirname(path), exist_ok=True)
        cv2.imwrite(path, cv2.flip(frame, 1))
        return path
    finally:
        cap.release()


GESTURE_WORDS = [
    (r"rock(?: on| sign| and roll)?|(?:the )?horns|i love you(?: sign)?|spider ?man(?: sign)?", "rock"),
    (r"thumbs? down", "thumbs_down"), (r"thumbs? up", "thumbs_up"), (r"(?:a )?fist", "fist"),
    (r"peace(?: sign)?|(?:a )?v(?: sign)?|two fingers", "peace"), (r"(?:an )?open (?:palm|hand)|(?:a )?palm|high five", "palm"),
    (r"swipe left", "swipe_left"), (r"swipe right", "swipe_right"), (r"(?:a )?wave", "wave"),
    (r"point(?:ing)? up", "point_up"), (r"point(?:ing)? down", "point_down"),
    (r"(?:a )?wink", "wink"), (r"(?:a )?nod|nod my head", "nod"), (r"(?:a )?head shake|shake my head", "shake"),
    (r"raise my eyebrows|(?:raised? )?eyebrows|eyebrow raise", "brows"),
    (r"both (?:palms|hands)(?: up)?|two palms|hands up", "both_palms"),
    (r"(?:a )?push|push forward|(?:a )?press|tap the air|air tap", "push"),
    (r"three(?: fingers)?", "three"), (r"four(?: fingers)?", "four"),
    (r"(?:a )?circle(?: clockwise)?|clockwise(?: circle)?|draw a circle", "circle_cw"),
    (r"(?:a )?(?:counter ?clockwise|anti ?clockwise)(?: circle)?|(?:a )?circle (?:counter ?clockwise|backwards?)", "circle_ccw"),
]
_GW = "|".join(f"(?:{w})" for w, _ in GESTURE_WORDS)


def gesture_from_words(w):
    w = re.sub(r"^(?:a|an|the|my) ", "", w.strip())
    for pat, name in GESTURE_WORDS:
        if re.fullmatch(pat, w):
            return name
    return None


def route_gesture_map(t):
    """'when I do the rock sign, open Spotify', 'make thumbs down lock in for an hour', 'reset my gestures'."""
    m = re.fullmatch(rf"(?:when(?:ever)? i (?:do |make |show(?: you)? |throw(?: up)? |hold up |put )?|make |map |set |use )(?:a |an |the |my )?({_GW})"
                     rf"(?: gesture| sign)?(?: to| do| mean| should| it should| then| you should| for)*(?: do| be)? (.+)", t)
    if m:
        g = gesture_from_words(m.group(1))
        cmd = re.sub(r"^(?:do|be|go|it|you) ", "", m.group(2)).strip()
        if g and len(cmd) > 2:
            return ("gesture_map", (g, cmd))
    if re.fullmatch(r"(?:reset|clear|undo) (?:my |all (?:my )?|the )?(?:custom )?gestures|put (?:my |the )?gestures back(?: to normal)?", t):
        return ("gesture_map", (None, None))
    m = re.fullmatch(rf"(?:forget|remove|delete|reset) (?:the |my )?({_GW})(?: gesture| sign)?", t)
    if m and gesture_from_words(m.group(1)):
        return ("gesture_map", (gesture_from_words(m.group(1)), None))
    if re.fullmatch(r"what (?:do|are) my (?:custom )?gestures(?: do)?|(?:list|show) my (?:custom )?gestures", t):
        return ("gesture_map", ("?", None))
    return None


def route_vision(t):
    r = route_gesture_map(t)
    if r:
        return r
    import re
    m = re.fullmatch(r"(?:count|track) my (pushups?|push ups?|squats?|curls?)|(pushup|push up|squat|curl) (?:mode|counter|time)", t)
    if m:
        w = (m.group(1) or m.group(2)).replace(" ", "")
        ex = "pushups" if w.startswith("push") else "squats" if w.startswith("squat") else "curls"
        return ("reps", ex)
    if re.fullmatch(r"(?:i'?m )?done|stop counting|that'?s it|finished|(?:stop|end) (?:the )?(?:set|reps|counting)", t):
        return ("reps_stop", None)
    if re.fullmatch(r"(?:turn |switch |shut )?(?:the |your |my )?camera(?: mode)? off|(?:turn|switch|shut) off (?:the |your |my )?camera(?: mode)?|"
                    r"stop (?:watching|looking)(?: at me)?|(?:no|disable) camera|close (?:your|the) eyes?", t):
        return ("camera", False)
    if re.fullmatch(r"(?:turn |switch )?(?:the |your |my )?camera(?: mode)? (?:back )?on|(?:turn|switch) on (?:the |your |my )?camera(?: mode)?|"
                    r"start (?:watching|looking)|(?:enable|open) (?:the |your )?camera|open your eyes?|you can look again", t):
        return ("camera", True)
    t = re.sub(r"\s+(?:right now|now|at the moment|currently)$", "", t)
    if re.search(r"\bhow many fingers\b|\bwhat (?:color|colour) (?:is|are) (?:my|this|these|the thing)\b|\bwhat(?:'s| is| am i) (?:in my hands?|on my (?:head|shirt|face|desk))\b|"
                 r"\bdo i look\b|\bhow do i look\b|\bam i (?:wearing|holding|smiling)\b|\bwhat (?:am i|i'?m) (?:wearing|holding|pointing at|showing you)\b|"
                 r"\bwhat(?:'s| is) (?:this|that) (?:in my hand|i'?m holding)\b|\b(?:look|check) (?:at )?(?:this|what i'?m holding)\b|\bcan you see (?:this|my|what)\b|^(?:you )?see (?:this|that|my \w+)$|\bwatch (?:me|this)\b", t):
        return ("camera_look", t)
    if re.fullmatch(r"(?:can you )?see me|(?:do |can )?you see me|(?:can you )?see what (?:i'?m|i am) doing|(?:can you )?tell what (?:i'?m|i am) doing|what (?:am i|i'?m) doing|what do you see|what can you see|look at me|describe me|"
                    r"how do i look|what am i (?:holding|wearing|eating|drinking)|who(?:'s| is) (?:with me|behind me|in the room with me)|"
                    r"what(?:'s| is) (?:behind me|in my hand)|what(?:'s| is) this(?: thing)?(?: i'?m holding)?|check me out", t):
        return ("camera_look", t)
    if re.fullmatch(r"(?:turn |switch )?(?:off |stop )?(?:the )?(?:hand )?gestures?(?: off)?|(?:turn|switch) off (?:the )?(?:hand )?gestures|stop (?:the )?gestures|no more gestures", t) and "on" not in t.split():
        return ("gestures", False)
    if re.fullmatch(r"(?:turn |switch )?(?:the )?(?:hand )?gestures? on|(?:turn|switch) on (?:the )?(?:hand )?gestures", t):
        return ("gestures", True)
    if re.fullmatch(r"(?:focus|lock|zoom) (?:in )?on me|follow me|track me|(?:start )?(?:following|tracking) me|keep (?:your )?eyes on me", t):
        return ("vision_focus", True)
    if re.fullmatch(r"stop (?:focusing|following|tracking|zooming)(?: on)?(?: me)?|unfocus|zoom out", t):
        return ("vision_focus", False)
    if re.fullmatch(r"(?:what|which) gestures?(?: can i use| do you know| are there)?|show me (?:the )?gestures", t):
        return ("gestures_help", None)
    return None


GESTURE_HELP = ("Peace sign and I start listening. Open palm, play or pause. Swipe right or left for the next or last song. "
                "Point up or down for volume, or make an OK sign and move it up or down like a dial. Nod for yes, shake your head for no. Both palms up stops me. Thumbs up says yes, thumbs down says no. A fist mutes. Wave to wake the room. "
                "Say touch mode to control the whole screen with your hands.")


def preview():
    """A window showing what Jarvis sees: hand points, the zoom box it follows you with, both readings and why a
    gesture did or didn't count. Close Jarvis first (one app per camera). Press Q to quit."""
    import cv2
    det = Detectors(hands=True, faces=False)
    cap, idx = open_camera(CAMERA_INDEX)
    if cap is None:
        print("no camera found")
        return
    setup_capture(cap)
    grab = LatestFrame(cap)
    try:
        import jarvis_faces
        fid = jarvis_faces.FaceID()
    except Exception as e:
        fid = None
        print("faces off in preview:", e)
    v = Vision.__new__(Vision)
    v.reader, v.focus, v.roi = GestureReader(), None, None
    last, last_t, n, fps_t, fps = "", 0, 0, time.time(), 0.0
    while True:
        frame = grab.next(timeout=2.0)
        if frame is None:
            print("no camera frames")
            break
        frame = cv2.flip(frame, 1)
        H, W = frame.shape[:2]
        n += 1
        if fid and n % 6 == 0:
            fs = fid.faces(frame)
            if fs:
                f = max(fs, key=lambda f: f[2] * f[3])
                v.focus = (f[0] / W, f[1] / H, f[2] / W, f[3] / H, time.time())
        roi = v._zoom_roi()
        lm = det.hand(cv2.cvtColor(frame, cv2.COLOR_BGR2RGB), time.time() * 1000, roi)
        label = det.last_label
        g = v.reader.feed(lm, label if lm is not None else None)
        if g:
            last, last_t = g, time.time()
        if roi:
            cv2.rectangle(frame, (int(roi[0] * W), int(roi[1] * H)), (int(roi[2] * W), int(roi[3] * H)), (255, 200, 80), 2)
        if lm:
            for x, y in lm:
                cv2.circle(frame, (int(x * W), int(y * H)), max(3, W // 300), (60, 90, 255), -1)
        if time.time() - fps_t >= 1:
            fps = n / (time.time() - fps_t)
            fps_t, n = time.time(), 0
        s = W / 1280
        txt = [(f"model: {label or '-'}   finger math: {pose_name(lm) if lm else 'no hand'}", (80, 200, 255)),
               (v.reader.why, (255, 255, 255)),
               (f"{W}x{H}  {fps:.0f} fps  " + ("following you" if roi else "whole picture") + "   F = follow me, Q = quit", (200, 200, 200))]
        for k, (t, col) in enumerate(txt):
            cv2.putText(frame, t, (int(16 * s), int((34 + 34 * k) * s)), cv2.FONT_HERSHEY_SIMPLEX, 0.75 * s, col, max(1, int(2 * s)))
        if time.time() - last_t < 1.5:
            cv2.putText(frame, last.replace("_", " ").upper(), (int(16 * s), int(160 * s)), cv2.FONT_HERSHEY_SIMPLEX, 1.6 * s, (60, 90, 255), max(2, int(4 * s)))
        show = cv2.resize(frame, (1280, int(H * 1280 / W))) if W > 1280 else frame
        cv2.imshow("Jarvis vision (Q to quit)", show)
        key = cv2.waitKey(1) & 0xFF
        if key == ord("q"):
            break
        if key == ord("f"):   # same as saying "focus on me"
            v.zoom_on = not getattr(v, "zoom_on", ZOOM)
            v.roi = None
    cap.release()
    cv2.destroyAllWindows()


if __name__ == "__main__":
    # no arguments, or anything with "preview" in it (a stray key press can sneak in): open the preview
    if len(sys.argv) == 1 or any("preview" in a.lower() for a in sys.argv[1:]):
        preview()
    else:
        print(__doc__)
