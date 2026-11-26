"""
How Atlas hears you, and the little sounds that tell you what it's doing.

  Speech detection   a real voice detector (webrtcvad) on every 20 ms of audio, not just "is it loud". Fans, music and
                     keyboard clacks don't count as talking, so it stops recording when you stop, not when the room does.
                     Without webrtcvad it falls back to loudness.
  Room noise         keeps learning how loud your room is while Atlas sits idle, so turning on a fan or opening a
                     window doesn't break it. The old version measured once at startup.
  Endpointing        stops faster after a full sentence (0.7 s pause), waits longer if you've only said a word or two
                     (you're probably still thinking), and keeps a bit of audio from before you started so the first
                     word isn't clipped.
  Cues               listening   two soft rising notes
                     got it      one soft low note when it stops recording
                     didn't hear a quick falling pair (it woke up but you said nothing)
                     dictation   three rising notes ("take a note")
                     error       a falling slide before it tells you something broke
"""

import collections
import time

import numpy as np

RATE = 16000


def _log(msg):
    print(time.strftime("[%H:%M:%S] ") + "listen: " + str(msg), flush=True)


# ---------------- room noise that keeps up with the room ----------------
class NoiseFloor:
    """Rolling estimate of the room's background level. float(noise) gives the current value."""
    def __init__(self, start=300.0, keep=400):
        self.hist = collections.deque(maxlen=keep)   # about 30 s of 80 ms frames
        self.value = float(start)

    def feed(self, frame):
        rms = float(np.sqrt(np.mean(frame.astype(np.float32) ** 2)))
        self.hist.append(rms)
        if len(self.hist) >= 25 and len(self.hist) % 25 == 0:
            # the 30th percentile: background, not the moments someone talks
            self.value = max(30.0, float(np.percentile(self.hist, 30)))
        return rms

    def __float__(self):
        return self.value

    def __mul__(self, k):
        return self.value * k

    __rmul__ = __mul__

    def __format__(self, spec):
        return format(self.value, spec)


# ---------------- is this speech? ----------------
class VoiceDetector:
    def __init__(self, aggressiveness=3):
        self.vad = None
        try:
            import webrtcvad
            self.vad = webrtcvad.Vad(aggressiveness)
        except Exception:
            pass

    def speech(self, frame, threshold):
        """True if this frame (int16, 16 kHz) has a voice in it. Loudness has to pass too, so far off TV doesn't count."""
        rms = float(np.sqrt(np.mean(frame.astype(np.float32) ** 2)))
        if rms < threshold * 0.6:
            return False
        if self.vad is None:
            return rms > threshold
        raw = frame.astype(np.int16).tobytes()
        step = 320 * 2   # 20 ms
        parts = [raw[i:i + step] for i in range(0, len(raw) - step + 1, step)]
        if not parts:
            return rms > threshold
        hits = 0
        for p in parts:
            try:
                hits += self.vad.is_speech(p, RATE)
            except Exception:
                return rms > threshold
        return hits * 2 >= len(parts)


class Endpointer:
    """Decides when you've finished talking."""
    def __init__(self, noise, vad=None, silence=None, frame_secs=0.08):
        self.threshold = max(float(noise) * 2.5, 250.0)
        self.vad = vad or VoiceDetector()
        self.silence = silence          # fixed pause if given (dictation), otherwise smart
        self.dt = frame_secs
        self.voiced, self.quiet, self.heard, self.run = 0.0, 0.0, False, 0

    def pause_needed(self):
        if self.silence:
            return self.silence
        if self.voiced < 0.6:
            return 1.3    # one word so far: you're probably still going
        if self.voiced < 2.0:
            return 0.9
        return 0.7

    def feed(self, frame):
        """Returns 'wait' (nothing yet), 'talking', or 'done'."""
        if self.vad.speech(frame, self.threshold):
            self.run += 1
            if not self.heard and self.run < 2:
                return "wait"   # one blip (a cough, a door) isn't you starting to talk
            self.heard = True
            self.voiced += self.dt
            self.quiet = 0.0
            return "talking"
        self.run = 0
        if not self.heard:
            return "wait"
        self.quiet += self.dt
        return "done" if self.quiet >= self.pause_needed() else "talking"


def record(get_frame, noise, silence=None, max_secs=30, wait_for_voice=5, pre=None, vad=None, clock=time.time):
    """Records until you stop talking. get_frame() blocks for the next mic frame. Returns float32 audio or None."""
    ep = Endpointer(noise, vad=vad, silence=silence)
    chunks = list(pre or [])
    start = clock()
    lead = collections.deque(maxlen=4)   # 320 ms before your first word, so it isn't clipped
    while clock() - start < max_secs:
        f = get_frame()
        state = ep.feed(f)
        if state == "wait":
            lead.append(f)
            if clock() - start > wait_for_voice:
                return None
            continue
        if lead:
            chunks.extend(lead)
            lead.clear()
        chunks.append(f)
        if state == "done":
            # trim most of the trailing silence, keep a little so the last word isn't cut
            keep = max(1, int(ep.quiet / ep.dt) - 3)
            chunks = chunks[:-keep] if len(chunks) > keep else chunks
            break
    if not ep.heard:
        return None
    return np.concatenate(chunks).astype(np.float32) / 32768.0


# ---------------- cues ----------------
SR = 24000


def _tone(freqs, dur, vol=0.16, glide=None):
    t = np.linspace(0, dur, int(SR * dur), False)
    if glide:
        f = np.linspace(glide[0], glide[1], t.size)
        phase = 2 * np.pi * np.cumsum(f) / SR
        w = np.sin(phase)
    else:
        w = sum(np.sin(2 * np.pi * f * t) * (0.6 ** i) for i, f in enumerate(freqs))
    env = np.minimum(1.0, t / 0.008) * np.exp(-t * (4.0 / dur))
    return (vol * w * env).astype(np.float32)


def _gap(secs):
    return np.zeros(int(SR * secs), np.float32)


def cue(kind):
    """Short sounds, all under 0.2 s so they never talk over you."""
    if kind == "listen":
        return np.concatenate([_tone([784, 1568], 0.05), _gap(0.01), _tone([1175, 2350], 0.07)])
    if kind == "heard":
        return _tone([523, 1046], 0.09, vol=0.11)
    if kind == "nothing":
        return np.concatenate([_tone([880], 0.06, vol=0.1), _gap(0.01), _tone([659], 0.08, vol=0.1)])
    if kind == "done":
        return _tone([1760], 0.035, vol=0.09)
    if kind == "long":
        return np.concatenate([_tone([659], 0.07), _gap(0.015), _tone([988], 0.07), _gap(0.015), _tone([1319], 0.09)])
    if kind == "error":
        return _tone([], 0.18, vol=0.12, glide=(660, 330))
    return _tone([880], 0.1)


def hotwords(*vocab):
    """Names Whisper should lean toward, for faster-whisper's hotwords option."""
    words = []
    for v in vocab:
        for w in (v or "").replace(";", ",").split(","):
            w = w.strip()
            if w and w.lower() not in (x.lower() for x in words):
                words.append(w)
    return " ".join(words[:60])
