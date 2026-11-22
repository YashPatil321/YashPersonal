"""
The fun layer on top of Jarvis's brain.

  Weather     live, no key (Open-Meteo). In the welcome, on game day, and "what's the weather at 7".
  Protocols   "house party protocol", "clean slate", "gaming mode", "study mode", "movie mode", "guest mode".
  Journal     "journal" records you talking for up to 3 minutes, cleans it up, saves it to Journal/ in the vault.
  Screen time tracks which apps you use, "screen time", and calls you out for YouTube during a focus session.
  Countdowns  "how many days until UC apps".
  Training    "I ran 3 miles in 24 minutes", "how many miles this week".
  Clipboard   "summarize my clipboard", "save my clipboard".
  Screen      "what am I looking at", "explain this error": screenshot to Claude.
  Alarm       "wake me up at 6:45": music fades in, then the morning brief. Survives restarts.
  Roast       "roast me", using your screen time and streaks.
"""

import json
import os
import re
import subprocess
import sys
import threading
import time
import urllib.request

import jarvis_brain as brain

IS_WIN = sys.platform == "win32"
HERE = os.path.dirname(os.path.abspath(__file__))
NO_WINDOW = 0x08000000 if IS_WIN else 0

# ---------------- settings (override in local_settings.py) ----------------
HOME_LAT, HOME_LON = 33.018, -117.123      # 4S Ranch
PARTY_PLAYLIST = ""          # Spotify link or a name, for house party protocol
WAKE_PLAYLIST = ""           # what the alarm fades in. Empty = your room playlist, else "morning chill"
WAKE_VOLUME = (10, 45)       # alarm fades from 10 to 45 percent over about two minutes
DISTRACTIONS = ["youtube", "instagram", "tiktok", "netflix", "twitch", "reddit", "x.com", "twitter", "snapchat"]
COUNTDOWNS = {               # spoken key words -> (date, what)
    "uc": ("2026-11-30", "UC applications are due"),
    "usc": ("2026-12-01", "the USC application is due"),
    "christmas": ("2026-12-25", "Christmas"),
    "new year": ("2027-01-01", "New Year's"),
}
SCREENTIME_FILE = os.path.join(HERE, ".screentime.json")
# ---------------------------------------------------------------------------


def _log(msg):
    print(time.strftime("[%H:%M:%S] ") + "extras: " + str(msg), flush=True)


# ================= weather =================
WMO = {0: "clear", 1: "mostly clear", 2: "partly cloudy", 3: "cloudy", 45: "foggy", 48: "foggy", 51: "light drizzle",
       53: "drizzle", 55: "heavy drizzle", 61: "light rain", 63: "rain", 65: "heavy rain", 71: "light snow", 73: "snow",
       75: "heavy snow", 80: "showers", 81: "showers", 82: "heavy showers", 95: "thunderstorms", 96: "thunderstorms", 99: "thunderstorms"}


def fetch_weather(lat=None, lon=None, opener=urllib.request.urlopen):
    url = ("https://api.open-meteo.com/v1/forecast?latitude=%s&longitude=%s&current=temperature_2m,weather_code,wind_speed_10m"
           "&hourly=temperature_2m,precipitation_probability,weather_code&daily=temperature_2m_max,temperature_2m_min,"
           "precipitation_probability_max,sunset&temperature_unit=fahrenheit&wind_speed_unit=mph&timezone=America%%2FLos_Angeles"
           "&forecast_days=2") % (lat or HOME_LAT, lon or HOME_LON)
    with opener(url, timeout=8) as r:
        return json.loads(r.read().decode())


def weather_line(w, hour=None):
    """Spoken weather. hour = 0..23 for a specific time today."""
    if hour is not None:
        times = w["hourly"]["time"]
        stamp = time.strftime("%Y-%m-%dT") + f"{hour:02d}:00"
        if stamp in times:
            i = times.index(stamp)
            t, rain, code = w["hourly"]["temperature_2m"][i], w["hourly"]["precipitation_probability"][i], w["hourly"]["weather_code"][i]
            h12 = f"{hour % 12 or 12} {'AM' if hour < 12 else 'PM'}"
            return f"At {h12} it'll be {round(t)} and {WMO.get(code, 'mixed')}" + (f", {rain} percent chance of rain." if rain >= 20 else ".")
    c, d = w["current"], w["daily"]
    sunset = d["sunset"][0][-5:]
    sh, sm = int(sunset[:2]), sunset[3:]
    line = (f"It's {round(c['temperature_2m'])} and {WMO.get(c['weather_code'], 'mixed')}. High {round(d['temperature_2m_max'][0])}, "
            f"low {round(d['temperature_2m_min'][0])}")
    rain = d["precipitation_probability_max"][0]
    line += f", {rain} percent chance of rain" if rain >= 20 else ""
    if c.get("wind_speed_10m", 0) >= 15:
        line += f", windy at {round(c['wind_speed_10m'])} miles an hour"
    return line + f". Sunset at {sh % 12 or 12}:{sm}."


def weather_brief():
    try:
        return weather_line(fetch_weather())
    except Exception as e:
        _log(f"weather: {e}")
        return ""


# ================= screen time =================
APP_NAMES = {"code.exe": "VS Code", "spotify.exe": "Spotify", "discord.exe": "Discord", "windowsterminal.exe": "the terminal",
             "claude.exe": "Claude", "steam.exe": "Steam", "obsidian.exe": "Obsidian", "whatsapp.exe": "WhatsApp",
             "excel.exe": "Excel", "winword.exe": "Word", "notepad.exe": "Notepad", "explorer.exe": "File Explorer"}
SITE_NAMES = [("youtube", "YouTube"), ("instagram", "Instagram"), ("tiktok", "TikTok"), ("netflix", "Netflix"), ("twitch", "Twitch"),
              ("reddit", "Reddit"), ("x.com", "X"), ("twitter", "X"), ("gmail", "Gmail"), ("inbox", "Gmail"), ("github", "GitHub"),
              ("claude", "Claude"), ("chatgpt", "ChatGPT"), ("common app", "Common App"), ("google docs", "Google Docs"),
              ("- google docs", "Google Docs"), ("canvas", "Canvas"), ("vercel", "Vercel"), ("solidhauz", "SolidHauz"), ("yash hq", "HQ")]
BROWSERS = ("chrome.exe", "msedge.exe", "firefox.exe", "brave.exe", "arc.exe")


def app_label(exe, title):
    exe, low = (exe or "").lower(), (title or "").lower()
    if exe in BROWSERS:
        for key, name in SITE_NAMES:
            if key in low:
                return name
        return "the browser"
    return APP_NAMES.get(exe, exe.replace(".exe", "").title() if exe else "")


class ScreenTime:
    def __init__(self, path=SCREENTIME_FILE, clock=time.time):
        self.path, self.clock = path, clock
        try:
            with open(path) as f:
                self.data = json.load(f)
        except Exception:
            self.data = {}
        self.current = ("", "")

    def add(self, label, secs):
        if not label:
            return
        day = time.strftime("%Y-%m-%d", time.localtime(self.clock()))
        d = self.data.setdefault(day, {})
        d[label] = d.get(label, 0) + secs
        if len(self.data) > 40:
            for k in sorted(self.data)[:-40]:
                del self.data[k]

    def save(self):
        try:
            with open(self.path, "w") as f:
                json.dump(self.data, f)
        except Exception as e:
            _log(f"screentime save: {e}")

    def today(self):
        return self.data.get(time.strftime("%Y-%m-%d", time.localtime(self.clock())), {})

    def top(self, n=4):
        return sorted(self.today().items(), key=lambda kv: -kv[1])[:n]

    def spoken(self, n=3):
        top = [(k, v) for k, v in self.top(n) if v >= 60]
        if not top:
            return "Barely any screen time today."
        total = sum(self.today().values())
        return f"{mins_text(total)} at the PC today. Most of it: " + ", ".join(f"{k} {mins_text(v)}" for k, v in top) + "."

    def minutes(self, label):
        return int(sum(v for k, v in self.today().items() if k.lower() == label.lower()) / 60)


def mins_text(secs):
    m = int(secs // 60)
    if m < 60:
        return f"{m} minute{'s' if m != 1 else ''}"
    h, m = divmod(m, 60)
    return f"{h} hour{'s' if h != 1 else ''}" + (f" {m}" if m else "")


def foreground_window():
    if not IS_WIN:
        return ("", "")
    import ctypes
    from ctypes import wintypes
    u, k = ctypes.windll.user32, ctypes.windll.kernel32
    h = u.GetForegroundWindow()
    if not h:
        return ("", "")
    buf = ctypes.create_unicode_buffer(512)
    u.GetWindowTextW(h, buf, 512)
    pid = wintypes.DWORD()
    u.GetWindowThreadProcessId(h, ctypes.byref(pid))
    exe = ""
    hp = k.OpenProcess(0x1000, False, pid.value)
    if hp:
        name = ctypes.create_unicode_buffer(512)
        size = wintypes.DWORD(512)
        if k.QueryFullProcessImageNameW(hp, 0, name, ctypes.byref(size)):
            exe = name.value.split("\\")[-1].lower()
        k.CloseHandle(hp)
    return (exe, buf.value)


# ================= clipboard and screenshot =================
def clipboard_text():
    if IS_WIN:
        try:
            return subprocess.run(["powershell", "-NoProfile", "-Command", "Get-Clipboard -Raw"], capture_output=True, text=True,
                                  timeout=6, encoding="utf-8", creationflags=NO_WINDOW).stdout.strip()
        except Exception:
            return ""
    try:
        import tkinter
        r = tkinter.Tk()
        r.withdraw()
        t = r.clipboard_get()
        r.destroy()
        return t
    except Exception:
        return ""


def screenshot(path=None, max_width=2560):
    """All monitors in one picture, scaled down so it stays readable but small. Returns the file path."""
    from PIL import ImageGrab
    path = path or os.path.join(HERE, ".cache", "screen.png")
    os.makedirs(os.path.dirname(path), exist_ok=True)
    img = ImageGrab.grab(all_screens=True)
    if img.width > max_width:
        img = img.resize((max_width, int(img.height * max_width / img.width)))
    img.save(path)
    return path


# ================= training =================
TRAINING_NOTE = "Training/2026-27.md"


def parse_training(t):
    """'i ran 3 miles in 24 minutes' -> ('run', 3.0, 24). 'i lifted' -> ('lift', None, None)"""
    m = re.fullmatch(r"(?:i |log a |log )?(?:ran|run|jogged|did a run of) (?:a )?([\d.]+|one|two|three|four|five|six|seven|eight|nine|ten|half a)"
                     r" (?:miles?|mile run|k|km|kilometers?)(?: in (\d+)(?: minutes?| mins?)?)?(?: today| tonight)?", t)
    if m:
        words = {"one": 1, "two": 2, "three": 3, "four": 4, "five": 5, "six": 6, "seven": 7, "eight": 8, "nine": 9, "ten": 10, "half a": 0.5}
        dist = float(words.get(m.group(1), m.group(1)))
        if re.search(r"\b(k|km|kilometers?)\b", t):
            dist = round(dist * 0.621, 2)
        return ("run", dist, int(m.group(2)) if m.group(2) else None)
    m = re.fullmatch(r"(?:i |log a |log )?(lifted|did legs|did upper body|hit the gym|worked out|did a workout|did sprints|lift)(?: for (\d+) minutes?)?(?: today)?", t)
    if m:
        kind = "sprints" if "sprint" in m.group(1) else "lift"
        return (kind, None, int(m.group(2)) if m.group(2) else None)
    return None


class Training:
    def __init__(self, vault):
        self.v = vault

    def add(self, kind, miles, mins):
        if not os.path.exists(self.v.path(TRAINING_NOTE)):
            self.v._write(TRAINING_NOTE, "# Training 2026-27\n\n", "w")
        pace = ""
        if miles and mins:
            p = mins / miles
            pace = f" ({int(p)}:{int(round((p % 1) * 60)):02d}/mi)"
        bits = f"{kind}" + (f" {miles:g} mi" if miles else "") + (f" {mins} min" if mins else "") + pace
        self.v._write(TRAINING_NOTE, f"- {self.v.now('%Y-%m-%d')} {bits}\n")
        self.v.log("Training: " + bits)
        return pace.strip(" ()")

    def week(self, today=None):
        base = today or time.time()
        start = time.strftime("%Y-%m-%d", time.localtime(base - 6 * 86400))
        miles, sessions = 0.0, 0
        for m in re.finditer(r"^- (\d{4}-\d\d-\d\d) (\w+)(?: ([\d.]+) mi)?", self.v.read(TRAINING_NOTE), re.M):
            if m.group(1) >= start:
                sessions += 1
                miles += float(m.group(3) or 0)
        return round(miles, 1), sessions


# ================= routes =================
def route_extras(t):
    if re.search(r"\bweather\b|\bhow (?:hot|cold) is it\b|\bis it (?:going to|gonna) rain\b|\bdo i need a (?:jacket|hoodie)\b", t):
        m = re.search(r"\bat (\d{1,2})(?::\d\d)? ?(am|pm|a m|p m)?\b", t)
        if m:
            h = int(m.group(1)) % 12
            pm = (m.group(2) or "").replace(" ", "") == "pm" or (not m.group(2) and 1 <= int(m.group(1)) <= 8)
            return ("weather", h + (12 if pm else 0))
        return ("weather", None)
    for pat, name in ((r"house party protocol|party (?:mode|protocol)", "party"), (r"clean slate(?: protocol)?|clear (?:my )?screen", "clean"),
                      (r"gaming (?:mode|protocol)|game time|time to game", "gaming"), (r"study (?:mode|protocol)|homework mode", "study"),
                      (r"movie (?:mode|night|protocol)", "movie"), (r"(?:guest|privacy|company) mode(?: on)?|i have (?:people|friends|guests) over", "guest"),
                      (r"(?:guest|privacy) mode off|(?:they|everyone)(?:'s| is| are) gone|back to normal", "normal")):
        if re.fullmatch(r"(?:activate |start |engage |turn on |initiate )?(?:the )?(?:" + pat + r")", t):
            return ("protocol", name)
    if re.fullmatch(r"(?:start (?:a |my )?)?journal(?:ing)?(?: entry| time)?|i want to journal|let me journal|(?:start a |new )?(?:journal|diary) entry", t):
        return ("journal", None)
    if re.search(r"\bscreen ?time\b|\bhow long (?:have i been|was i) on (.+)", t):
        m = re.search(r"\bhow long (?:have i been|was i) on (.+?)(?: today)?$", t)
        return ("screentime", m.group(1) if m else None)
    m = re.search(r"\bhow (?:many|long) (?:days )?(?:until|till|til|to|before) (.+)|\bcountdown (?:to|for|until) (.+)", t)
    if m:
        return ("countdown", (m.group(1) or m.group(2)).strip())
    tr = parse_training(t)
    if tr:
        return ("training", tr)
    if re.search(r"\bhow many miles\b|\bmy training\b|\btraining this week\b", t):
        return ("training_week", None)
    if re.search(r"\b(?:summarize|explain|read|what'?s (?:on|in)) (?:my |the )?clipboard\b", t):
        return ("clipboard", "read" if t.startswith(("read", "what")) else "summarize")
    if re.search(r"\b(?:save|keep) (?:my |the )?clipboard\b", t):
        return ("clipboard", "save")
    if re.fullmatch(r"what am i looking at|(?:look at|explain|read|check) (?:my |the |this )?(?:screen|page)|what'?s on my screen|"
                    r"(?:explain|what'?s|what is|help me with|fix) (?:this|that) (?:error|bug|problem|question|page)|help me with (?:this|what'?s on (?:my )?screen)", t):
        return ("look", t)
    m = re.fullmatch(r"(?:wake me up|set (?:an |my )?alarm(?: for)?|alarm(?: for)?) (?:at )?(\d{1,2})(?:[: ](\d\d))? ?(am|pm|a m|p m|in the morning)?(?: tomorrow)?", t)
    if m:
        h, mm = int(m.group(1)), int(m.group(2) or 0)
        ap = (m.group(3) or "").replace(" ", "")
        if ap == "pm" and h < 12:
            h += 12
        if ap in ("am", "inthemorning") and h == 12:
            h = 0
        return ("alarm", f"{h:02d}:{mm:02d}")
    if re.fullmatch(r"(?:cancel|turn off|delete|stop) (?:my |the )?alarm", t):
        return ("alarm_off", None)
    if re.fullmatch(r"(?:roast me|talk trash|trash talk me|be honest with me|how am i doing)", t):
        return ("roast", t)
    return None


def countdown(spoken, today=None):
    key = next((k for k in COUNTDOWNS if re.search(r"\b" + re.escape(k) + r"\b", spoken)), None)
    if not key:
        return None
    date, what = COUNTDOWNS[key]
    base = time.localtime(today or time.time())
    t0 = time.mktime((base.tm_year, base.tm_mon, base.tm_mday, 0, 0, 0, 0, 0, -1))
    t1 = time.mktime(time.strptime(date, "%Y-%m-%d"))
    days = round((t1 - t0) / 86400)
    if days < 0:
        return f"That already passed, {-days} days ago."
    if days == 0:
        return f"Today. {what[0].upper() + what[1:]} today."
    return f"{days} day{'s' if days != 1 else ''} until {what}."


# ================= the layer =================
class Extras:
    def __init__(self, say, ask, pc=None, spotify=None, brain_=None, record_long=None, screen_cmd=None, room_playlist=""):
        self.say, self.ask, self.pc, self.sp, self.b = say, ask, pc, spotify, brain_
        self.record_long, self.screen_cmd, self.room_playlist = record_long, screen_cmd, room_playlist
        self.st = ScreenTime()
        self.last_callout = 0
        self.distracted_for = 0

    def start(self):
        threading.Thread(target=self._screentime_loop, daemon=True).start()
        threading.Thread(target=self._alarm_loop, daemon=True).start()
        if self.b:
            self.b.fact_sources.append(lambda: ("Weather now: " + weather_brief()) if not brain.quiet_now() else "")
            self.b.fact_sources.append(lambda: ("Screen time today so far: " + self.st.spoken()) if self.st.today() else "")

    # ---- screen time + focus callouts ----
    def _screentime_loop(self, step=30):
        n = 0
        while True:
            time.sleep(step)
            try:
                if brain.idle_seconds() > 120:
                    continue
                exe, title = foreground_window()
                label = app_label(exe, title)
                self.st.add(label, step)
                n += 1
                if n % 10 == 0:
                    self.st.save()
                self.focus_check(label, step)
            except Exception as e:
                _log(f"screentime: {e}")

    def focus_check(self, label, step=30):
        if not (self.b and self.b.focus_started):
            self.distracted_for = 0
            return False
        if label.lower() in [d.replace(".com", "") for d in DISTRACTIONS] or label.lower() in ("youtube", "instagram", "tiktok", "netflix", "twitch", "reddit", "x"):
            self.distracted_for += step
        else:
            self.distracted_for = 0
        if self.distracted_for >= 90 and time.time() - self.last_callout > 300:
            self.last_callout = time.time()
            left = max(0, int((self.b.focus_timer.interval - (time.time() - self.b.focus_started)) / 60)) if self.b.focus_timer else 0
            self.say(f"Yash. You're supposed to be locked in, and you're on {label}." + (f" {left} minutes left. Back to it." if left else " Back to it."))
            return True
        return False

    # ---- alarm ----
    def _alarm_loop(self):
        while True:
            time.sleep(20)
            st = brain.load_state()
            at = st.get("alarm")
            if not at:
                continue
            if time.strftime("%H:%M") == at and st.get("alarm_fired") != time.strftime("%Y-%m-%d"):
                st["alarm_fired"] = time.strftime("%Y-%m-%d")
                st.pop("alarm", None)
                brain.save_state(st)
                try:
                    self.fire_alarm()
                except Exception as e:
                    _log(f"alarm: {e}")

    def fire_alarm(self):
        if self.pc:
            self.pc.nudge_display()
        song = WAKE_PLAYLIST or self.room_playlist or "morning chill"
        lo, hi = WAKE_VOLUME
        if self.sp and self.sp.ready:
            try:
                self.sp.volume(lo)
                self.sp.play(song, launch=self.pc.launch if self.pc else None)
                for v in range(lo, hi + 1, 5):
                    time.sleep(15)
                    self.sp.volume(v)
            except Exception as e:
                _log(f"alarm music: {e}")
        elif self.b and self.b.chime:
            for f in (660, 880, 990, 1320):
                self.b.chime(f)
        if self.b:
            quick, finish = self.b.greet("alarm")
            self.say("Good morning, Yash. Time to get up. " + weather_brief())
            finish()
        else:
            self.say("Good morning, Yash. Time to get up.")

    # ---- voice ----
    def handle(self, action, arg):
        say = self.say
        if action == "weather":
            try:
                say(weather_line(fetch_weather(), arg))
            except Exception as e:
                _log(f"weather: {e}")
                say("I can't reach the weather right now.")
        elif action == "protocol":
            self.protocol(arg)
        elif action == "journal":
            self.journal()
        elif action == "screentime":
            if arg:
                name = next((n for k, n in SITE_NAMES if k in arg), arg.title())
                m = self.st.minutes(name)
                say(f"{mins_text(m * 60)} on {name} today." if m else f"No time on {name} today.")
            else:
                say(self.st.spoken())
        elif action == "countdown":
            line = countdown(arg)
            say(line or self.ask(f"Out loud in one sentence: how many days from today until {arg}? Use my Google Calendar if it's an "
                                 "event of mine, otherwise what you know. Count from today's date."))
        elif action == "training":
            kind, miles, mins = arg
            pace = Training(self.b.vault).add(kind, miles, mins)
            wk, n = Training(self.b.vault).week()
            say(("Logged. " + (f"{pace} pace. " if pace else "")) + (f"{wk:g} miles this week, " if wk else "") + f"{n} session{'s' if n != 1 else ''} in the last 7 days.")
        elif action == "training_week":
            wk, n = Training(self.b.vault).week()
            say(f"{wk:g} miles and {n} sessions in the last 7 days." if n else "Nothing logged this week. After a run say, I ran 3 miles in 24 minutes.")
        elif action == "clipboard":
            text = clipboard_text()
            if not text:
                return say("Your clipboard is empty, or it's not text.")
            if arg == "save":
                self.b.vault.note("Clipboard: " + text[:1500].replace("\n", " "))
                say("Saved it to your inbox.")
            elif arg == "read" and len(text) < 400:
                say(text)
            else:
                say(self.ask("Out loud in under 60 words, explain or summarize this text I copied. If it's code or an error, say what it "
                             "means and the fix.\n\n" + text[:6000], tools="WebSearch"))
        elif action == "look":
            try:
                path = screenshot()
            except Exception as e:
                _log(f"screenshot: {e}")
                return say("I can't take a screenshot. Install Pillow: pip install pillow.")
            say("Looking.")
            say(self.ask(f"Read the screenshot at {path} (my screens, the big one is a 49 inch ultrawide). I asked: '{arg}'. Answer out "
                         "loud in under 70 words. If there's an error, say what it means and the fix. If it's a question or homework, "
                         "explain how to think about it, don't just give the answer.", tools="Read,WebSearch"))
        elif action == "alarm":
            st = brain.load_state()
            st["alarm"] = arg
            st.pop("alarm_fired", None)
            brain.save_state(st)
            h, m = int(arg[:2]), arg[3:]
            say(f"Alarm set for {h % 12 or 12}:{m} {'AM' if h < 12 else 'PM'}. Music fades in, then your brief. Leave the PC on.")
        elif action == "alarm_off":
            st = brain.load_state()
            had = st.pop("alarm", None)
            brain.save_state(st)
            say("Alarm off." if had else "No alarm set.")
        elif action == "roast":
            facts = [self.st.spoken(), brain.streak_line(brain.streaks(self.b.vault)) or "no streaks going", self.b.season.spoken()]
            say(self.ask("Roast Yash in under 50 spoken words, like a funny friend, not mean. Then one real line of encouragement. "
                         "Use these facts: " + " ".join(facts) + " No hyphens." if "roast" in arg or "trash" in arg else
                         "Be honest with Yash in under 60 spoken words about how he's doing this week, using these facts and his "
                         "calendar: " + " ".join(facts) + " One thing he's doing well, one to fix. No hyphens."))

    def protocol(self, name):
        say, sp, pc, b = self.say, self.sp, self.pc, self.b
        play = (lambda q: threading.Thread(target=b.play, args=(q,), daemon=True).start()) if b and b.play else (lambda q: None)
        if name == "party":
            play(PARTY_PLAYLIST or "party hits")
            if sp and sp.ready:
                threading.Timer(4, lambda: sp.volume(80)).start()
            if b:
                b.hold(3 * 3600)
            say("House party protocol. Volume up, notifications off. Have fun.")
        elif name == "clean":
            if self.screen_cmd:
                self.screen_cmd("keys", "show desktop")
            say("Clean slate.")
        elif name == "gaming":
            if pc:
                pc.launch("steam://open/main")
                pc.launch("discord:")
            if b:
                b.hold(2 * 3600)
            say("Gaming mode. Steam and Discord are up, I'll hold everything but leave times.")
        elif name == "study":
            if self.screen_cmd:
                try:
                    self.screen_cmd("layout", "school")
                except Exception as e:
                    _log(f"study layout: {e}")
            if b:
                b.handle("focus", 50)
        elif name == "movie":
            if pc and pc.spotify_title():
                pc.key("play_pause")
            if b:
                b.hold(3 * 3600)
            say("Movie mode. Music off, I'll stay quiet unless you need to leave.")
        elif name == "guest":
            if b:
                b.guest = True
                b.hold(4 * 3600)
            say("Guest mode. I won't say anything private out loud.")
        elif name == "normal":
            if b:
                b.guest = False
                b.hold(0)
                b.flush_news()
            say("Back to normal.") if not (b and b.news) else None

    def journal(self):
        if not self.record_long:
            return self.say("Journaling needs the mic loop running.")
        self.say("Go ahead. Take your time. I'll stop when you're quiet for a few seconds.")
        text = self.record_long()
        if not text or len(text.split()) < 4:
            return self.say("I didn't catch anything. Say journal when you're ready.")
        cleaned = self.ask("Clean up this spoken journal entry: fix transcription mistakes and punctuation, split into short paragraphs, "
                           "keep his words and voice, do not add anything. Then on the last line write TITLE: and a 3 to 6 word title, "
                           "and MOOD: one word.\n\n" + text) or text
        body, title, mood = cleaned, "", ""
        m = re.search(r"TITLE:\s*(.+)", cleaned)
        if m:
            title = m.group(1).split("MOOD:")[0].strip()
        m2 = re.search(r"MOOD:\s*(\w+)", cleaned)
        if m2:
            mood = m2.group(1)
        body = re.sub(r"\n?TITLE:.*", "", body, flags=re.S).strip()
        v = self.b.vault
        rel = f"Journal/{v.now('%Y-%m-%d')}.md"
        head = "" if os.path.exists(v.path(rel)) else f"---\ntags: [journal]\n---\n# Journal, {v.now('%B %d').replace(' 0', ' ')}\n"
        v._write(rel, head + f"\n## {v.now('%I:%M %p').lstrip('0')}" + (f", {title}" if title else "") + (f"\nMood: {mood}" if mood else "") + "\n\n" + body + "\n")
        v.log(f"Journal: [[{rel[:-3]}]]" + (f" ({mood})" if mood else ""))
        self.say("Saved to your journal." + (f" I called it {title}." if title else ""))
