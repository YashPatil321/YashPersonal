"""
Face recognition for Jarvis. OpenCV's YuNet finds faces, SFace tells them apart. Runs on your PC.
Only number fingerprints of faces are stored (in .cache/faces), never pictures.

  "learn my face"            looks at you for a few seconds and remembers you
  "this is mom" / "learn dad's face"   remembers someone else (they look at the camera)
  "who's here" / "who am I"  says who it sees
  "forget mom's face"        deletes that person

What it does with it:
  only you count as "at the desk", so the welcome back is for you, not your sister walking past
  says hi to people it knows by name
  someone it doesn't know shows up: guest mode on, nothing private out loud (AUTO_GUEST)
  someone sits at your PC while you're gone for a minute: the screen locks (AUTO_LOCK)
"""

import json
import os
import re
import time

HERE = os.path.dirname(os.path.abspath(__file__))

# ---------------- settings (override in local_settings.py) ----------------
FACES = True
OWNER = "yash"
# Both of these only ever act after you've said "learn my face". Until then Jarvis can't tell you from a stranger,
# so it does nothing (it used to lock you out of your own PC and switch on guest mode).
AUTO_GUEST = True            # someone it doesn't know in view, for 15 seconds, while you're there: guest mode until they leave
AUTO_LOCK = False            # off by default. True = lock the PC if a stranger is at it and you haven't been seen for LOCK_AFTER
LOCK_AFTER = 120
GUEST_AFTER = 15
MATCH = 0.40                 # cosine similarity to count as the same person (SFace's own cutoff is 0.363)
FACE_DIR = os.path.join(HERE, ".cache", "faces")
MODEL_URLS = {
    "detect": ["https://github.com/opencv/opencv_zoo/raw/main/models/face_detection_yunet/face_detection_yunet_2023mar.onnx",
               "https://huggingface.co/opencv/face_detection_yunet/resolve/main/face_detection_yunet_2023mar.onnx"],
    "recognize": ["https://github.com/opencv/opencv_zoo/raw/main/models/face_recognition_sface/face_recognition_sface_2021dec.onnx",
                  "https://huggingface.co/opencv/face_recognition_sface/resolve/main/face_recognition_sface_2021dec.onnx"],
}
MODEL_DIR = os.path.join(HERE, ".cache", "models")
# ---------------------------------------------------------------------------


def _log(msg):
    print(time.strftime("[%H:%M:%S] ") + "faces: " + str(msg), flush=True)


def model(name):
    os.makedirs(MODEL_DIR, exist_ok=True)
    fn = MODEL_URLS[name][0].rsplit("/", 1)[-1]
    path = os.path.join(MODEL_DIR, fn)
    if os.path.exists(path) and os.path.getsize(path) > 100000:
        return path
    import urllib.request
    for url in MODEL_URLS[name]:
        try:
            _log(f"downloading {fn}")
            urllib.request.urlretrieve(url, path + ".part")
            os.replace(path + ".part", path)
            return path
        except Exception as e:
            _log(f"download failed from {url.split('/')[2]}: {e}")
    raise RuntimeError(f"couldn't download {fn}")


class FaceBook:
    """Known people: name -> list of 128 number fingerprints."""
    def __init__(self, folder=None):
        self.folder = folder or FACE_DIR
        os.makedirs(self.folder, exist_ok=True)
        self.people = {}
        for fn in os.listdir(self.folder):
            if fn.endswith(".json"):
                try:
                    with open(os.path.join(self.folder, fn)) as f:
                        self.people[fn[:-5]] = json.load(f)
                except Exception:
                    pass

    def add(self, name, feats):
        name = clean_name(name)
        self.people[name] = (self.people.get(name, []) + [list(map(float, f)) for f in feats])[-40:]
        with open(os.path.join(self.folder, name + ".json"), "w") as f:
            json.dump(self.people[name], f)
        return name

    def forget(self, name):
        name = clean_name(name)
        if name in self.people:
            del self.people[name]
            try:
                os.remove(os.path.join(self.folder, name + ".json"))
            except OSError:
                pass
            return True
        return False

    def rename(self, old, new):
        old, new = clean_name(old), clean_name(new)
        if old not in self.people or old == new:
            return None
        self.people[new] = (self.people.get(new, []) + self.people.pop(old))[-40:]
        with open(os.path.join(self.folder, new + ".json"), "w") as f:
            json.dump(self.people[new], f)
        try:
            os.remove(os.path.join(self.folder, old + ".json"))
        except OSError:
            pass
        return new

    def best(self, feat):
        """(name, score) of the closest person, or (None, best_score)."""
        import numpy as np
        f = np.asarray(feat, dtype=np.float32).ravel()
        f = f / (np.linalg.norm(f) or 1)
        top, top_s = None, -1.0
        for name, feats in self.people.items():
            m = np.asarray(feats, dtype=np.float32)
            m = m / (np.linalg.norm(m, axis=1, keepdims=True) + 1e-9)
            s = float(np.max(m @ f))
            if s > top_s:
                top, top_s = name, s
        return (top, top_s) if top_s >= MATCH else (None, top_s)


def clean_name(name):
    name = re.sub(r"[^a-z0-9 ]", "", name.lower()).strip()
    name = re.sub(r"^(my |the )", "", name)
    return name.replace(" ", "_") or "someone"


def spoken_name(name):
    return name.replace("_", " ").title() if name else "someone"


class FaceID:
    """Finds and names faces in a BGR frame."""
    def __init__(self, book=None):
        import cv2
        self.cv2 = cv2
        self.det = cv2.FaceDetectorYN.create(model("detect"), "", (320, 320), 0.8, 0.3, 50)
        self.rec = cv2.FaceRecognizerSF.create(model("recognize"), "")
        self.book = book or FaceBook()

    def faces(self, bgr):
        h, w = bgr.shape[:2]
        self.det.setInputSize((w, h))
        _, found = self.det.detect(bgr)
        return [] if found is None else list(found)

    def feature(self, bgr, face):
        return self.rec.feature(self.rec.alignCrop(bgr, face)).ravel()

    def who(self, bgr):
        """[(name or None, score, size)] for every face, biggest first."""
        out = []
        for face in self.faces(bgr):
            name, score = self.book.best(self.feature(bgr, face))
            out.append((name, score, float(face[2] * face[3])))
        return sorted(out, key=lambda x: -x[2])

    def biggest_feature(self, bgr):
        fs = self.faces(bgr)
        if not fs:
            return None
        face = max(fs, key=lambda f: f[2] * f[3])
        return self.feature(bgr, face)


class Room:
    """Turns per frame sightings into steady arrivals and departures, then decides what Jarvis does."""
    def __init__(self, clock=time.time, keep=8.0):
        self.clock, self.keep = clock, keep
        self.seen = {}          # name ("?" for strangers) -> last time seen
        self.hits = {}          # name -> consecutive sightings
        self.present = set()
        self.stranger_since = None

    def feed(self, names):
        """names: list of names (None for unknown) seen in one check. Returns (arrived, left)."""
        now = self.clock()
        cur = {n or "?" for n in names}
        confirmed = set()
        for n in cur:
            self.hits[n] = self.hits.get(n, 0) + 1
            if self.hits[n] >= 2:   # two checks in a row, so one blurry frame doesn't count
                self.seen[n] = now
                confirmed.add(n)
        for n in list(self.hits):
            if n not in cur:
                self.hits[n] = 0
        arrived = confirmed - self.present
        left = {n for n in self.present if now - self.seen.get(n, 0) > self.keep}
        self.present = (self.present | arrived) - left
        if "?" in self.present or (self.present - {OWNER}):
            self.stranger_since = self.stranger_since or now
        else:
            self.stranger_since = None
        return arrived, left

    def owner_here(self):
        return OWNER in self.present

    def others(self):
        return {n for n in self.present if n != OWNER}

    owner_known = False   # set by the camera loop: has "learn my face" been done?

    def should_lock(self):
        """A stranger at the desk for LOCK_AFTER seconds while you haven't been seen. Never before you've enrolled."""
        if not (AUTO_LOCK and self.owner_known and self.stranger_since) or self.owner_here():
            return False
        gone = self.clock() - self.seen.get(OWNER, 0)
        return self.clock() - self.stranger_since >= LOCK_AFTER and gone >= LOCK_AFTER

    def guests(self):
        """People who should switch on guest mode: strangers in view for GUEST_AFTER seconds. Never before you've enrolled."""
        if not (AUTO_GUEST and self.owner_known and self.stranger_since):
            return False
        return self.clock() - self.stranger_since >= GUEST_AFTER


NOT_NAMES = set("""it that this me amazing cool sick crazy insane fire good bad great awesome wrong right fine perfect broken weird
funny hard easy so too really not the a what why how lit dope trash mid nice""".split())


def route_faces(t):
    if re.fullmatch(r"(?:(?:learn|remember|scan|save|memorize|know) (?:my|this|this is my) face|(?:remember )?(?:that )?this is (?:me|my face)|"
                    r"(?:it'?s|its) me|face id(?: setup)?|set up face id|(?:remember|learn) (?:what i look like|me))(?: please)?", t):
        return ("face_learn", OWNER)
    m = re.fullmatch(r"this is my (.+)|(?:meet|say hi to) (?:my )?(.+)|(?:learn|remember|scan) (?:my )?(.+?)'?s face|this is (\w+)", t)
    if m:
        name = next(g for g in m.groups() if g).strip()
        if len(name.split()) <= 3 and name not in NOT_NAMES and not (m.group(4) and name in NOT_NAMES):
            return ("face_learn", name)
    m = re.fullmatch(r"forget (?:my )?(.+?)'?s face|forget my face", t)
    if m:
        return ("face_forget", OWNER if t == "forget my face" else m.group(1))
    if re.fullmatch(r"who'?s here|who is here|who (?:do you see|is in the room|can you see)|who am i|do you know (?:who i am|me)", t):
        return ("face_who", None)
    if re.fullmatch(r"who (?:do you know|have you met)|list (?:the )?faces", t):
        return ("face_list", None)
    return None
