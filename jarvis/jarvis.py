"""
Jarvis: say the wake word (or clap twice), ask out loud, hear the answer.

  1. openWakeWord listens on your mic for "hey jarvis" (local, tiny CPU cost)
  2. records you until you stop talking
  3. faster-whisper turns it into text on your GPU
  4. quick commands (music, volume, apps, sites, lock) run instantly from a safe allow list
  5. everything else goes to Claude Code (your Max plan, one ongoing conversation)
  6. Kokoro reads the answer out loud

Clap twice: wakes the monitor, opens HQ, says hi, and before noon reads a short morning brief.

Modes:
  python jarvis.py              run
  python jarvis.py --doctor     check GPU, whisper, mic, speakers, Claude, connectors
  python jarvis.py --devices    list audio devices (the ones Jarvis picks are marked)
  python jarvis.py --levels     live mic meter for tuning claps and the wake word
  python jarvis.py --say "hi"   test the voice
  python jarvis.py --ask "what's my day look like"   test the brain without the mic
  python jarvis.py --spotify-login   connect Spotify (optional, see README)
"""

import base64
import glob
import hashlib
import json
import os
import queue
import random
import re
import secrets
import shutil
import subprocess
import sys
import threading
import time
import urllib.error
import urllib.parse
import urllib.request

import numpy as np

import jarvis_brain
import jarvis_claude
import jarvis_extras
import jarvis_orb
import jarvis_phone
import jarvis_room
import jarvis_screen

# ---------------- settings you might change ----------------
MIC_DEVICE = None            # None = find the Focusrite by name. Or put a number from --devices
MIC_NAME_HINTS = ["focusrite", "scarlett"]
MIC_CHANNEL = 0              # Focusrite input 1 = 0, input 2 = 1
MIC_GAIN = 1.0               # software boost for a quiet mic (your Scarlett likes about 6)
SPEAKER_DEVICE = None        # None = Windows default output
WAKE_WORD = "hey_jarvis"     # built in options: hey_jarvis, alexa, hey_mycroft
WAKE_THRESHOLD = 0.5         # raise to 0.6 or 0.7 if it triggers by accident
WHISPER_MODEL = "large-v3-turbo"   # "small.en" if your GPU setup gives you trouble
VOICE = "am_michael"         # kokoro voices: am_michael, am_adam, af_heart, bf_emma ...
SILENCE_SECONDS = 1.2        # how long you pause before it stops recording
MAX_RECORD_SECONDS = 30
WORKDIR = os.path.dirname(os.path.abspath(__file__))   # Claude reads CLAUDE.md from here
HQ_URL = "https://claude.ai/artifact/9ZQx1xYZwPMRDhDuoT5oVE"
HQ_FULLSCREEN = True         # open HQ as a full screen app window in Chrome or Edge
CLAP_WAKE = True
CLAP_LEVEL = 0.35            # how loud a clap must be (0 to 1)
CLAP_CREST = 4.0             # how sharp: peak divided by average. Claps are spiky, voices are not
CLAP_GAP = (0.15, 0.9)       # seconds allowed between the two claps
GREETING = "Welcome back Yash. Systems online."
MORNING_BRIEF_BEFORE = 12    # on a clap wake before this hour, read a short brief (once a day)
# claude.ai connectors show up in Claude Code as mcp__claude_ai_<Name>. Run --doctor to confirm names.
CONNECTOR_TOOLS = "mcp__claude_ai_Google_Calendar,mcp__claude_ai_Gmail"
# Voice can search, read your calendar and mail, and write new files only inside notes/. Never add Bash.
ALLOWED_TOOLS = "WebSearch,WebFetch,Edit(./notes/**)," + CONNECTOR_TOOLS
SPOTIFY_CLIENT_ID = "9168fe0d1873402497e1738a923b9a76"       # optional, from developer.spotify.com. Then run --spotify-login once
AUTO_UPDATE_HOUR = 4         # restart into new code around 4 AM when an update is waiting. None = off
BROWSER = "chrome"           # chrome or edge, for HQ and every site Jarvis opens
BROWSER_PROFILE = ""         # Chrome profile folder like "Profile 1". Empty = find it from BROWSER_ACCOUNT
BROWSER_ACCOUNT = ""         # the email of the profile to use. Empty = your personal @gmail.com profile, never the school one
ORB = True                   # the little dot ring in the corner that shows when Jarvis is listening
WHATSAPP_CONTACTS = {}       # name -> phone with country code, in local_settings.py. e.g. {"mom": "+18585550100"}
NTFY_TOPIC = ""              # optional: phone push on clap. Install the ntfy app on your iPhone, subscribe to a long random topic, paste it here
# your cloud Claude Code sessions, through the claude.ai Claude Code Remote connector (run --doctor to confirm the name)
SESSIONS_TOOLS = "mcp__claude_ai_Claude_Code_Remote__list_sessions,mcp__claude_ai_Claude_Code_Remote__get_session,mcp__claude_ai_Claude_Code_Remote__list_events"
SESSIONS_SEND = "mcp__claude_ai_Claude_Code_Remote__send_message"
# -----------------------------------------------------------

# Your own settings live in local_settings.py, which updates never overwrite.
try:
    import local_settings as _local
    _mine = {k: v for k, v in vars(_local).items() if k.isupper()}
except ImportError:
    _mine = {}
globals().update(_mine)
for _mod in (jarvis_room, jarvis_orb, jarvis_claude, jarvis_screen, jarvis_brain, jarvis_extras, jarvis_phone):
    for _k, _v in _mine.items():
        if hasattr(_mod, _k):
            setattr(_mod, _k, _v)
if "CONNECTOR_TOOLS" in _mine and "ALLOWED_TOOLS" not in _mine:
    ALLOWED_TOOLS = "WebSearch,WebFetch,Edit(./notes/**)," + CONNECTOR_TOOLS

RATE = 16000
FRAME = 1280   # 80 ms, what openWakeWord expects
STATE_FILE = os.path.join(WORKDIR, ".session.json")
SPOTIFY_FILE = os.path.join(WORKDIR, ".spotify.json")
IS_WIN = sys.platform == "win32"

SPOKEN_STYLE = (
    "You are Jarvis, Yash's voice assistant. Everything you write is read aloud by a "
    "text to speech engine, so answer in plain spoken sentences. No markdown, no lists, "
    "no code blocks, no URLs, no emoji. Keep it under 80 words unless he asks for detail. "
    "For his calendar and email use the Google Calendar and Gmail tools. Times are Pacific."
)


def log(msg):
    print(time.strftime("%H:%M:%S"), msg, flush=True)


# ================= audio devices =================
def _sd():
    import sounddevice as sd
    return sd


HOST_PREF = ["MME", "Windows DirectSound", "Windows WASAPI", "Windows WDM-KS"]


def pick_device(devices, hostapis, hints, want_input=True):
    """Find a device whose name matches a hint. Prefer MME: Windows resamples there, so 16 kHz just works."""
    key = "max_input_channels" if want_input else "max_output_channels"
    found = []
    for i, d in enumerate(devices):
        if d[key] <= 0:
            continue
        name = d["name"].lower()
        if any(h in name for h in hints):
            api = hostapis[d["hostapi"]]["name"]
            rank = HOST_PREF.index(api) if api in HOST_PREF else len(HOST_PREF)
            found.append((rank, i))
    return min(found)[1] if found else None


def resolve_devices():
    sd = _sd()
    mic = MIC_DEVICE
    if mic is None:
        mic = pick_device(sd.query_devices(), sd.query_hostapis(), MIC_NAME_HINTS, True)
    return mic, SPEAKER_DEVICE


def resample(block, n_out):
    """Linear resample one block to exactly n_out samples. Fine for speech at 16 kHz."""
    if len(block) == n_out:
        return block
    x_old = np.linspace(0.0, 1.0, num=len(block), endpoint=False)
    x_new = np.linspace(0.0, 1.0, num=n_out, endpoint=False)
    return np.interp(x_new, x_old, block.astype(np.float32)).astype(np.int16)


audio_q = queue.Queue()


class Mic:
    """Opens the mic at 16 kHz, or at the device's own rate and resamples (Focusrite often refuses 16 kHz)."""
    def __init__(self, device):
        self.device = device
        self.stream = None

    def __enter__(self):
        sd = _sd()
        ch = MIC_CHANNEL + 1

        def cb_direct(indata, frames, t, status):
            audio_q.put(boost(indata[:, MIC_CHANNEL].copy()))

        try:
            self.stream = sd.InputStream(samplerate=RATE, channels=ch, dtype="int16", blocksize=FRAME,
                                         device=self.device, callback=cb_direct)
            self.stream.start()
            log(f"mic open at 16 kHz (device {self.device})")
        except Exception as e:
            sr = int(sd.query_devices(self.device, "input")["default_samplerate"])
            block = int(round(FRAME * sr / RATE))
            log(f"mic refused 16 kHz ({e}); opening at {sr} Hz and resampling")

            def cb_resample(indata, frames, t, status):
                audio_q.put(boost(resample(indata[:, MIC_CHANNEL], FRAME)))

            self.stream = sd.InputStream(samplerate=sr, channels=ch, dtype="int16", blocksize=block,
                                         device=self.device, callback=cb_resample)
            self.stream.start()
        return self

    def __exit__(self, *a):
        if self.stream:
            self.stream.stop()
            self.stream.close()


def boost(x):
    if MIC_GAIN == 1.0:
        return x
    return np.clip(x.astype(np.float32) * MIC_GAIN, -32768, 32767).astype(np.int16)


def drain_mic():
    while not audio_q.empty():
        audio_q.get_nowait()


def frame_stats(frame):
    f = frame.astype(np.float32) / 32768.0
    peak = float(np.max(np.abs(f))) if f.size else 0.0
    rms = float(np.sqrt(np.mean(f ** 2))) if f.size else 0.0
    return peak, rms


def record_until_silence(noise_floor, silence=None, max_secs=None, wait_for_voice=5):
    """Record after the wake word until the speaker goes quiet."""
    threshold = max(noise_floor * 3.0, 300)
    chunks, silent_for, heard_voice = [], 0.0, False
    start = time.time()
    silence, max_secs = silence or SILENCE_SECONDS, max_secs or MAX_RECORD_SECONDS
    while time.time() - start < max_secs:
        chunk = audio_q.get()
        chunks.append(chunk)
        loud = np.sqrt(np.mean(chunk.astype(np.float32) ** 2)) > threshold
        if loud:
            heard_voice, silent_for = True, 0.0
        else:
            silent_for += FRAME / RATE
        if heard_voice and silent_for >= silence:
            break
        if not heard_voice and time.time() - start > wait_for_voice:
            return None   # woke up but nobody said anything
    return np.concatenate(chunks).astype(np.float32) / 32768.0


# ================= speech to text =================
def add_cuda_dlls():
    """On Windows, faster-whisper does not find the CUDA DLLs that pip installs. Point it at them."""
    if not IS_WIN:
        return []
    added = []
    for sp in sys.path:
        for pattern in ("nvidia/*/bin", "torch/lib"):
            for d in glob.glob(os.path.join(sp, pattern)):
                if os.path.isdir(d) and d not in added:
                    try:
                        os.add_dll_directory(d)
                    except Exception:
                        pass
                    os.environ["PATH"] = d + os.pathsep + os.environ.get("PATH", "")
                    added.append(d)
    return added


def load_whisper():
    add_cuda_dlls()
    from faster_whisper import WhisperModel
    try:
        m = WhisperModel(WHISPER_MODEL, device="cuda", compute_type="float16")
        # RTX 50 cards can load fine and then fail on the first real decode, so test one now
        warm = (np.random.default_rng(0).standard_normal(RATE) * 0.01).astype(np.float32)
        list(m.transcribe(warm, language="en", beam_size=1, vad_filter=False)[0])
        log(f"whisper {WHISPER_MODEL} on GPU")
        return m, "cuda"
    except Exception as e:
        log(f"GPU whisper failed ({e}); falling back to CPU small.en")
        return WhisperModel("small.en", device="cpu", compute_type="int8"), "cpu"


def transcribe(model, audio):
    segments, _ = model.transcribe(audio, language="en", beam_size=1, vad_filter=True)
    return " ".join(s.text.strip() for s in segments).strip()


# ================= text to speech =================
class Speaker:
    def __init__(self):
        self.kokoro = None
        try:
            from kokoro import KPipeline
            self.kokoro = KPipeline(lang_code="a" if VOICE[0] == "a" else "b")
            log(f"kokoro voice {VOICE}")
        except Exception as e:
            log(f"kokoro unavailable ({e}); using Windows voice")
            import pyttsx3
            self.engine = pyttsx3.init()

    capture = threading.local()   # a request from your phone collects the answer here instead of speaking

    def say(self, text):
        cap = getattr(Speaker.capture, "lines", None)
        if cap is not None:
            cap.append(re.sub(r"[*#`_>\[\]]", "", text))
            if not getattr(Speaker.capture, "speak", False):
                return
        jarvis_orb.send("speaking")
        try:
            self._say(text)
        finally:
            jarvis_orb.send("idle")

    def _say(self, text):
        sd = _sd()
        text = re.sub(r"[*#`_>\[\]]", "", text)
        text = re.sub(r"https?://\S+", "", text)
        print("  >>", text, flush=True)
        if self.kokoro:
            for _, _, audio in self.kokoro(text, voice=VOICE):
                sd.play(audio, 24000, device=SPEAKER_DEVICE)
                sd.wait()
        else:
            self.engine.say(text)
            self.engine.runAndWait()

    def powerup(self):
        """The walk in sound: a deep drop, a rising whoosh, then a bright chord that blooms. About 2.6 seconds."""
        sd = _sd()
        sd.play(wake_sound(), 44100, device=SPEAKER_DEVICE)
        sd.wait()

    def chime(self, freq=880):
        sd = _sd()
        t = np.linspace(0, 0.12, int(24000 * 0.12), False)
        tone = 0.2 * np.sin(2 * np.pi * freq * t) * np.hanning(t.size)
        sd.play(tone.astype(np.float32), 24000, device=SPEAKER_DEVICE)
        sd.wait()


# ================= double clap =================
class ClapDetector:
    """Two sharp, loud, short spikes close together = double clap.
    Sharp means a high peak compared to the frame's average energy, which speech and music rarely have."""
    def __init__(self, level=None, crest=None, gap=None):
        self.level = CLAP_LEVEL if level is None else level
        self.crest = CLAP_CREST if crest is None else crest
        self.gap = CLAP_GAP if gap is None else gap
        self.last_clap = float("-inf")
        self.quiet_frames = 0

    def is_clap_frame(self, frame):
        peak, rms = frame_stats(frame)
        return peak >= self.level and (peak / max(rms, 1e-6)) >= self.crest, peak

    def feed(self, frame, now=None):
        now = time.time() if now is None else now
        sharp, peak = self.is_clap_frame(frame)
        if sharp and self.quiet_frames >= 2:
            self.quiet_frames = 0
            gap = now - self.last_clap
            self.last_clap = now
            if self.gap[0] <= gap <= self.gap[1]:
                self.last_clap = float("-inf")
                return True
        elif peak < self.level * 0.4:
            self.quiet_frames += 1
        else:
            self.quiet_frames = 0
        return False


# ================= PC control (safe allow list only) =================
VK = {"play_pause": 0xB3, "next": 0xB0, "prev": 0xB1, "mute": 0xAD, "vol_down": 0xAE, "vol_up": 0xAF}

APPS = {   # spoken name -> what to launch. Nothing here can delete or change files.
    "spotify": "spotify:", "chrome": "chrome", "edge": "msedge", "discord": "discord:",
    "vs code": "code", "vscode": "code", "visual studio code": "code", "notepad": "notepad",
    "calculator": "calc", "file explorer": "explorer", "explorer": "explorer", "files": "explorer",
    "settings": "ms-settings:", "steam": "steam://open/main", "terminal": "wt", "task manager": "taskmgr",
}
SITES = {
    "hq": HQ_URL, "youtube": "https://www.youtube.com", "gmail": "https://mail.google.com",
    "email": "https://mail.google.com", "calendar": "https://calendar.google.com", "drive": "https://drive.google.com",
    "github": "https://github.com", "vercel": "https://vercel.com/dashboard", "supabase": "https://supabase.com/dashboard",
    "claude": "https://claude.ai", "common app": "https://apply.commonapp.org", "spotify web": "https://open.spotify.com",
}


class PC:
    """Everything that touches Windows. Swapped for a recorder in tests."""
    def key(self, name, times=1):
        if not IS_WIN:
            log(f"[key {name} x{times}]")
            return
        import ctypes
        u = ctypes.windll.user32
        for _ in range(times):
            u.keybd_event(VK[name], 0, 0, 0)
            u.keybd_event(VK[name], 0, 2, 0)
            time.sleep(0.01)

    def launch(self, target):
        log(f"launch {target}")
        if IS_WIN:
            os.startfile(target) if ":" in target else subprocess.Popen(["cmd", "/c", "start", "", target], creationflags=0x08000000)
        else:
            import webbrowser
            webbrowser.open(target)

    def open_url(self, url, app_window=False):
        """Opens in your personal browser profile, not whatever Windows thinks is the default."""
        log(f"open {url}")
        exe, prof = browser_exe(), browser_profile()
        if IS_WIN and exe:
            args = [exe] + (["--profile-directory=" + prof] if prof else [])
            args += ["--app=" + url, "--start-fullscreen"] if app_window else ["--new-window" if app_window is None else "", url]
            subprocess.Popen([a for a in args if a])
            return
        import webbrowser
        webbrowser.open(url)

    def lock(self):
        log("lock screen")
        if IS_WIN:
            import ctypes
            ctypes.windll.user32.LockWorkStation()

    def nudge_display(self):
        if IS_WIN:
            import ctypes
            u = ctypes.windll.user32
            u.mouse_event(0x0001, 1, 0, 0, 0)
            u.mouse_event(0x0001, -1, 0, 0, 0)

    def monitor_off(self):
        log("monitor off")
        if IS_WIN:
            import ctypes
            ctypes.windll.user32.SendMessageW(0xFFFF, 0x0112, 0xF170, 2)   # broadcast: turn displays off

    def spotify_title(self):
        """What the Spotify desktop app shows in its window title, like 'Artist - Song'."""
        if not IS_WIN:
            return ""
        try:
            out = subprocess.run(["powershell", "-NoProfile", "-Command",
                                  "(Get-Process Spotify -ErrorAction SilentlyContinue | Where-Object {$_.MainWindowTitle}).MainWindowTitle"],
                                 capture_output=True, text=True, timeout=5, creationflags=0x08000000).stdout.strip()
            return "" if out in ("", "Spotify", "Spotify Free", "Spotify Premium") else out
        except Exception:
            return ""


WORDNUM = {"one": 1, "a": 1, "an": 1, "two": 2, "three": 3, "four": 4, "six": 6, "seven": 7, "eight": 8, "nine": 9, "twelve": 12, "forty five": 45, "five": 5, "ten": 10, "fifteen": 15, "twenty": 20, "thirty": 30, "forty": 40, "fifty": 50,
           "sixty": 60, "seventy": 70, "eighty": 80, "ninety": 90, "hundred": 100, "a hundred": 100}


def _num(s):
    m = re.search(r"\d+", s)
    if m:
        return int(m.group())
    for w, n in sorted(WORDNUM.items(), key=lambda x: -len(x[0])):
        if w in s:
            return n
    return None


def _dur(secs):
    secs = int(secs)
    if secs < 60:
        return f"{secs} seconds"
    m = secs // 60
    return f"{m} minute" + ("s" if m != 1 else "") if m < 60 else f"{m // 60} hour" + ("s" if m // 60 != 1 else "") + (f" {m % 60} minutes" if m % 60 else "")


BROWSERS = {
    "chrome": [r"C:\Program Files\Google\Chrome\Application\chrome.exe", r"C:\Program Files (x86)\Google\Chrome\Application\chrome.exe",
               os.path.expandvars(r"%LOCALAPPDATA%\Google\Chrome\Application\chrome.exe")],
    "edge": [r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe", r"C:\Program Files\Microsoft\Edge\Application\msedge.exe"],
}
USER_DATA = {"chrome": r"%LOCALAPPDATA%\Google\Chrome\User Data", "edge": r"%LOCALAPPDATA%\Microsoft\Edge\User Data"}


def browser_exe():
    return next((p for p in BROWSERS.get(BROWSER, []) if os.path.exists(p)), None)


def browser_profiles(local_state_path=None):
    """[(folder, name, email)] from the browser's own Local State file."""
    path = local_state_path or os.path.join(os.path.expandvars(USER_DATA.get(BROWSER, "")), "Local State")
    try:
        with open(path, encoding="utf-8") as f:
            cache = json.load(f).get("profile", {}).get("info_cache", {})
    except Exception:
        return []
    return [(d, i.get("name", ""), (i.get("user_name") or "").lower()) for d, i in cache.items()]


def browser_profile(local_state_path=None):
    """The profile to open: the one you named, else the one signed in as BROWSER_ACCOUNT,
    else the only personal gmail.com profile, so the school account never opens HQ."""
    if BROWSER_PROFILE:
        return BROWSER_PROFILE
    profs = browser_profiles(local_state_path)
    if BROWSER_ACCOUNT:
        hit = next((d for d, _, e in profs if e == BROWSER_ACCOUNT.lower()), None)
        if hit:
            return hit
    personal = [d for d, _, e in profs if e.endswith("@gmail.com")]
    return personal[0] if len(personal) == 1 else None


def wake_sound(sr=44100, volume=0.5):
    """Synthesized locally, no files. Stereo float32."""
    rng = np.random.default_rng(7)
    dur = 2.6
    t = np.arange(int(sr * dur)) / sr
    out = np.zeros_like(t)
    # 1. sub drop: 90 Hz falling to 38 Hz with a soft thump
    f = 38 + 52 * np.exp(-t * 3.0)
    phase = 2 * np.pi * np.cumsum(f) / sr
    out += 0.9 * np.sin(phase) * np.exp(-t * 1.6) * np.clip(t * 60, 0, 1)
    # 2. riser: filtered noise swelling into the hit at 1.15 s
    n = rng.standard_normal(t.size)
    k = np.exp(-np.linspace(0, 8, 64)); k /= k.sum()
    n = np.convolve(n, k, mode="same")
    rise = np.clip(t / 1.15, 0, 1) ** 3 * (t < 1.2) + (t >= 1.2) * np.exp(-(t - 1.2) * 9)
    out += 0.55 * n / (np.abs(n).max() + 1e-9) * rise
    # 3. the hit: A major spread across octaves, bright attack, long bloom
    hit = t >= 1.15
    th = np.where(hit, t - 1.15, 0)
    env = hit * (1 - np.exp(-th * 40)) * np.exp(-th * 1.25)
    for fr, a in ((110, .5), (220, .45), (277.18, .3), (329.63, .32), (440, .3), (554.37, .18), (659.25, .2), (880, .12), (1318.5, .06)):
        out += a * env * (np.sin(2 * np.pi * fr * th) + 0.25 * np.sin(2 * np.pi * fr * 2.003 * th))
    # 4. shimmer: high sparkle after the hit
    out += 0.08 * env * np.sin(2 * np.pi * 2637 * th) * (0.5 + 0.5 * np.sin(2 * np.pi * 7 * th))
    out = np.tanh(out * 1.4)
    out *= volume / (np.abs(out).max() + 1e-9)
    fade = np.clip((dur - t) / 0.3, 0, 1)
    out *= fade
    # gentle stereo width from a tiny delay on the right channel
    d = int(sr * 0.012)
    right = np.concatenate([np.zeros(d), out[:-d]])
    return np.stack([out, 0.85 * right + 0.15 * out], axis=1).astype(np.float32)


def update_waiting():
    try:
        r = subprocess.run([sys.executable, os.path.join(WORKDIR, "update.py"), "--check"], capture_output=True, timeout=180,
                           creationflags=0x08000000 if IS_WIN else 0)
        return r.returncode == 10
    except Exception as e:
        log(f"update check failed: {e}")
        return False


def nightly_update_watch(jarvis):
    """Once a night at AUTO_UPDATE_HOUR, if new code is waiting, ask the main loop to restart into it."""
    done_day = None
    while True:
        time.sleep(600)
        lt = time.localtime()
        if AUTO_UPDATE_HOUR is not None and lt.tm_hour == AUTO_UPDATE_HOUR and done_day != lt.tm_yday:
            done_day = lt.tm_yday
            if update_waiting():
                log("update waiting, restarting into it")
                jarvis.restart_for_update = True


def push_phone(text):
    """Optional iPhone notification through ntfy (free app). Only a short status line is sent."""
    try:
        urllib.request.urlopen(urllib.request.Request("https://ntfy.sh/" + NTFY_TOPIC, data=text.encode(),
                                                      headers={"Title": "Yash HQ", "Tags": "red_circle"}), timeout=8)
    except Exception as e:
        log(f"push failed: {e}")


def route(text):
    """Turn a spoken line into a local command, or None to send it to Claude.
    Returns (action, arg). Only actions from this list can ever run by voice."""
    t = re.sub(r"[^\w\s']", " ", text.lower())
    t = re.sub(r"^\s*(hey\s+)?jarvis\s*", "", t)
    t = re.sub(r"\b(please|can you|could you|for me|real quick)\b", " ", t)
    t = re.sub(r"\s+", " ", t).strip()

    if re.fullmatch(r"(go to sleep|shut down jarvis)", t) or t == "go to sleep":
        return ("sleep", None)
    if re.fullmatch(r"(yes|yeah|yep|do it|send it|confirm|go ahead)", t):
        return ("confirm", True)
    if re.fullmatch(r"(no|nope|cancel|never ?mind|don't)", t):
        return ("confirm", False)
    if re.fullmatch(r"(update yourself|check for updates|update jarvis|install updates?|get the latest version)", t):
        return ("update", None)
    if re.search(r"\b(what are|how are|status of|check on) my (claude )?(cloud )?(sessions|agents)( doing)?\b|\bsession status\b", t):
        return ("sessions", None)
    m = re.fullmatch(r"(?:whatsapp|send (?:a )?whatsapp to|message|text) (.+?)(?: on whatsapp)? (?:saying |that |to say )?(.+)", t)
    if m and (t.startswith(("whatsapp", "send a whatsapp", "send whatsapp")) or "on whatsapp" in t):
        return ("whatsapp", (m.group(1).strip(), m.group(2).strip()))
    cc = jarvis_brain.route_brain(t) or jarvis_phone.route_phone(t) or jarvis_extras.route_extras(t) or jarvis_claude.route_claude(t) or jarvis_screen.route_screen(t)
    if cc:
        return cc
    if re.fullmatch(r"what time is it|what's the time|time", t):
        return ("time", None)
    m = re.search(r"\b(?:set )?(?:a )?timer (?:for )?(.+?) (seconds?|minutes?|hours?)\b", t) or re.fullmatch(r"(.+?) (seconds?|minutes?|hours?) timer", t)
    if m and _num(m.group(1)) is not None:
        return ("timer", _num(m.group(1)) * {"s": 1, "m": 60, "h": 3600}[m.group(2)[0]])
    m = re.fullmatch(r"remind me in (.+?) (minutes?|hours?) (?:to |that |about )?(.+)", t)
    if m and _num(m.group(1)) is not None:
        return ("remind", (_num(m.group(1)) * (60 if m.group(2)[0] == "m" else 3600), m.group(3)))
    m = re.fullmatch(r"(?:take a note|note to self|make a note|write down)(?: that)? (.+)", t)
    if m:
        return ("note", m.group(1))
    if re.fullmatch(r"(good ?night|goodnight jarvis|i'?m going to bed|bedtime)", t):
        return ("goodnight", None)
    if re.fullmatch(r"(turn off|sleep) (the )?(monitor|screen|display)s?|(monitor|screen) off", t):
        return ("monitor_off", None)
    if re.search(r"\b(what are|how are|status of|check on) my (claude )?(sessions|agents)\b|\bsession status\b", t):
        return ("sessions", None)
    m = re.fullmatch(r"(?:tell|message) (?:the |my )?(.+?) session (?:to |that )?(.+)", t)
    if m:
        return ("session_send", (m.group(1), m.group(2)))
    if re.search(r"\bnew conversation\b|\bstart over\b|\bfresh start\b", t):
        return ("reset", None)
    if re.search(r"\b(open|show|pull up) (the )?hq\b|\bwake (everything|up the room|up)\b|\bi'?m (home|back)\b", t):
        return ("hq", None)
    if re.search(r"\block (the |my )?(screen|computer|pc)\b", t):
        return ("lock", None)

    # music
    if re.search(r"\b(what'?s|what is) (playing|this song)\b|\bwhat song is this\b", t):
        return ("now_playing", None)
    if re.fullmatch(r"(pause|stop)( the)?( music| song| spotify)?|(resume|unpause)( the)?( music| song| spotify)?|play( the)? music|play spotify|resume|play", t):
        return ("play_pause", None)
    if re.search(r"\b(next|skip)( the)?( song| track)?\b", t) and len(t.split()) <= 4 and not t.startswith(("play ", "queue ")):
        return ("next", None)
    if re.search(r"\b(previous|last|go back)( the)?( song| track)\b|\bprevious\b", t) and len(t.split()) <= 4:
        return ("prev", None)
    m = re.fullmatch(r"(?:queue|queue up|add) (.+?)(?: to (?:the |my )?queue)?(?: on spotify)?|play (.+?) next", t)
    if m and (t.startswith("queue") or "queue" in t or t.endswith(" next")):
        return ("spotify_queue", (m.group(1) or m.group(2)).strip())
    m = re.fullmatch(r"(?:play|put on|throw on|spin) (.+?)( on spotify)?", t)
    if m and m.group(1) not in ("music", "spotify"):
        return ("spotify_play", m.group(1).strip())

    # volume
    if re.fullmatch(r"(un)?mute( the)?( sound| volume| audio)?", t):
        return ("mute", None)
    m = re.search(r"\b(set )?(the )?volume (to|at) (.+)", t)
    if m and _num(m.group(4)) is not None:
        return ("volume_set", max(0, min(100, _num(m.group(4)))))
    if re.search(r"\b(volume up|turn (it )?up|louder)\b", t):
        return ("volume_up", _num(t) or 10)
    if re.search(r"\b(volume down|turn (it )?down|quieter|softer)\b", t):
        return ("volume_down", _num(t) or 10)

    # apps and sites
    m = re.fullmatch(r"(open|launch|start|go to|pull up) (.+)", t)
    if m:
        name = re.sub(r"^(the|my|up)\s+", "", m.group(2)).strip()
        name = re.sub(r"\s+(app|website|site|page)$", "", name)
        if name in SITES:
            return ("site", name)
        if name in APPS:
            return ("app", name)
    return None


# ================= Spotify Web API (optional) =================
class Spotify:
    """Real playback control. Needs SPOTIFY_CLIENT_ID and Spotify Premium. Without it, Jarvis uses media keys."""
    REDIRECT = "http://127.0.0.1:8765/callback"
    SCOPES = "user-read-playback-state user-modify-playback-state user-read-currently-playing user-library-read playlist-read-private playlist-read-collaborative"

    def __init__(self):
        self.tok = {}
        try:
            with open(SPOTIFY_FILE) as f:
                self.tok = json.load(f)
        except Exception:
            pass

    @property
    def ready(self):
        return bool(SPOTIFY_CLIENT_ID and self.tok.get("refresh_token"))

    def _save(self):
        with open(SPOTIFY_FILE, "w") as f:
            json.dump(self.tok, f)

    def _token_req(self, data):
        data["client_id"] = SPOTIFY_CLIENT_ID
        req = urllib.request.Request("https://accounts.spotify.com/api/token", data=urllib.parse.urlencode(data).encode(),
                                     headers={"Content-Type": "application/x-www-form-urlencoded"})
        with urllib.request.urlopen(req, timeout=10) as r:
            t = json.load(r)
        t["expires_at"] = time.time() + t.get("expires_in", 3600) - 60
        if "refresh_token" not in t:
            t["refresh_token"] = self.tok.get("refresh_token")
        self.tok = t
        self._save()

    def login(self):
        """One time: opens Spotify in the browser, catches the redirect on localhost."""
        from http.server import BaseHTTPRequestHandler, HTTPServer
        import webbrowser
        if not SPOTIFY_CLIENT_ID:
            sys.exit("Put your SPOTIFY_CLIENT_ID at the top of jarvis.py first (see README).")
        verifier = secrets.token_urlsafe(64)
        challenge = base64.urlsafe_b64encode(hashlib.sha256(verifier.encode()).digest()).rstrip(b"=").decode()
        state = secrets.token_urlsafe(16)
        got = {}

        class H(BaseHTTPRequestHandler):
            def do_GET(self):
                q = urllib.parse.parse_qs(urllib.parse.urlparse(self.path).query)
                got.update({k: v[0] for k, v in q.items()})
                self.send_response(200)
                self.end_headers()
                self.wfile.write(b"Spotify connected. You can close this tab.")

            def log_message(self, *a):
                pass

        srv = HTTPServer(("127.0.0.1", 8765), H)
        webbrowser.open("https://accounts.spotify.com/authorize?" + urllib.parse.urlencode({
            "client_id": SPOTIFY_CLIENT_ID, "response_type": "code", "redirect_uri": self.REDIRECT,
            "code_challenge_method": "S256", "code_challenge": challenge, "scope": self.SCOPES, "state": state}))
        print("Approve in the browser window...")
        while "code" not in got and "error" not in got:
            srv.handle_request()
        if got.get("state") != state or "code" not in got:
            sys.exit("Spotify login failed: " + got.get("error", "state mismatch"))
        self._token_req({"grant_type": "authorization_code", "code": got["code"], "redirect_uri": self.REDIRECT, "code_verifier": verifier})
        print("Spotify connected.")

    def _api(self, method, path, body=None):
        if time.time() > self.tok.get("expires_at", 0):
            self._token_req({"grant_type": "refresh_token", "refresh_token": self.tok["refresh_token"]})
        req = urllib.request.Request("https://api.spotify.com/v1" + path, method=method,
                                     data=json.dumps(body).encode() if body is not None else None,
                                     headers={"Authorization": "Bearer " + self.tok["access_token"], "Content-Type": "application/json"})
        with urllib.request.urlopen(req, timeout=10) as r:
            raw = r.read()
        return json.loads(raw) if raw else {}

    # ---- understanding what you asked for ----
    MOODS = r"chill|hype|lofi|lo fi|study|focus|workout|gym|sad|happy|party|sleep|rap|hip hop|pregame|game day|throwback|jazz|classical|acoustic|indie|rock|pop|country|edm|r&b|rnb|latin|bollywood|punjabi"

    @staticmethod
    def parse(query):
        """'drake' -> artist or track, 'gods plan by drake' -> track, 'my gym playlist' -> your playlist,
        'my liked songs' -> likes, 'the album scorpion' -> album, 'something chill' -> mood playlist."""
        q = re.sub(r"\s+", " ", query.lower()).strip()
        q = re.sub(r"^(some|a little|me|the song|song|track)\s+", lambda m: "some " if m.group(1) == "some" else "", q)
        if re.fullmatch(r"(my )?(liked|saved|favorite|favourite) (songs|music|tracks)|my likes|my liked", q):
            return {"kind": "liked"}
        m = re.fullmatch(r"my (.+?) playlist|my playlist (?:called |named )?(.+)", q)
        if m:
            return {"kind": "myplaylist", "q": (m.group(1) or m.group(2)).strip()}
        m = re.fullmatch(r"(?:the |a )?(.+?) playlist|(?:the |a )?playlist (?:called |named )?(.+)", q)
        if m:
            return {"kind": "playlist", "q": (m.group(1) or m.group(2)).strip()}
        m = re.fullmatch(r"(?:the )?album (.+?)(?: by (.+))?|(?:the )?(.+?) album(?: by (.+))?", q)
        if m:
            return {"kind": "album", "q": (m.group(1) or m.group(3)).strip(), "artist": (m.group(2) or m.group(4) or "").strip()}
        m = re.fullmatch(r"(?:something|anything|some|music for|songs for) ?(" + Spotify.MOODS + r")(?: music| songs| vibes)?|(" + Spotify.MOODS + r") (?:music|songs|vibes)", q)
        if m:
            return {"kind": "playlist", "q": (m.group(1) or m.group(2)).strip()}
        m = re.fullmatch(r"(?:some |songs by |music by |more )(.+)|(.+?) songs", q)
        if m:
            return {"kind": "artist", "q": (m.group(1) or m.group(2)).strip()}
        m = re.fullmatch(r"(.+?) by (.+)", q)
        if m:
            return {"kind": "track", "q": m.group(1).strip(), "artist": m.group(2).strip()}
        return {"kind": "any", "q": q}

    def device(self, launch=None, wait=10.0):
        """The device to play on. Prefers what's already playing, then this PC. Opens Spotify if nothing is there."""
        t0 = time.time()
        while True:
            devs = self._api("GET", "/me/player/devices").get("devices", [])
            act = next((d for d in devs if d.get("is_active")), None) or next((d for d in devs if d.get("type") == "Computer"), None) or (devs[0] if devs else None)
            if act or not launch or time.time() - t0 > wait:
                return act
            if time.time() - t0 < 0.5:
                launch("spotify:")
            time.sleep(1.0)

    def _search(self, kind, q, limit=5):
        res = self._api("GET", "/search?" + urllib.parse.urlencode({"q": q, "type": kind, "limit": limit}))
        return [i for i in (res.get(kind + "s", {}).get("items") or []) if i]

    def resolve(self, query):
        """Turn what you said into something playable: ({'uris': [...]} or {'context_uri': ...}, spoken name)."""
        r = self.parse(query)
        k = r["kind"]
        if k == "liked":
            items = self._api("GET", "/me/tracks?limit=50").get("items", [])
            uris = [i["track"]["uri"] for i in items if i.get("track")]
            if not uris:
                return None, None
            random.shuffle(uris)
            return {"uris": uris}, "your liked songs"
        if k == "myplaylist":
            mine = self._api("GET", "/me/playlists?limit=50").get("items", [])
            want = r["q"]
            best = next((p for p in mine if p and p.get("name", "").lower() == want), None) or next((p for p in mine if p and want in p.get("name", "").lower()), None)
            if best:
                return {"context_uri": best["uri"]}, "your " + best["name"] + " playlist"
            k, r = "playlist", {"q": want}
        if k == "playlist":
            pl = self._search("playlist", r["q"], 3)
            return ({"context_uri": pl[0]["uri"]}, pl[0]["name"] + " playlist") if pl else (None, None)
        if k == "album":
            al = self._search("album", r["q"] + (" artist:" + r["artist"] if r.get("artist") else ""), 3)
            return ({"context_uri": al[0]["uri"]}, al[0]["name"] + " by " + al[0]["artists"][0]["name"]) if al else (None, None)
        if k == "artist":
            ar = self._search("artist", r["q"], 3)
            return ({"context_uri": ar[0]["uri"]}, ar[0]["name"]) if ar else (None, None)
        if k == "track":
            tr = self._search("track", "track:" + r["q"] + " artist:" + r["artist"], 5) or self._search("track", r["q"] + " " + r["artist"], 5)
            return ({"uris": [tr[0]["uri"]]}, tr[0]["name"] + " by " + tr[0]["artists"][0]["name"]) if tr else (None, None)
        # bare name: an artist if it matches one exactly, otherwise the best song
        q = r["q"]
        ar = self._search("artist", q, 3)
        if ar and ar[0].get("name", "").lower().replace("the ", "") == q.replace("the ", ""):
            return {"context_uri": ar[0]["uri"]}, ar[0]["name"]
        tr = self._search("track", q, 5)
        if tr:
            return {"uris": [tr[0]["uri"]]}, tr[0]["name"] + " by " + tr[0]["artists"][0]["name"]
        return (({"context_uri": ar[0]["uri"]}, ar[0]["name"]) if ar else (None, None))

    def play(self, query, launch=None):
        """Play anything by name. Returns what's playing, or None if nothing matched."""
        body, name = self.resolve(query)
        if not body:
            return None
        dev = self.device(launch)
        q = "?device_id=" + dev["id"] if dev else ""
        if "context_uri" in body and "playlist" in body["context_uri"] or "artist" in body.get("context_uri", ""):
            try:
                self._api("PUT", "/me/player/shuffle?state=true" + ("&device_id=" + dev["id"] if dev else ""))
            except Exception:
                pass
        self._api("PUT", "/me/player/play" + q, body)
        return name

    def queue(self, query, launch=None):
        """Add one song to the queue."""
        body, name = self.resolve(query)
        if not body:
            return None
        uri = (body.get("uris") or [None])[0]
        if not uri:
            tr = self._search("track", query, 1)
            if not tr:
                return None
            uri, name = tr[0]["uri"], tr[0]["name"] + " by " + tr[0]["artists"][0]["name"]
        self._api("POST", "/me/player/queue?" + urllib.parse.urlencode({"uri": uri}))
        return name

    def now_playing(self):
        r = self._api("GET", "/me/player/currently-playing")
        it = r.get("item") or {}
        if not it:
            return None
        return it.get("name", "") + " by " + ", ".join(a["name"] for a in it.get("artists", [])[:2])

    def volume(self, pct):
        self._api("PUT", "/me/player/volume?volume_percent=" + str(int(pct)))


# ================= the brain: Claude Code =================
def find_claude():
    return shutil.which("claude") or shutil.which("claude.exe") or shutil.which("claude.cmd")


def load_session():
    try:
        with open(STATE_FILE) as f:
            return json.load(f).get("session_id")
    except Exception:
        return None


def save_session(sid):
    with open(STATE_FILE, "w") as f:
        json.dump({"session_id": sid}, f)


BRAIN = None   # set in main, adds memory and today's log to every prompt


def ask_claude(prompt, session_id, claude=None, tools=None):
    """The question goes in on stdin, never on the command line, so nothing you say can run as a command."""
    claude = claude or find_claude()
    now = time.strftime("%A %B %d, %I:%M %p")
    extra, tools = "", tools or ALLOWED_TOOLS
    if BRAIN:
        try:
            extra = BRAIN.context_for_claude()
        except Exception:
            extra = ""
        tools += ",Read,Grep,Glob"   # read only, so he can ask about his notes
    cmd = [claude, "-p", "--output-format", "json", "--append-system-prompt", SPOKEN_STYLE + " Local time now: " + now + "." + extra,
           "--allowedTools", tools]
    if BRAIN:
        cmd += ["--add-dir", BRAIN.vault.root]
    if session_id:
        cmd += ["--resume", session_id]
    r = subprocess.run(cmd, cwd=WORKDIR, input=prompt, capture_output=True, text=True, encoding="utf-8",
                       timeout=300, creationflags=0x08000000 if IS_WIN else 0)
    if r.returncode != 0 and session_id:
        return ask_claude(prompt, None, claude, tools)   # old session gone, start a new one
    try:
        data = json.loads(r.stdout)
    except Exception:
        log(f"claude failed (code {r.returncode}): {(r.stderr or r.stdout)[:400]}")
        return "I couldn't reach Claude. Check the Jarvis window.", session_id
    return data.get("result") or "I didn't get an answer back.", data.get("session_id") or session_id


MORNING_PROMPT = ("Give me a morning brief I can hear in about 20 seconds: my first event today with its time, "
                  "how many other events, and anything in my unread email from a real person that needs me. "
                  "If you can't reach my calendar, just say so in one sentence.")


def restore_windows(titles):
    """Un-minimize the windows that were open before you left. Only windows that still exist."""
    scr = jarvis_screen.Screen()
    want = {t.split(": ", 1)[-1] for t in titles}
    n = 0
    for h, _, title in scr.windows():
        if title[:80] in want:
            scr.show(h, "restore")
            n += 1
    return n


# ================= main =================
class Jarvis:
    def __init__(self, speaker, pc=None, spotify=None, claude=None):
        self.speaker, self.pc, self.spotify, self.claude = speaker, pc or PC(), spotify or Spotify(), claude
        self.session_id = load_session()
        self.last_brief_day = None
        self.quiet_until = 0.0
        self.pending = None
        self.restart_for_update = False
        self.brain = None
        self.extras = None
        self.lock = threading.RLock()   # voice and phone requests take turns
        self.record_long = None   # set in main: records up to 3 minutes and returns the text

    def ask_once(self, prompt, tools=None):
        return ask_claude(prompt, None, self.claude, (CONNECTOR_TOOLS + "," + tools) if tools else CONNECTOR_TOOLS)[0]

    def make_brain(self):
        sc = lambda a, arg: jarvis_screen.ScreenControl(lambda *_: None, self.pc.launch, open_url=self.pc.open_url).handle(a, arg)
        self.brain = jarvis_brain.Brain(self.speaker.say, self.ask_once, chime=self.speaker.chime, launch=self.pc.launch, screen=sc)
        self.brain.play = lambda q: self.spotify.play(q, launch=self.pc.launch) if self.spotify.ready else self.pc.launch("spotify:search:" + urllib.parse.quote(q))
        self.brain.restore_windows = restore_windows
        jarvis_phone.NTFY_TOPIC = jarvis_phone.NTFY_TOPIC or NTFY_TOPIC
        self.phone = jarvis_phone.Phone(self.speaker.say, clipboard=jarvis_extras.clipboard_text)
        if jarvis_phone.MIRROR_TO_PHONE:
            self.brain.mirror = lambda title, text: jarvis_phone.push(text, title, priority=4, tags="bell")
            spoken = self.brain.planner.say

            def planner_say(line):
                spoken(line)
                if self.brain.presence.away and line.lower().startswith(("heads up", "leave in", "time to go")):
                    jarvis_phone.push(line, "Leave reminder", priority=5, tags="car")
            self.brain.planner.say = planner_say
        self.extras = jarvis_extras.Extras(self.speaker.say, self.ask_once, pc=self.pc, spotify=self.spotify, brain_=self.brain,
                                           record_long=self.record_long, screen_cmd=sc, room_playlist=jarvis_room.ROOM_PLAYLIST)
        return self.brain

    def later(self, secs, text):
        def fire():
            try:
                self.speaker.chime(1320)
                self.speaker.say(text)
            except Exception as e:
                log(f"timer: {e}")
        t = threading.Timer(secs, fire)
        t.daemon = True
        t.start()

    def wake_room(self):
        """The walk in scene. Opening HQ here also tells HQ on the iPad to wake up."""
        self.pc.nudge_display()
        snd = threading.Thread(target=lambda: self.speaker.powerup(), daemon=True)
        snd.start()
        self.pc.open_url(HQ_URL + "#wake", app_window=HQ_FULLSCREEN)   # #wake plays HQ's full screen takeover here and on the iPad
        if hasattr(self.pc, "arrange"):
            try:
                self.pc.arrange()
            except Exception as e:
                log(f"layout failed: {e}")
        threading.Thread(target=lambda: log("music: " + jarvis_room.start_music(self.pc, self.spotify, log)), daemon=True).start()
        log("room awake, HQ opened")
        if NTFY_TOPIC:
            threading.Thread(target=push_phone, args=("HQ is online. Welcome back.",), daemon=True).start()
        if self.brain:
            quick, finish = self.brain.greet("clap")   # starts reading the calendar right away
            snd.join(timeout=4)
            self.speaker.say(quick)
            finish()   # "welcome back from practice ..." plus the morning brief and today's reminders
            return
        snd.join(timeout=4)
        self.speaker.say(GREETING)
        today = time.strftime("%Y-%m-%d")
        if time.localtime().tm_hour < MORNING_BRIEF_BEFORE and self.last_brief_day != today:
            self.last_brief_day = today
            answer, _ = ask_claude(MORNING_PROMPT, None, self.claude)
            self.speaker.say(answer)

    def remote_ask(self, text, speak=False):
        """A request from your phone. Returns what Jarvis would have said."""
        with self.lock:
            Speaker.capture.lines, Speaker.capture.speak = [], speak
            try:
                log(f"phone: {text}")
                self.handle(text)
                return " ".join(Speaker.capture.lines) or "Done."
            finally:
                Speaker.capture.lines = None

    def phone_event(self, name):
        log(f"phone event: {name}")
        b = self.brain
        if name == "home":
            if b:
                b.presence.arrived_at = time.time()
                b.vault.log("Got home")
            return "Welcome home. Clap when you walk in."
        if name == "leave":
            if b:
                b.presence.before_leaving = jarvis_brain.window_snapshot()[:8]
                b.vault.log("Left home")
            return "Have a good one."
        if name == "awake":
            if jarvis_brain.quiet_now() and time.localtime().tm_hour < 4:
                return "It's the middle of the night. Go back to sleep."
            threading.Thread(target=lambda: self.lock.acquire() or self._wake_unlocked(), daemon=True).start()
            return "Morning. Waking up your room."
        if name == "bed":
            threading.Thread(target=lambda: self.remote_ask("goodnight", speak=True), daemon=True).start()
            return "Goodnight. Shutting the room down."
        return "Unknown event."

    def _wake_unlocked(self):
        try:
            self.wake_room()
        finally:
            self.lock.release()

    def handle(self, text):
        """Returns False to quit."""
        if self.brain:
            self.brain.presence.seen()
        cmd = route(text)
        if cmd:
            log(f"command: {cmd}")
            return self.run(*cmd)
        answer, self.session_id = ask_claude(text, self.session_id, self.claude)
        save_session(self.session_id)
        self.speaker.say(answer)
        return True

    def run(self, action, arg):
        say, pc, sp = self.speaker.say, self.pc, self.spotify
        if action == "confirm":
            job, self.pending = self.pending, None
            if not job:
                say("Nothing to confirm.")
            elif arg:
                job()
            else:
                say("Cancelled.")
            return True
        self.pending = None
        if action == "update":
            if update_waiting():
                say("Updating. Back in a few seconds.")
                self.restart_for_update = True
            else:
                say("I'm already on the latest version.")
        elif action == "whatsapp":
            name, msg = arg
            num = next((v for k, v in WHATSAPP_CONTACTS.items() if k.lower() == name.lower()), None)
            if not num:
                say(f"I don't have a WhatsApp number for {name}. Add it to WHATSAPP_CONTACTS in local settings.")
                return True
            text = jarvis_screen.clean_typing(msg)

            def send():
                digits = re.sub(r"[^0-9]", "", num)
                pc.launch("whatsapp://send?phone=" + digits + "&text=" + urllib.parse.quote(text))
                time.sleep(3.5)
                sc = jarvis_screen.ScreenControl(say, pc.launch, open_url=pc.open_url)
                h = sc.s.find("whatsapp")
                if h:
                    sc.s.focus(h)
                    time.sleep(0.4)
                    sc.s.chord(["RETURN"])
                    say("Sent.")
                else:
                    say("WhatsApp didn't open. The message is ready in the app if it shows up.")
            self.pending = send
            say(f"WhatsApp {name}: {text} Say yes to send.")
            return True
        elif action == "time":
            say("It's " + time.strftime("%I:%M %p").lstrip("0") + ".")
        elif action == "timer":
            self.later(arg, "Timer done.")
            say("Timer set for " + _dur(arg) + ".")
        elif action == "remind":
            secs, what = arg
            self.later(secs, "Reminder: " + what)
            say("I'll remind you in " + _dur(secs) + ".")
        elif action == "note" and self.brain:
            self.brain.vault.note(arg)
            say("Noted.")
        elif action == "note":
            os.makedirs(os.path.join(WORKDIR, "notes"), exist_ok=True)
            with open(os.path.join(WORKDIR, "notes", "inbox.md"), "a", encoding="utf-8") as f:
                f.write(time.strftime("- %Y-%m-%d %H:%M ") + arg + "\n")
            say("Noted.")
        elif action == "goodnight":
            pc.key("play_pause") if pc.spotify_title() else None
            if self.brain:
                say("One sec.")
                if self.extras and self.extras.st.today():
                    self.brain.vault.log("Screen time: " + self.extras.st.spoken())
                    self.extras.st.save()
                recap = self.brain.goodnight()
                if recap:
                    say(recap)
            say("Goodnight Yash. Shutting the room down.")
            pc.monitor_off()
        elif action == "monitor_off":
            pc.monitor_off()
        elif action == "sessions":
            say("Checking your sessions.")
            ans, _ = ask_claude("Give me a spoken status of my Claude Code cloud sessions: which are working, which are waiting on me, "
                                "and what the most recent one did. Use the Claude Code Remote tools.", None, self.claude, SESSIONS_TOOLS)
            say(ans)
        elif action == "session_send":
            name, msg = arg
            msg = jarvis_claude.clean_task(msg)

            def send():
                say("Sending.")
                ans, _ = ask_claude(f"Find my Claude Code cloud session whose title best matches '{name}'. If exactly one clearly matches, "
                                    f"send it this message with send_message: '{msg}'. Then tell me in one sentence which session got it. "
                                    "If none or several match, send nothing and say which ones you found.", None, self.claude,
                                    SESSIONS_TOOLS + "," + SESSIONS_SEND)
                say(ans)
            self.pending = send
            say(f"Send to the {name} session: {msg}. Say yes to send.")
            return True
        if action in ("remember", "memory_list", "vault_search", "vault_open", "vault_log", "game_result", "season", "focus", "focus_end", "what_now",
                      "stat", "streaks", "pregame", "restore", "shop", "due", "weekly", "mail_check"):
            if not self.brain:
                self.make_brain()
            if action == "focus" and jarvis_brain.FOCUS_MUSIC and sp.ready:
                threading.Thread(target=lambda: sp.play(jarvis_brain.FOCUS_MUSIC, launch=pc.launch), daemon=True).start()
            self.brain.handle(action, arg)
            return True
        if action == "phone":
            if not self.brain:
                self.make_brain()
            self.phone.handle(arg)
            return True
        if action in ("weather", "protocol", "journal", "screentime", "countdown", "training", "training_week", "clipboard", "look",
                      "alarm", "alarm_off", "roast"):
            if not self.extras:
                self.make_brain()
            self.extras.handle(action, arg)
            return True
        if action in ("snap", "maximize", "minimize", "focus", "layout", "keys", "type"):
            jarvis_screen.ScreenControl(say, pc.launch, open_url=pc.open_url).handle(action, arg)
            return True
        if action.startswith(("cc_", "chat_", "claude_")):
            jarvis_claude.ClaudeControl(say, pc, self.claude or find_claude()).handle(action, arg)
            return True
        elif action == "sleep":
            say("Going offline.")
            return False
        elif action == "reset":
            self.session_id = None
            save_session(None)
            say("Fresh start.")
        elif action == "hq":
            self.wake_room()
        elif action == "lock":
            say("Locking.")
            pc.lock()
        elif action == "play_pause":
            pc.key("play_pause")
        elif action == "next":
            pc.key("next")
        elif action == "prev":
            pc.key("prev")
        elif action == "mute":
            pc.key("mute")
        elif action == "volume_up":
            pc.key("vol_up", max(1, arg // 2))
        elif action == "volume_down":
            pc.key("vol_down", max(1, arg // 2))
        elif action == "volume_set":
            pc.key("vol_down", 50)
            pc.key("vol_up", arg // 2)
            say(f"Volume {arg}.")
        elif action == "now_playing":
            song = None
            if sp.ready:
                try:
                    song = sp.now_playing()
                except Exception as e:
                    log(f"spotify api: {e}")
            song = song or pc.spotify_title()
            say(f"This is {song}." if song else "Nothing's playing on Spotify.")
        elif action in ("spotify_play", "spotify_queue"):
            done, err = None, ""
            if sp.ready:
                try:
                    done = (sp.play if action == "spotify_play" else sp.queue)(arg, launch=pc.launch)
                except urllib.error.HTTPError as e:
                    err = "premium" if e.code == 403 else "device" if e.code == 404 else ""
                    log(f"spotify api: {e}")
                except Exception as e:
                    log(f"spotify api: {e}")
            if done:
                say(("Playing " if action == "spotify_play" else "Queued ") + done + ".")
            elif sp.ready and err == "premium":
                say("Spotify only lets Premium accounts be controlled. I opened the search instead.")
                pc.launch("spotify:search:" + urllib.parse.quote(arg))
            elif sp.ready and not err:
                say(f"I couldn't find {arg} on Spotify.")
            else:
                pc.launch("spotify:search:" + urllib.parse.quote(arg))
                say(f"Pulled up {arg} on Spotify.")
        elif action == "site":
            pc.open_url(SITES[arg], app_window=(arg == "hq" and HQ_FULLSCREEN))
            say("Opening " + ("HQ" if arg == "hq" else arg) + ".")
        elif action == "app":
            if arg in ("chrome", "edge"):
                pc.open_url("about:blank", app_window=None)
            else:
                pc.launch(APPS[arg])
            say("Opening " + arg + ".")
        return True


def doctor():
    ok = lambda b: "PASS" if b else "FAIL"
    print(f"python {sys.version.split()[0]}  {ok(sys.version_info[:2] in ((3, 11), (3, 12)))} (needs 3.11 or 3.12)")
    try:
        import torch
        cuda = torch.cuda.is_available()
        print(f"torch {torch.__version__} cuda {ok(cuda)}" + (f"  {torch.cuda.get_device_name(0)} sm_{''.join(map(str, torch.cuda.get_device_capability(0)))}" if cuda else ""))
    except Exception as e:
        print(f"torch FAIL ({e})")
    print("cuda dll folders:", len(add_cuda_dlls()))
    try:
        _, dev = load_whisper()
        print(f"whisper {ok(dev == 'cuda')} on {dev}")
    except Exception as e:
        print(f"whisper FAIL ({e})")
    try:
        sd = _sd()
        mic, spk = resolve_devices()
        name = sd.query_devices(mic)["name"] if mic is not None else "Windows default"
        print(f"mic {ok(mic is not None)} -> {mic}: {name}" + ("" if mic is not None else "  (no Focusrite found by name; set MIC_DEVICE)"))
        print(f"speaker -> {spk if spk is not None else 'Windows default'}: {sd.query_devices(kind='output')['name'] if spk is None else sd.query_devices(spk)['name']}")
    except Exception as e:
        print(f"audio FAIL ({e})")
    c = find_claude()
    print(f"claude {ok(bool(c))} -> {c}")
    if c:
        try:
            out = subprocess.run([c, "mcp", "list"], capture_output=True, text=True, timeout=60, encoding="utf-8").stdout
            print("claude connectors:\n" + "\n".join("   " + l for l in out.strip().splitlines()[:20]))
            names = re.findall(r"claude\.ai ([\w ]+?):", out)
            if names:
                print("   tool prefixes to use:", ", ".join("mcp__claude_ai_" + n.strip().replace(" ", "_") for n in names))
        except Exception as e:
            print(f"   could not list connectors ({e})")
    print(f"spotify api {'connected' if Spotify().ready else 'off (media keys only)'}")
    v = jarvis_brain.Vault()
    print(f"vault -> {v.root}  " + ("Obsidian PASS" if v.is_obsidian else "plain folder (open it in Obsidian as a vault, or set VAULT)"))
    print(f"idle seconds now: {jarvis_brain.idle_seconds():.0f}")


def levels():
    """Live meter: talk, clap, say 'hey jarvis' and watch the numbers to tune the settings at the top."""
    from openwakeword.model import Model
    from openwakeword.utils import download_models
    download_models([WAKE_WORD])
    wake = Model(wakeword_models=[WAKE_WORD], inference_framework="onnx")
    claps = ClapDetector()
    mic, _ = resolve_devices()
    print(f"CLAP_LEVEL {CLAP_LEVEL}  CLAP_CREST {CLAP_CREST}  WAKE_THRESHOLD {WAKE_THRESHOLD}. Ctrl+C to stop.")
    with Mic(mic):
        while True:
            f = audio_q.get()
            peak, rms = frame_stats(f)
            crest = peak / max(rms, 1e-6)
            score = wake.predict(f).get(WAKE_WORD, 0)
            double = claps.feed(f)
            bar = "#" * int(peak * 40)
            tag = "  << DOUBLE CLAP" if double else "  < clap" if peak >= CLAP_LEVEL and crest >= CLAP_CREST else ""
            tag += "  << WAKE" if score >= WAKE_THRESHOLD else ""
            if peak > 0.02 or tag:
                print(f"peak {peak:4.2f} crest {crest:4.1f} wake {score:4.2f} |{bar:<40}|{tag}", flush=True)


def main():
    if "--profiles" in sys.argv:
        pick = browser_profile()
        for d, n, e in browser_profiles():
            print(("-> " if d == pick else "   ") + f"{d:12} {n:20} {e}")
        print("\nJarvis opens: " + (pick or "the browser default (set BROWSER_PROFILE in local_settings.py)"))
        return
    if "--devices" in sys.argv:
        sd = _sd()
        mic, _ = resolve_devices()
        print(sd.query_devices())
        print(f"\nJarvis will use mic {mic}" + ("" if mic is not None else " (none matched, Windows default)"))
        return
    if "--doctor" in sys.argv:
        return doctor()
    if "--levels" in sys.argv:
        return levels()
    if "--phone" in sys.argv:
        jarvis_phone.NTFY_TOPIC = jarvis_phone.NTFY_TOPIC or NTFY_TOPIC
        print(jarvis_phone.setup_text())
        return
    if "--spotify-login" in sys.argv:
        return Spotify().login()
    if "--say" in sys.argv:
        return Speaker().say(sys.argv[sys.argv.index("--say") + 1])
    claude = find_claude()
    if not claude:
        sys.exit("Can't find the claude command. Install Claude Code and log in first.")
    if "--ask" in sys.argv:
        print(ask_claude(sys.argv[sys.argv.index("--ask") + 1], None, claude)[0])
        return

    from openwakeword.model import Model
    from openwakeword.utils import download_models
    download_models([WAKE_WORD])
    wake = Model(wakeword_models=[WAKE_WORD], inference_framework="onnx")

    jarvis_room.keep_awake()
    if ORB:
        pyw = os.path.join(os.path.dirname(sys.executable), "pythonw.exe")
        subprocess.Popen([pyw if os.path.exists(pyw) else sys.executable, os.path.join(WORKDIR, "jarvis_orb.py")], cwd=WORKDIR)
        jarvis_orb.send("thinking")   # loading models
    whisper, _ = load_whisper()
    speaker = Speaker()
    jarvis = Jarvis(speaker, claude=claude)
    global BRAIN
    BRAIN = jarvis.make_brain()
    BRAIN.start()
    jarvis.extras.start()
    if jarvis_phone.PHONE_SERVER:
        try:
            jarvis_phone.Bridge(jarvis.remote_ask, jarvis.phone_event).start()
        except Exception as e:
            log(f"phone bridge off: {e}")
    claps = ClapDetector()
    mic, _ = resolve_devices()

    with Mic(mic):
        noise = np.median([np.sqrt(np.mean(audio_q.get().astype(np.float32) ** 2)) for _ in range(25)])

        def record_long():
            drain_mic()
            jarvis_orb.send("listening")
            speaker.chime(660)
            a = record_until_silence(noise, silence=4.0, max_secs=180, wait_for_voice=10)
            jarvis_orb.send("thinking")
            return transcribe(whisper, a) if a is not None else ""
        jarvis.record_long = record_long
        jarvis.extras.record_long = record_long
        jarvis_orb.send("idle")
        log(f"listening for '{WAKE_WORD.replace('_', ' ')}'" + (" and double claps" if CLAP_WAKE else "") + f" (room noise {noise:.0f})")

        threading.Thread(target=nightly_update_watch, args=(jarvis,), daemon=True).start()
        while True:
            frame = audio_q.get()
            if jarvis.restart_for_update:
                jarvis_orb.send("quit")
                return 3   # start.bat pulls the new code and starts again
            if time.time() < jarvis.quiet_until:
                continue
            if CLAP_WAKE and claps.feed(frame):
                wake.reset()
                try:
                    jarvis.wake_room()
                except Exception as e:
                    log(f"wake failed: {e}")
                drain_mic()
                jarvis.quiet_until = time.time() + 1.0
                continue
            if wake.predict(frame).get(WAKE_WORD, 0) < WAKE_THRESHOLD:
                continue

            wake.reset()
            drain_mic()
            jarvis_orb.send("listening")
            speaker.chime()
            drain_mic()
            audio = record_until_silence(noise)
            if audio is None:
                jarvis_orb.send("idle")
                continue
            jarvis_orb.send("thinking")
            text = transcribe(whisper, audio)
            log(f"you: {text}")
            if not text:
                jarvis_orb.send("idle")
                continue
            try:
                with jarvis.lock:
                    keep = jarvis.handle(text)
                if not keep:
                    jarvis_orb.send("quit")
                    return
            except Exception as e:
                log(f"error: {e}")
                jarvis_orb.send("error")
                speaker.say("Something broke. Check the Jarvis window.")
            jarvis_orb.send("idle")
            drain_mic()                       # don't hear itself
            jarvis.quiet_until = time.time() + 1.0
            wake.reset()


if __name__ == "__main__":
    try:
        sys.exit(main() or 0)
    except KeyboardInterrupt:
        pass
