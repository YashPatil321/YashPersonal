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

import os as _os
_os.environ.setdefault("GLOG_minloglevel", "3")          # mediapipe's C++ chatter
_os.environ.setdefault("TF_CPP_MIN_LOG_LEVEL", "3")
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

import jarvis_activity
import jarvis_autostart
import jarvis_brain
import jarvis_claude
import jarvis_extras
import jarvis_orb
import jarvis_phone
import jarvis_room
import jarvis_wake
import jarvis_chats
import jarvis_chatui
import jarvis_evolve
import jarvis_multi
import jarvis_persona
import jarvis_vaultstyle
import jarvis_learn
import jarvis_audio
import jarvis_routines
import jarvis_trust
import jarvis_screen
import jarvis_vision
import jarvis_cad
import jarvis_desk
import jarvis_faces
import jarvis_memory
import jarvis_hqsync
import jarvis_touch
import jarvis_uia

# ---------------- settings you might change ----------------
MIC_DEVICE = None            # None = find the Focusrite by name. Or put a number from --devices
MIC_NAME_HINTS = ["focusrite", "scarlett"]
MIC_CHANNEL = 0              # Focusrite input 1 = 0, input 2 = 1
MIC_GAIN = 1.0               # software boost for a quiet mic (your Scarlett likes about 6)
SPEAKER_DEVICE = None        # None = Windows default output
ASSISTANT_NAME = "Atlas"     # what it calls itself, and (with WAKE_NAME) what you call it
WAKE_NAME = "atlas"          # say this name to wake it ("Atlas" or "Atlas, what's my day look like"). "" turns it off
WAKE_WORD = "hey_jarvis"     # built in: hey_jarvis, alexa, hey_mycroft, hey_rhasspy. Or the path to your own .onnx wake word model
BARGE_THRESHOLD = 0.7        # how sure it must be it heard the wake word to cut itself off while talking (higher = fewer accidents)
WAKE_THRESHOLD = 0.5         # raise to 0.6 or 0.7 if it triggers by accident
WHISPER_MODEL = "large-v3-turbo"   # "small.en" if your GPU setup gives you trouble
VOICE = "am_michael"         # kokoro voices: am_michael, am_fenrir, am_puck, bm_george, af_heart ...
VOICE_SPEED = 1.06           # kokoro: a touch quicker sounds more like a person and less like a reader
# The most human voice: ElevenLabs. Make a free account at elevenlabs.io, copy your API key, put it here
# (in local_settings.py). Pick a voice by name with "change your voice to Chris" (or paste any voice id).
ELEVENLABS_KEY = ""
ELEVEN_VOICE = "Chris"
ELEVEN_MODEL = "eleven_flash_v2_5"   # fastest; "eleven_multilingual_v2" sounds a little richer but is slower
ELEVEN_VOICES = {   # ElevenLabs' built in voices
    "chris": "iP95p4xoKVk53GoZ742B", "brian": "nPczCjzI2devNBz1zQrb", "will": "bIHbv24MWmeRgasZH58o",
    "eric": "cjVigY5qzO86Huf0OWal", "liam": "TX3LPaxmHKxFdv7VOQHJ", "adam": "pNInz6obpgDQGcFmaJgB",
    "roger": "CwhRBWXzGAHq8TQ4Fs17", "george": "JBFqnCBsd6RMkjVDRZzb", "daniel": "onwK4e9ZLuTAKqWW03F9",
    "charlie": "IKne3meq5aSn9XLyUdCD", "callum": "N2lVS1w4EtoT3dr4eOWO",
}
SILENCE_SECONDS = 1.0        # how long you pause before it stops recording
CLAUDE_MODEL = "sonnet"      # the brain for voice answers: sonnet is fast and sharp. "opus" for the deepest thinking (slower)
STREAM = True                # start talking at the first sentence instead of waiting for the whole answer
TELEGRAM_TOKEN = ""          # your own Telegram bot (from @BotFather) to talk to Atlas from your phone. See jarvis_trust.py
TELEGRAM_CHAT_ID = 0         # filled in automatically when you pair
PUSH_TO_TALK = True          # Ctrl+Alt+Space anywhere in Windows = talk to Atlas (no wake word, works with loud music)
VOICE_INPUT = True           # False = no mic at all: you type to Atlas in its window (say or type "voice off" / "voice on")
CHAT_ON_START = True         # open the Atlas chat window every time Atlas starts
TYPE_TO_ATLAS = True         # type commands into the Atlas window too (handy with no mic or no GPU)
FOLLOWUP_SECONDS = 6         # after Atlas talks, just keep talking: no need to say its name again for this long (0 = off)
KEEP_LISTENING = True        # while Claude thinks, Atlas still hears you, so you can give it more commands
# words Whisper should expect, so names come out right. Add your own in local_settings.py as VOCAB_EXTRA
VOCAB = ("Yash, Atlas, Jarvis, SolidHauz, Del Norte, Nighthawks, O'Rielly, Coach Roty, Babson, UC, USC, Common App, Obsidian, "
         "Spotify, Claude, Claude Code, Vercel, Supabase, GitHub, HQ, ProMX, San Pasqual, Torrey Pines, Calexico, 4S Ranch, "
         "VS Code, WhatsApp, iPad, CAD, STEP file, Chrome, YouTube, Gmail, lock in, focus mode")
VOCAB_EXTRA = ""
MAX_RECORD_SECONDS = 30
WORKDIR = os.path.dirname(os.path.abspath(__file__))   # Claude reads CLAUDE.md from here
HQ_URL = "https://claude.ai/artifact/9ZQx1xYZwPMRDhDuoT5oVE"
HQ_FULLSCREEN = True         # open HQ as a full screen app window in Chrome or Edge
WAKE_OPENS_HQ = False        # the wake up (clap, "wake up") also opens HQ full screen. Off: "open HQ" does it when you want it
WAKE_MUSIC = False           # the wake up also starts your room playlist
WAKE_SCENE_EVERY = 3         # hours: the full wake up (greeting and brief) at most this often. A clap in between just listens
CLAP_WAKE = True
CLAP_LEVEL = 0.35            # how loud a clap must be (0 to 1)
CLAP_CREST = 4.0             # how sharp: peak divided by average. Claps are spiky, voices are not
CLAP_GAP = (0.15, 0.9)       # seconds allowed between the two claps
GREETING = "Hey Yash."
MORNING_BRIEF_BEFORE = 12    # on a clap wake before this hour, read a short brief (once a day)
# claude.ai connectors show up in Claude Code as mcp__claude_ai_<Name>. Run --doctor to confirm names.
CONNECTOR_TOOLS = "mcp__claude_ai_Google_Calendar,mcp__claude_ai_Gmail"
# Voice can search, read your calendar and mail, and write new files only inside notes/. Never add Bash.
ALLOWED_TOOLS = "WebSearch,WebFetch,Edit(./notes/**)," + CONNECTOR_TOOLS
# FULL_ACCESS: Claude can do anything on this PC (run commands, change files and settings) without asking.
# Always off in guest mode, so friends or a TV can't make it do things. Set False in local_settings.py to go back
# to Jarvis telling you what it wants to do and you saying "yes" first.
FULL_ACCESS = True
AUTO_PAUSE = True            # pause music when you walk away from the desk, resume when you're back
HANDBOOK_URL = "https://claude.ai/artifact/KNwkFv1zmBsfcPdC29e4fx"
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
for _mod in (jarvis_room, jarvis_orb, jarvis_claude, jarvis_screen, jarvis_brain, jarvis_extras, jarvis_phone, jarvis_vision, jarvis_faces, jarvis_touch, jarvis_desk, jarvis_cad, jarvis_autostart, jarvis_hqsync, jarvis_activity, jarvis_memory, jarvis_wake, jarvis_chats, jarvis_evolve, jarvis_multi, jarvis_persona, jarvis_vaultstyle, jarvis_learn, jarvis_audio, jarvis_routines, jarvis_trust):
    for _k, _v in _mine.items():
        if hasattr(_mod, _k):
            setattr(_mod, _k, _v)


def typing_console():
    """Typing mode: a clean window with only your conversation. Logs still go to jarvis.log, and the noise native
    libraries print (camera, mediapipe) goes to jarvis-errors.log."""
    global CONSOLE_LOGS
    CONSOLE_LOGS = False
    if sys.platform == "win32":
        os.system("")   # turns on colors in the Windows console
        try:
            import ctypes
            ctypes.windll.kernel32.SetConsoleTitleW("Atlas")
        except Exception:
            pass
    try:
        sys.stdout.flush()
        err = open(os.path.join(os.path.dirname(os.path.abspath(__file__)), "jarvis-errors.log"), "a", encoding="utf-8")
        os.dup2(err.fileno(), 2)
        sys.stderr = err
    except Exception:
        pass
    os.system("cls" if sys.platform == "win32" else "clear")
    print("\n\033[38;5;117m  ATLAS\033[0m   \033[38;5;245mtyping mode. Ask anything or give a command. "
          "Try: desk mode, calibrate the desk, what's on today. Type voice on to use the mic.\033[0m\n", flush=True)


def total_ram_gb():
    if sys.platform != "win32":
        return 64.0
    try:
        import ctypes

        class MS(ctypes.Structure):
            _fields_ = [("len", ctypes.c_ulong), ("load", ctypes.c_ulong), ("total", ctypes.c_ulonglong), ("avail", ctypes.c_ulonglong),
                        ("tp", ctypes.c_ulonglong), ("ap", ctypes.c_ulonglong), ("tv", ctypes.c_ulonglong), ("av", ctypes.c_ulonglong),
                        ("ax", ctypes.c_ulonglong)]
        m = MS()
        m.len = ctypes.sizeof(MS)
        ctypes.windll.kernel32.GlobalMemoryStatusEx(ctypes.byref(m))
        return m.total / 2 ** 30
    except Exception:
        return 64.0


# Lite mode, for a laptop or a small PC: no always-on camera (the desk still opens it when you say desk mode),
# no face ID, and the Windows voice instead of the AI one. On by itself with under 12 GB of RAM. LITE = False forces it off.
LITE = _mine.get("LITE", total_ram_gb() < 12)
if LITE:
    for _mod, _k in ((jarvis_vision, "VISION"), (jarvis_faces, "FACES"), (jarvis_vision, "FACE_GESTURES")):
        if _k not in _mine:
            setattr(_mod, _k, False)
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

PERSONALITY = (
    "Personality: calm, quick and sharp, with a dry sense of humor. A little cocky, completely loyal, like the smart older "
    "friend who runs his whole setup. Talk like a person, not a help desk: contractions, short sentences, real reactions. "
    "Banter is fine (soccer, his builds, SolidHauz), corny is not, fake enthusiasm never. Call him Yash, now and then boss. "
    "When you do something, say it's done in a few words, don't narrate how. Don't ask permission for things he asked for. "
    "If something fails, say what you'll try next, then try it."
)
SPOKEN_STYLE = (
    f"You are {ASSISTANT_NAME}, Yash's AI, living on his PC. Everything you write is read aloud by a text to speech engine, "
    "so answer in plain spoken sentences. No markdown, no lists, no code blocks, no URLs, no emoji, no hyphens or em dashes. "
    "Keep it under 60 words unless he asks for detail, and put the answer in the first sentence. "
    "Sound like a real person talking, not reading: contractions always, mix short and longer sentences, react first when "
    "it fits (oh nice, wait, okay so, honestly, no way), a small 'hmm' or 'ha' only when it's natural, and say numbers "
    "and times the way people say them (quarter past four, like twenty bucks). Never list things out loud, never sound "
    "like customer service, never say you're an AI unless he asks. "
    "For his calendar and email use the Google Calendar and Gmail tools. Times are Pacific. " + PERSONALITY
)


LOG_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "jarvis.log")


PROMPT = "\033[38;5;245m  you   \033[0m "
CONSOLE_LOGS = True   # off in typing mode: the window shows only your conversation (everything still goes to jarvis.log)


def log(msg):
    """Prints, and keeps a copy in jarvis.log so problems are findable even when the window is hidden."""
    line = time.strftime("%Y-%m-%d %H:%M:%S ") + str(msg)
    if CONSOLE_LOGS:
        print(line[11:], flush=True)
    try:
        if os.path.exists(LOG_FILE) and os.path.getsize(LOG_FILE) > 2_000_000:
            os.replace(LOG_FILE, LOG_FILE + ".old")
        with open(LOG_FILE, "a", encoding="utf-8") as f:
            f.write(line + "\n")
    except OSError:
        pass


# ================= audio devices =================
KOKORO_NAMES = {"michael": "am_michael", "fenrir": "am_fenrir", "puck": "am_puck", "echo": "am_echo", "adam": "am_adam",
                "eric": "am_eric", "liam": "am_liam", "onyx": "am_onyx", "george": "bm_george", "fable": "bm_fable",
                "lewis": "bm_lewis", "heart": "af_heart", "bella": "af_bella", "emma": "bf_emma"}


def set_local_setting(name, value):
    """Writes NAME = value into local_settings.py (replacing an earlier line), so it sticks across restarts and updates."""
    path = os.path.join(WORKDIR, "local_settings.py")
    try:
        lines = open(path, encoding="utf-8").read().splitlines()
    except OSError:
        lines = []
    lines = [l for l in lines if not re.match(rf"\s*{name}\s*=", l)]
    lines.append(f"{name} = {value!r}")
    with open(path, "w", encoding="utf-8") as f:
        f.write("\n".join(lines) + "\n")


def eleven_tts(text):
    """One sentence from ElevenLabs as 24 kHz float audio, or None."""
    import urllib.request
    vid = ELEVEN_VOICES.get(ELEVEN_VOICE.lower(), ELEVEN_VOICE)
    body = json.dumps({"text": text, "model_id": ELEVEN_MODEL,
                       "voice_settings": {"stability": 0.38, "similarity_boost": 0.8, "style": 0.35, "use_speaker_boost": True}}).encode()
    req = urllib.request.Request(f"https://api.elevenlabs.io/v1/text-to-speech/{vid}?output_format=pcm_24000", data=body,
                                 method="POST", headers={"xi-api-key": ELEVENLABS_KEY, "Content-Type": "application/json"})
    try:
        with urllib.request.urlopen(req, timeout=15) as r:
            raw = r.read()
        return np.frombuffer(raw, dtype=np.int16).astype(np.float32) / 32768.0
    except Exception as e:
        log(f"elevenlabs: {str(e)[:160]}")
        return None


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
    """Record until you stop talking: a real voice detector and smart pauses (see jarvis_listen)."""
    import jarvis_listen
    return jarvis_listen.record(audio_q.get, noise_floor, silence=silence, max_secs=max_secs or MAX_RECORD_SECONDS,
                                wait_for_voice=wait_for_voice)


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
        import ctranslate2
        if ctranslate2.get_cuda_device_count() == 0:   # no NVIDIA card: don't download the big model just to find out
            log("no NVIDIA GPU, using CPU whisper small.en")
            return WhisperModel("small.en", device="cpu", compute_type="int8"), "cpu"
    except Exception:
        pass
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


HALLUCINATIONS = {"", "you", "thank you", "thank you.", "thanks for watching", "thanks for watching!", "bye", "bye.", ".",
                  "thank you for watching", "subtitles by the amara.org community", "uh", "um", "hmm"}


_LEARNED = {"mtime": 0, "text": ""}


def learned_vocab():
    """Words Atlas learned from your corrections (it misheard them before)."""
    path = os.path.join(WORKDIR, ".vocab_learned.txt")
    try:
        m = os.path.getmtime(path)
        if m != _LEARNED["mtime"]:
            _LEARNED.update(mtime=m, text=open(path, encoding="utf-8").read().strip()[-600:])
    except OSError:
        return ""
    return _LEARNED["text"]


def transcribe(model, audio):
    """Whisper, primed with Yash's names and words, a wider search, and a filter for its made up lines on silence."""
    learned = learned_vocab()
    prompt = (f"Yash talking to {ASSISTANT_NAME}, his AI. Names and words: " + VOCAB + (", " + VOCAB_EXTRA if VOCAB_EXTRA else "")
              + (", " + learned if learned else "") + ".")
    import jarvis_listen
    kw = dict(language="en", beam_size=5, vad_filter=True, initial_prompt=prompt, condition_on_previous_text=False,
              no_speech_threshold=0.6, vad_parameters={"min_silence_duration_ms": 300, "speech_pad_ms": 200})
    hot = jarvis_listen.hotwords(ASSISTANT_NAME, VOCAB, VOCAB_EXTRA, learned)
    try:
        segments, _ = model.transcribe(audio, hotwords=hot or None, **kw)   # leans toward your names and words
    except TypeError:
        segments, _ = model.transcribe(audio, **kw)   # older faster-whisper
    segs = [s for s in segments if getattr(s, "no_speech_prob", 0) < 0.7]
    text = " ".join(s.text.strip() for s in segs).strip()
    return "" if text.lower().strip(" .!?") in {h.strip(" .!?") for h in HALLUCINATIONS} else text


# ================= text to speech =================
class Speaker:
    def __init__(self):
        self.kokoro = None
        try:
            if LITE and not ELEVENLABS_KEY:
                raise RuntimeError("lite mode")
            from kokoro import KPipeline
            self.kokoro = KPipeline(lang_code="a" if VOICE[0] == "a" else "b")
            log(f"kokoro voice {VOICE}")
        except Exception as e:
            log(f"kokoro unavailable ({e}); using Windows voice")
            import pyttsx3
            self.engine = pyttsx3.init()
        self.stop_flag = threading.Event()
        self.say_lock = threading.RLock()
        self.cut_at = 0.0
        self.last_end = 0.0
        self.speaking = False
        self.interrupted = False
        self.watch = None   # watch(frame) -> True cuts Jarvis off mid sentence. Set in main: wake word or a double clap

    def stop(self):
        """Stop talking right now."""
        self.cut_at = time.time()   # an answer still streaming in sees this and stops reading the rest
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
    on_said = None                 # set in main: everything Jarvis says goes in the conversation log
    last_line = ""                 # the last thing it said, for the command center

    def say(self, text):
        if Speaker.on_said:
            try:
                Speaker.on_said(text)
            except Exception:
                pass
        Speaker.last_line = text[:240]
        if not CONSOLE_LOGS and text.strip():
            print(f"\r\033[K\033[38;5;117m  Atlas \033[0m {text.strip()}\n{PROMPT}", end="", flush=True)
        cap = getattr(Speaker.capture, "lines", None)
        if cap is not None:
            cap.append(re.sub(r"[*#`_>\[\]]", "", text))
            if not getattr(Speaker.capture, "speak", False):
                return
        with self.say_lock:   # one voice: answers, job reports and quick commands take turns
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
                self.last_end = time.time()
                jarvis_orb.send("idle")

    def _say(self, text):
        sd = _sd()
        text = re.sub(r"[*#`_>\[\]]", "", text)
        text = re.sub(r"https?://\S+", "", text)
        print("  >>", text, flush=True)
        if ELEVENLABS_KEY and not getattr(self, "eleven_broken", False):
            audio = eleven_tts(text)
            if audio is not None:
                self._play(audio, 24000)
                return
            self.eleven_fail = getattr(self, "eleven_fail", 0) + 1
            if self.eleven_fail >= 3:
                self.eleven_broken = True
                log("ElevenLabs keeps failing, using the built in voice for now")
        if self.kokoro:
            for _, _, audio in self.kokoro(text, voice=VOICE, speed=VOICE_SPEED):
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

    def _play(self, audio, rate):
        sd = _sd()
        if self.stop_flag.is_set():
            return
        sd.play(audio, rate, device=SPEAKER_DEVICE)
        end = time.time() + len(audio) / rate + 0.05
        while time.time() < end and not self.stop_flag.is_set():
            time.sleep(0.02)
        if self.stop_flag.is_set():
            sd.stop()

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

    def cue(self, kind, wait=True):
        """listen, heard, nothing, long, done, error: see jarvis_listen."""
        import jarvis_listen
        def play():
            try:
                sd = _sd()
                sd.play(jarvis_listen.cue(kind), jarvis_listen.SR, device=SPEAKER_DEVICE)
                sd.wait()
            except Exception as e:
                log(f"cue: {e}")
        if wait:
            play()
        else:
            threading.Thread(target=play, daemon=True).start()


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


def running_as_admin():
    if not IS_WIN:
        return False
    try:
        import ctypes
        return bool(ctypes.windll.shell32.IsUserAnAdmin())
    except Exception:
        return False


def launch_as_user(args):
    """Jarvis runs as administrator, but apps it opens shouldn't: Chrome as admin breaks your profile and sign in.
    So when Jarvis is admin, start them with a normal user's rights."""
    if IS_WIN and running_as_admin():
        try:
            return subprocess.Popen(["runas", "/trustlevel:0x20000", subprocess.list2cmdline(args)], creationflags=0x08000000)
        except Exception as e:
            log(f"launch as user failed ({e}), launching normally")
    return subprocess.Popen(args)


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
        if IS_WIN and running_as_admin():
            # explorer hands it to your normal desktop session, so the app doesn't open as admin
            subprocess.Popen(["explorer.exe", target])
        elif IS_WIN:
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
            launch_as_user([a for a in args if a])
            return
        import webbrowser
        webbrowser.open(url)

    def open_window(self, url, w=880, h=980):
        """A page as its own app window (no tabs or address bar), sized like a normal window."""
        exe, prof = browser_exe(), browser_profile()
        if not exe:
            exe, prof = jarvis_desk._browser(), None
        if IS_WIN and exe:
            args = [exe] + (["--profile-directory=" + prof] if prof else []) + ["--app=" + url, f"--window-size={w},{h}"]
            launch_as_user(args)
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


def read_version():
    """What update.py wrote after the last update: when, the commit, and the last few change notes."""
    try:
        with open(os.path.join(WORKDIR, ".version.json"), encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return None


def update_waiting():
    try:
        r = subprocess.run([sys.executable, os.path.join(WORKDIR, "update.py"), "--check"], capture_output=True, timeout=180,
                           creationflags=0x08000000 if IS_WIN else 0)
        return r.returncode == 10
    except Exception as e:
        log(f"update check failed: {e}")
        return False


def push_to_talk(jarvis):
    """A global shortcut, Ctrl+Alt+Space: Atlas listens right away, wherever you are. Pressing it while Atlas talks
    cuts it off. (Ctrl+Space alone is taken by too many apps, like VS Code.)"""
    if not IS_WIN:
        return
    import ctypes
    from ctypes import wintypes
    u = ctypes.windll.user32
    MOD_ALT, MOD_CONTROL, MOD_NOREPEAT, VK_SPACE, WM_HOTKEY = 0x1, 0x2, 0x4000, 0x20, 0x0312
    if not u.RegisterHotKey(None, 0xA71A, MOD_CONTROL | MOD_ALT | MOD_NOREPEAT, VK_SPACE):
        log("push to talk: Ctrl+Alt+Space is already used by another app")
        return
    log("push to talk: Ctrl+Alt+Space")
    msg = wintypes.MSG()
    while u.GetMessageW(ctypes.byref(msg), None, 0, 0) != 0:
        if msg.message == WM_HOTKEY:
            if jarvis.speaker.speaking:
                jarvis.speaker.stop()
            jarvis.listen_requested = True


def run_update_now(jarvis, speak=False):
    """Installs the update while Atlas is still running (you see every step in this window and in jarvis.log),
    and only then restarts into it. If anything goes wrong, it says so and keeps running the current version."""
    say = jarvis.speaker.say if speak else (lambda t: None)
    try:
        r = subprocess.Popen([sys.executable, os.path.join(WORKDIR, "update.py")], cwd=WORKDIR, stdout=subprocess.PIPE,
                             env=dict(os.environ, ATLAS_RUNNING="1", PYTHONUNBUFFERED="1"),
                             stderr=subprocess.STDOUT, text=True, encoding="utf-8", errors="replace",
                             creationflags=0x08000000 if IS_WIN else 0)
        out = []
        for line in r.stdout:
            line = line.rstrip()
            if line:
                out.append(line)
                log(line)
        code = r.wait(timeout=1800)
    except Exception as e:
        log(f"update failed: {e}")
        say("The update didn't install. Check the Atlas window.")
        return False
    try:
        st = json.load(open(os.path.join(WORKDIR, ".update_status.json")))
    except Exception:
        st = {"ok": code == 0}
    if code != 0 or not st.get("ok", True):
        why = re.sub(r"[^\w\s.,']", " ", st.get("error", "") or (out[-1] if out else ""))[:160]
        say("The update didn't install. " + why)
        return False
    say("Updated. Restarting.")
    time.sleep(1.5)
    jarvis.restart_for_update = True   # start.bat starts the new code (its own update check finds nothing left to do)
    return True


def nightly_update_watch(jarvis):
    """Checks for new code every 30 minutes. Restarts into it when you've been away from the keyboard for 15 minutes
    (so it never cuts you off mid task), or at AUTO_UPDATE_HOUR no matter what."""
    last_check, waiting = 0.0, False
    while True:
        time.sleep(60)
        lt = time.localtime()
        if time.time() - last_check > 1800 or (AUTO_UPDATE_HOUR is not None and lt.tm_hour == AUTO_UPDATE_HOUR):
            last_check = time.time()
            waiting = update_waiting()
            if waiting:
                log("an update is waiting")
        if not waiting:
            continue
        b = jarvis.brain
        away = jarvis_brain.idle_seconds() > 900 and not (b and b.focus_started) and not jarvis.speaker.speaking
        if away or (AUTO_UPDATE_HOUR is not None and lt.tm_hour == AUTO_UPDATE_HOUR):
            log("installing the update")
            run_update_now(jarvis)
            return


def reactive_watch(jarvis):
    """Reacts to you without being asked: pauses the music when you walk away from the desk (camera doesn't see you
    and the keyboard is untouched for 90 seconds), and resumes it when you're back."""
    paused_by_me = False
    while True:
        time.sleep(5)
        try:
            if not AUTO_PAUSE:
                continue
            v = jarvis.vision
            sees = v is not None and v.ok and v.enabled
            away_cam = sees and v.seconds_since_face() > 90
            idle = jarvis_brain.idle_seconds()
            away = away_cam and idle > 90
            back = (sees and v.seconds_since_face() < 5) or idle < 3
            song = ACTIVITY.song if ACTIVITY else ""
            if away and song and not paused_by_me:
                jarvis.pc.key("play_pause")
                paused_by_me = True
                log("you walked away, paused the music")
            elif paused_by_me and back:
                jarvis.pc.key("play_pause")
                paused_by_me = False
                log("you're back, music on")
        except Exception as e:
            log(f"reactive: {e}")


def push_phone(text):
    """Optional iPhone notification through ntfy (free app). Only a short status line is sent."""
    try:
        urllib.request.urlopen(urllib.request.Request("https://ntfy.sh/" + NTFY_TOPIC, data=text.encode(),
                                                      headers={"Title": "Yash HQ", "Tags": "red_circle"}), timeout=8)
    except Exception as e:
        log(f"push failed: {e}")


# Commands that do something you'd notice right away. If the sentence is really about changing, setting up or asking
# about something ("change my wake up song", "how do I lock my screen", "why did the music stop"), it goes to Claude
# instead, which understands the whole sentence.
SENSITIVE = {"hq", "lock", "sleep", "goodnight", "monitor_off", "standby", "update", "reset", "play_pause", "next", "prev", "spotify_play",
             "spotify_queue", "protocol", "camera", "gestures", "vision_focus", "touch", "desk", "face_learn", "face_forget", "alarm", "alarm_off",
             "phone", "hush", "test_pc", "cad_open", "cad_close", "focus", "focus_end", "whatsapp", "session_send", "mute",
             "now_playing", "browser", "site", "app", "tab_close", "tabs_close_others", "ui_click", "handbook", "game_result"}
META = re.compile(r"\b(?:change|changing|edit|rename|configure|customi[sz]e|replace|swap|instead|different|default|settings?|"
                  r"automatically|set (?:my|the|it|up|a new)|make (?:my|it|the|that) (?:\w+ )?(?:be|into|to|more|less|different)|"
                  r"switch (?:my|the) .+ to|update (?:my|the) (?!yourself)|how (?:do|does|can|would|should|come)|why|what does|"
                  r"explain|is it possible|can (?:i|we) (?:make|change|set|get)|remember to|next time|from now on|whenever|every time)\b")


def route(text):
    """Turn a spoken line into a local command, or None to send it to Claude.
    Returns (action, arg). Only actions from this list can ever run by voice."""
    u = re.search(r"\b(?:learn|remember|save|file|study)\b.{0,30}?((?:https?://|www\.)\S+|\b[\w-]+\.(?:com|org|edu|io|ai|net|dev)(?:/\S*)?)", text, re.I)
    if u:   # a link in the sentence (typed, or Whisper wrote it out): the wiki learns it
        link = u.group(1).rstrip(".,!?)")
        return ("learn", ("url", link if link.startswith("http") else "https://" + link))
    t = re.sub(r"\s+", " ", re.sub(r"[^\w\s']", " ", text.lower())).strip()
    t = re.sub(r"^\s*(hey\s+)?(jarvis|" + re.escape(ASSISTANT_NAME.lower()) + r")\s*", "", t)
    for mod in MODS:   # your own add ons (mods folder) get first say
        try:
            r = mod.route(t) if hasattr(mod, "route") else None
            if r:
                return ("mod", (mod, r))
        except Exception as e:
            log(f"mod {mod.__name__} route: {e}")
    cmd = _route(text)
    if cmd and cmd[0] in SENSITIVE and META.search(t):
        return None   # it's a request about the thing, not the thing itself
    return cmd


def _route(text):
    t = re.sub(r"[^\w\s']", " ", text.lower())
    t = re.sub(r"^\s*(hey\s+)?(jarvis|" + re.escape(ASSISTANT_NAME.lower()) + r")\s*", "", t)
    t = re.sub(r"\b(please|can you|could you|for me|real quick)\b", " ", t)
    t = re.sub(r"\s+", " ", t).strip()

    if re.search(r"\b(?:show|open|pull up)(?: me)? (?:the |my )?(?:jarvis )?(?:handbook|manual|cheat ?sheet|commands|gesture guide)\b|\bwhat can (?:you do|i say)\b", t):
        return ("handbook", None)
    if re.fullmatch(r"what(?:'s| is) new|what changed|what(?:'s| is) in (?:the|this) update|what did you (?:get|learn) (?:new|in the update)", t):
        return ("whats_new", None)
    if re.fullmatch(r"what version (?:are you(?: on)?|is this)|(?:are you|is jarvis) up to date|which version", t):
        return ("version", None)
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
    if re.fullmatch(r"(?:turn (?:off|on) (?:the )?(?:voice|mic|microphone)(?: input)?|(?:voice|mic|microphone) (?:off|on)|(?:typing|type) (?:mode|only))", t):
        return ("voice_input", not re.search(r"\boff\b|typ", t))
    if re.fullmatch(r"(?:(?:can you |please |go )?(?:update|upgrade) (?:yourself|jarvis|atlas|your ?self|now|the code)|check for (?:an )?updates?|"
                    r"install (?:the )?updates?|get (?:the )?latest(?: version)?|update)(?: please| now)?", t):
        return ("update", None)
    if re.search(r"\b(what are|how are|status of|check on) my (claude )?(cloud )?(sessions|agents)( doing)?\b|\bsession status\b", t):
        return ("sessions", None)
    m = re.fullmatch(r"(?:whatsapp|send (?:a )?whatsapp to|message|text) (.+?)(?: on whatsapp)? (?:saying |that |to say )?(.+)", t)
    if m and (t.startswith(("whatsapp", "send a whatsapp", "send whatsapp")) or "on whatsapp" in t):
        return ("whatsapp", (m.group(1).strip(), m.group(2).strip()))
    # screen and Claude commands first: "type the weather is nice" must type, not check the weather
    cc = jarvis_screen.route_screen(t) if re.match(r"(?:type|press|hit) ", t) else None
    m = re.fullmatch(r"(?:change|switch|set) your voice to (\w+)|use (?:the )?(\w+) voice|talk (?:like|as) (\w+)", t)
    if m:
        return ("voice_set", next(g for g in m.groups() if g))
    if re.fullmatch(r"(?:what|which) voices? (?:can you (?:use|do)|do you have|are there)|list (?:your )?voices", t):
        return ("voice_list", None)
    if re.fullmatch(r"(?:install|set up|turn on) (?:vision clicking|omni ?parser|better clicking|screen vision)", t):
        return ("install_vision", None)
    if re.fullmatch(r"(?:open|show|pull up|bring up) (?:the |a |my )?(?:chat|chat window|atlas chat|typing window|text box)", t):
        return ("chat_open", None)
    if re.fullmatch(r"(?:open|show|pull up|bring up) (?:the |my )?(?:command center|command centre|mission control|atlas dashboard|your dashboard)", t):
        return ("command_center", None)
    cc = cc or jarvis_trust.route_trust(t) or jarvis_routines.route_routines(t) or jarvis_learn.route_learn(t) or jarvis_vaultstyle.route_vault(t) or jarvis_multi.route_model(t) or jarvis_persona.route_persona(t) or jarvis_multi.route_jobs(t) or jarvis_evolve.route_evolve(t) or jarvis_memory.route_memory(t) or jarvis_chats.route_chats(t) or jarvis_claude.route_claude(t) or jarvis_screen.route_screen(t) or jarvis_uia.route_uia(t) \
        or jarvis_faces.route_faces(t) or jarvis_vision.route_vision(t) or jarvis_activity.route_activity(t) \
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
    if re.fullmatch(r"(?:go (?:to|into) |enter )?stand ?by(?: mode)?|night mode|screens? off|(?:turn|shut) (?:off )?(?:the |my )?screens?(?: off)?|power down(?: the screens)?", t):
        return ("standby", None)
    if re.search(r"\b(what are|how are|status of|check on) my (claude )?(sessions|agents)\b|\bsession status\b", t):
        return ("sessions", None)
    m = re.fullmatch(r"(?:tell|message) (?:the |my )?(.+?) session (?:to |that )?(.+)", t)
    if m:
        return ("session_send", (m.group(1), m.group(2)))
    if re.search(r"\bnew conversation\b|\bstart over\b|\bfresh start\b", t):
        return ("reset", None)
    if re.fullmatch(r"(?:open|show|pull up|bring up) (?:the |my )?(?:hq|dashboard)", t):
        return ("hq_open", None)
    if re.fullmatch(r"wake (?:everything|the room|up the room|up)(?: everything)?|wake everything up|"
                    r"(?:ok(?:ay)? )?i'?m (?:home|back)|wakey wakey|rise and shine|systems? on(?:line)?", t):
        return ("hq", None)
    if re.fullmatch(r"lock (?:the |my )?(?:screen|computer|pc)(?: now)?", t):
        return ("lock", None)

    # music
    if re.search(r"\b(what'?s|what is) (playing|this song)\b|\bwhat song is this\b", t):
        return ("now_playing", None)
    if re.fullmatch(r"(pause|stop)( the)?( music| song| spotify| it)?|(?:shut up|quiet) the music", t):
        return ("music_pause", None)
    if re.fullmatch(r"(resume|unpause|continue)( the)?( music| song| spotify| it)?|play( the)? music|play spotify|play|keep playing|put (the )?music back on", t):
        return ("music_play", None)
    if re.fullmatch(r"play ?pause|toggle (the )?music", t):
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


def claude_cmd(claude):
    """claude.cmd (the npm install) runs through cmd.exe, which mangles long arguments. Skip it and run node directly."""
    if claude and claude.lower().endswith((".cmd", ".bat")):
        base = os.path.dirname(claude)
        cli = os.path.join(base, "node_modules", "@anthropic-ai", "claude-code", "cli.js")
        node = os.path.join(base, "node.exe") if os.path.exists(os.path.join(base, "node.exe")) else shutil.which("node")
        if os.path.exists(cli) and node:
            return [node, cli]
    return [claude]


SYS_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), ".cache", "sys")


def system_prompt_args(text):
    """Atlas's instructions (personality sheet, memory, lessons, what's on screen...) go to Claude in a file:
    on the command line they hit Windows' length limit ("The command line is too long")."""
    try:
        os.makedirs(SYS_DIR, exist_ok=True)
        now = time.time()
        for f in os.listdir(SYS_DIR):   # tidy up old ones
            try:
                if now - os.path.getmtime(os.path.join(SYS_DIR, f)) > 1800:
                    os.remove(os.path.join(SYS_DIR, f))
            except OSError:
                pass
        path = os.path.join(SYS_DIR, f"{os.getpid()}-{threading.get_ident()}-{int(now * 1000)}.txt")
        with open(path, "w", encoding="utf-8") as f:
            f.write(text)
        return ["--append-system-prompt-file", path]
    except Exception as e:
        log(f"system prompt file: {e}")
        return ["--append-system-prompt", one_line(text)[:7000]]


def one_line(text):
    """Command line safe: no new lines (Windows stops reading there) and no double quotes."""
    return re.sub(r"\s*\n\s*", " | ", text).replace('"', "'")


STANDBY_AFTER = 10      # minutes with nobody at the desk (no face, no keyboard or mouse): screens off, Jarvis keeps watching
STANDBY_LOCK = False    # also lock Windows when it goes into standby


def fullscreen_app():
    """True when the front window fills its screen (a video or a game), so standby leaves it alone."""
    if not IS_WIN:
        return False
    try:
        import ctypes
        from ctypes import wintypes
        u = ctypes.windll.user32
        hwnd = u.GetForegroundWindow()
        if not hwnd or hwnd == u.GetShellWindow() or hwnd == u.GetDesktopWindow():
            return False
        r = wintypes.RECT()
        u.GetWindowRect(hwnd, ctypes.byref(r))

        class MI(ctypes.Structure):
            _fields_ = [("cbSize", wintypes.DWORD), ("rcMonitor", wintypes.RECT), ("rcWork", wintypes.RECT), ("dwFlags", wintypes.DWORD)]
        mi = MI()
        mi.cbSize = ctypes.sizeof(MI)
        u.GetMonitorInfoW(u.MonitorFromWindow(hwnd, 2), ctypes.byref(mi))
        m = mi.rcMonitor
        return r.left <= m.left and r.top <= m.top and r.right >= m.right and r.bottom >= m.bottom
    except Exception:
        return False


GESTURE_MAP_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), ".gesture_map.json")


def load_gesture_map():
    """Your own gesture shortcuts: {"rock": "open spotify", ...}. They replace what that gesture normally does."""
    try:
        with open(GESTURE_MAP_FILE, encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return {}


def save_gesture_map(m):
    with open(GESTURE_MAP_FILE, "w", encoding="utf-8") as f:
        json.dump(m, f, indent=1)


def spotify_api(sp, method, path):
    """True when Spotify did it."""
    try:
        sp._api(method, path)
        return True
    except Exception as e:
        log(f"spotify {path}: {e}")
        return False


def music_playing(sp, pc):
    """True or False when we can tell, None when we can't. Spotify's API first, then its window title
    (it shows the song while playing and just 'Spotify' when paused)."""
    if sp is not None and getattr(sp, "ready", False):
        try:
            st = sp._api("GET", "/me/player") or {}
            if "is_playing" in st:
                return bool(st["is_playing"])
        except Exception:
            pass
    try:
        for _, exe, title in jarvis_screen.Screen().windows():
            if exe.lower().startswith("spotify"):
                return title.strip() not in ("", "Spotify", "Spotify Free", "Spotify Premium")
    except Exception:
        pass
    return None


RELATIONS = {"dad", "mom", "brother", "sister", "grandma", "grandpa", "uncle", "aunt", "cousin", "girlfriend", "boyfriend",
             "coach", "friend", "best_friend", "teacher", "stepdad", "stepmom"}

SESSION_HOURS = 12   # start a fresh Claude conversation after this long; the conversation log carries the context over


def load_session():
    try:
        with open(STATE_FILE) as f:
            d = json.load(f)
        if time.time() - d.get("started", 0) > SESSION_HOURS * 3600:
            return None
        return d.get("session_id")
    except Exception:
        return None


def save_session(sid):
    try:
        with open(STATE_FILE) as f:
            old = json.load(f)
    except Exception:
        old = {}
    started = old.get("started", time.time()) if sid and sid == old.get("session_id") else time.time()
    with open(STATE_FILE, "w") as f:
        json.dump({"session_id": sid, "started": started}, f)


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


def code_files():
    out = [os.path.join(WORKDIR, f) for f in os.listdir(WORKDIR) if (f.startswith("jarvis") and f.endswith(".py")) or f == "local_settings.py"]
    mods = os.path.join(WORKDIR, "mods")
    if os.path.isdir(mods):
        out += [os.path.join(mods, f) for f in os.listdir(mods) if f.endswith(".py")]
    return out


def snapshot_code():
    """Jarvis's own code and settings as they are now, so a bad self edit can be put back."""
    snap = {}
    for p in code_files():
        try:
            with open(p, "rb") as f:
                snap[p] = f.read()
        except OSError:
            pass
    return snap


def mark_local_change(name):
    path = os.path.join(WORKDIR, ".local_changes.json")
    try:
        names = set(json.load(open(path)))
    except Exception:
        names = set()
    names.add(name)
    json.dump(sorted(names), open(path, "w"))


def check_code_changes(before):
    """After Claude ran: which files changed, and do they still compile? Broken ones get their old version back.
    Returns None if nothing changed, else (broken_names, good_names)."""
    import py_compile
    now = snapshot_code()
    changed = [p for p in set(before) | set(now) if before.get(p) != now.get(p)]
    if not changed:
        return None
    broken, good = [], []
    for p in changed:
        if p not in now:
            good.append(os.path.basename(p))
            continue
        try:
            py_compile.compile(p, doraise=True)
            good.append(os.path.basename(p))
            if os.path.basename(p).startswith("jarvis") and os.path.dirname(p) == WORKDIR:
                mark_local_change(os.path.basename(p))   # updates keep this edit
        except py_compile.PyCompileError as e:
            log(f"self edit broke {os.path.basename(p)}: {str(e)[:200]}")
            if p in before:
                with open(p, "wb") as f:
                    f.write(before[p])
            else:
                os.remove(p)
            broken.append(os.path.basename(p))
    return broken, good


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


ACTIVITY = None   # set in main: what he's doing right now, added to every question
EVOLVER = None    # set in main: lessons and self improvement
WHISPER_HOLDER = {}
PERSONA = None    # set in main: the living character sheet


def style_now():
    """How to talk, with the character sheet in place of the fixed personality once it exists."""
    if PERSONA:
        try:
            return SPOKEN_STYLE.replace(PERSONALITY, PERSONA.prompt())
        except Exception:
            pass
    return SPOKEN_STYLE
CONVOS = None     # set in main: the conversation log (short term memory, transcripts, daily lasting facts)
MODS = []         # add ons in C:\jarvis\mods, loaded at start


def load_mods():
    """Every .py file in the mods folder. A mod can have route(t) -> (action, arg) or None, and handle(jarvis, action, arg).
    Updates never touch this folder, so it's where Jarvis (or you) adds new features."""
    import importlib.util
    folder = os.path.join(WORKDIR, "mods")
    os.makedirs(folder, exist_ok=True)
    out = []
    for fn in sorted(os.listdir(folder)):
        if fn.endswith(".py") and not fn.startswith("_"):
            try:
                spec = importlib.util.spec_from_file_location("mod_" + fn[:-3], os.path.join(folder, fn))
                m = importlib.util.module_from_spec(spec)
                spec.loader.exec_module(m)
                out.append(m)
                log(f"mod loaded: {fn}")
            except Exception as e:
                log(f"mod {fn} failed to load, skipped: {e}")
    return out


def ask_claude(prompt, session_id, claude=None, tools=None, full=False, on_text=None, model=None):
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
    if full:
        extra += (f" You have full access to Yash's Windows PC. To see or control the screen (windows, tabs, buttons, typing, "
                  f"shortcuts, screenshots) run: \"{sys.executable}\" \"{os.path.join(WORKDIR, 'jarvis_ctl.py')}\" help. "
                  "For anything on screen, work in a loop: run jarvis_ctl.py look (a screenshot with a coordinate grid plus a "
                  "numbered list of everything clickable with positions), read the image, act with clicknum, typeinto, keys, "
                  "clickxy, drag or scroll, then look again to check it worked; use read to get the text of a page or doc. "
                  "Prefer clicknum over guessing coordinates. You can also SEE YASH: "
                  "jarvis_ctl.py camera saves a photo from his webcam and prints its path, read that image whenever a question "
                  "needs eyes (what he's holding, wearing, doing, how many fingers). Never say you don't have a camera. "
                  f"Your own settings (wake up music = ROOM_PLAYLIST, alarm music = WAKE_PLAYLIST, party = PARTY_PLAYLIST, "
                  f"pregame = GAMEDAY_PLAYLIST, focus music = FOCUS_MUSIC, voice = VOICE, your name = ASSISTANT_NAME, mic gain "
                  f"and more) are Python lines like NAME = \"value\" in {os.path.join(WORKDIR, 'local_settings.py')}. To change "
                  "one, edit that file (add the line if it's missing; playlists are Spotify links, find them with the Spotify "
                  "tools or web search). You can also improve yourself: your code is the jarvis*.py files in "
                  f"{WORKDIR}. For a new feature, prefer a mod: a .py file in {os.path.join(WORKDIR, 'mods')} with "
                  "route(t) returning (action, arg) or None for the lowercase spoken line t, and handle(jarvis, action, arg) "
                  "that does it (jarvis.speaker.say(text) talks, jarvis.pc has key/launch/open_url). Edit the main files only "
                  "for real fixes. Your edits survive updates. After you change any of these files Jarvis checks they compile, "
                  "puts back anything broken, and restarts itself to load the change, so just say what you changed. "
                  "Do what he asks; don't tell him to do it himself. "
                  "You also run Yash's Claude: start a cloud Claude Code session with: claude --cloud \"task\" (run it in "
                  "that project's folder, it uses the GitHub repo there; the projects he's used are in ~/.claude/projects); "
                  "follow up on one with: claude -p --cloud <session id> --output-format json (message on stdin); pull one "
                  "down with: claude --teleport <id>; open a local session in a new terminal window; drive a session from his "
                  "phone with: claude --remote-control. Sessions you start are listed in "
                  f"{os.path.join(WORKDIR, '.cloud_sessions.json')}. His claude.ai chats (from his data export) are notes in his "
                  "vault under Claude/Chats, one per chat: Grep them when he asks what he talked to Claude about. For a chat "
                  "newer than the export, open claude.ai/recents in the browser and read the screen with jarvis_ctl.")
    if EVOLVER:
        try:
            les = EVOLVER.lessons(1200)
            if les:
                extra += " Lessons from Yash's past corrections, follow them: " + les.replace("\n", " ")
        except Exception:
            pass
    if ACTIVITY:
        try:
            extra += " " + ACTIVITY.context()
        except Exception:
            pass
    if CONVOS and not prompt.startswith("[context]"):
        try:
            recent = CONVOS.recent()
            if recent:
                # rides in the message, not on the command line: Windows cuts command lines off at the first new line
                prompt = ("[context] Your recent conversation with Yash, oldest first (includes quick commands Jarvis "
                          "handled itself; use it for what 'that', 'it' or a one word reply like 'smaller' means):\n"
                          + recent + "\n[/context]\n\n" + prompt)
        except Exception:
            pass
    cmd = claude_cmd(claude) + ["-p", "--output-format", "stream-json" if on_text else "json"] + \
        system_prompt_args(style_now() + " Local time now: " + now + "." + extra) + ["--allowedTools", tools]
    if on_text:
        cmd += ["--verbose", "--include-partial-messages"]
    if model or CLAUDE_MODEL:
        cmd += ["--model", model or CLAUDE_MODEL]
    if BRAIN:
        cmd += ["--add-dir", BRAIN.vault.root]
    if full:
        cmd[cmd.index("--allowedTools") + 1] = tools + "," + ",".join(FULL_TOOLS)
        cmd += ["--dangerously-skip-permissions"]
        for d in full_access_dirs():
            cmd += ["--add-dir", d]
    if session_id:
        cmd += ["--resume", session_id]
    if on_text:
        data = stream_claude(cmd, prompt, on_text)
        if data is None and session_id:
            return ask_claude(prompt, None, claude, tools, full, on_text, model)   # old session gone, start a new one
        if data is None:
            log("streaming didn't work, asking the normal way")
            return ask_claude(prompt, None, claude, tools, full, None, model)
        LAST_DENIED = data.get("permission_denials") or []
        if LAST_DENIED:
            log("claude wanted to: " + "; ".join(describe_denied([d]) for d in LAST_DENIED[:5]))
        return data.get("result") or "", data.get("session_id") or session_id
    r = subprocess.run(cmd, cwd=WORKDIR, input=prompt, capture_output=True, text=True, encoding="utf-8",
                       timeout=300, creationflags=0x08000000 if IS_WIN else 0)
    if r.returncode != 0 and session_id:
        return ask_claude(prompt, None, claude, tools, full, None, model)   # old session gone, start a new one
    try:
        data = json.loads(r.stdout)
    except Exception:
        err = (r.stderr or r.stdout or "")
        log(f"claude failed (code {r.returncode}): {err[:400]}")
        nxt = {"opus": "sonnet", "sonnet": "haiku"}.get(model or CLAUDE_MODEL)
        if nxt and re.search(r"overload|rate.?limit|usage limit|quota|529|too many requests|capacity|not available", err, re.I):
            log(f"model ladder: {model or CLAUDE_MODEL} is busy, trying {nxt}")
            return ask_claude(prompt, None, claude, tools, full, None, nxt)
        return "I couldn't reach Claude. Check the Atlas window.", session_id
    LAST_DENIED = data.get("permission_denials") or []
    if LAST_DENIED:
        log("claude wanted to: " + "; ".join(describe_denied([d]) for d in LAST_DENIED[:5]))
    return data.get("result") or "I didn't get an answer back.", data.get("session_id") or session_id


# What Atlas says while Claude uses a tool, so you hear what it's actually doing instead of "one sec".
# (The idea comes from Huw Prosser's Fury: tool call announcements.) Each phrase at most once per answer.
TOOL_PHRASES = [
    (r"Google_Calendar", "Checking your calendar."), (r"Gmail", "Looking through your email."),
    (r"Google_Drive", "Checking your Drive."), (r"Solidhauz", "Checking the shop."), (r"Spotify", "Checking Spotify."),
    (r"Claude_Code_Remote", "Checking your Claude sessions."), (r"Vercel", "Checking Vercel."), (r"Supabase", "Checking the database."),
    (r"^WebSearch$", "Searching the web."), (r"^WebFetch$", "Reading up on it."),
    (r"jarvis_ctl\.py\W+camera", "Taking a look."), (r"jarvis_ctl\.py\W+(?:look|screenshot)", "Looking at your screen."),
    (r"jarvis_ctl\.py\W+(?:click|type|keys|drag|scroll|double|right|focus|snap|open)", "On it."),
    (r"jarvis_ctl\.py\W+read", "Reading what's on screen."),
    (r"^(?:Read|Grep|Glob)$", "Checking your notes."), (r"^(?:Edit|Write|MultiEdit)$", "Making the change."),
]
TOOL_SAYINGS = {p for _, p in TOOL_PHRASES}


def tool_phrase(name, inp):
    """'Checking your calendar.' for a calendar tool call, None for ones not worth saying."""
    key = name
    if name in ("Bash", "PowerShell"):
        key = str((inp or {}).get("command", ""))
        if "jarvis_ctl" not in key:
            return None   # plain commands: quiet
    elif name in ("Read", "Grep", "Glob"):
        path = str((inp or {}).get("file_path") or (inp or {}).get("path") or "")
        if not path.lower().endswith(".md"):
            return None   # reading code or settings, not his notes
    for pat, phrase in TOOL_PHRASES:
        if re.search(pat, key):
            return phrase
    return None


SENTENCE_END = re.compile(r"(.+?[.!?])(\s+|$)", re.S)


def stream_claude(cmd, prompt, on_text, filler_after=2.5):
    """Runs Claude and hands each finished sentence to on_text as it arrives, so Jarvis starts talking right away.
    Says a quick "one sec" if nothing has come back after a couple of seconds. Returns the final result event, or None.
    on_text returns False to stop (you interrupted)."""
    p = subprocess.Popen(cmd, cwd=WORKDIR, stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                         text=True, encoding="utf-8", creationflags=0x08000000 if IS_WIN else 0)
    lines = queue.Queue()

    def pump():
        for line in p.stdout:
            lines.put(line)
        lines.put(None)
    threading.Thread(target=pump, daemon=True).start()
    try:
        p.stdin.write(prompt)
        p.stdin.close()
    except Exception:
        pass
    buf, result, spoke, t0, filled = "", None, False, time.time(), False
    announced = set()

    def flush(final=False):
        nonlocal buf, spoke
        while True:
            m = SENTENCE_END.match(buf)
            if not m or (len(m.group(1)) < 12 and not final and len(buf) < 60):
                break
            sentence, buf = m.group(1).strip(), buf[m.end():]
            if sentence:
                spoke = True
                if on_text(sentence) is False:
                    return False
        if final and buf.strip():
            spoke = True
            on_text(buf.strip())
            buf = ""
        return True

    stopped = False
    while True:
        try:
            line = lines.get(timeout=0.25)
        except queue.Empty:
            if not spoke and not filled and time.time() - t0 > filler_after:
                filled = True
                on_text(random.choice(["One sec.", "On it.", "Checking.", "Give me a second.", "Working on it."]))
            if p.poll() is not None and lines.empty():
                break
            continue
        if line is None:
            break
        try:
            ev = json.loads(line)
        except Exception:
            continue
        kind = ev.get("type")
        if kind == "stream_event":
            d = (ev.get("event") or {}).get("delta") or {}
            if d.get("type") == "text_delta" and not stopped:
                buf += d.get("text", "")
                if not flush():
                    stopped = True
                    p.kill()
            elif (ev.get("event") or {}).get("type") == "content_block_stop" and buf.strip() and not stopped:
                if not flush(final=True):
                    stopped = True
        elif kind == "assistant" and not stopped:   # a finished message: say which tools it's about to use
            for blk in ((ev.get("message") or {}).get("content") or []):
                if isinstance(blk, dict) and blk.get("type") == "tool_use":
                    ph = tool_phrase(blk.get("name", ""), blk.get("input"))
                    if ph and ph not in announced and not buf.strip():
                        announced.add(ph)
                        filled = True   # this replaces the generic "one sec"
                        if on_text(ph) is False:
                            stopped = True
                            p.kill()
        elif kind == "result":
            result = ev
    if not stopped:
        flush(final=True)
    try:
        p.wait(timeout=5)
    except Exception:
        pass
    if result is None:
        log(f"claude failed (code {p.returncode}): {(p.stderr.read() if p.stderr else '')[:400]}")
        return None
    result["_spoke"] = spoke and not filled or (spoke and filled and bool(result.get("result")))
    result["_said_any"] = spoke
    return result


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
        self.last_heard, self.follow_frames, self.recording = 0.0, [], False
        self.undo_log = jarvis_trust.UndoLog()
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

    # ---- standby: screens off, Jarvis awake. A PC that's really asleep can't hear or see anything, so Jarvis keeps
    # Windows from sleeping and does this instead. Clap, say the wake word, or just sit down and it wakes up. ----
    standby = False

    def enter_standby(self, why="asked"):
        if self.standby:
            return
        self.standby, self.standby_at = True, time.time()
        log(f"standby ({why}): screens off, still listening and watching")
        if self.vision:
            self.vision.low_power = True
        if STANDBY_LOCK:
            self.pc.lock()
        time.sleep(0.5)
        self.pc.monitor_off()
        jarvis_orb.send("idle")

    def leave_standby(self, why="input", greet=True):
        if not self.standby:
            return False
        self.standby = False
        gone = int((time.time() - getattr(self, "standby_at", time.time())) / 60)
        log(f"awake ({why}) after {gone} min in standby")
        if self.vision:
            self.vision.low_power = False
        self.pc.nudge_display()
        if greet and why == "face":
            b = self.brain
            if b:
                threading.Thread(target=b.presence.tick, daemon=True).start()   # the welcome back, right away
            elif not jarvis_brain.quiet_now():
                self.speaker.say("Welcome back.")
        return True

    def standby_watch(self):
        """Goes into standby after STANDBY_AFTER minutes with nobody at the desk; wakes on keyboard or mouse."""
        while True:
            time.sleep(15)
            try:
                idle = jarvis_brain.idle_seconds()
                if self.standby:
                    if idle < 5:
                        self.leave_standby("keyboard or mouse", greet=False)
                    continue
                if not STANDBY_AFTER or not (self.vision and self.vision.ok):
                    continue   # without the camera Windows' own screen timeout does this job
                away = min(idle, self.vision.seconds_since_face())
                if away > STANDBY_AFTER * 60 and not self.speaker.speaking and not fullscreen_app() \
                        and not (self.brain and self.brain.focus_started):
                    self.enter_standby("nobody here")
            except Exception as e:
                log(f"standby watch: {e}")

    def phone_nudge(self, seconds):
        """Your phone's been out during a focus session."""
        b = self.brain
        if not b or not b.focus_started or self.speaker.speaking:
            return
        left = ""
        if b.focus_timer:
            m = int((b.focus_started + b.focus_timer.interval - time.time()) / 60)
            left = f" {m} minutes left." if m > 1 else " Almost done."
        self.speaker.say(random.choice(["Phone down, Yash.", "Phone's out. Back to it.", "Eyes off the phone."]) + left)
        try:
            b.vault.log("Picked up the phone during focus")
        except Exception:
            pass

    def gesture(self, name):
        """A hand gesture from the camera."""
        if not getattr(jarvis_vision, "GESTURES_ON", True):
            return
        log(f"gesture: {name}")
        pc = self.pc
        if name == "eyes_closed":
            b = self.brain
            if b and b.focus_started and not self.speaker.speaking:
                self.speaker.say("Eyes open, Yash. Stand up for a minute if you need to.")
            return
        if name in ("dial_up", "dial_down"):
            pc.key("vol_up" if name == "dial_up" else "vol_down", 1)
            return
        custom = load_gesture_map().get(name)
        if custom and not (name in ("thumbs_up", "thumbs_down", "nod", "shake") and self.pending):
            log(f"gesture {name} -> {custom}")
            threading.Thread(target=lambda: self.speaker.chime(1480), daemon=True).start()
            threading.Thread(target=self.handle, args=(custom,), daemon=True).start()
            return
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
        elif name in ("nod", "shake"):
            if not self.pending:
                return   # heads move all the time; only an answer to a question counts
            with self.lock:
                self.run("confirm", name == "nod")
        elif name == "push":
            if self.pending:
                with self.lock:
                    self.run("confirm", True)
            else:
                pc.key("play_pause")
        elif name in ("circle_cw", "circle_ccw"):
            pc.key("vol_up" if name == "circle_cw" else "vol_down", 4)
        elif name in ("three", "four"):
            return   # yours to map: "when I hold up three fingers, open my SolidHauz dashboard"
        elif name == "both_palms":
            self.speaker.stop()
            self.pending = None
            return
        elif name in ("wink", "brows"):
            return   # yours to map: "when I wink, play my focus playlist"
        elif name == "thumbs_down":
            if self.pending:
                with self.lock:
                    self.run("confirm", False)
            else:
                return
        elif name == "rock":
            return   # recognized, not used for anything yet
        elif name == "wave":
            self.pc.nudge_display()   # screen on, nothing else
        if name not in ("point_up", "point_down", "peace", "wave"):
            threading.Thread(target=lambda: self.speaker.chime(1480), daemon=True).start()

    def local_url(self, path):
        return f"http://127.0.0.1:{jarvis_phone.PHONE_PORT}{path}?token={jarvis_phone.token()}"

    def open_desk_page(self, path):
        """Opens the desk full screen on the projector."""
        scr = jarvis_desk.projector_screen(or_main=True)
        url = self.local_url(path)
        exe, prof = browser_exe(), browser_profile()
        if not exe:
            exe, prof = jarvis_desk._browser(), None   # no Chrome here: Edge is on every Windows PC
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

    def desk_calibrate(self, d, say):
        """Projects the markers (or, with the laser, 4 dots to touch), lines the camera up, then gets out of the way."""
        self.open_desk_page("/desk")
        if jarvis_desk.DESK_TOUCH == "laser":
            say("Calibrating. Touch each dot as it shows up, and hold it for a second.")
        else:
            say("Calibrating. Keep your hands off the mat for a second.")

        def done(ok):
            if d.mode == "screen":
                time.sleep(0.8)
                self.close_desk_page()
                say("Calibrated. The mat's a touchscreen now. Point to aim, hold still to tap, pinch to drag, two fingers to scroll.")
            else:
                say("Desk calibrated. Touch anything.")
        d.calibrate(done)

    def close_desk_page(self):
        if not IS_WIN:
            return
        try:
            import ctypes
            for hwnd, _, title in jarvis_screen.Screen().windows():
                if title.startswith("Jarvis Desk"):
                    ctypes.windll.user32.PostMessageW(hwnd, 0x0010, 0, 0)   # WM_CLOSE
        except Exception as e:
            log(f"close desk page: {e}")

    def command_state(self):
        """Everything the command center shows, in one go."""
        out = dict(self.desk_state())
        out["orb"] = jarvis_orb.LAST.get("state", "idle")
        out["said"] = getattr(Speaker, "last_line", "")
        out["standby"] = bool(self.standby)
        out["model"] = getattr(self, "model_override", None)
        out["spice"] = PERSONA.spice() if PERSONA else None
        out["camera"] = bool(self.vision and self.vision.ok and self.vision.enabled)
        jb = getattr(self, "jobs", None)
        now = time.time()
        out["jobs"] = [{"text": jarvis_multi.short(j["text"], 9), "secs": int(now - j["t"])}
                       for j in (list(jb.running) if jb else []) if not j.get("dropped")]
        if self.brain:
            v = self.brain.vault
            try:
                rs = os.path.join(v.root, "Research")
                out["research"] = sorted((f[:-3] for f in os.listdir(rs) if f.endswith(".md")), reverse=True)[:4] if os.path.isdir(rs) else []
            except Exception:
                out["research"] = []
            mem = sum(1 for l in (v.read("Jarvis/Memory.md") or "").splitlines() if l.startswith("- "))
            les = sum(1 for l in (v.read("Jarvis/Lessons.md") or "").splitlines() if l.startswith("- "))
            last = (jarvis_evolve.load_state().get("changes") or [{}])[-1].get("summary", "")
            out["self"] = [["Remembers", f"{mem} facts"], ["Learned", f"{les} lessons"]] + ([["Last change", last[:60]]] if last else [])
        if CONVOS:
            out["convo"] = [{"who": "you" if r["who"] == "you" else "atlas", "text": r["text"][:160]}
                            for r in CONVOS.rows(now - 6 * 3600)[-6:]]
        return out

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
        if lock and not (F.AUTO_LOCK and room.owner_known):
            return   # can't tell you from a stranger yet, so never lock
        if lock:
            log("someone else at the desk while you're away, locking")
            self.pc.lock()
            if b:
                b.vault.log("Locked the PC, someone else was at the desk")
            jarvis_phone.push("Someone was at your PC while you were gone, so I locked it.", "Jarvis security", priority=5, tags="lock")
            return
        log(f"people: +{sorted(arrived)} -{sorted(left)}")
        if self.standby and (F.OWNER in arrived or (not room.owner_known and arrived)):
            self.leave_standby("face")
        if not room.owner_known and arrived and getattr(self, "asked_face_day", "") != time.strftime("%Y-%m-%d"):
            self.asked_face_day = time.strftime("%Y-%m-%d")
            self.speaker.say("I can see you, but I don't know your face yet. Say: Atlas, learn my face.")
        others = room.guests()   # only once your face is learned, and only after 15 seconds
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

    def wake_room(self, force=False):
        """The walk in scene: screen on, a short hello and what's next. HQ and music only if you turned them on.
        Clapping again later doesn't repeat it, it just listens like the wake word."""
        was_standby = self.leave_standby("clap", greet=False)
        self.pc.nudge_display()
        if not force and not was_standby and time.time() - self.last_wake < WAKE_SCENE_EVERY * 3600:
            self.listen_requested = True   # main loop chimes and listens
            return
        self.last_wake = time.time()
        snd = threading.Thread(target=lambda: self.speaker.powerup(), daemon=True)
        snd.start()
        if WAKE_OPENS_HQ:
            self.pc.open_url(HQ_URL + "#wake", app_window=HQ_FULLSCREEN)   # #wake plays HQ's full screen takeover here and on the iPad
            if hasattr(self.pc, "arrange"):
                try:
                    self.pc.arrange()
                except Exception as e:
                    log(f"layout failed: {e}")
        if WAKE_MUSIC:
            threading.Thread(target=lambda: log("music: " + jarvis_room.start_music(self.pc, self.spotify, log)), daemon=True).start()
        log("room awake" + (", HQ opened" if WAKE_OPENS_HQ else ""))
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
        if CONVOS and EVOLVER:
            try:
                prev = CONVOS.rows(time.time() - 300)
                you = next((r["text"] for r in reversed(prev) if r["who"] == "you"), "")
                me = " ".join(r["text"] for r in prev if r["who"] != "you" and r["t"] >= (prev[-1]["t"] - 60 if prev else 0))[-300:]
                if you:
                    EVOLVER.learn_from(text, you, me)
            except Exception as e:
                log(f"learn: {e}")
        if CONVOS and PERSONA:
            try:
                prev = CONVOS.rows(time.time() - 600)
                last_me = next((r["text"] for r in reversed(prev) if r["who"] != "you"), "")
                PERSONA.react(text, last_me)
            except Exception as e:
                log(f"persona: {e}")
        if CONVOS:
            CONVOS.add("you", text)
            if self.brain and jarvis_memory.worth_remembering(text):
                # catch important things as you say them, quietly, in the background
                recent = CONVOS.recent(hours=2, max_chars=1500)
                threading.Thread(target=jarvis_memory.capture, daemon=True,
                                 args=(text, recent, lambda pr: ask_claude(pr, None, self.claude, tools="Read", model="haiku")[0], self.brain, log)).start()
        if self.brain:
            self.brain.presence.seen()
        # "this is my dad" ... "his name is Neil": put the real name on the face you just met
        m = re.fullmatch(r"(?:his|her|their) name(?:'s| is) (\w+(?: \w+)?)[.!]?", text.strip().lower())
        just = getattr(self, "just_met", None)
        if m and just and time.time() - just[1] < 180 and self.vision and getattr(self.vision, "faceid", None):
            label, real = just[0], m.group(1)
            if self.vision.faceid.book.rename(label, real):
                self.just_met = None
                if self.brain:
                    self.brain.vault.remember(f"Yash's {jarvis_faces.spoken_name(label).lower()} is named {real.title()}"
                                              if label in RELATIONS else f"{real.title()} is someone Yash introduced")
                self.speaker.say(f"Got it. {real.title()} it is. Hi {real.title()}.")
                return
        cmd = route(text)
        if cmd:
            log(f"command: {cmd}")
            return self.run(*cmd)
        parts = jarvis_multi.split_commands(text, route)
        if parts:
            # several requests in one breath: quick ones now, the rest to Claude as one request
            log("several: " + " | ".join(p for p, _ in parts))
            keep = True
            for piece, c in parts:
                if c:
                    log(f"command: {c}")
                    keep = self.run(*c) is not False and keep
                else:
                    done = [p for p, c2 in parts if c2]
                    keep = self.ask(piece + (f"  (I said all of this: \"{text}\". You already did: {'; '.join(done)}.)" if done else "")) \
                        is not False and keep
            return keep
        return self.ask(text)

    def research(self, topic):
        """A real research job: many sources, a report in the vault, a short spoken answer. Runs in the background."""
        folder = os.path.join(self.brain.vault.root, "Research") if self.brain else os.path.join(WORKDIR, "notes", "Research")
        prompt = jarvis_multi.research_prompt(topic, folder)

        def work():
            return ask_claude(prompt, None, self.claude, full=FULL_ACCESS and not (self.brain and self.brain.guest), model="opus")[0]
        if getattr(self, "jobs", None) and self.jobs.start("research " + topic, work):
            self.speaker.say("Researching it. Give me a few minutes, I'll tell you when the report's in your notes.")
        else:
            self.speaker.say(work())
        return True

    def ask(self, text):
        """Anything the quick commands don't cover goes to Claude. Bigger jobs run in the background. With KEEP_LISTENING
        the answer is worked out on its own thread, so Atlas keeps hearing you (more commands, or cut it off)."""
        m = jarvis_multi.RESEARCH.match(text.strip().rstrip("?.!"))
        if m and len(m.group(1).split()) >= 2:
            return self.research(m.group(1))
        if KEEP_LISTENING and threading.current_thread() is threading.main_thread():
            if not hasattr(self, "convo_lock"):
                self.convo_lock = threading.Lock()
            if self.convo_lock.acquire(blocking=False):
                def run_it():
                    try:
                        jarvis_orb.send("thinking")
                        self._ask(text)
                    except Exception as e:
                        log(f"error: {e}")
                        self.speaker.say("Something broke. Check the Atlas window.")
                    finally:
                        self.convo_lock.release()
                threading.Thread(target=run_it, daemon=True).start()
                return True
            # already thinking about something: this one runs next to it
            if getattr(self, "jobs", None) and self.jobs.start(text, lambda: ask_claude(text, None, self.claude,
                                                                                         full=FULL_ACCESS and not (self.brain and self.brain.guest))[0]):
                self.speaker.say("On it, after this.")
                return True
        return self._ask(text)

    def _ask(self, text):
        guest = bool(self.brain and self.brain.guest)
        if jarvis_multi.BACKGROUND and getattr(self, "jobs", None) and jarvis_multi.is_task(text):
            full_bg = FULL_ACCESS and not guest

            def work():
                before = snapshot_code()
                ans, _ = ask_claude(text, None, self.claude, full=full_bg,
                                    model=jarvis_multi.pick_model(text, CLAUDE_MODEL, getattr(self, "model_override", None)))
                ch = check_code_changes(before)
                if ch and ch[1]:
                    threading.Timer(4.0, lambda: setattr(self, "restart_for_update", True)).start()
                return ans
            if self.jobs.start(text, work):
                self.speaker.say(random.choice(["On it. Keep going, I'll tell you when it's done.", "On it, in the background.",
                                                "Working on it. Ask me anything meanwhile."]))
                return True
        full = FULL_ACCESS and not guest
        spoken = []

        asked_at = time.time()

        def speak(sentence):
            if self.speaker.interrupted or self.speaker.cut_at > asked_at:
                return False   # you cut it off: stop reading the rest
            spoken.append(sentence)
            self.speaker.say(sentence)
            return not (self.speaker.interrupted or self.speaker.cut_at > asked_at)
        before = snapshot_code()
        model = jarvis_multi.pick_model(text, CLAUDE_MODEL, getattr(self, "model_override", None))
        if model != CLAUDE_MODEL:
            log(f"model: {model}")
        answer, self.session_id = ask_claude(text, self.session_id, self.claude, full=full, on_text=speak if STREAM else None,
                                             model=model)
        save_session(self.session_id)
        changed = check_code_changes(before)
        if changed is not None:
            broken, good = changed
            if broken:
                self.speaker.say("That change broke my code, so I put the old version back: " + ", ".join(broken) + ".")
            if good:
                log("code or settings changed: " + ", ".join(good) + ". Restarting to load it.")
                try:   # so "undo your last change" and the boot guard can put it back
                    folder = jarvis_evolve.backup_snapshot(before, "you asked: " + text[:200])
                    jarvis_evolve.mark_pending(folder, "the change you asked for: " + text[:120])
                    if EVOLVER:
                        EVOLVER.changelog("Changed myself because you asked: " + text[:200], good, text[:120])
                except Exception as e:
                    log(f"backup: {e}")
                threading.Timer(4.0, lambda: setattr(self, "restart_for_update", True)).start()
        denied = list(LAST_DENIED)
        real = [x for x in spoken if x not in ("One sec.", "On it.", "Checking.", "Give me a second.", "Working on it.")
                and x not in TOOL_SAYINGS]
        if STREAM and real and not denied:
            return True   # already said it, sentence by sentence
        if self.speaker.cut_at > asked_at:
            return True   # you cut it off and moved on
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

    UNDO = {   # action -> (what it undoes, how)
        "volume_up": ("the volume", lambda self, a: self.pc.key("vol_down", max(1, (a or 10) // 2))),
        "volume_down": ("the volume", lambda self, a: self.pc.key("vol_up", max(1, (a or 10) // 2))),
        "music_pause": ("the pause", lambda self, a: self.run("music_play", None)),
        "music_play": ("that", lambda self, a: self.run("music_pause", None)),
        "next": ("the skip", lambda self, a: self.run("prev", None)),
        "mute": ("mute", lambda self, a: self.pc.key("mute")),
        "focus": ("the focus session", lambda self, a: self.brain and self.brain.end_focus(early=True)),
        "standby": ("standby", lambda self, a: self.leave_standby("undo", greet=False)),
        "monitor_off": ("standby", lambda self, a: self.leave_standby("undo", greet=False)),
        "gestures": ("gestures", lambda self, a: setattr(jarvis_vision, "GESTURES_ON", not a)),
        "vision_focus": ("follow mode", lambda self, a: setattr(self.vision, "zoom_on", not a) if self.vision else None),
        "spice": ("the spice change", lambda self, a: PERSONA and PERSONA.set_spice(delta=-a)),
        "tab_close": ("the tab", lambda self, a: __import__("jarvis_ctl").press(__import__("jarvis_ctl").chord("ctrl+shift+t"))),
        "remember": ("that", lambda self, a: self.brain and jarvis_trust.forget(self.brain.vault, a)),
    }

    def run(self, action, arg):
        say, pc, sp = self.speaker.say, self.pc, self.spotify
        if action in self.UNDO and getattr(self, "undo_log", None):
            label, fn = self.UNDO[action]
            self.undo_log.push(label, lambda f=fn, a=arg: f(self, a))
        amb = getattr(self, "ambient", None)
        if action in ("spice", "spice_set", "persona_me", "persona_jokes", "persona_reset", "persona_grow"):
            pz = PERSONA
            if not pz:
                say("My personality file isn't set up yet.")
            elif action in ("spice", "spice_set"):
                n = pz.set_spice(delta=arg) if action == "spice" else pz.set_spice(value=arg)
                say({1: "Fine. Calm mode. Boring, but calm.", 2: "Dialed down.", 3: "Normal me.", 4: "Back to full personality.",
                     5: "Oh you asked for it. Level five. No brakes."}[n])
            elif action == "persona_me":
                say(ask_claude("In your own voice, out loud, under 60 words: who you are and what we've got going, from your "
                               "character sheet. Be yourself.", None, self.claude, tools="Read")[0])
            elif action == "persona_jokes":
                say(ask_claude("Out loud, under 60 words, in character: our running jokes, nicknames and best moments from your "
                               "character sheet. If there aren't any yet, say we need to fix that.", None, self.claude, tools="Read")[0])
            elif action == "persona_reset":
                pz.reset()
                say("Fresh start. I kept the old me in a backup in case you miss him.")
            else:
                say("Give me a minute, rereading our conversations.")
                threading.Thread(target=lambda: say("Updated myself. Ask me who I am." if pz.rewrite(force=True)
                                                    else "Couldn't rewrite myself right now."), daemon=True).start()
            return True
        if action == "undo_action":
            got = self.undo_log.pop() if getattr(self, "undo_log", None) else None
            if not got:
                say("Nothing recent I can take back.")
            else:
                label, fn = got
                try:
                    fn()
                    say(f"Undid {label}.")
                except Exception as e:
                    say(f"Couldn't undo {label}: {e}")
            return True
        if action == "forget_fact":
            n = jarvis_trust.forget(self.brain.vault, arg) if self.brain else 0
            say(f"Forgot it." if n == 1 else f"Forgot {n} things." if n else "I don't have anything like that saved.")
            return True
        if action in ("routine_add", "routine_list", "routine_del", "quiet_set"):
            rt = getattr(self, "routines", None)
            if action == "quiet_set":
                a, b = arg
                jarvis_brain.QUIET_HOURS = (a, b)
                set_local_setting("QUIET_HOURS", (a, b))
                say(f"Got it. Nothing unprompted from {(a % 12) or 12} {'PM' if a >= 12 else 'AM'} to {(b % 12) or 12} "
                    f"{'PM' if b >= 12 else 'AM'}. Routines you set inside that still go off.")
            elif not rt:
                say("Routines aren't running.")
            elif action == "routine_add":
                d = rt.add(arg)
                rid = rt.items[-1]["id"]
                if getattr(self, "undo_log", None):
                    self.undo_log.push("that routine", lambda: setattr(rt, "items", [r for r in rt.items if r["id"] != rid]) or rt._save())
                say("Done. " + d[0].upper() + d[1:] + ".")
            elif action == "routine_list":
                say("You've got " + "; ".join(jarvis_routines.describe(r) for r in rt.items) + "." if rt.items else "No routines yet.")
            else:
                n = rt.remove(arg)
                say(f"Removed {n} routine{'s' if n != 1 else ''}." if n else "I don't see a routine like that.")
            return True
        if action in ("learn", "wiki_ask", "cards", "quiz"):
            lr = getattr(self, "learner", None)
            if not lr:
                say("The wiki needs your vault, and I can't find it.")
            else:
                msg = lr.handle(action, arg)
                if msg:
                    say(msg)
            return True
        if action in ("voice_set", "voice_list"):
            global ELEVEN_VOICE, VOICE
            if action == "voice_list":
                say(("With ElevenLabs: " + ", ".join(n.title() for n in ELEVEN_VOICES) + ". Built in: ") if ELEVENLABS_KEY else
                    "Built in voices: " + ", ".join(n.title() for n in KOKORO_NAMES) + ". Add an ElevenLabs key for the really human ones.")
                return True
            name = arg.lower()
            if ELEVENLABS_KEY and name in ELEVEN_VOICES:
                ELEVEN_VOICE = name.title()
                set_local_setting("ELEVEN_VOICE", ELEVEN_VOICE)
                self.speaker.eleven_broken = False
                say(f"This is {ELEVEN_VOICE}. Better?")
            elif name in KOKORO_NAMES:
                VOICE = KOKORO_NAMES[name]
                set_local_setting("VOICE", VOICE)
                say(f"Okay, this is {name.title()}. What do you think?")
            elif name in ELEVEN_VOICES:
                say(f"{name.title()} is an ElevenLabs voice. Put your ElevenLabs key in local settings and I can use it.")
            else:
                say(f"I don't have a voice called {name}. Say list your voices.")
            return True
        if action == "install_vision":
            say("Installing vision clicking. It's a big download, I'll tell you when it's ready.")

            def go():
                r = subprocess.run([sys.executable, os.path.join(WORKDIR, "jarvis_ctl.py"), "install-vision"], capture_output=True,
                                   text=True, timeout=3600, creationflags=0x08000000 if IS_WIN else 0)
                log("install-vision: " + (r.stdout or r.stderr)[-300:])
                return "Vision clicking is ready. I can find buttons in any app now." if r.returncode == 0 else "Vision clicking didn't install. Check the Atlas window."
            if getattr(self, "jobs", None):
                self.jobs.start("install vision clicking", go)
            return True
        if action == "chat_open":
            pc.open_window(self.local_url("/chat"))
            say("Chat's open.")
            return True
        if action == "command_center":
            pc.open_url(self.local_url("/command"), app_window=True)
            say("Command center's up.")
            return True
        if action == "obs_plugins":
            if not self.brain:
                say("I can't find your vault.")
            else:
                say("Installing Dataview, Spaced Repetition and Templater.")
                got = jarvis_vaultstyle.install_plugins(self.brain.vault.root, log)
                say(f"Installed {len(got)} plugins. In Obsidian, go to Settings, Community plugins, and turn them on once if it asks."
                    if got else "Couldn't download them. Check the Atlas window.")
            return True
        if action in ("obs_open", "obs_new", "obs_daily"):
            if not self.brain:
                say("I can't find your vault.")
            else:
                jarvis_vaultstyle.handle_obsidian(action, arg, self.brain.vault.root, say)
            return True
        if action == "vault_fix":
            if not self.brain:
                say("I can't find your vault.")
            else:
                n = jarvis_vaultstyle.VaultStyle(self.brain.vault, log).run()
                say(f"Done. Galaxy look is on, I linked {n} notes, and your Atlas home page is up to date. Restart Obsidian to see the new look.")
            return True
        if action == "model_set":
            self.model_override = arg
            say({None: "Back to picking the model myself: quick stuff fast, hard stuff with Opus.",
                 "opus": "Opus for everything. Smartest, a bit slower.", "sonnet": "Sonnet for everything.",
                 "haiku": "Haiku for everything. Fast, not as sharp."}[arg])
            return True
        if action == "model_which":
            ov = getattr(self, "model_override", None)
            say(f"{ov.capitalize()} for everything, you set that." if ov else
                "I pick per request: Haiku for small talk, Opus for research and hard thinking, Sonnet for the rest.")
            return True
        if action in ("jobs_status", "jobs_drop"):
            jb = getattr(self, "jobs", None)
            if not jb:
                say("Nothing running in the background.")
            elif action == "jobs_status":
                say(jb.status())
            else:
                gone = jb.drop_newest()
                say(f"Dropped it: {jarvis_multi.short(gone)}." if gone else "Nothing to drop.")
            return True
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
        if action in ("tabs_list", "tab_switch", "tab_close", "tabs_close_others", "ui_click"):
            jarvis_uia.handle(action, arg, say)
            return True
        if action == "browser":
            kind, site = arg
            new = ("edge://newtab/" if BROWSER == "edge" else "chrome://newtab/")
            url = SITES.get(site, new) if site else new
            # handing the address to the browser opens it in your profile: a new tab in the open window,
            # or a new window when you asked for one. No focus tricks needed.
            pc.open_url(url, app_window=None if kind == "window" else False)
            say(("New window." if kind == "window" else "New tab.") if not site else f"Opening {site} in a new tab.")
            return True
        if action == "convo_recap":
            when = arg
            day = time.strftime("%Y-%m-%d", time.localtime(time.time() - (86400 if when in ("yesterday", "last night") else 0)))
            text = CONVOS.day_text(day) if CONVOS else ""
            if len(text) < 40:
                say("We didn't talk much " + ("yesterday." if day != time.strftime("%Y-%m-%d") else "today yet."))
                return True
            say(ask_claude(f"Recap out loud, in under 60 words, what Yash and you talked about {when}: the main topics, what got "
                           "done, and anything still open. From this transcript:\n" + text[-10000:], None, self.claude, tools="Read")[0])
            return True
        if action == "memory_about":
            mem = self.brain.vault.memory(6000) if self.brain else ""
            if len(mem.strip()) < 20:
                say("Not much yet. Tell me things about you and I'll keep the important ones.")
                return True
            say(ask_claude("Out loud, in under 70 words, tell Yash the most useful things you remember about him, newest and "
                           "most important first, from these notes:\n" + mem, None, self.claude, tools="Read")[0])
            return True
        if action == "convo_search":
            hits = CONVOS.search(arg) if CONVOS else []
            if not hits:
                return self.run("vault_search", arg)   # not in our talks: check his notes
            lines = "\n".join(f"{time.strftime('%a %b %d %H:%M', time.localtime(h['t']))} {'Yash' if h['who'] == 'you' else 'Jarvis'}: {h['text']}" for h in sorted(hits, key=lambda h: h['t']))
            say(ask_claude(f"From these past conversation lines, answer out loud in under 50 words what was said about {arg}, "
                           "with roughly when:\n" + lines, None, self.claude, tools="Read")[0])
            return True
        if action == "mod":
            mod, (act, a) = arg
            try:
                mod.handle(self, act, a)
            except Exception as e:
                log(f"mod {mod.__name__}: {e}")
                say("My add on for that broke. Ask me to fix it.")
            return True
        if action == "handbook":
            pc.open_url(HANDBOOK_URL)
            say("Here's the handbook. Every gesture and everything you can say.")
            return True
        if action == "activity":
            if not ACTIVITY:
                say("I'm not tracking that yet.")
            elif "before" in arg:
                prev = ACTIVITY.before()
                say(f"Before this you were in {prev['app']}" + (f", on {prev['title']}." if prev["title"] else ".") if prev else "This is the first thing you've done in a while.")
            else:
                say(ACTIVITY.spoken(180 if "today" in arg else 60))
            return True
        if action in ("version", "whats_new"):
            v = read_version()
            if not v:
                say("I can't tell which version I'm on. Say update yourself and I'll get the latest.")
            elif action == "version":
                say(f"I'm on the version from {v['when']}. " + ("A newer one is waiting, say update yourself." if update_waiting() else "That's the latest."))
            else:
                news = [re.sub(r"^Jarvis[^:]*:\s*", "", x).split(";")[0].split(",")[0] for x in v.get("recent", [])[:3]]
                say("Latest changes: " + ". ".join(news) + "." if news else f"I'm on the version from {v['when']}.")
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
                say(f"{len(bad)} problem{'s' if len(bad) > 1 else ''}. First one: {bad[0][0]}. {bad[0][1]} The full list is in the Atlas window.")
            return True
        if action == "voice_input":
            set_local_setting("VOICE_INPUT", bool(arg))
            say("Mic on. Restarting to load it." if arg else "Typing only from now on. Restarting.")
            self.restart_for_update = True
            return True
        if action == "update":
            if update_waiting():
                say("Updating. Give me a minute.")
                threading.Thread(target=run_update_now, args=(self, True), daemon=True).start()
            else:
                try:
                    st = json.load(open(os.path.join(WORKDIR, ".update_status.json")))
                except Exception:
                    st = {"ok": True}
                if not st.get("ok"):
                    say("I couldn't reach the update. " + re.sub(r"[^\w\s.,']", " ", st.get("error", ""))[:160] + ". Check the internet, or run the installer once.")
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
            say("Goodnight Yash. Shutting the room down. Clap or say my name and I'm back.")
            self.enter_standby("goodnight")
        elif action == "monitor_off":
            self.enter_standby("asked")
        elif action == "standby":
            say("Standing by. Clap, say my name, or sit down and I'll wake up.")
            self.enter_standby("asked")
        elif action == "sessions":
            cc = jarvis_claude.ClaudeControl(say, pc, self.claude or find_claude())
            cc.handle("cc_recent", None)   # on this PC
            cc.cloud_list()                # in the cloud
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
                      "stat", "streaks", "pregame", "restore", "shop", "due", "weekly", "mail_check", "remind_return"):
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
        if action == "desk_status":
            say(self.desk.status() if self.desk else "The desk isn't set up. It needs the phone bridge on.")
            return True
        if action in ("desk", "desk_cal", "desk_cards", "holo"):
            d = self.desk
            if not d:
                say("The desk needs the phone bridge on. Set PHONE SERVER to True.")
            elif action == "desk":
                mode = arg if arg in ("screen", "panels") else (jarvis_desk.DESK_MODE if arg else None)
                if mode == "screen":
                    d.mode = "screen"
                    self.close_desk_page()
                    d.start()
                    if d.cal.ready:
                        say("The mat's a touchscreen. Point to aim, hold still to tap, pinch to drag, two fingers to scroll.")
                    else:
                        self.desk_calibrate(d, say)
                elif mode == "panels":
                    d.mode = "panels"
                    d.start()
                    self.open_desk_page("/desk")
                    say("Desk online." + ("" if d.cal.ready else " First time: say calibrate the desk."))
                else:
                    d.stop()
                    self.close_desk_page()
                    say("Desk off.")
            elif action == "desk_cal":
                self.desk_calibrate(d, say)
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
                say("Face ID didn't load. Check the Atlas window for the reason.")
            elif action == "face_learn":
                who = "you" if arg == jarvis_faces.OWNER else jarvis_faces.spoken_name(arg)
                say(f"Look at the camera, {'' if who == 'you' else who + ', '}and turn your head a little side to side.")

                def done(name, n):
                    if not name:
                        say("I couldn't see a face. Get closer to the camera and try again.")
                    elif name == jarvis_faces.OWNER:
                        say(f"Got you, Yash. I'll know it's you from now on.")
                    else:
                        self.just_met = (name, time.time())
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
        if action in ("evolve", "evolve_undo", "evolve_recap", "evolve_lessons"):
            ev = EVOLVER
            if not ev:
                say("Self improvement isn't running.")
            elif action == "evolve":
                say("On it. I'll work on " + (arg if arg else "what went wrong lately") + " and tell you when it's done. Keep using me.")
                threading.Thread(target=ev.improve, args=(arg,), daemon=True).start()
            elif action == "evolve_undo":
                why = ev.undo()
                if why is None:
                    say("There's nothing to undo.")
                else:
                    say("Put my code back to how it was before that change. Restarting.")
                    threading.Timer(3.0, lambda: setattr(self, "restart_for_update", True)).start()
            elif action == "evolve_recap":
                say(ev.recap())
            else:
                les = ev.lessons(2000)
                say(ask_claude("Out loud in under 60 words, the most useful things these lessons say you learned from Yash's "
                               "corrections:\n" + les, None, self.claude, tools="Read")[0] if les else "Nothing yet. Correct me when I get something wrong and I'll remember it.")
            return True
        if action == "gesture_map":
            g, cmd = arg
            gm = load_gesture_map()
            nice = lambda x: x.replace("_", " ").replace("rock", "rock sign")
            if g == "?":
                say("Your custom gestures: " + "; ".join(f"{nice(k)} does {v}" for k, v in gm.items()) + "." if gm
                    else "No custom gestures yet. Say something like, when I do the rock sign, open Spotify.")
            elif g is None:
                save_gesture_map({})
                say("Gestures are back to normal.")
            elif cmd is None:
                gm.pop(g, None)
                save_gesture_map(gm)
                say(f"{nice(g).capitalize()} is back to normal.")
            else:
                gm[g] = cmd
                save_gesture_map(gm)
                say(f"Done. {nice(g).capitalize()} now does: {cmd}.")
            return True
        if action == "vision_focus":
            v = self.vision
            if not v or not v.ok:
                say("The camera isn't running.")
            else:
                v.zoom_on = arg
                if not arg:
                    v.roi = None
                known = bool(v.faceid and jarvis_faces.OWNER in v.faceid.book.people)
                say(("Locked on you. I'll follow you and read your hands from farther away."
                     + ("" if known else " Say learn my face so I follow only you.")) if arg else "Okay, not following you anymore.")
            return True
        if action == "gestures":
            jarvis_vision.GESTURES_ON = arg
            say("Hand gestures on. Hold your hand up toward the camera to use them." if arg else "Hand gestures off. The camera still sees you. Say gestures on to bring them back.")
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
        if action.startswith("chats_") and action != "chats_open":
            ch = getattr(self, "chats", None) or jarvis_chats.Chats(say, lambda pr: ask_claude(pr, None, self.claude, tools="Read")[0],
                                                                   vault=self.brain.vault if self.brain else None, open_url=pc.open_url)
            ch.handle(action, arg)
            return True
        if action.startswith(("cc_", "chat_", "claude_", "cloud_")) or action == "chats_open":
            done = jarvis_claude.ClaudeControl(say, pc, self.claude or find_claude()).handle(action, arg)
            if done is False and action == "cloud_send":
                return self.run("session_send", (arg[0] or "latest", arg[1]))   # not one Atlas started: try the connector
            return True
        elif action == "sleep":
            say("Going offline.")
            return False
        elif action == "reset":
            self.session_id = None
            save_session(None)
            say("Fresh start.")
        elif action == "hq":
            self.wake_room(force=True)
        elif action == "hq_open":
            pc.open_url(HQ_URL, app_window=HQ_FULLSCREEN)
            say("HQ is up.")
        elif action == "lock":
            say("Locking.")
            pc.lock()
        elif action == "play_pause":
            pc.key("play_pause")
        elif action in ("music_pause", "music_play"):
            playing = music_playing(sp, pc)
            want = action == "music_play"
            if playing is want:
                pass   # already how you want it: pressing the key would flip it the wrong way
            elif sp.ready and spotify_api(sp, "PUT", "/me/player/" + ("play" if want else "pause")):
                pass
            else:
                pc.key("play_pause")
        elif action == "next":
            if not (sp.ready and spotify_api(sp, "POST", "/me/player/next")):
                pc.key("next")
        elif action == "prev":
            if not (sp.ready and spotify_api(sp, "POST", "/me/player/previous")):
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
                say("New window.")
                return True
            existing = jarvis_trust.find_window(arg)
            if existing:   # already running: bring it up instead of opening a second copy
                try:
                    jarvis_screen.Screen().focus(existing)
                except Exception:
                    pass
                say(f"{arg.title()} is up front.")
                return True
            before = jarvis_trust._windows()
            pc.launch(APPS[arg])
            say("Opening " + arg + ".")

            def check(name=arg):
                h = jarvis_trust.verify_open(name, before, timeout=10)
                if h is False:
                    say(f"{name.title()} didn't open. Want me to try another way?")
                elif h and getattr(self, "undo_log", None):
                    self.undo_log.push(name, lambda: IS_WIN and __import__("ctypes").windll.user32.PostMessageW(h, 0x0010, 0, 0))
            threading.Thread(target=check, daemon=True).start()
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
    no_quick_edit()
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

    wake = None
    if VOICE_INPUT:
        from openwakeword.model import Model
        from openwakeword.utils import download_models
        if not WAKE_WORD.endswith(".onnx"):
            download_models([WAKE_WORD])
        wake = Model(wakeword_models=[WAKE_WORD], inference_framework="onnx")
    else:
        typing_console()

    jarvis_room.keep_awake()
    if ORB:
        pyw = os.path.join(os.path.dirname(sys.executable), "pythonw.exe")
        subprocess.Popen([pyw if os.path.exists(pyw) else sys.executable, os.path.join(WORKDIR, "jarvis_orb.py")], cwd=WORKDIR)
        jarvis_orb.send("thinking")   # loading models
    whisper = load_whisper()[0] if VOICE_INPUT else None
    WHISPER_HOLDER["model"] = whisper   # for Telegram voice notes
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
    global ACTIVITY, MODS, CONVOS
    MODS = load_mods()
    CONVOS = jarvis_memory.Conversations(vault=BRAIN.vault)
    def _said(text):
        CONVOS.add("jarvis", text)
        jarvis_chatui.add("atlas", text)   # the chat window shows everything Atlas says
    Speaker.on_said = _said
    global EVOLVER
    EVOLVER = jarvis_evolve.Evolver(claude_cmd(jarvis.claude or find_claude() or "claude"), LOG_FILE, vault=BRAIN.vault,
                                    say=speaker.say, news=BRAIN.news, restart=lambda: setattr(jarvis, "restart_for_update", True),
                                    idle=lambda: min(jarvis_brain.idle_seconds(), jarvis.vision.seconds_since_face() if jarvis.vision else 1e9),
                                    ask=lambda pr: ask_claude(pr, None, jarvis.claude, tools="Read", model="haiku")[0])
    threading.Thread(target=EVOLVER.nightly, daemon=True).start()
    threading.Timer(150, jarvis_evolve.confirm_boot).start()   # up for a couple of minutes: the last change is good
    if os.path.exists(jarvis_evolve.REVERTED):
        try:
            gone = json.load(open(jarvis_evolve.REVERTED)).get("summary", "")
            os.remove(jarvis_evolve.REVERTED)
            BRAIN.news.append("My last change to myself kept me from starting, so I undid it" + (f": {gone}" if gone else "") + ".")
        except Exception:
            pass
    threading.Thread(target=jarvis_vaultstyle.VaultStyle(BRAIN.vault, log).watch, daemon=True).start()
    def start_job(label, prompt, quiet=False):
        full = FULL_ACCESS and not (BRAIN and BRAIN.guest)
        work = lambda: ask_claude(prompt, None, jarvis.claude, full=full, model="opus" if "upkeep" not in label else "sonnet")[0]
        if quiet or not jarvis.jobs.start(label, work):
            threading.Thread(target=work, daemon=True).start()
    jarvis.learner = jarvis_learn.Learner(BRAIN.vault, start_job, lambda p: (jarvis.ask(p), None)[1],
                                          clipboard=jarvis_extras.clipboard_text, log=log)
    threading.Thread(target=jarvis.learner.watch, daemon=True).start()
    global PERSONA
    PERSONA = jarvis_persona.Persona(BRAIN.vault, ask=lambda pr: ask_claude(pr, None, jarvis.claude, tools="Read", model="opus")[0],
                                     convos=CONVOS, name=ASSISTANT_NAME)
    threading.Thread(target=PERSONA.watch, daemon=True).start()
    if TELEGRAM_TOKEN:
        def tg_ask(text):
            return jarvis.remote_ask(text, speak=False)

        def tg_transcribe(path):
            from faster_whisper import decode_audio
            return transcribe(WHISPER_HOLDER["model"], decode_audio(path, sampling_rate=16000)) if WHISPER_HOLDER.get("model") else ""
        jarvis.telegram = jarvis_trust.Telegram(TELEGRAM_TOKEN, TELEGRAM_CHAT_ID, tg_ask, tg_transcribe,
                                                save_chat=lambda c: set_local_setting("TELEGRAM_CHAT_ID", c), log=log)
        threading.Thread(target=jarvis.telegram.run, daemon=True).start()
    jarvis.jobs = jarvis_multi.Jobs(speaker.say, lambda: not speaker.speaking and not getattr(jarvis, "recording", False),
                                    lock=jarvis.lock, log=log)
    if getattr(jarvis, "telegram", None):
        def job_say(text, _say=speaker.say):
            _say(text)
            if BRAIN and (BRAIN.presence.away or jarvis_brain.idle_seconds() > 600):
                jarvis.telegram.send(text)   # you're not at the desk: it goes to your phone too
        jarvis.jobs.say = job_say
    jarvis.chats = jarvis_chats.Chats(speaker.say, lambda pr: ask_claude(pr, None, jarvis.claude, tools="Read")[0], vault=BRAIN.vault,
                                      remember=BRAIN.vault.remember, open_url=jarvis.pc.open_url)
    threading.Thread(target=jarvis.chats.watch, daemon=True).start()

    def daily_digest():
        """Once a day: lasting facts from yesterday's conversations go into Memory.md."""
        time.sleep(180)
        while True:
            _digest_once()
            time.sleep(6 * 3600)   # Jarvis can run for days; check again later

    def _digest_once():
        state = os.path.join(WORKDIR, ".memory_state.json")
        try:
            done = set(json.load(open(state)).get("digested", []))
        except Exception:
            done = set()
        for back in (2, 1):
            day = time.strftime("%Y-%m-%d", time.localtime(time.time() - back * 86400))
            if day in done:
                continue
            try:
                facts = CONVOS.digest_day(day, lambda prompt: ask_claude(prompt, None, claude, tools="Read")[0], BRAIN)
                log(f"remembered {len(facts)} lasting facts from {day}")
            except Exception as e:
                log(f"memory digest: {e}")
                continue
            done.add(day)
        try:
            json.dump({"digested": sorted(done)[-60:]}, open(state, "w"))
        except OSError:
            pass
    threading.Thread(target=daily_digest, daemon=True).start()
    ACTIVITY = jarvis_activity.Activity(sample=jarvis_extras.foreground_window, music=jarvis.pc.spotify_title,
                                        at_desk=lambda: (jarvis.vision.seconds_since_face() < 60) if jarvis.vision and jarvis.vision.ok and jarvis.vision.enabled else None,
                                        idle=jarvis_brain.idle_seconds).start()
    jarvis.activity = ACTIVITY
    v = read_version()
    log("version: " + (f"{v['when']} ({v.get('commit', '')[:7]})" if v else "unknown, say update yourself"))
    try:   # say so when this start is a new version, so you know the update really landed
        lb = os.path.join(WORKDIR, ".last_boot_version")
        prev = open(lb).read().strip() if os.path.exists(lb) else ""
        cur = (v or {}).get("commit", "")
        if cur and prev and cur != prev:
            threading.Timer(4.0, lambda: speaker.say(f"Update installed. I'm on the version from {v['when']}.")).start()
        if cur:
            open(lb, "w").write(cur)
    except Exception as e:
        log(f"version note: {e}")
    jarvis.hqsync = jarvis_hqsync.HQSync(jarvis).start()   # what Jarvis is doing, on HQ on the iPad
    if jarvis_vision.VISION:
        jarvis.vision = jarvis_vision.Vision(on_gesture=jarvis.gesture, say=speaker.say, on_people=jarvis.people)
        jarvis.vision.phone_watch = lambda: bool(BRAIN and BRAIN.focus_started)
        jarvis.vision.on_phone = jarvis.phone_nudge
        jarvis.vision.start()
        if jarvis_vision.PRESENCE_FROM_CAMERA:
            BRAIN.presence.idle = lambda: min(jarvis_brain.idle_seconds(), jarvis.vision.seconds_since_face())
    if jarvis_phone.PHONE_SERVER:
        try:
            bridge = jarvis_phone.Bridge(jarvis.remote_ask, jarvis.phone_event).start()
            def camera_jpg(h, q):
                path = os.path.join(WORKDIR, ".cache", "camera.jpg")
                ok = None
                if jarvis.vision and jarvis.vision.enabled:
                    try:
                        ok = jarvis.vision.snapshot(path)
                    except Exception as e:
                        log(f"camera snapshot: {e}")
                body = open(ok, "rb").read() if ok else b"camera off or unavailable"
                h.send_response(200 if ok else 503)
                h.send_header("Content-Type", "image/jpeg" if ok else "text/plain")
                h.send_header("Content-Length", str(len(body)))
                h.end_headers()
                h.wfile.write(body)
            bridge.routes["/camera.jpg"] = camera_jpg

            def command_page(h, q):
                body = open(os.path.join(WORKDIR, "command.html"), encoding="utf-8").read().encode("utf-8")
                h.send_response(200)
                h.send_header("Content-Type", "text/html; charset=utf-8")
                h.send_header("Content-Length", str(len(body)))
                h.send_header("Cache-Control", "no-store")
                h.end_headers()
                h.wfile.write(body)

            def command_json(h, q):
                try:
                    body = json.dumps(jarvis.command_state()).encode("utf-8")
                except Exception as e:
                    body = json.dumps({"error": str(e)}).encode("utf-8")
                h.send_response(200)
                h.send_header("Content-Type", "application/json")
                h.send_header("Content-Length", str(len(body)))
                h.send_header("Cache-Control", "no-store")
                h.end_headers()
                h.wfile.write(body)
            def memory_json(h, q):
                if q.get("delete") and BRAIN:
                    jarvis_trust.forget(BRAIN.vault, q["delete"], q.get("kind"))
                body = json.dumps(jarvis_trust.facts(BRAIN.vault) if BRAIN else []).encode("utf-8")
                h.send_response(200)
                h.send_header("Content-Type", "application/json")
                h.send_header("Content-Length", str(len(body)))
                h.send_header("Cache-Control", "no-store")
                h.end_headers()
                h.wfile.write(body)
            bridge.routes["/command/memory"] = memory_json
            bridge.routes["/command"] = command_page
            jarvis_chatui.register(bridge, jarvis, orb_state=lambda: jarvis_orb.LAST.get("state", "idle"))
            if CHAT_ON_START or not VOICE_INPUT:   # the chat window opens with Atlas
                threading.Timer(2.0, lambda: jarvis.pc.open_window(jarvis.local_url("/chat"))).start()
            bridge.routes["/command/state"] = command_json
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
                jarvis.desk.vision = jarvis.vision   # so a PC with one camera can share it with the desk
                jarvis.desk.register(bridge)
        except Exception as e:
            log(f"phone bridge off: {e}")
    claps = ClapDetector()
    mic, _ = resolve_devices()

    def sp_volume():
        if not jarvis.spotify.ready:
            return None
        return ((jarvis.spotify._api("GET", "/me/player") or {}).get("device") or {}).get("volume_percent")
    ambient = jarvis_audio.Ambient(own_voice=lambda: speaker.speaking, spotify_title=jarvis.pc.spotify_title,
                                   volume_get=sp_volume, volume_set=lambda v: jarvis.spotify._api("PUT", f"/me/player/volume?volume_percent={int(v)}"))
    jarvis.ambient = ambient
    ambient.release_when_idle(lambda: speaker.speaking or jarvis.recording or jarvis.listen_requested
                              or bool(getattr(jarvis, "convo_lock", None) and jarvis.convo_lock.locked()))

    def run_routine(text):
        with jarvis.lock:
            jarvis.handle(text)
    jarvis.routines = jarvis_routines.Routines(speaker.say, run_routine,
                                               busy=lambda: speaker.speaking or jarvis.recording, log=log)
    threading.Thread(target=jarvis.routines.watch, daemon=True).start()
    if PUSH_TO_TALK:
        threading.Thread(target=push_to_talk, args=(jarvis,), daemon=True).start()

    def barge(frame):
        if CLAP_WAKE and not ambient.playing and claps.feed(frame):   # songs are full of claps
            return True
        return wake.predict(frame).get(WAKE_KEY, 0) >= max(WAKE_THRESHOLD, BARGE_THRESHOLD)
    speaker.watch = barge if VOICE_INPUT else None

    def typed():
        """Type to Atlas in its window: anything you'd say, without the name. Works alongside the mic."""
        time.sleep(1 if not VOICE_INPUT else 3)
        if VOICE_INPUT:
            print("\n  Type to Atlas here any time (e.g. desk mode). Press Enter to send.\n", flush=True)
        else:
            print(PROMPT, end="", flush=True)
        while True:
            try:
                line = input().strip()
            except EOFError:
                return
            except Exception:
                time.sleep(1)
                continue
            if not line:
                if not VOICE_INPUT:
                    print(PROMPT, end="", flush=True)
                continue
            log(f"you (typed): {line}")
            jarvis_chatui.add("you", line)
            jarvis.last_heard = time.time()
            try:
                jarvis_orb.send("thinking")
                with jarvis.lock:
                    keep = jarvis.handle(line)
                if not keep:
                    hard_exit(0, "going offline")
            except Exception as e:
                log(f"error: {e}")
                if not VOICE_INPUT:
                    speaker.say(f"That broke: {str(e)[:120]}")
            jarvis_orb.send("idle")
            if not VOICE_INPUT:
                print(f"\r\033[K{PROMPT}", end="", flush=True)
    if not VOICE_INPUT:
        jarvis.record_long = jarvis.extras.record_long = lambda: input("\033[38;5;245m  dictate\033[0m ").strip()
        threading.Thread(target=nightly_update_watch, args=(jarvis,), daemon=True).start()
        threading.Thread(target=reactive_watch, args=(jarvis,), daemon=True).start()
        threading.Thread(target=jarvis.standby_watch, daemon=True).start()
        threading.Thread(target=typed, daemon=True).start()
        jarvis_orb.send("idle")
        log("typing mode: no microphone")
        while True:
            time.sleep(0.5)
            if jarvis.restart_for_update:
                hard_exit(3, "restarting into the update")
    if TYPE_TO_ATLAS and sys.stdin and sys.stdin.isatty():
        threading.Thread(target=typed, daemon=True).start()

    with Mic(mic):
        import jarvis_listen
        noise = jarvis_listen.NoiseFloor(np.median([np.sqrt(np.mean(audio_q.get().astype(np.float32) ** 2)) for _ in range(25)]))

        def record_long():
            drain_mic()
            jarvis_orb.send("listening")
            speaker.cue("long")
            drain_mic()
            a = record_until_silence(noise, silence=4.0, max_secs=180, wait_for_voice=10)
            speaker.cue("heard" if a is not None else "nothing", wait=False)
            jarvis_orb.send("thinking")
            return transcribe(whisper, a) if a is not None else ""
        jarvis.record_long = record_long
        jarvis.extras.record_long = record_long
        jarvis_orb.send("idle")
        log(f"listening for '{WAKE_WORD.replace('_', ' ')}'" + (" and double claps" if CLAP_WAKE else "") + f" (room noise {noise:.0f})")

        threading.Thread(target=nightly_update_watch, args=(jarvis,), daemon=True).start()
        threading.Thread(target=reactive_watch, args=(jarvis,), daemon=True).start()
        threading.Thread(target=jarvis.standby_watch, daemon=True).start()
        spotter = None
        if WAKE_NAME:
            def quick_text(a):
                segs, _ = whisper.transcribe(a, language="en", beam_size=1, without_timestamps=True, vad_filter=False,
                                             initial_prompt=f"{ASSISTANT_NAME}.", condition_on_previous_text=False)
                return " ".join(x.text for x in segs)
            spotter = jarvis_wake.PhraseSpotter(quick_text, WAKE_NAME, noise=noise)
            log(f"also listening for the name '{WAKE_NAME}'")
        while True:
            frame = audio_q.get()
            if jarvis.restart_for_update:
                hard_exit(3, "restarting into the update")   # start.bat pulls the new code and starts again
            if time.time() < jarvis.quiet_until:
                continue
            if not speaker.speaking and not jarvis.recording:
                noise.feed(frame)   # keeps learning how loud the room is
            named = None
            if spotter and not speaker.speaking:   # don't wake on its own voice
                spotter.feed(frame)
                named = spotter.poll()
            follow = None
            if FOLLOWUP_SECONDS and not speaker.speaking and not named and not jarvis.listen_requested and not ambient.playing \
                    and 0.35 < time.time() - speaker.last_end < FOLLOWUP_SECONDS and speaker.last_end > jarvis.last_heard:
                loud = float(np.sqrt(np.mean(frame.astype(np.float32) ** 2))) > max(noise * 3.5, 400)
                jarvis.follow_frames = (jarvis.follow_frames + [frame])[-3:] if loud else []
                if len(jarvis.follow_frames) >= 2:   # you started talking again: keep going, no name needed
                    follow, jarvis.follow_frames = list(jarvis.follow_frames), []
            if CLAP_WAKE and not ambient.playing and claps.feed(frame):
                wake.reset()
                try:
                    jarvis.wake_room()
                except Exception as e:
                    log(f"wake failed: {e}")
                drain_mic()
                jarvis.quiet_until = time.time() + 1.0
                continue
            text = None
            jarvis.recording = bool(named) or bool(follow) or jarvis.listen_requested
            if follow:
                jarvis_orb.send("listening")
                more = record_until_silence(noise, wait_for_voice=1.5)
                audio = np.concatenate([np.concatenate(follow).astype(np.float32) / 32768.0] + ([more] if more is not None else []))
                jarvis_orb.send("thinking")
                heard = transcribe(whisper, audio)
                jarvis.recording = False
                if not heard or len(heard.split()) < 2 and heard.lower().strip(" .!?") not in ("yes", "no", "yeah", "nope", "stop", "pause", "next", "thanks"):
                    jarvis_orb.send("idle")
                    jarvis.last_heard = time.time()   # one try per reply, so room noise can't keep it listening
                    continue
                text = jarvis_wake.strip_name(heard, WAKE_NAME) if WAKE_NAME else heard
            elif named:
                # "Atlas" alone: chime and listen. "Atlas, open Spotify": the rest of the sentence is the command.
                audio, finished, rest = named
                ambient.duck()   # music down so it can hear the rest of what you say
                jarvis.leave_standby("voice", greet=False)
                if speaker.speaking:
                    speaker.stop()
                if not finished:
                    jarvis_orb.send("listening")
                    more = record_until_silence(noise, wait_for_voice=1.5)
                    if more is not None:
                        audio = np.concatenate([audio, more])
                if finished and not rest:
                    text = None   # just the name: fall through to the chime
                else:
                    jarvis_orb.send("thinking")
                    text = jarvis_wake.strip_name(transcribe(whisper, audio), WAKE_NAME)
                    if not text:
                        text = None
                if text is None and finished and rest:
                    text = rest
                if text is None:
                    pass
                else:
                    wake.reset()
                    spotter.reset()
            elif jarvis.listen_requested:
                jarvis.listen_requested = False   # peace sign to the camera
            elif wake.predict(frame).get(WAKE_KEY, 0) < WAKE_THRESHOLD:
                continue

            if text is None:
                jarvis.recording = True   # background jobs wait to report until you're done talking
                ambient.duck()            # music down while you talk and it answers
                wake.reset()
                if spotter:
                    spotter.reset()
                jarvis.leave_standby("voice", greet=False)
                if speaker.speaking:
                    speaker.stop()
                drain_mic()
                jarvis_orb.send("listening")
                speaker.cue("listen")
                drain_mic()   # just the cue's own echo (it's 0.13 s), not you
                audio = record_until_silence(noise)
                speaker.cue("heard" if audio is not None else "nothing", wait=False)
                if audio is None:
                    jarvis.recording = False
                    jarvis_orb.send("idle")
                    continue
                jarvis_orb.send("thinking")
                text = transcribe(whisper, audio)
            jarvis.recording = False
            jarvis.last_heard = time.time()
            log(f"you: {text}")
            jarvis_chatui.add("you", text)
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
                speaker.cue("error")
                speaker.say("Something broke. Check the Atlas window.")
            jarvis_orb.send("idle")
            if speaker.interrupted:           # you cut it off: it stops talking and listens to you right away
                speaker.interrupted = False
                jarvis.listen_requested = True
                wake.reset()
                continue
            drain_mic()                       # don't hear itself
            jarvis.quiet_until = time.time() + 1.0
            wake.reset()
            if spotter:
                spotter.reset()


def no_quick_edit():
    """Clicking inside a Windows console window pauses the program until you press a key (Quick Edit). For a
    program that runs all day in that window, that's a freeze. Turn it off for this window."""
    if sys.platform != "win32":
        return
    try:
        import ctypes
        k = ctypes.windll.kernel32
        h = k.GetStdHandle(-10)
        mode = ctypes.c_uint32()
        if k.GetConsoleMode(h, ctypes.byref(mode)):
            k.SetConsoleMode(h, (mode.value & ~0x0040) | 0x0080)
    except Exception:
        pass


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
    if IS_WIN:
        # os._exit still lets the sound and GPU drivers run their shutdown code, and one of them can deadlock there,
        # which left Jarvis frozen on "restarting into the update". TerminateProcess skips all of that.
        try:
            import ctypes
            k = ctypes.windll.kernel32
            k.TerminateProcess(k.GetCurrentProcess(), code)
        except Exception:
            pass
    os._exit(code)


if __name__ == "__main__":
    try:
        sys.exit(main() or 0)
    except KeyboardInterrupt:
        pass
