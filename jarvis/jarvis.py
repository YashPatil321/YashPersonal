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

import jarvis_autostart
import jarvis_brain
import jarvis_claude
import jarvis_extras
import jarvis_orb
import jarvis_phone
import jarvis_room
import jarvis_screen
import jarvis_vision
import jarvis_cad
import jarvis_desk
import jarvis_faces
import jarvis_hqsync
import jarvis_touch

# ---------------- settings you might change ----------------
MIC_DEVICE = None            # None = find the Focusrite by name. Or put a number from --devices
MIC_NAME_HINTS = ["focusrite", "scarlett"]
MIC_CHANNEL = 0              # Focusrite input 1 = 0, input 2 = 1
MIC_GAIN = 1.0               # software boost for a quiet mic (your Scarlett likes about 6)
SPEAKER_DEVICE = None        # None = Windows default output
ASSISTANT_NAME = "Jarvis"    # what it calls itself. The wake word is separate (below)
WAKE_WORD = "hey_jarvis"     # built in: hey_jarvis, alexa, hey_mycroft, hey_rhasspy. Or the path to your own .onnx wake word model
BARGE_THRESHOLD = 0.7        # how sure it must be it heard the wake word to cut itself off while talking (higher = fewer accidents)
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
# FULL_ACCESS: Claude can do anything on this PC (run commands, change files and settings) without asking.
# Always off in guest mode, so friends or a TV can't make it do things. Set False in local_settings.py to go back
# to Jarvis telling you what it wants to do and you saying "yes" first.
FULL_ACCESS = True
# What full access allows. These go in Claude Code's own allow list (C:\jarvis\.claude\settings.local.json, which
# Jarvis writes for you) and on every call, so it works even where Claude Code ignores its "skip permissions" switch.
FULL_TOOLS = ["Bash", "PowerShell", "Read", "Edit", "Write", "MultiEdit", "NotebookEdit", "Glob", "Grep", "WebFetch", "WebSearch",
              "Task", "TodoWrite", "mcp__claude_ai_Google_Calendar", "mcp__claude_ai_Gmail", "mcp__claude_ai_Google_Drive",
              "mcp__claude_ai_Spotify", "mcp__claude_ai_Solidhauz", "mcp__claude_ai_Vercel", "mcp__claude_ai_Supabase",
              "mcp__claude_ai_Claude_Code_Remote", "ArtifactData", "Artifact"]
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
for _mod in (jarvis_room, jarvis_orb, jarvis_claude, jarvis_screen, jarvis_brain, jarvis_extras, jarvis_phone, jarvis_vision, jarvis_faces, jarvis_touch, jarvis_desk, jarvis_cad, jarvis_autostart, jarvis_hqsync):
    for _k, _v in _mine.items():
        if hasattr(_mod, _k):
            setattr(_mod, _k, _v)
WAKE_PUSH = _mine.get("WAKE_PUSH", False)   # also ping your phone on every clap
if not NTFY_TOPIC:   # make a private phone topic once, so phone features are on out of the box
    _tf = os.path.join(os.path.dirname(os.path.abspath(__file__)), ".ntfy_topic")
    try:
        NTFY_TOPIC = open(_tf).read().strip()
    except OSError:
        NTFY_TOPIC = "yash-jarvis-" + secrets.token_hex(6)
        try:
            open(_tf, "w").write(NTFY_TOPIC)
        except OSError:
            pass
jarvis_phone.NTFY_TOPIC = jarvis_phone.NTFY_TOPIC or NTFY_TOPIC
if "CONNECTOR_TOOLS" in _mine and "ALLOWED_TOOLS" not in _mine:
    ALLOWED_TOOLS = "WebSearch,WebFetch,Edit(./notes/**)," + CONNECTOR_TOOLS

WAKE_KEY = os.path.splitext(os.path.basename(WAKE_WORD))[0] if WAKE_WORD.endswith(".onnx") else WAKE_WORD
RATE = 16000
FRAME = 1280   # 80 ms, what openWakeWord expects
STATE_FILE = os.path.join(WORKDIR, ".session.json")
SPOTIFY_FILE = os.path.join(WORKDIR, ".spotify.json")
IS_WIN = sys.platform == "win32"

SPOKEN_STYLE = (
    f"You are {ASSISTANT_NAME}, Yash's voice assistant. Everything you write is read aloud by a "
    "text to speech engine, so answer in plain spoken sentences. No markdown, no lists, "
    "no code blocks, no URLs, no emoji. Keep it under 80 words unless he asks for detail. "
    "For his calendar and email use the Google Calendar and Gmail tools. Times are Pacific."
)


LOG_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "jarvis.log")


def log(msg):
    """Prints, and keeps a copy in jarvis.log so problems are findable even when the window is hidden."""
    line = time.strftime("%Y-%m-%d %H:%M:%S ") + str(msg)
    print(line[11:], flush=True)
    try:
        if os.path.exists(LOG_FILE) and os.path.getsize(LOG_FILE) > 2_000_000:
            os.replace(LOG_FILE, LOG_FILE + ".old")
        with open(LOG_FILE, "a", encoding="utf-8") as f:
            f.write(line + "\n")
    except OSError:
        pass


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
        self.stop_flag = threading.Event()
        self.speaking = False
        self.interrupted = False
        self.watch = None   # watch(frame) -> True cuts Jarvis off mid sentence. Set in main: wake word or a double clap

    def stop(self):
        """Stop talking right now."""
        self.stop_flag.set()
        try:
            _sd().stop()
        except Exception:
            pass

    def _watch(self):
        """While Jarvis talks, keep listening for the wake word or a double clap, and stop talking if you do."""
        while self.speaking and not self.stop_flag.is_set():
            try:
                frame = audio_q.get(timeout=0.1)
            except queue.Empty:
                continue
            try:
                if self.watch(frame):
                    log("interrupted")
                    self.interrupted = True
                    self.stop()
                    return
            except Exception as e:
                log(f"interrupt watch: {e}")
                return

    capture = threading.local()   # a request from your phone collects the answer here instead of speaking

    def say(self, text):
        cap = getattr(Speaker.capture, "lines", None)
        if cap is not None:
            cap.append(re.sub(r"[*#`_>\[\]]", "", text))
            if not getattr(Speaker.capture, "speak", False):
                return
        self.stop_flag.clear()
        self.interrupted = False
        self.speaking = True
        jarvis_orb.send("speaking")
        if self.watch and threading.current_thread() is threading.main_thread():
            threading.Thread(target=self._watch, daemon=True).start()
        try:
            self._say(text)
        finally:
            self.speaking = False
            jarvis_orb.send("idle")

    def _say(self, text):
        sd = _sd()
        text = re.sub(r"[*#`_>\[\]]", "", text)
        text = re.sub(r"https?://\S+", "", text)
        print("  >>", text, flush=True)
        if self.kokoro:
            for _, _, audio in self.kokoro(text, voice=VOICE):
                if self.stop_flag.is_set():
                    break
                sd.play(audio, 24000, device=SPEAKER_DEVICE)
                end = time.time() + len(audio) / 24000 + 0.05
                while time.time() < end and not self.stop_flag.is_set():
                    time.sleep(0.02)
                if self.stop_flag.is_set():
                    sd.stop()
                    break
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
    t = re.sub(r"^\s*(hey\s+)?(jarvis|" + re.escape(ASSISTANT_NAME.lower()) + r")\s*", "", t)
    t = re.sub(r"\b(please|can you|could you|for me|real quick)\b", " ", t)
    t = re.sub(r"\s+", " ", t).strip()

    if re.fullmatch(r"(?:test|check) (?:the |my )?(?:computer|pc|screen) control|run (?:a )?(?:self ?test|diagnostics?)|(?:test|check) yourself", t):
        return ("test_pc", None)
    if re.fullmatch(r"(?:ok(?:ay)? )?(?:stop|stop talking|shut up|be quiet|quiet|enough|that's enough|hush|nevermind|never mind that)", t):
        return ("hush", None)
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
    # screen and Claude commands first: "type the weather is nice" must type, not check the weather
    cc = jarvis_screen.route_screen(t) if re.match(r"(?:type|press|hit) ", t) else None
    cc = cc or jarvis_claude.route_claude(t) or jarvis_screen.route_screen(t) \
        or jarvis_brain.route_brain(t) or jarvis_phone.route_phone(t) or jarvis_cad.route_cad(t) or jarvis_desk.route_desk(t) \
        or jarvis_touch.route_touch(t) or jarvis_faces.route_faces(t) or jarvis_vision.route_vision(t) or jarvis_extras.route_extras(t)
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

    # browser tabs and windows
    b = re.sub(r"\b(up|a|the|me|another|fresh|blank|empty)\b", " ", t)
    b = re.sub(r"\s+", " ", b).strip()
    m = re.fullmatch(r"(?:open|start|make|give|create|pull|bring)? ?new (?:chrome |browser |edge )?tab(?: in (?:chrome|edge|browser))?|(?:new )?(?:chrome|browser) tab|(?:open|give|make|start) tab", b)
    if m:
        return ("browser", ("tab", None))
    m = re.fullmatch(r"(?:open|start|make|give|create)? ?new (?:chrome |browser |edge )?window(?: in (?:chrome|edge))?|(?:new )?(?:chrome|browser) window", b)
    if m:
        return ("browser", ("window", None))
    m = re.fullmatch(r"(?:open|go to|pull|bring|load|show) (.+?) in new tab", b)
    if m and re.sub(r"^(?:my|the)\s+", "", m.group(1)) in SITES:
        return ("browser", ("tab", re.sub(r"^(?:my|the)\s+", "", m.group(1))))
    if re.fullmatch(r"close (?:this |that |the |current )?tab", t):
        return ("keys", "close tab")
    if re.fullmatch(r"(?:reopen|bring back|undo close)(?: the| that| my)?(?: last)?(?: closed)? tab", t):
        return ("keys", "reopen tab")

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


LAST_DENIED = []   # what Claude wanted to do but wasn't allowed to, from the last answer


def full_access_dirs():
    """Where full access may read and write: your home folder and, on Windows, every drive."""
    dirs = [os.path.expanduser("~")]
    if IS_WIN:
        import string
        dirs += [f"{d}:\\" for d in string.ascii_uppercase if os.path.exists(f"{d}:\\")]
    return dirs


def write_claude_permissions(full=None):
    """Claude Code reads .claude/settings.local.json in Jarvis's folder. With full access on, Jarvis keeps an allow
    list there so Claude never has to ask (it can't show you a prompt from the background). Turning full access off
    takes Jarvis's entries back out. Anything you added yourself is left alone."""
    full = FULL_ACCESS if full is None else full
    path = os.path.join(WORKDIR, ".claude", "settings.local.json")
    try:
        with open(path, encoding="utf-8") as f:
            cfg = json.load(f)
    except Exception:
        cfg = {}
    perms = cfg.setdefault("permissions", {})
    mine = set(cfg.get("_jarvis_added", []))
    allow = [a for a in perms.get("allow", []) if a not in mine]
    if full:
        add = [t for t in FULL_TOOLS if t not in allow]
        perms["allow"] = allow + add
        perms["additionalDirectories"] = sorted(set(perms.get("additionalDirectories", [])) | set(full_access_dirs()))
        perms["defaultMode"] = "bypassPermissions"
        cfg["_jarvis_added"] = add
    else:
        perms["allow"] = allow
        if perms.get("defaultMode") == "bypassPermissions":
            perms.pop("defaultMode")
        cfg.pop("_jarvis_added", None)
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(cfg, f, indent=2)
    return path


def describe_denied(denied):
    """'run a command: Get-ScheduledTask ...' in a few spoken words."""
    if not denied:
        return ""
    d = denied[0]
    tool, inp = d.get("tool_name", "something"), d.get("tool_input") or {}
    what = inp.get("command") or inp.get("file_path") or inp.get("path") or inp.get("url") or ""
    what = re.sub(r"\s+", " ", str(what))[:90]
    verb = {"Bash": "run a command", "PowerShell": "run a command", "Edit": "change a file", "Write": "write a file",
            "MultiEdit": "change a file", "NotebookEdit": "change a notebook"}.get(tool, "use " + tool)
    more = f", and {len(denied) - 1} more step{'s' if len(denied) > 2 else ''}" if len(denied) > 1 else ""
    return f"{verb}{': ' + what if what else ''}{more}"


def ask_claude(prompt, session_id, claude=None, tools=None, full=False):
    """The question goes in on stdin, never on the command line, so nothing you say can run as a command.
    full=True lets Claude do anything on this PC (only after you said yes, or with FULL_ACCESS on)."""
    global LAST_DENIED
    claude = claude or find_claude()
    full = full or (FULL_ACCESS and not (BRAIN and BRAIN.guest))
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
    if full:
        cmd[cmd.index("--allowedTools") + 1] = tools + "," + ",".join(FULL_TOOLS)
        cmd += ["--dangerously-skip-permissions"]
        for d in full_access_dirs():
            cmd += ["--add-dir", d]
    if session_id:
        cmd += ["--resume", session_id]
    r = subprocess.run(cmd, cwd=WORKDIR, input=prompt, capture_output=True, text=True, encoding="utf-8",
                       timeout=300, creationflags=0x08000000 if IS_WIN else 0)
    if r.returncode != 0 and session_id:
        return ask_claude(prompt, None, claude, tools, full)   # old session gone, start a new one
    try:
        data = json.loads(r.stdout)
    except Exception:
        log(f"claude failed (code {r.returncode}): {(r.stderr or r.stdout)[:400]}")
        return "I couldn't reach Claude. Check the Jarvis window.", session_id
    LAST_DENIED = data.get("permission_denials") or []
    if LAST_DENIED:
        log("claude wanted to: " + "; ".join(describe_denied([d]) for d in LAST_DENIED[:5]))
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
        self.vision = None
        self.desk = None
        self.cad = None
        self.listen_requested = False   # a peace sign to the camera works like the wake word
        self.last_wake = 0.0
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

    def gesture(self, name):
        """A hand gesture from the camera."""
        log(f"gesture: {name}")
        pc = self.pc
        if self.speaker.speaking and name in ("palm", "fist"):
            self.speaker.stop()   # hand up = stop talking
            return
        if name == "peace":
            self.listen_requested = True
        elif name == "palm":
            pc.key("play_pause")
        elif name == "swipe_right":
            pc.key("next")
        elif name == "swipe_left":
            pc.key("prev")
        elif name == "point_up":
            pc.key("vol_up", 2)
        elif name == "point_down":
            pc.key("vol_down", 2)
        elif name == "fist":
            pc.key("mute")
        elif name == "thumbs_up":
            if self.pending:
                with self.lock:
                    self.run("confirm", True)
        elif name == "wave":
            if time.time() - self.last_wake > 600:
                with self.lock:
                    self.wake_room()
            else:
                self.speaker.say("Hey.")
        if name not in ("point_up", "point_down", "peace", "wave"):
            threading.Thread(target=lambda: self.speaker.chime(1480), daemon=True).start()

    def local_url(self, path):
        return f"http://127.0.0.1:{jarvis_phone.PHONE_PORT}{path}?token={jarvis_phone.token()}"

    def open_desk_page(self, path):
        """Opens the desk full screen on the projector."""
        scr = jarvis_desk.projector_screen()
        url = self.local_url(path)
        exe, prof = browser_exe(), browser_profile()
        if IS_WIN and exe and scr:
            x, y, w, h, _ = scr
            args = [exe] + (["--profile-directory=" + prof] if prof else []) + ["--app=" + url, f"--window-position={x},{y}", f"--window-size={w},{h}"]
            subprocess.Popen(args)

            def fit():   # Chrome sometimes ignores the position, so move it there ourselves
                time.sleep(3)
                sc = jarvis_screen.Screen()
                for hwnd, _, title in sc.windows():
                    if title.startswith("Jarvis Desk") or title.startswith("Jarvis Hologram"):
                        sc.place(hwnd, (x, y, w, h))
                        sc.focus(hwnd)
                        time.sleep(0.3)
                        import ctypes
                        ctypes.windll.user32.keybd_event(0x7A, 0, 0, 0)   # F11: full screen, no title bar
                        ctypes.windll.user32.keybd_event(0x7A, 0, 2, 0)
                        break
            threading.Thread(target=fit, daemon=True).start()
        else:
            self.pc.open_url(url, app_window=True)

    def desk_state(self):
        """What the desk panels show."""
        b, out = self.brain, {}
        now = time.time()
        if b:
            lt = time.localtime()
            base = time.mktime((lt.tm_year, lt.tm_mon, lt.tm_mday, 0, 0, 0, 0, 0, -1))
            evs = []
            for e in getattr(b.planner, "events", []):
                m = re.match(r"(\d{1,2}):(\d{2})", str(e.get("start", "")))
                if m:
                    at = base + int(m.group(1)) * 3600 + int(m.group(2)) * 60
                    if at > now - 300:
                        evs.append((at, e))
            evs.sort(key=lambda x: x[0])
            if evs:
                at, e = evs[0]
                leave = next(((a, x) for a, x in evs if x.get("leave") or str(x.get("title", "")).lower().startswith("leave")), None)
                out["next"] = {"title": e.get("title", ""), "when": time.strftime("%I:%M %p", time.localtime(at)).lstrip("0"),
                               "leave_in": int((leave[0] - now) / 60) if leave else None}
            out["log"] = [{"t": l[2:7], "text": l[8:]} for l in b.vault.today_log(8).splitlines()]
            out["season"] = b.season.spoken()
            out["streaks"] = jarvis_brain.streak_line(jarvis_brain.streaks(b.vault))
            if b.focus_started and b.focus_timer:
                out["focus"] = {"total": int(b.focus_timer.interval / 60), "done": int((now - b.focus_started) / 60)}
            out["focus_today"] = jarvis_brain.focus_minutes(b.vault.read(b.vault.daily_rel()))
        cache = getattr(self, "_desk_cache", {})
        self._desk_cache = cache
        if now - cache.get("music_t", 0) > 6:
            cache["music"], cache["music_t"] = self.pc.spotify_title(), now
        if now - cache.get("wx_t", 0) > 600:
            cache["wx"], cache["wx_t"] = jarvis_extras.weather_brief(), now
        out["music"], out["weather"] = cache.get("music"), cache.get("wx")
        if self.vision and self.vision.last_seen_names:
            out["people"] = ", ".join(("Yash" if n == jarvis_faces.OWNER else jarvis_faces.spoken_name(n)) if n else "a guest"
                                      for n in self.vision.last_seen_names)
        return out

    def people(self, arrived, left, room, lock=False):
        """Face ID: who came and went."""
        F, b = jarvis_faces, self.brain
        if lock:
            log("someone else at the desk while you're away, locking")
            self.pc.lock()
            if b:
                b.vault.log("Locked the PC, someone else was at the desk")
            jarvis_phone.push("Someone was at your PC while you were gone, so I locked it.", "Jarvis security", priority=5, tags="lock")
            return
        log(f"people: +{sorted(arrived)} -{sorted(left)}")
        others = room.others()
        if b and F.AUTO_GUEST:
            if others and not b.guest:
                b.guest = True
                b.auto_guest = True
            elif not others and getattr(b, "auto_guest", False):
                b.guest, b.auto_guest = False, False
                b.flush_news()
        greeted = getattr(self, "greeted", {})
        self.greeted = greeted
        for n in arrived:
            if n in ("?", F.OWNER):
                continue
            if time.time() - greeted.get(n, 0) > 1800 and not jarvis_brain.quiet_now():
                greeted[n] = time.time()
                self.speaker.say(f"Hey {F.spoken_name(n)}.")
            if b:
                b.vault.log(f"{F.spoken_name(n)} came by")

    def wake_room(self):
        """The walk in scene. Opening HQ here also tells HQ on the iPad to wake up."""
        self.last_wake = time.time()
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
        if NTFY_TOPIC and WAKE_PUSH:
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
        guest = bool(self.brain and self.brain.guest)
        full = FULL_ACCESS and not guest
        answer, self.session_id = ask_claude(text, self.session_id, self.claude, full=full)
        save_session(self.session_id)
        denied = list(LAST_DENIED)
        if denied and not full and not guest:
            # Claude needed a permission it can't ask for on screen, so ask out loud instead
            what = describe_denied(denied)
            self.speaker.say(f"To do that I need to {what}. Say yes to let me, just this once.")

            def go():
                self.speaker.say("On it.")
                ans, self.session_id = ask_claude(f"I approved it. Go ahead and do what I asked: {text}", self.session_id,
                                                  self.claude, full=True)
                save_session(self.session_id)
                self.speaker.say(ans)
            self.pending = go
            return True
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
        if action == "browser":
            kind, site = arg
            new = ("edge://newtab/" if BROWSER == "edge" else "chrome://newtab/")
            url = SITES.get(site, new) if site else new
            # handing the address to the browser opens it in your profile: a new tab in the open window,
            # or a new window when you asked for one. No focus tricks needed.
            pc.open_url(url, app_window=None if kind == "window" else False)
            say(("New window." if kind == "window" else "New tab.") if not site else f"Opening {site} in a new tab.")
            return True
        if action == "hush":
            self.pending = None
            return True
        if action == "test_pc":
            say("Testing computer control. I'll open Notepad and move it around. Don't touch the mouse for a few seconds.")
            res = jarvis_screen.selftest(log=log, launch=pc.launch)
            bad = [(n, fix) for n, ok, fix in res if not ok]
            if not bad:
                say("Everything works. Moving windows, focus, typing and shortcuts all passed.")
            else:
                say(f"{len(bad)} problem{'s' if len(bad) > 1 else ''}. First one: {bad[0][0]}. {bad[0][1]} The full list is in the Jarvis log.")
            return True
        if action == "update":
            if update_waiting():
                say("Updating. Back in a few seconds.")
                self.restart_for_update = True
            elif not shutil.which("git"):
                say("I can't update myself because Git isn't installed. Run the installer once from PowerShell.")
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
        if action.startswith("cad_"):
            hub = self.cad
            if not hub:
                say("The workshop needs the phone bridge on. Set PHONE SERVER to True.")
                return True
            if action == "cad_open":
                models = hub.models()
                if not models:
                    say("I didn't find any CAD files in Downloads, Documents or Desktop. Export a STEP or STL and try again.")
                    return True
                path = jarvis_cad.match_model(arg, models) if arg else models[0][0]
                if not path:
                    say(f"I couldn't find a model called {arg}.")
                    return True
                hub.active = True
                if not getattr(self, "cad_page_open", False):
                    pc.open_url(self.local_url("/cad"), app_window=True)
                    self.cad_page_open = True
                    threading.Timer(2.5, lambda: hub.open(path)).start()
                else:
                    hub.open(path)
                name = os.path.splitext(os.path.basename(path))[0]
                say(f"Opening {name}. Pinch to spin it, two hands to zoom, open both palms to explode it." if self.vision else f"Opening {name}.")
            elif action == "cad_next":
                models = hub.models()
                paths = [m[0] for m in models]
                i = (paths.index(hub.current) + 1) % len(paths) if hub.current in paths else 0
                if paths:
                    hub.open(paths[i])
                    say(os.path.splitext(os.path.basename(paths[i]))[0] + ".")
            elif action == "cad_cmd":
                c, v = arg
                hub.send(c, value=v)
                say({"explode": "Exploding." if v else "Putting it back together.", "section": "Cutting it open." if v else "Closed.",
                     "look": {"wire": "Wireframe.", "solid": "Solid.", "holo": "Hologram."}.get(v, ""), "reset": "Reset.",
                     "spin": "Spinning." if v else "Holding still.", "snapshot": "Taking a picture."}.get(c, ""))
            elif action == "cad_holo":
                pc.open_url(self.local_url("/cad") + "&holo=1", app_window=True)
                say("Hologram view open. Put it under the pyramid, or open the hologram link on the iPad.")
            elif action == "cad_size":
                inf = hub.info
                if not inf.get("size_mm"):
                    say("No model is open.")
                else:
                    x, z, y = inf["size_mm"][0], inf["size_mm"][2], inf["size_mm"][1]
                    fmt = lambda v: f"{v / 25.4:.1f} inches" if v > 0 else "0"
                    sel = inf.get("selected")
                    line = f"It's {round(x)} by {round(z)} by {round(y)} millimeters, about {fmt(x)} by {fmt(z)} by {fmt(y)}, with {inf.get('parts', 0)} parts."
                    if sel:
                        sx, sz, sy = sel["size"]
                        line += f" The selected {sel['name']} is {sx:g} by {sz:g} by {sy:g} millimeters."
                    say(line)
            elif action == "cad_part":
                sel = hub.info.get("selected")
                say(f"That's the {sel['name']}, {' by '.join(f'{v:g}' for v in sel['size'])} millimeters." if sel else "Nothing is selected. Quick pinch on a part to pick it.")
            elif action == "cad_close":
                hub.active = False
                hub.send("close")
                say("Workshop closed.")
            return True
        if action in ("desk", "desk_cal", "desk_cards", "holo"):
            d = self.desk
            if not d:
                say("The desk needs the phone bridge on. Set PHONE SERVER to True.")
            elif action == "desk":
                if arg:
                    d.start()
                    self.open_desk_page("/desk")
                    say("Desk online." + ("" if d.cal.ready else " First time: say calibrate the desk."))
                else:
                    d.stop()
                    say("Desk off.")
            elif action == "desk_cal":
                self.open_desk_page("/desk")
                say("Calibrating. Keep your hands off the desk for a second.")
                d.calibrate(lambda ok: say("Desk calibrated. Touch anything."))
            elif action == "desk_cards":
                pc.open_url(self.local_url("/desk/cards"))
                say("Your desk cards are open. Print them, cut them out, and put them on the desk.")
            elif action == "holo":
                pc.open_url(self.local_url("/holo"), app_window=True)
                say("Hologram up. For the iPad pyramid, open the hologram link from jarvis dot py dash dash desk on the iPad.")
            return True
        if action in ("touch", "face_learn", "face_forget", "face_who", "face_list"):
            v = self.vision
            if not v or not v.ok:
                say("The camera isn't running. Install mediapipe and opencv, then set VISION to True in local settings.")
            elif action == "touch":
                if arg:
                    v.touch = (jarvis_touch.TouchController(), jarvis_touch.WindowsTouch(on_exit=lambda: self.run("touch", False)))
                    say("Touch mode. Move your hand to drive, pinch to click, hold the pinch to drag, make a fist to grab a window. "
                        "Hold your palm open for two seconds to stop.")
                else:
                    was, v.touch = v.touch, None
                    say("Touch mode off." if was else "Touch mode wasn't on.")
            elif not v.faceid:
                say("Face ID didn't load. Check the Jarvis window for the reason.")
            elif action == "face_learn":
                who = "you" if arg == jarvis_faces.OWNER else jarvis_faces.spoken_name(arg)
                say(f"Look at the camera, {'' if who == 'you' else who + ', '}and turn your head a little side to side.")

                def done(name, n):
                    if not name:
                        say("I couldn't see a face. Get closer to the camera and try again.")
                    elif name == jarvis_faces.OWNER:
                        say(f"Got you, Yash. I'll know it's you from now on.")
                    else:
                        say(f"Nice to meet you, {jarvis_faces.spoken_name(name)}.")
                v.learn_face(arg, done)
            elif action == "face_forget":
                ok = v.faceid.book.forget(arg)
                say("Forgotten." if ok else f"I don't know {jarvis_faces.spoken_name(arg)}.")
            elif action == "face_who":
                names = v.last_seen_names
                if not names:
                    say("I don't see anyone.")
                else:
                    known = [("you, Yash" if n == jarvis_faces.OWNER else jarvis_faces.spoken_name(n)) for n in names if n]
                    unknown = sum(1 for n in names if not n)
                    parts = known + ([f"{unknown} person I don't know" if unknown == 1 else f"{unknown} people I don't know"] if unknown else [])
                    say("I see " + " and ".join(parts) + ".")
            elif action == "face_list":
                ppl = [("you" if n == jarvis_faces.OWNER else jarvis_faces.spoken_name(n)) for n in v.faceid.book.people]
                say("I know " + ", ".join(ppl) + "." if ppl else "I don't know anyone yet. Say learn my face.")
            return True
        if action == "camera_look":
            if self.vision and not self.vision.enabled:
                say("My camera's off. Say camera on and ask again.")
                return True
            path = os.path.join(WORKDIR, ".cache", "camera.jpg")
            try:
                got = self.vision.snapshot(path) if self.vision else jarvis_vision.grab_frame(path)
            except Exception as e:
                log(f"camera look: {e}")
                got = None
            if not got:
                say("I can't see anything. Is the webcam plugged in? Install the camera parts with python update.py dash dash extras.")
                return True
            say("Looking.")
            try:
                ans = ask_claude(f"Read the image at {got}. It's a webcam photo of Yash at his desk, taken just now. He asked out loud: "
                                 f"'{arg}'. Answer out loud in under 45 words like a friend in the room: what he's doing, what he's holding "
                                 "or what's around him, whatever answers his question. Don't comment on his looks unless he asked.",
                                 None, self.claude, tools="Read")[0]
            finally:
                try:
                    os.remove(got)   # never kept
                except OSError:
                    pass
            say(ans)
            return True
        if action in ("reps", "reps_stop", "camera", "gestures_help"):
            v = self.vision
            if action == "gestures_help":
                say(jarvis_vision.GESTURE_HELP if v else "The camera is off. Install mediapipe and opencv, then set VISION to True.")
            elif not v:
                say("The camera isn't set up. Install mediapipe and opencv, then set VISION to True in local settings.")
            elif action == "reps":
                def done(ex, n):
                    if self.brain and n:
                        jarvis_extras.Training(self.brain.vault).add(f"{n} {ex}", None, None)
                    say(f"{n} {ex}. " + ("Logged it. " if n else "") + ("Strong set." if n >= 20 else "Nice." if n else "I didn't count any. Get your whole body in the camera."))
                v.count(arg, done)
                say(f"Counting {arg}. Get your whole body in the camera. Say done when you're finished.")
            elif action == "reps_stop":
                if not v.stop_count():
                    say("I wasn't counting anything.")
            elif action == "camera":
                v.enabled = arg
                say("Camera on. I can see you." if arg else "Camera off. I can't see anything now. Say camera on to bring it back.")
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
    import importlib.util as _u
    for pkg, mod in (("pillow", "PIL"), ("opencv", "cv2"), ("mediapipe", "mediapipe")):
        print(f"{pkg}: {'PASS' if _u.find_spec(mod) else 'missing (python update.py --extras)'}")
    print(f"phone topic: {NTFY_TOPIC}  (subscribe to this in the ntfy app)")
    print(f"camera: {'on' if jarvis_vision.VISION else 'off'}, face id {'on' if jarvis_faces.FACES else 'off'}, "
          f"faces known: {', '.join(jarvis_faces.FaceBook().people) or 'none yet'}")
    v = jarvis_brain.Vault()
    print(f"vault -> {v.root}  " + ("Obsidian PASS" if v.is_obsidian else "plain folder (open it in Obsidian as a vault, or set VAULT)"))
    print(f"idle seconds now: {jarvis_brain.idle_seconds():.0f}")


def levels():
    """Live meter: talk, clap, say 'hey jarvis' and watch the numbers to tune the settings at the top."""
    from openwakeword.model import Model
    from openwakeword.utils import download_models
    if not WAKE_WORD.endswith(".onnx"):
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
            score = wake.predict(f).get(WAKE_KEY, 0)
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
    if "--test-pc" in sys.argv:
        res = jarvis_screen.selftest()
        with open(os.path.join(WORKDIR, "pc-test.txt"), "w", encoding="utf-8") as f:
            f.write("\n".join(("PASS " if ok else "FAIL ") + n + ("" if ok else "  fix: " + fix) for n, ok, fix in res))
        print("\nSaved to pc-test.txt")
        return
    if "--desk" in sys.argv:
        ip, tok = jarvis_phone.lan_ip(), jarvis_phone.token()
        base = f"http://{ip}:{jarvis_phone.PHONE_PORT}"
        print(f"Desk (projector):   {base}/desk?token={tok}")
        print(f"Hologram, 4 views:  {base}/holo?token={tok}   (iPad under a Pepper's ghost pyramid)")
        print(f"Hologram, 1 view:   {base}/holo?single=1&token={tok}   (LED hologram fan or transparent screen)")
        print(f"Desk cards to print: {base}/desk/cards?token={tok}")
        print(f"CAD workshop:       {base}/cad?token={tok}")
        print(f"CAD hologram:       {base}/cad?holo=1&token={tok}   (your model under the pyramid on the iPad)")
        print("Jarvis must be running for these links to work.")
        return
    if "--vision" in sys.argv:
        return jarvis_vision.preview()
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
    if not WAKE_WORD.endswith(".onnx"):
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
    try:
        log("claude permissions: " + write_claude_permissions())
    except Exception as e:
        log(f"couldn't write Claude's permissions file: {e}")
    # how was I started, and can I actually control windows? fixes the startup task if it can, says so if not
    threading.Thread(target=lambda: jarvis_autostart.check(log=log, say=speaker.say), daemon=True).start()
    global BRAIN
    BRAIN = jarvis.make_brain()
    BRAIN.start()
    jarvis.extras.start()
    jarvis.hqsync = jarvis_hqsync.HQSync(jarvis).start()   # what Jarvis is doing, on HQ on the iPad
    if jarvis_vision.VISION:
        jarvis.vision = jarvis_vision.Vision(on_gesture=jarvis.gesture, say=speaker.say, on_people=jarvis.people).start()
        if jarvis_vision.PRESENCE_FROM_CAMERA:
            BRAIN.presence.idle = lambda: min(jarvis_brain.idle_seconds(), jarvis.vision.seconds_since_face())
    if jarvis_phone.PHONE_SERVER:
        try:
            bridge = jarvis_phone.Bridge(jarvis.remote_ask, jarvis.phone_event).start()
            jarvis.cad = jarvis_cad.CadHub(say=speaker.say)
            jarvis_cad.SNAP_DIR = os.path.join(BRAIN.vault.root, "CAD")
            if BRAIN.vault.root not in jarvis_cad.CAD_FOLDERS:
                jarvis_cad.CAD_FOLDERS.append(BRAIN.vault.root)
            jarvis.cad.register(bridge)
            if jarvis.vision:
                jarvis.vision.cad = jarvis.cad
            if jarvis_desk.DESK:
                jarvis.desk = jarvis_desk.Desk(lambda phrase: jarvis.remote_ask(phrase, speak=True), jarvis.pc.key,
                                               state=jarvis.desk_state, say=speaker.say)
                jarvis.desk.register(bridge)
        except Exception as e:
            log(f"phone bridge off: {e}")
    claps = ClapDetector()
    mic, _ = resolve_devices()

    def barge(frame):
        if CLAP_WAKE and claps.feed(frame):
            return True
        return wake.predict(frame).get(WAKE_KEY, 0) >= max(WAKE_THRESHOLD, BARGE_THRESHOLD)
    speaker.watch = barge

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
                hard_exit(3, "restarting into the update")   # start.bat pulls the new code and starts again
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
            if jarvis.listen_requested:
                jarvis.listen_requested = False   # peace sign to the camera
            elif wake.predict(frame).get(WAKE_KEY, 0) < WAKE_THRESHOLD:
                continue

            wake.reset()
            if speaker.speaking:
                speaker.stop()
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
                    hard_exit(0, "going offline")
            except Exception as e:
                log(f"error: {e}")
                jarvis_orb.send("error")
                speaker.say("Something broke. Check the Jarvis window.")
            jarvis_orb.send("idle")
            if speaker.interrupted:           # you cut it off: it stops talking and listens to you right away
                speaker.interrupted = False
                jarvis.listen_requested = True
                wake.reset()
                continue
            drain_mic()                       # don't hear itself
            jarvis.quiet_until = time.time() + 1.0
            wake.reset()


def hard_exit(code, why=""):
    """Ends Jarvis right now. A normal exit waits for every background part (audio, the voice model, the GPU
    speech engine, open connections) to stop by itself, and on Windows one of them can hang forever, which left
    Jarvis stuck after "Updating. Back in a few seconds." This doesn't wait."""
    log(f"exit {code}: {why}")
    try:
        jarvis_orb.send("quit")
        sys.stdout.flush()
        sys.stderr.flush()
    except Exception:
        pass
    os._exit(code)


if __name__ == "__main__":
    try:
        sys.exit(main() or 0)
    except KeyboardInterrupt:
        pass
