"""
Several things at once.

  Many commands in one breath   "open Spotify, play Drake and set a timer for 10 minutes" runs all three. Quick
                                commands run right away, one after the other; whatever's left goes to Claude as one
                                request. "Play rock and roll" stays one command (a split only counts when every
                                piece makes sense on its own).
  Background jobs               bigger asks ("research the best laptops under 1000", "draft an email to coach about
                                Saturday", "clean up my downloads folder") run in the background. Atlas says "on it"
                                and keeps listening, so you can ask for more. When a job finishes it tells you, without
                                talking over you. Several can run at the same time.
  "what are you working on"     the jobs still running.   "forget that job" / "never mind that"   drops the newest one.
"""

import re
import threading
import time

BACKGROUND = True            # big asks run in the background while Atlas keeps listening
MAX_JOBS = 4                 # at the same time

SEP = re.compile(r"\s*(?:,\s*(?:and\s+then|and|then|also)?|;|\band then\b|\bthen\b|\band also\b|\balso\b|\band\b)\s+", re.I)
TASK = re.compile(r"^(?:can you |could you |please |go |i need you to |i want you to )*"
                  r"(?:write|draft|research|find out|look into|dig into|make|create|build|fix|organize|plan|summarize|"
                  r"compare|analy[sz]e|go through|clean up|prepare|generate|figure out|put together|work out|review|"
                  r"read through|check all|update my|rewrite|translate|edit|outline|brainstorm|come up with)\b", re.I)
BACKGROUND_ASK = re.compile(r"\b(?:in the background|while i(?:'m| am)?\b|when you get a chance|take your time|no rush)\b", re.I)


def split_commands(text, route, min_free_words=3):
    """[(piece, command or None)] when the sentence holds more than one request, else None.
    route(piece) returns the local command for a piece, or None when it needs Claude."""
    t = text.strip().rstrip(".!?")
    pieces = [p.strip(" ,.") for p in SEP.split(t) if p and p.strip(" ,.")]
    if len(pieces) < 2:
        return None
    # glue a short piece that isn't a command onto the one before ("play rock" + "roll", "text mom" + "dad")
    merged = []
    for p in pieces:
        cmd = route(p)
        if merged and cmd is None and len(p.split()) < min_free_words:
            prev = merged.pop()
            joined = prev[0] + " and " + p
            merged.append((joined, route(joined)))
            continue
        merged.append((p, cmd))
    if len(merged) < 2:
        return None
    if not any(c for _, c in merged):
        return None   # nothing quick in there: Claude takes the whole sentence (it can do several things itself)
    # consecutive pieces for Claude go together as one request
    out = []
    for p, c in merged:
        if c is None and out and out[-1][1] is None:
            out[-1] = (out[-1][0] + " and " + p, None)
        else:
            out.append((p, c))
    return out if len(out) >= 2 else None


def is_task(text):
    """A bigger job worth doing in the background, not a quick question."""
    t = text.strip()
    if BACKGROUND_ASK.search(t):
        return True
    return bool(TASK.search(t)) and len(t.split()) >= 5


def short(text, n=8):
    w = re.sub(r"^(?:can you |could you |please )+", "", text.strip(), flags=re.I).split()
    return " ".join(w[:n]) + ("..." if len(w) > n else "")


class Jobs:
    """Background jobs, and the one voice that reports them when it's a good moment."""
    def __init__(self, say, can_talk, lock=None, log=print):
        self.say, self.can_talk, self.lock, self.log = say, can_talk, lock, log
        self.running = []          # [{"text", "t", "dropped"}]
        self.done = []             # finished, waiting for a moment to be told
        self.m = threading.Lock()
        threading.Thread(target=self._announcer, daemon=True).start()

    def start(self, text, work):
        """work() returns what to say when it's finished."""
        with self.m:
            if len([j for j in self.running if not j["dropped"]]) >= MAX_JOBS:
                return False
            job = {"text": text, "t": time.time(), "dropped": False}
            self.running.append(job)

        def go():
            try:
                result = work()
            except Exception as e:
                result = f"That one failed: {e}"
            with self.m:
                if job in self.running:
                    self.running.remove(job)
                if not job["dropped"]:
                    self.done.append((job, result))
            self.log(f"job done: {short(text)}")
        threading.Thread(target=go, daemon=True).start()
        return True

    def drop_newest(self):
        with self.m:
            live = [j for j in self.running if not j["dropped"]]
            if not live:
                return None
            live[-1]["dropped"] = True
            return live[-1]["text"]

    def status(self):
        with self.m:
            live = [j for j in self.running if not j["dropped"]]
        if not live:
            return "Nothing running in the background."
        return "Working on: " + "; ".join(f"{short(j['text'])}, {int(time.time() - j['t'])} seconds in" for j in live) + "."

    def _announcer(self):
        while True:
            time.sleep(0.5)
            with self.m:
                if not self.done:
                    continue
            if not self.can_talk():
                continue
            got = self.lock.acquire(timeout=0.2) if self.lock else True
            if not got:
                continue
            try:
                with self.m:
                    if not self.done:
                        continue
                    job, result = self.done.pop(0)
                many = len(self.running) + len(self.done)
                self.say(f"Done with {short(job['text'], 6)}. " + (result or "Finished.") +
                         (f" {many} more still going." if many else ""))
            finally:
                if self.lock:
                    self.lock.release()


def route_jobs(t):
    if re.fullmatch(r"what are you (?:working on|doing)(?: right now| in the background)?|(?:any|what) (?:background )?jobs(?: running)?|"
                    r"are you (?:still )?working on (?:anything|something)|how'?s (?:it|that) (?:coming|going)", t):
        return ("jobs_status", None)
    if re.fullmatch(r"(?:forget|drop|cancel|scrap|never ?mind) (?:that|the last|your last|that last) (?:job|task|one)?|never ?mind that", t):
        return ("jobs_drop", None)
    return None
