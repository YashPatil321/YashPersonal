"""
What Yash is doing, live. Every 10 seconds: the app and window in front, whether he's at the keyboard,
what's playing, and whether the camera sees him. Kept as a timeline (last few hours, in memory only).

Every question Jarvis sends to Claude carries a short "right now" line from this, so Jarvis just knows:
  "Right now: in VS Code on jarvis.py for 14 min. Before that YouTube 6 min. Spotify: Travis Scott, FE!N.
   At the desk (camera sees him)."

Voice: "what have I been doing", "how long have I been on this", "what was I doing before this".
"""

import re
import threading
import time
from collections import deque

SAMPLE_SECONDS = 10
KEEP_HOURS = 6


def _log(msg):
    print(time.strftime("[%H:%M:%S] ") + "activity: " + str(msg), flush=True)


def mins(secs):
    m = int(round(secs / 60))
    if m < 1:
        return "under a minute"
    if m < 60:
        return f"{m} min"
    h, m = divmod(m, 60)
    return f"{h} hr" + (f" {m} min" if m else "")


def short_title(app, title):
    """The useful bit of a window title: 'jarvis.py' from 'jarvis.py - YashPersonal - Visual Studio Code'."""
    t = re.sub(r"\s+[-|·]\s+(Google Chrome|Microsoft Edge|Visual Studio Code|Brave|Notepad|Discord|Spotify.*|Obsidian.*)$", "", title or "")
    t = re.sub(r"^\(\d+\)\s*", "", t)   # "(3) Inbox" -> "Inbox"
    if app and t.lower().endswith(" - " + app.lower()):
        t = t[: -len(app) - 3]
    return t.strip()[:70]


class Activity:
    def __init__(self, sample=None, clock=time.time, music=None, at_desk=None, idle=None):
        """sample() -> (exe, title). music() -> song or ''. at_desk() -> True/False/None. idle() -> seconds."""
        self.sample, self.clock, self.music, self.at_desk, self.idle = sample, clock, music, at_desk, idle
        self.segments = deque()   # dicts: app, title, start, end
        self.song, self.song_t = "", 0.0
        self.lock = threading.Lock()

    def record(self, app, title, now=None):
        now = self.clock() if now is None else now
        with self.lock:
            seg = self.segments[-1] if self.segments else None
            if seg and seg["app"] == app and seg["title"] == title and now - seg["end"] < SAMPLE_SECONDS * 3:
                seg["end"] = now
            else:
                self.segments.append({"app": app, "title": title, "start": now, "end": now})
            while self.segments and now - self.segments[0]["end"] > KEEP_HOURS * 3600:
                self.segments.popleft()

    def tick(self):
        if self.idle and self.idle() > 300:
            return   # away from the keyboard
        exe, title = self.sample() if self.sample else ("", "")
        import jarvis_extras
        app = jarvis_extras.app_label(exe, title) if exe else ""
        if app:
            self.record(app, short_title(app, title))
        if self.music and self.clock() - self.song_t > 30:
            try:
                self.song = self.music() or ""
            except Exception:
                self.song = ""
            self.song_t = self.clock()

    def loop(self):
        while True:
            try:
                self.tick()
            except Exception as e:
                _log(e)
            time.sleep(SAMPLE_SECONDS)

    def start(self):
        threading.Thread(target=self.loop, daemon=True).start()
        return self

    # ---- reading it back ----
    def current(self):
        """The app he's in now and for how long (same app, any title)."""
        with self.lock:
            if not self.segments:
                return None
            last = self.segments[-1]
            if self.clock() - last["end"] > SAMPLE_SECONDS * 6:
                return None
            start = last["start"]
            for seg in reversed(list(self.segments)[:-1]):
                if seg["app"] != last["app"] or start - seg["end"] > SAMPLE_SECONDS * 6:
                    break
                start = seg["start"]
            return {"app": last["app"], "title": last["title"], "secs": self.clock() - start}

    def totals(self, minutes=60):
        cut = self.clock() - minutes * 60
        out = {}
        with self.lock:
            for seg in self.segments:
                if seg["end"] < cut:
                    continue
                out[seg["app"]] = out.get(seg["app"], 0) + max(SAMPLE_SECONDS, seg["end"] - max(seg["start"], cut))
        return sorted(out.items(), key=lambda kv: -kv[1])

    def before(self):
        """The app he was in before the current one."""
        cur = self.current()
        if not cur:
            return None
        with self.lock:
            for seg in reversed(self.segments):
                if seg["app"] != cur["app"]:
                    return seg
        return None

    def context(self):
        """One line for Claude: what he's doing right now."""
        bits = []
        cur = self.current()
        if cur:
            bits.append(f"in {cur['app']}" + (f" on '{cur['title']}'" if cur["title"] else "") + f" for {mins(cur['secs'])}")
            prev = self.before()
            if prev:
                bits.append(f"before that {prev['app']}" + (f" ('{prev['title']}')" if prev["title"] else ""))
        elif self.idle and self.idle() > 300:
            bits.append(f"away from the keyboard for {mins(self.idle())}")
        if self.song:
            bits.append(f"music playing: {self.song}")
        desk = self.at_desk() if self.at_desk else None
        if desk is True:
            bits.append("the camera sees him at the desk")
        elif desk is False:
            bits.append("the camera doesn't see him at the desk")
        top = [f"{a} {mins(s)}" for a, s in self.totals(60)[:4]]
        if top:
            bits.append("last hour: " + ", ".join(top))
        return ("Right now he is " + "; ".join(bits) + ".") if bits else ""

    def spoken(self, minutes=60):
        cur = self.current()
        top = [(a, s) for a, s in self.totals(minutes) if s >= 60][:4]
        if not cur and not top:
            return "I haven't seen you on the computer in a while."
        out = []
        if cur:
            out.append(f"You're in {cur['app']}" + (f", on {cur['title']}" if cur["title"] else "") + f", for {mins(cur['secs'])}.")
        if top:
            out.append(f"In the last {'hour' if minutes == 60 else mins(minutes * 60)}: " + ", ".join(f"{a} {mins(s)}" for a, s in top) + ".")
        return " ".join(out)


def route_activity(t):
    if re.fullmatch(r"what (?:have i been|was i) doing(?: (?:today|this (?:morning|afternoon|evening)|for the last hour|lately))?|"
                    r"what(?:'s| is) my (?:activity|day been like on the computer)|how long have i been (?:on|in|doing) (?:this|here|it)|"
                    r"what was i doing before (?:this|that)", t):
        return ("activity", t)
    return None
