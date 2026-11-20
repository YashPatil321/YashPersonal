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
import re
import secrets
import shutil
import subprocess
import sys
import threading
import time
import urllib.parse
import urllib.request

import numpy as np

import jarvis_claude
import jarvis_room

# ---------------- settings you might change ----------------
MIC_DEVICE = None            # None = find the Focusrite by name. Or put a number from --devices
MIC_NAME_HINTS = ["focusrite", "scarlett"]
MIC_CHANNEL = 0              # Focusrite input 1 = 0, input 2 = 1
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
SPOTIFY_CLIENT_ID = ""       # optional, from developer.spotify.com. Then run --spotify-login once
NTFY_TOPIC = ""              # optional: phone push on clap. Install the ntfy app on your iPhone, subscribe to a long random topic, paste it here
# your cloud Claude Code sessions, through the claude.ai Claude Code Remote connector (run --doctor to confirm the name)
SESSIONS_TOOLS = "mcp__claude_ai_Claude_Code_Remote__list_sessions,mcp__claude_ai_Claude_Code_Remote__get_session,mcp__claude_ai_Claude_Code_Remote__list_events"
SESSIONS_SEND = "mcp__claude_ai_Claude_Code_Remote__send_message"
# -----------------------------------------------------------

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
            audio_q.put(indata[:, MIC_CHANNEL].copy())

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
                audio_q.put(resample(indata[:, MIC_CHANNEL], FRAME))

            self.stream = sd.InputStream(samplerate=sr, channels=ch, dtype="int16", blocksize=block,
                                         device=self.device, callback=cb_resample)
            self.stream.start()
        return self

    def __exit__(self, *a):
        if self.stream:
            self.stream.stop()
            self.stream.close()


def drain_mic():
    while not audio_q.empty():
        audio_q.get_nowait()


def frame_stats(frame):
    f = frame.astype(np.float32) / 32768.0
    peak = float(np.max(np.abs(f))) if f.size else 0.0
    rms = float(np.sqrt(np.mean(f ** 2))) if f.size else 0.0
    return peak, rms


def record_until_silence(noise_floor):
    """Record after the wake word until the speaker goes quiet."""
    threshold = max(noise_floor * 3.0, 300)
    chunks, silent_for, heard_voice = [], 0.0, False
    start = time.time()
    while time.time() - start < MAX_RECORD_SECONDS:
        chunk = audio_q.get()
        chunks.append(chunk)
        loud = np.sqrt(np.mean(chunk.astype(np.float32) ** 2)) > threshold
        if loud:
            heard_voice, silent_for = True, 0.0
        else:
            silent_for += FRAME / RATE
        if heard_voice and silent_for >= SILENCE_SECONDS:
            break
        if not heard_voice and time.time() - start > 5:
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

    def say(self, text):
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
        """A short rising chord: the room powering on."""
        sd = _sd()
        sr, dur = 24000, 0.9
        t = np.linspace(0, dur, int(sr * dur), False)
        sweep = np.zeros_like(t)
        for i, f in enumerate((220, 330, 440, 660)):
            env = np.clip((t - i * 0.12) * 8, 0, 1) * np.exp(-np.clip(t - i * 0.12, 0, None) * 2.2)
            sweep += np.sin(2 * np.pi * f * (1 + 0.04 * t) * t) * env
        sd.play((0.12 * sweep / max(1e-6, np.max(np.abs(sweep)))).astype(np.float32), sr, device=SPEAKER_DEVICE)
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
        log(f"open {url}")
        if IS_WIN and app_window:
            for exe in (r"C:\Program Files\Google\Chrome\Application\chrome.exe",
                        r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe",
                        r"C:\Program Files\Microsoft\Edge\Application\msedge.exe"):
                if os.path.exists(exe):
                    subprocess.Popen([exe, "--app=" + url, "--start-fullscreen"])
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
    if re.search(r"\b(what are|how are|status of|check on) my (claude )?(cloud )?(sessions|agents)( doing)?\b|\bsession status\b", t):
        return ("sessions", None)
    cc = jarvis_claude.route_claude(t)
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
    m = re.fullmatch(r"(?:take a note|note to self|make a note|write down|remember)(?: that)? (.+)", t)
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
    if re.search(r"\b(next|skip)( the)?( song| track)?\b", t) and len(t.split()) <= 4:
        return ("next", None)
    if re.search(r"\b(previous|last|go back)( the)?( song| track)\b|\bprevious\b", t) and len(t.split()) <= 4:
        return ("prev", None)
    m = re.fullmatch(r"play (.+?)( on spotify)?", t)
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
    SCOPES = "user-read-playback-state user-modify-playback-state user-read-currently-playing"

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

    def play(self, query):
        """Search and play. 'lofi playlist' plays a playlist, 'drake' plays the top track."""
        kind = "playlist" if "playlist" in query else "album" if re.search(r"\balbum\b", query) else "track"
        q = re.sub(r"\b(the )?(playlist|album|song)\b", "", query).strip() or query
        res = self._api("GET", "/search?" + urllib.parse.urlencode({"q": q, "type": kind, "limit": 1}))
        items = [i for i in (res.get(kind + "s", {}).get("items") or []) if i]
        if not items:
            return None
        it = items[0]
        self._api("PUT", "/me/player/play", {"uris": [it["uri"]]} if kind == "track" else {"context_uri": it["uri"]})
        who = ", ".join(a["name"] for a in it.get("artists", [])[:1]) if kind != "playlist" else ""
        return it["name"] + (" by " + who if who else "")

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


def ask_claude(prompt, session_id, claude=None, tools=None):
    """The question goes in on stdin, never on the command line, so nothing you say can run as a command."""
    claude = claude or find_claude()
    now = time.strftime("%A %B %d, %I:%M %p")
    cmd = [claude, "-p", "--output-format", "json", "--append-system-prompt", SPOKEN_STYLE + " Local time now: " + now + ".",
           "--allowedTools", tools or ALLOWED_TOOLS]
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


# ================= main =================
class Jarvis:
    def __init__(self, speaker, pc=None, spotify=None, claude=None):
        self.speaker, self.pc, self.spotify, self.claude = speaker, pc or PC(), spotify or Spotify(), claude
        self.session_id = load_session()
        self.last_brief_day = None
        self.quiet_until = 0.0
        self.pending = None

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
        self.pc.open_url(HQ_URL, app_window=HQ_FULLSCREEN)
        if hasattr(self.pc, "arrange"):
            try:
                self.pc.arrange()
            except Exception as e:
                log(f"layout failed: {e}")
        threading.Thread(target=lambda: log("music: " + jarvis_room.start_music(self.pc, self.spotify, log)), daemon=True).start()
        log("room awake, HQ opened")
        if NTFY_TOPIC:
            threading.Thread(target=push_phone, args=("HQ is online. Welcome back.",), daemon=True).start()
        try:
            self.speaker.powerup()
        except Exception:
            pass
        self.speaker.say(GREETING)
        today = time.strftime("%Y-%m-%d")
        if time.localtime().tm_hour < MORNING_BRIEF_BEFORE and self.last_brief_day != today:
            self.last_brief_day = today
            answer, _ = ask_claude(MORNING_PROMPT, None, self.claude)
            self.speaker.say(answer)

    def handle(self, text):
        """Returns False to quit."""
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
        if action == "time":
            say("It's " + time.strftime("%I:%M %p").lstrip("0") + ".")
        elif action == "timer":
            self.later(arg, "Timer done.")
            say("Timer set for " + _dur(arg) + ".")
        elif action == "remind":
            secs, what = arg
            self.later(secs, "Reminder: " + what)
            say("I'll remind you in " + _dur(secs) + ".")
        elif action == "note":
            os.makedirs(os.path.join(WORKDIR, "notes"), exist_ok=True)
            with open(os.path.join(WORKDIR, "notes", "inbox.md"), "a", encoding="utf-8") as f:
                f.write(time.strftime("- %Y-%m-%d %H:%M ") + arg + "\n")
            say("Noted.")
        elif action == "goodnight":
            pc.key("play_pause") if pc.spotify_title() else None
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
        elif action == "spotify_play":
            played = None
            if sp.ready:
                try:
                    played = sp.play(arg)
                except Exception as e:
                    log(f"spotify api: {e}")
            if played:
                say(f"Playing {played}.")
            else:
                pc.launch("spotify:search:" + urllib.parse.quote(arg))
                say(f"Pulled up {arg} on Spotify.")
        elif action == "site":
            pc.open_url(SITES[arg], app_window=(arg == "hq" and HQ_FULLSCREEN))
            say("Opening " + ("HQ" if arg == "hq" else arg) + ".")
        elif action == "app":
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
    whisper, _ = load_whisper()
    speaker = Speaker()
    jarvis = Jarvis(speaker, claude=claude)
    claps = ClapDetector()
    mic, _ = resolve_devices()

    with Mic(mic):
        noise = np.median([np.sqrt(np.mean(audio_q.get().astype(np.float32) ** 2)) for _ in range(25)])
        log(f"listening for '{WAKE_WORD.replace('_', ' ')}'" + (" and double claps" if CLAP_WAKE else "") + f" (room noise {noise:.0f})")

        while True:
            frame = audio_q.get()
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
            speaker.chime()
            drain_mic()
            audio = record_until_silence(noise)
            if audio is None:
                continue
            text = transcribe(whisper, audio)
            log(f"you: {text}")
            if not text:
                continue
            try:
                if not jarvis.handle(text):
                    return
            except Exception as e:
                log(f"error: {e}")
                speaker.say("Something broke. Check the Jarvis window.")
            drain_mic()                       # don't hear itself
            jarvis.quiet_until = time.time() + 1.0
            wake.reset()


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        pass
