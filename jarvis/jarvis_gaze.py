"""
Atlas knows which screen you're looking at (from your head's direction, read by the webcam's face mesh).

  "calibrate my eyes"           look at the middle of each screen for 2 seconds when it says so (once)
  "follow my eyes"              the mouse jumps to the screen you turn to (and back to where it was on that screen)
  "stop following my eyes"
  "move this to where I'm looking" / "send spotify here"    windows go to the screen you're facing
  "which screen am I looking at"

It uses head direction, not the pupils: a webcam can tell which of 2 or 3 screens you face very reliably, but not
which word you're reading. Turning your head a little toward a screen is enough.
"""

import json
import math
import os
import re
import sys
import threading
import time

HERE = os.path.dirname(os.path.abspath(__file__))
FILE = os.path.join(HERE, ".cache", "gaze.json")
IS_WIN = sys.platform == "win32"
GAZE_HOLD = 0.7          # seconds you have to face a new screen before it counts (glances don't)


def _log(msg):
    print(time.strftime("[%H:%M:%S] ") + "gaze: " + str(msg), flush=True)


class Gaze:
    def __init__(self, head=lambda: None, screens=lambda: []):
        """head() -> (yaw, pitch, ...) or None, fresh from the face mesh. screens() -> monitors left to right."""
        self.head, self.screens = head, screens
        self.points = self._load()          # [[yaw, pitch]] per screen, left to right
        self.current, self.cand, self.cand_t = None, None, 0.0
        self.follow = False
        self.cursor_at = {}                 # screen -> where the mouse was last time you were on it
        self.on_change = None

    def _load(self):
        try:
            return json.load(open(FILE)).get("points", [])
        except Exception:
            return []

    def _save(self):
        os.makedirs(os.path.dirname(FILE), exist_ok=True)
        json.dump({"points": self.points, "when": time.strftime("%Y-%m-%d %H:%M")}, open(FILE, "w"))

    @property
    def ready(self):
        return len(self.points) >= 2

    def classify(self, yaw, pitch):
        """Nearest calibrated screen. Yaw counts more than pitch: screens sit side by side far more than stacked."""
        if not self.ready:
            return None
        d = [math.hypot(yaw - p[0], (pitch - p[1]) * 0.6) for p in self.points]
        i = min(range(len(d)), key=d.__getitem__)
        # too far off every screen (looking at your phone, the ceiling): no answer
        return i if d[i] < max(12.0, self._spread() * 0.9) else None

    def _spread(self):
        if len(self.points) < 2:
            return 20.0
        ys = sorted(p[0] for p in self.points)
        return min(b - a for a, b in zip(ys, ys[1:])) or 20.0

    def calibrate(self, say, wait=time.sleep):
        mons = self.screens()
        if len(mons) < 2:
            say("You've only got one screen, so there's nothing to tell apart.")
            return False
        pts = []
        for i, m in enumerate(mons):
            say(f"Look at the middle of {'the left' if i == 0 else 'the right' if i == len(mons) - 1 else 'the middle'} screen." if len(mons) <= 3
                else f"Look at screen {i + 1}.")
            wait(1.2)
            got, end = [], time.time() + 2.0
            while time.time() < end:
                h = self.head()
                if h:
                    got.append((h[0], h[1]))
                wait(0.07)
            if len(got) < 8:
                say("I couldn't see your face well. Sit in front of the webcam and try again.")
                return False
            got.sort()
            mid = got[len(got) // 4: len(got) * 3 // 4] or got   # drop the turning-in and turning-away frames
            pts.append([sum(g[0] for g in mid) / len(mid), sum(g[1] for g in mid) / len(mid)])
        if self._too_close(pts):
            say("Those screens looked the same from your head angle. Turn your head toward each one a bit more and try again.")
            return False
        self.points = pts
        self._save()
        say("Got it. I know which screen you're looking at now.")
        return True

    @staticmethod
    def _too_close(pts):
        return any(math.hypot(a[0] - b[0], a[1] - b[1]) < 6 for i, a in enumerate(pts) for b in pts[i + 1:])

    def watch(self):
        while True:
            time.sleep(0.1)
            try:
                h = self.head()
                if not h or not self.ready:
                    continue
                s = self.classify(h[0], h[1])
                now = time.time()
                if s is None or s == self.current:
                    self.cand = None
                    continue
                if s != self.cand:
                    self.cand, self.cand_t = s, now
                elif now - self.cand_t >= GAZE_HOLD:
                    prev, self.current, self.cand = self.current, s, None
                    if self.follow:
                        self._jump(prev, s)
                    if self.on_change:
                        self.on_change(prev, s)
            except Exception as e:
                _log(f"watch: {e}")
                time.sleep(1)

    def _jump(self, prev, to):
        """The mouse goes to the screen you turned to, back where you left it there."""
        if not IS_WIN:
            return
        import ctypes
        from ctypes import wintypes
        u = ctypes.windll.user32
        pt = wintypes.POINT()
        u.GetCursorPos(ctypes.byref(pt))
        mons = self.screens()
        if prev is not None:
            self.cursor_at[prev] = (pt.x, pt.y)
        if to >= len(mons):
            return
        x, y, w, h = mons[to][:4]
        if x <= pt.x < x + w and y <= pt.y < y + h:
            return   # already there
        tx, ty = self.cursor_at.get(to, (x + w // 2, y + h // 2))
        u.SetCursorPos(int(tx), int(ty))


def route_gaze(t):
    if re.fullmatch(r"(?:calibrate|set up|train) (?:my )?(?:eyes|gaze|eye tracking|head tracking|looking)", t):
        return ("gaze_cal", None)
    if re.fullmatch(r"(?:follow|track) my (?:eyes|gaze|head|look)|(?:turn on |start )?(?:eye|gaze) (?:follow|tracking|mouse)(?: on)?|mouse follows? my eyes", t):
        return ("gaze_follow", True)
    if re.fullmatch(r"(?:stop|don'?t) (?:following|follow|tracking|track) my (?:eyes|gaze|head)|(?:eye|gaze) (?:follow|tracking|mouse) off", t):
        return ("gaze_follow", False)
    if re.fullmatch(r"which (?:screen|monitor|display) am i (?:looking at|facing|on)|where am i looking", t):
        return ("gaze_which", None)
    return None
