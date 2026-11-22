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
CAMERA_SIZE = (640, 360)
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

    def feed(self, lm):
        now = self.clock()
        self.why = "no hand" if lm is None else ""
        if lm is not None and _d(lm[INDEX_MCP], lm[PINKY_MCP]) < MIN_HAND:
            self.why, lm = "hand too far from the camera", None
        elif lm is not None and lm[WRIST][1] > MAX_WRIST_Y:
            self.why, lm = "hand too low, raise it", None
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
            return None
        name = pose_name(lm)
        self.why = "reading: " + (name or "no clear shape")
        cx = sum(lm[i][0] for i in (WRIST, INDEX_MCP, PINKY_MCP)) / 3

        if name == "palm":
            self.track.append((now, cx))
            while self.track and now - self.track[0][0] > 1.6:
                self.track.popleft()
            motion = self._motion(now)
            if motion and now - self.last_fire > self.cooldown:
                self.last_fire, self.fired_cur, self.since = now, True, now
                self.track.clear()
                return motion
        else:
            self.track.clear()

        if name != self.cur:
            self.cur, self.since, self.fired_cur = name, now, False
            return None
        if name is None or now - self.since < self.hold:
            return None
        if name == "palm" and self._moving():
            return None
        if self.fired_cur and name not in self.REPEATS:
            return None
        gap = 0.45 if name in self.REPEATS else self.cooldown
        if now - self.last_fire < gap:
            return None
        self.last_fire, self.fired_cur = now, True
        return name

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
        if turns >= 3 and max(xs) - min(xs) > 0.12:
            return "wave"
        recent = [(t, x) for t, x in pts if now - t <= 0.5]
        if len(recent) >= 3:
            dx = recent[-1][1] - recent[0][1]
            if abs(dx) > 0.30 and turns <= 1:
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
    "face": "https://storage.googleapis.com/mediapipe-models/face_detector/blaze_face_short_range/float16/latest/blaze_face_short_range.tflite",
    "pose": "https://storage.googleapis.com/mediapipe-models/pose_landmarker/pose_landmarker_lite/float16/latest/pose_landmarker_lite.task",
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
        self.hands = vision.HandLandmarker.create_from_options(vision.HandLandmarkerOptions(
            base_options=BaseOptions(model_asset_path=model_path("hand")), running_mode=V, num_hands=2,
            min_hand_detection_confidence=0.6, min_hand_presence_confidence=0.6, min_tracking_confidence=0.6)) if hands else None
        self.faces = vision.FaceDetector.create_from_options(vision.FaceDetectorOptions(
            base_options=BaseOptions(model_asset_path=model_path("face")), running_mode=V, min_detection_confidence=0.5)) if faces else None
        self.pose = None
        self.last_ts = 0

    def _img(self, rgb):
        return self.mp.Image(image_format=self.mp.ImageFormat.SRGB, data=rgb)

    def _ts(self, ts):
        self.last_ts = max(int(ts), self.last_ts + 1)   # VIDEO mode needs strictly rising timestamps
        return self.last_ts

    def hands_all(self, rgb, ts):
        r = self.hands.detect_for_video(self._img(rgb), self._ts(ts))
        return [[(p.x, p.y) for p in h] for h in r.hand_landmarks]

    def hand(self, rgb, ts):
        hs = self.hands_all(rgb, ts)
        return max(hs, key=lambda h: _d(h[INDEX_MCP], h[PINKY_MCP])) if hs else None

    def face(self, rgb, ts):
        return bool(self.faces.detect_for_video(self._img(rgb), self._ts(ts)).detections)

    def body(self, rgb, ts):
        if not self.pose:
            v = self.vision
            self.pose = v.PoseLandmarker.create_from_options(v.PoseLandmarkerOptions(
                base_options=self.Base(model_asset_path=model_path("pose")), running_mode=v.RunningMode.VIDEO))
        r = self.pose.detect_for_video(self._img(rgb), self._ts(ts))
        return [(p.x, p.y) for p in r.pose_landmarks[0]] if r.pose_landmarks else None


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
        cap.set(cv2.CAP_PROP_FRAME_WIDTH, CAMERA_SIZE[0])
        cap.set(cv2.CAP_PROP_FRAME_HEIGHT, CAMERA_SIZE[1])
        try:
            import jarvis_faces
            if jarvis_faces.FACES:
                self.faceid, self.room = jarvis_faces.FaceID(), jarvis_faces.Room()
                _log(f"face id on, knows: {', '.join(self.faceid.book.people) or 'nobody yet, say learn my face'}")
        except Exception as e:
            _log(f"face id off: {e}")
        self.ok = True
        _log("camera on")
        n, face_seen, pinch_was = 0, False, False
        while True:
            if not self.enabled:
                time.sleep(0.5)
                continue
            good, frame = cap.read()
            if not good:
                time.sleep(0.2)
                continue
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
                if self.faceid and n % 12 == 0:   # who's here, about once a second
                    self._faces_step(frame)
                elif det.faces and not self.faceid and n % 10 == 0:   # faces about twice a second is plenty
                    seen = det.face(rgb, ts)
                    if seen:
                        self.last_face = time.time()
                    if seen != face_seen:
                        face_seen = seen
                        if self.on_face:
                            self.on_face(seen)
                if not det.hands:
                    continue
                if self.cad and self.cad.active:
                    self.cad.set_hands(det.hands_all(rgb, ts))
                    continue
                if self.touch:
                    ctl, exe = self.touch
                    exe.run(ctl.feed(det.hands_all(rgb, ts)))
                    continue
                lm = det.hand(rgb, ts)
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
            g = self.reader.feed(lm)
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
            if f is not None:
                feats.append(f)
        if time.time() >= until or len(feats) >= 20:
            self.enroll = None
            saved = self.faceid.book.add(name, feats[2:] if len(feats) > 5 else feats) if self.faceid and feats else None
            done(saved, len(feats))

    def _faces_step(self, frame):
        import jarvis_faces
        found = self.faceid.who(frame)
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


def route_vision(t):
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
    if re.fullmatch(r"(?:what|which) gestures?(?: can i use| do you know| are there)?|show me (?:the )?gestures", t):
        return ("gestures_help", None)
    return None


GESTURE_HELP = ("Peace sign and I start listening. Open palm, play or pause. Swipe right or left for the next or last song. "
                "Point up or down for volume. Thumbs up says yes. A fist mutes. Wave to wake the room. "
                "Say touch mode to control the whole screen with your hands.")


def preview():
    """A window showing the camera, the hand points and the gesture it reads. Press Q to quit."""
    import cv2
    det = Detectors(hands=True, faces=False)
    cap, idx = open_camera(CAMERA_INDEX)
    if cap is None:
        print("no camera found")
        return
    print(f"camera {idx}")
    reader, last, last_t = GestureReader(), "", 0
    while True:
        good, frame = cap.read()
        if not good:
            print("no camera frames")
            break
        frame = cv2.flip(frame, 1)
        lm = det.hand(cv2.cvtColor(frame, cv2.COLOR_BGR2RGB), time.time() * 1000)
        if lm:
            h, w = frame.shape[:2]
            for x, y in lm:
                cv2.circle(frame, (int(x * w), int(y * h)), 4, (60, 90, 255), -1)
        g = reader.feed(lm)
        if g:
            last, last_t = g, time.time()
        cv2.putText(frame, f"shape: {pose_name(lm) if lm else 'no hand'}", (16, 32), cv2.FONT_HERSHEY_SIMPLEX, 0.8, (80, 200, 255), 2)
        cv2.putText(frame, reader.why, (16, 110), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (255, 255, 255), 2)
        if lm:
            cv2.putText(frame, f"palm {_d(lm[INDEX_MCP], lm[PINKY_MCP]):.3f} (needs {MIN_HAND})  wrist {lm[WRIST][1]:.2f} (needs under {MAX_WRIST_Y})",
                        (16, 140), cv2.FONT_HERSHEY_SIMPLEX, 0.55, (200, 200, 200), 1)
        if time.time() - last_t < 1.5:
            cv2.putText(frame, f"GESTURE: {last}", (16, 70), cv2.FONT_HERSHEY_SIMPLEX, 1.0, (60, 90, 255), 3)
        cv2.imshow("Jarvis vision (Q to quit)", frame)
        if cv2.waitKey(1) & 0xFF == ord("q"):
            break
    cap.release()
    cv2.destroyAllWindows()


if __name__ == "__main__":
    if "--preview" in sys.argv:
        preview()
    else:
        print(__doc__)
