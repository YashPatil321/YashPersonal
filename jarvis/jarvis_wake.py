"""
Wake on a name without a trained wake word model. Atlas listens for speech, and when a short burst of it starts,
the speech model (already loaded for everything else) checks whether it begins with the name. "Atlas" alone gets
the chime; "Atlas, what's my day look like" in one breath just works.

The built in "hey jarvis" wake word keeps working next to it.
"""

import re
import threading
import time

import numpy as np

RATE, FRAME = 16000, 1280
EARLY_CHECK = 1.4        # seconds of speech before the first "was that my name" check
MAX_SEGMENT = 12.0       # longest stretch of speech it holds on to
END_SILENCE = 0.55       # this much quiet ends a stretch of speech
# how Whisper tends to hear the name
SPELLINGS = {"atlas": r"atlas|at last|atless|atlus|atlis|addless|adless|at lest|outlast|atlases"}


def name_pattern(name):
    alts = SPELLINGS.get(name.lower(), re.escape(name.lower()))
    return re.compile(rf"^(?:(?:hey|hi|yo|ok|okay|so|um|uh)\s+)?(?:{alts})\b[\s,.!?]*(.*)$", re.S)


class PhraseSpotter:
    """feed() every microphone frame. poll() returns (audio_so_far, finished, rest_of_sentence) once the name is heard."""
    def __init__(self, transcribe, name="atlas", noise=300.0, clock=time.time):
        self.transcribe, self.pat, self.clock = transcribe, name_pattern(name), clock
        self.threshold = max(noise * 3.0, 300.0)
        self.pre = []                       # a little audio from before the speech started
        self.seg, self.quiet, self.speaking = [], 0.0, False
        self.checked_early = False
        self.hit = None
        self.busy = False
        self.lock = threading.Lock()
        self.enabled = True

    def reset(self):
        with self.lock:
            self.seg, self.quiet, self.speaking, self.checked_early, self.hit, self.pre = [], 0.0, False, False, None, []

    def feed(self, frame):
        if not self.enabled:
            return
        loud = float(np.sqrt(np.mean(frame.astype(np.float32) ** 2))) > self.threshold
        with self.lock:
            if not self.speaking:
                self.pre = (self.pre + [frame])[-4:]
                if loud:
                    self.speaking, self.seg, self.quiet, self.checked_early = True, list(self.pre), 0.0, False
                return
            self.seg.append(frame)
            self.quiet = 0.0 if loud else self.quiet + FRAME / RATE
            secs = len(self.seg) * FRAME / RATE
            if not self.checked_early and secs >= EARLY_CHECK:
                self.checked_early = True
                self._check(list(self.seg), finished=False)
            if self.quiet >= END_SILENCE or secs >= MAX_SEGMENT:
                seg, early = self.seg, self.checked_early
                self.speaking, self.seg, self.pre = False, [], []
                if self.hit is not None and not self.hit[1]:
                    # heard the name early on and the sentence has now ended: hand over all of it
                    self.hit = (np.concatenate(seg).astype(np.float32) / 32768.0, True, self.hit[2], self.hit[3])
                elif self.hit is None and secs - self.quiet >= 0.25:
                    self._check(seg, finished=True)

    def _check(self, frames, finished):
        """Runs the speech model on a background thread so listening never stalls."""
        if self.busy and not finished:
            return
        self.busy = True
        audio = np.concatenate(frames).astype(np.float32) / 32768.0

        def work():
            try:
                text = (self.transcribe(audio[: int(RATE * 3.0)]) or "").strip().lower()
                m = self.pat.match(re.sub(r"^[^a-z]+", "", text))
                if m:
                    with self.lock:
                        if self.hit is None:
                            self.hit = (audio, finished, m.group(1).strip(" ,.!?"), self.clock())
            finally:
                self.busy = False
        threading.Thread(target=work, daemon=True).start()

    def poll(self):
        """(audio, finished, rest) once, right after the name is heard; else None. While the sentence is still going,
        the frames that arrive after the check are added on, so the caller keeps recording from there."""
        with self.lock:
            if self.hit is None:
                return None
            audio, finished, rest, _ = self.hit
            if not finished and self.speaking and self.seg:
                more = np.concatenate(self.seg).astype(np.float32) / 32768.0
                audio = more if len(more) > len(audio) else audio
            still_talking = self.speaking
            self.hit, self.seg, self.speaking, self.pre = None, [], False, []
            return audio, (finished and not still_talking), rest


def strip_name(text, name="atlas"):
    """'Atlas, what's my day look like' -> 'what's my day look like'."""
    m = name_pattern(name).match(re.sub(r"^[^A-Za-z]+", "", text or "").lower())
    if not m:
        return text
    rest = m.group(1)
    return text[len(text) - len(rest):].strip(" ,.!?") if rest else ""
