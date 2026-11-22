"""
Jarvis's memory and situational awareness.

  Vault      your Obsidian vault (plain Markdown files). Daily notes, memory, inbox, season log.
  Presence   knows when you left the desk and when you came back (keyboard and mouse idle time).
  Situation  on a wake, works out what you were just doing (practice, a game, school) from the
             calendar and how long you were gone, then greets you like it knows.
  Planner    reminders before leave blocks, practices and games, from the calendar.
  Season     "we won 3 1 against San Pasqual" logs the game and keeps your record.
  Focus      "lock in for an hour" focus sessions, logged to the daily note.

Everything here only writes inside the vault. Nothing deletes files.
"""

import json
import os
import re
import sys
import threading
import time

IS_WIN = sys.platform == "win32"
HERE = os.path.dirname(os.path.abspath(__file__))

# ---------------- settings (override in local_settings.py) ----------------
VAULT = ""                   # your Obsidian vault folder. Empty = the vault Obsidian has open, else C:\jarvis\notes
DAILY_FOLDER = "Daily"       # where daily notes go inside the vault
JARVIS_FOLDER = "Jarvis"     # memory, inbox
SEASON_NOTE = "Soccer/Season 2026-27.md"
AWAY_MINUTES = 20            # no keyboard or mouse for this long = you left the desk
AUTO_WELCOME = True          # greet you when you sit back down after being away, even without a clap
AUTO_WELCOME_AFTER = 45      # minutes away before an automatic welcome
QUIET_HOURS = (23, 6)        # no automatic welcomes or reminders from 11 PM to 6 AM
FOCUS_MUSIC = ""             # optional, e.g. "lofi beats". Played when a focus session starts
PLAN_REFRESH_HOURS = (7, 12, 15, 18)   # re-read the calendar for reminders at these hours
STATE_FILE = os.path.join(HERE, ".brain.json")
# ---------------------------------------------------------------------------


def _log(msg):
    print(time.strftime("[%H:%M:%S] ") + "brain: " + str(msg), flush=True)


# ================= vault =================
def obsidian_vaults(config_path=None):
    """Vaults Obsidian knows about: [(path, open)]."""
    config_path = config_path or os.path.join(os.environ.get("APPDATA", ""), "obsidian", "obsidian.json")
    try:
        with open(config_path, encoding="utf-8") as f:
            data = json.load(f)
        vs = data.get("vaults", {}).values()
        return sorted(((v.get("path", ""), bool(v.get("open"))) for v in vs if v.get("path")), key=lambda x: not x[1])
    except Exception:
        return []


def find_vault():
    if VAULT:
        return VAULT
    for path, _ in obsidian_vaults():
        if os.path.isdir(path):
            return path
    return os.path.join(HERE, "notes")


class Vault:
    def __init__(self, root=None, clock=time.localtime):
        self.root = root or find_vault()
        self.clock = clock
        self.lock = threading.Lock()

    @property
    def name(self):
        return os.path.basename(os.path.normpath(self.root))

    @property
    def is_obsidian(self):
        return os.path.isdir(os.path.join(self.root, ".obsidian"))

    def path(self, rel):
        p = os.path.normpath(os.path.join(self.root, rel))
        if not p.startswith(os.path.normpath(self.root)):
            raise ValueError("outside the vault")
        return p

    def read(self, rel):
        try:
            with open(self.path(rel), encoding="utf-8") as f:
                return f.read()
        except FileNotFoundError:
            return ""

    def _write(self, rel, text, mode="a"):
        p = self.path(rel)
        os.makedirs(os.path.dirname(p), exist_ok=True)
        with self.lock, open(p, mode, encoding="utf-8") as f:
            f.write(text)

    def now(self, fmt):
        return time.strftime(fmt, self.clock())

    # daily note
    def daily_rel(self, day=None):
        return f"{DAILY_FOLDER}/{day or self.now('%Y-%m-%d')}.md"

    def daily(self):
        rel = self.daily_rel()
        if not os.path.exists(self.path(rel)):
            title = self.now("%A, %B %d").replace(" 0", " ")
            self._write(rel, f"---\ndate: {self.now('%Y-%m-%d')}\ntags: [daily]\n---\n# {title}\n\n## Brief\n\n## Log\n", "w")
        return rel

    def log(self, line):
        """Adds a timestamped line to the end of today's note (the Log section is last)."""
        rel = self.daily()
        self._write(rel, f"- {self.now('%H:%M')} {line.strip()}\n")
        return rel

    def brief(self, text):
        rel = self.daily()
        body = self.read(rel)
        if "## Brief\n\n## Log" in body:
            body = body.replace("## Brief\n\n## Log", "## Brief\n" + text.strip() + "\n\n## Log", 1)
            self._write(rel, body, "w")
        else:
            self.log("Brief: " + text)

    def today_log(self, max_lines=12):
        lines = [l for l in self.read(self.daily_rel()).splitlines() if l.startswith("- ")]
        return "\n".join(lines[-max_lines:])

    # memory and inbox
    def remember(self, fact):
        rel = f"{JARVIS_FOLDER}/Memory.md"
        if not os.path.exists(self.path(rel)):
            self._write(rel, "# What Jarvis remembers\n\nAdd or delete lines freely. Jarvis reads this before it answers.\n\n", "w")
        self._write(rel, f"- {fact.strip()} ({self.now('%b %d').replace(' 0', ' ')})\n")
        self.log("Remembered: " + fact)

    def memory(self, max_chars=1800):
        text = "\n".join(l for l in self.read(f"{JARVIS_FOLDER}/Memory.md").splitlines() if l.startswith("- "))
        return text[-max_chars:]

    def note(self, text):
        self._write(f"{JARVIS_FOLDER}/Inbox.md", f"- [ ] {text.strip()} ({self.now('%b %d %H:%M')})\n")
        self.log("Note: " + text)

    # search
    def search(self, query, n=5):
        """Plain local search. Returns [(rel_path, snippet)] best first."""
        words = [w for w in re.findall(r"[a-z0-9']+", query.lower()) if len(w) > 2 and w not in STOP]
        if not words:
            return []
        hits = []
        for dirpath, dirs, files in os.walk(self.root):
            dirs[:] = [d for d in dirs if not d.startswith(".")]
            for fn in files:
                if not fn.endswith(".md"):
                    continue
                p = os.path.join(dirpath, fn)
                try:
                    with open(p, encoding="utf-8") as f:
                        text = f.read()
                except Exception:
                    continue
                low, name = text.lower(), fn.lower()
                score = sum(low.count(w) for w in words) + sum(5 for w in words if w in name)
                if not score:
                    continue
                at = min((low.find(w) for w in words if w in low), default=0)
                snip = re.sub(r"\s+", " ", text[max(0, at - 160): at + 340]).strip()
                hits.append((score, os.path.relpath(p, self.root).replace("\\", "/"), snip))
        hits.sort(key=lambda h: -h[0])
        return [(r, s) for _, r, s in hits[:n]]

    def uri(self, rel):
        import urllib.parse
        return "obsidian://open?vault=" + urllib.parse.quote(self.name) + "&file=" + urllib.parse.quote(rel[:-3] if rel.endswith(".md") else rel)


STOP = set("the and for what did write about with that this have from were was are you my me our all any notes note say says".split())


# ================= season =================
def parse_result(t):
    """'we won 3 1 against san pasqual' -> ('W', 3, 1, 'San Pasqual')"""
    m = re.search(r"\bwe (won|lost|tied|drew)\b(?: the game)?(?: (\d+|zero|one|two|three|four|five|six|seven|eight|nine|ten)"
                  r"(?: to | | ?- ?)(\d+|zero|one|two|three|four|five|six|seven|eight|nine|ten))?(?: (?:against|vs|versus|to|over) (.+))?$", t)
    if not m:
        return None
    nums = {"zero": 0, "one": 1, "two": 2, "three": 3, "four": 4, "five": 5, "six": 6, "seven": 7, "eight": 8, "nine": 9, "ten": 10}
    a = nums.get(m.group(2), m.group(2)) if m.group(2) else None
    b = nums.get(m.group(3), m.group(3)) if m.group(3) else None
    a, b = (int(a), int(b)) if a is not None else (None, None)
    res = {"won": "W", "lost": "L"}.get(m.group(1), "T")
    if a is not None and res == "W" and a < b or res == "L" and a is not None and a > b:
        a, b = b, a   # "we won 1 3" means 3 1
    opp = (m.group(4) or "").strip().title()
    return res, a, b, opp


class Season:
    def __init__(self, vault):
        self.v = vault

    def add(self, res, us, them, opp, note=""):
        rel = SEASON_NOTE
        if not os.path.exists(self.v.path(rel)):
            self.v._write(rel, "# Del Norte Varsity Soccer 2026-27\n\n| Date | Opponent | Result | Score | Notes |\n|---|---|---|---|---|\n", "w")
        score = f"{us}-{them}" if us is not None else ""
        self.v._write(rel, f"| {self.v.now('%b %d').replace(' 0', ' ')} | {opp or '?'} | {res} | {score} | {note} |\n")
        self.v.log(f"Game: {res} {score} {('vs ' + opp) if opp else ''}".strip())

    def record(self):
        w = l = t = 0
        for line in self.v.read(SEASON_NOTE).splitlines():
            cells = [c.strip() for c in line.strip("|").split("|")]
            if len(cells) >= 3 and cells[2] in ("W", "L", "T"):
                w, l, t = w + (cells[2] == "W"), l + (cells[2] == "L"), t + (cells[2] == "T")
        return w, l, t

    def spoken(self):
        w, l, t = self.record()
        if not (w or l or t):
            return "No games logged yet. After a game say, we won 2 1 against whoever."
        return f"You're {w} and {l}" + (f" and {t}" if t else "") + " this season."


# ================= presence =================
def idle_seconds():
    """Seconds since the last keyboard or mouse input on Windows. 0 elsewhere."""
    if not IS_WIN:
        return 0.0
    import ctypes

    class LASTINPUTINFO(ctypes.Structure):
        _fields_ = [("cbSize", ctypes.c_uint), ("dwTime", ctypes.c_uint)]
    li = LASTINPUTINFO()
    li.cbSize = ctypes.sizeof(li)
    if not ctypes.windll.user32.GetLastInputInfo(ctypes.byref(li)):
        return 0.0
    return max(0.0, (ctypes.windll.kernel32.GetTickCount() - li.dwTime) / 1000.0)


def load_state():
    try:
        with open(STATE_FILE) as f:
            return json.load(f)
    except Exception:
        return {}


def save_state(st):
    try:
        with open(STATE_FILE, "w") as f:
            json.dump(st, f)
    except Exception as e:
        _log(f"state save failed: {e}")


class Presence:
    """Tracks when you were last at the desk. seen() is called on every clap or voice command too."""
    def __init__(self, idle=idle_seconds, clock=time.time, snapshot=None):
        self.idle, self.clock, self.snapshot = idle, clock, snapshot
        st = load_state()
        self.last_active = st.get("last_active", clock())
        self.before_leaving = st.get("before_leaving", [])
        self.away = False
        self.on_return = None   # called with minutes away when you sit back down

    def seen(self):
        self.last_active = self.clock()
        self.away = False
        self._save()

    def away_minutes(self):
        return max(0, int((self.clock() - self.last_active) / 60))

    def _save(self):
        st = load_state()
        st.update(last_active=self.last_active, before_leaving=self.before_leaving)
        save_state(st)

    def tick(self):
        idle = self.idle()
        now = self.clock()
        if idle < 90:
            if self.away and self.on_return:
                gone = int((now - idle - self.last_active) / 60)
                self.away = False
                self.last_active = now - idle
                self._save()
                try:
                    self.on_return(gone)
                except Exception as e:
                    _log(f"welcome failed: {e}")
                return
            self.last_active = now - idle
            self.away = False
        elif idle > AWAY_MINUTES * 60 and not self.away:
            self.away = True
            if self.snapshot:
                try:
                    self.before_leaving = self.snapshot()[:8]
                except Exception:
                    pass
        self._save()

    def watch(self):
        while True:
            time.sleep(30)
            try:
                self.tick()
            except Exception as e:
                _log(f"presence: {e}")


def window_snapshot():
    """What was on screen: ['Code: SolidHauz quote.tsx', ...]"""
    try:
        import jarvis_screen
        skip = ("explorer.exe", "textinputhost.exe", "shellexperiencehost.exe", "applicationframehost.exe", "pythonw.exe")
        out = []
        for _, exe, title in jarvis_screen.Screen().windows():
            if exe in skip or not title.strip() or title in ("Program Manager",):
                continue
            out.append(f"{exe.replace('.exe', '')}: {title[:80]}")
        return out
    except Exception:
        return []


def quiet_now(hour=None):
    h = time.localtime().tm_hour if hour is None else hour
    a, b = QUIET_HOURS
    return h >= a or h < b if a > b else a <= h < b


# ================= situation =================
def quick_line(hour, away_min):
    """Said instantly while the calendar is checked."""
    if hour < 5:
        return "You're up late, Yash."
    if away_min >= 60 * 24 * 2:
        return "Yash. It's been a while. Welcome back."
    if hour < 11:
        return "Morning, Yash." if away_min > 240 else "Welcome back, Yash."
    if hour < 17:
        return "Welcome back, Yash."
    if hour < 22:
        return "Evening, Yash. Welcome back."
    return "Welcome back. It's getting late."


def away_text(m):
    if m < 2:
        return "he never really left"
    if m < 90:
        return f"he was away about {m} minutes"
    if m < 60 * 36:
        return f"he was away about {round(m / 60, 1)} hours"
    return f"he was away about {round(m / 1440)} days"


def situation_prompt(vault, presence, morning=False, now=None):
    now = now or time.localtime()
    gone = presence.away_minutes()
    left_at = time.strftime("%I:%M %p", time.localtime(presence.last_active)).lstrip("0")
    parts = [
        f"Yash just walked back into his room and woke the system. It is {time.strftime('%A %B %d, %I:%M %p', now)}. "
        f"He was last active at the desk at {left_at}, so {away_text(gone)}.",
        "Check his Google Calendar for what ended while he was gone (practice, a game, school, a meeting, a trip) and what is next "
        "today and tomorrow morning. Leave blocks named 'Leave for ...' matter most.",
    ]
    if presence.before_leaving:
        parts.append("Before he left, his screen had: " + "; ".join(presence.before_leaving[:6]) + ".")
    log = vault.today_log() if vault else ""
    if log:
        parts.append("Today's log so far:\n" + log)
    if morning:
        parts.append("This is his first wake of the day, so fold in a short morning brief: his first event and leave time, how many "
                     "other events, and any unread email from a real person that needs him.")
    parts.append(
        "Reply with ONLY a JSON object, no other text: "
        '{"greeting": "what Jarvis says out loud, under 55 words, warm and natural, like a friend who knows his day. '
        "Name what he just did if you can tell (for example: welcome back from practice, how did the game go). "
        "Then the next thing he needs and when to leave. No hyphens, no lists, no markdown.\", "
        '"just_did": "practice | game | school | other | unknown", '
        '"events": [{"title": "...", "start": "HH:MM 24h today", "leave": true or false}]}'
        " where events are the rest of TODAY only, in order.")
    return "\n\n".join(parts)


PLAN_PROMPT = ("List the rest of today's events from my Google Calendar, in order. Reply with ONLY JSON, no other text: "
               '{"events": [{"title": "...", "start": "HH:MM 24h", "leave": true or false}]} '
               "leave is true for blocks named Leave for something.")


def parse_json(text):
    if not text:
        return None
    m = re.search(r"\{.*\}", text, re.S)
    if not m:
        return None
    try:
        return json.loads(m.group(0))
    except Exception:
        return None


# ================= planner =================
class Planner:
    """Speaks reminders before events. events come from the calendar through Claude."""
    def __init__(self, say, chime=None, clock=time.time, timer=threading.Timer):
        self.say, self.chime, self.clock, self.timer = say, chime, clock, timer
        self.armed = {}

    @staticmethod
    def alerts(ev):
        """[(minutes_before, line)] for one event."""
        title = (ev.get("title") or "").strip()
        low = title.lower()
        if ev.get("leave") or low.startswith("leave"):
            what = re.sub(r"^leave (for )?", "", title, flags=re.I) or "it"
            what = re.sub(r"^(game|practice|school)\b", r"the \1", what, flags=re.I)
            return [(30, f"Heads up. You leave for {what} in 30 minutes. Start packing."),
                    (10, f"Leave in 10 minutes for {what}."),
                    (0, f"Time to go. Leave for {what} now.")]
        if "game" in low or " vs " in low or " at " in low and "soccer" in low:
            return [(15, f"{title} in 15 minutes.")]
        if "practice" in low:
            return [(20, f"{title} in 20 minutes.")]
        return [(10, f"{title} in 10 minutes.")]

    def load(self, events, day=None):
        lt = time.localtime(self.clock())
        base = time.mktime((lt.tm_year, lt.tm_mon, lt.tm_mday, 0, 0, 0, 0, 0, -1))
        n = 0
        for ev in events or []:
            m = re.match(r"(\d{1,2}):(\d{2})", str(ev.get("start", "")))
            if not m:
                continue
            at = base + int(m.group(1)) * 3600 + int(m.group(2)) * 60
            for before, line in self.alerts(ev):
                fire = at - before * 60
                key = (ev.get("title"), m.group(0), before)
                wait = fire - self.clock()
                if key in self.armed or wait < 5 or wait > 18 * 3600:
                    continue
                t = self.timer(wait, self._fire, args=(line,))
                t.daemon = True
                t.start()
                self.armed[key] = t
                n += 1
        return n

    def _fire(self, line):
        if quiet_now() and not line.lower().startswith(("time to go", "leave in")):
            return
        try:
            if self.chime:
                self.chime(1100)
            self.say(line)
        except Exception as e:
            _log(f"reminder: {e}")


# ================= voice routes =================
def route_brain(t):
    """Voice lines this module handles. t is already lowercased and cleaned."""
    if re.fullmatch(r"(?:remember|don't forget|keep in mind)(?: that)? (.+)", t):
        return ("remember", re.sub(r"^(?:remember|don't forget|keep in mind)(?: that)? ", "", t))
    m = re.fullmatch(r"(?:what do you (?:remember|know) about|what did i (?:write|say|note) about|search my (?:notes|vault) for|"
                     r"what do my notes say about|find (?:my )?notes? (?:on|about)|look up in my notes) (.+)", t)
    if m:
        return ("vault_search", m.group(1))
    if re.fullmatch(r"(?:open|show|pull up) (?:my |today's )?(?:daily note|note for today|obsidian|journal|vault)", t):
        return ("vault_open", None)
    if re.fullmatch(r"(?:what do you remember|what do you know about me)", t):
        return ("memory_list", None)
    r = parse_result(t)
    if r:
        return ("game_result", r)
    if re.search(r"\b(?:what'?s|what is|how'?s) (?:our|my|the) (?:record|season)\b", t):
        return ("season", None)
    m = re.fullmatch(r"(?:lock in|focus mode on|start (?:a )?focus(?: session)?|focus|deep work)(?: for)?(?: (.+?) (minutes?|hours?))?", t)
    if m and (m.group(1) is None or _num(m.group(1)) is not None):
        mins = 50 if m.group(1) is None else _num(m.group(1)) * (60 if m.group(2)[0] == "h" else 1)
        return ("focus", int(mins))
    if re.fullmatch(r"(?:stop|end|cancel) (?:the )?focus(?: session| mode)?|i'?m done focusing", t):
        return ("focus_end", None)
    if re.fullmatch(r"(?:log|add to (?:my )?(?:log|daily note)) (.+)", t):
        return ("vault_log", re.sub(r"^(?:log|add to (?:my )?(?:log|daily note)) ", "", t))
    if re.fullmatch(r"(?:what'?s )?(?:my|the) plan(?: for)?(?: today| tonight)?|what should i (?:do|work on) (?:now|tonight|today)", t):
        return ("what_now", None)
    return None


def _num(s):
    words = {"a": 1, "an": 1, "one": 1, "two": 2, "three": 3, "four": 4, "five": 5, "ten": 10, "fifteen": 15, "twenty": 20,
             "twenty five": 25, "thirty": 30, "forty": 40, "forty five": 45, "fifty": 50, "sixty": 60, "ninety": 90, "half an": 0.5}
    s = s.strip()
    if s in words:
        return words[s]
    m = re.search(r"\d+(\.\d+)?", s)
    return float(m.group(0)) if m and "." in m.group(0) else int(m.group(0)) if m else None


# ================= the brain =================
class Brain:
    def __init__(self, say, ask, chime=None, launch=None, screen=None, vault=None, presence=None):
        """ask(prompt, tools) -> text, a one off Claude call with calendar and mail."""
        self.say, self.ask, self.chime, self.launch, self.screen = say, ask, chime, launch, screen
        self.vault = vault or Vault()
        self.presence = presence or Presence(snapshot=window_snapshot)
        self.season = Season(self.vault)
        self.planner = Planner(say, chime)
        self.focus_timer = None
        self.focus_started = 0
        self.last_brief_day = load_state().get("brief_day")

    def start(self):
        if AUTO_WELCOME:
            self.presence.on_return = self.auto_welcome
        threading.Thread(target=self.presence.watch, daemon=True).start()
        threading.Thread(target=self._plan_refresh, daemon=True).start()
        _log(f"vault: {self.vault.root}" + ("" if self.vault.is_obsidian else " (not an Obsidian vault yet, it still works)"))

    def context_for_claude(self):
        """Added to every Claude prompt so answers know what Jarvis knows."""
        mem = self.vault.memory()
        out = f" His Obsidian vault is at {self.vault.root}; read it with Read, Grep and Glob when he asks about his notes."
        if mem:
            out += " Things he asked you to remember:\n" + mem
        log = self.vault.today_log(8)
        if log:
            out += "\nToday's log:\n" + log
        return out

    # walk in
    def greet(self, reason="clap"):
        """Returns (quick_line, thread). The thread speaks the situational greeting when it is ready."""
        lt = time.localtime()
        gone = self.presence.away_minutes()
        today = time.strftime("%Y-%m-%d")
        morning = lt.tm_hour < 12 and self.last_brief_day != today
        prompt = situation_prompt(self.vault, self.presence, morning=morning)
        result = {}

        def work():
            try:
                result["text"] = self.ask(prompt)
            except Exception as e:
                result["text"] = ""
                _log(f"situation: {e}")
        th = threading.Thread(target=work, daemon=True)
        th.start()
        self.presence.seen()
        return quick_line(lt.tm_hour, gone), lambda wait=60: self._finish(th, result, wait, morning, today, reason, gone)

    def _finish(self, th, result, wait, morning, today, reason, gone):
        th.join(timeout=wait)
        data = parse_json(result.get("text", ""))
        if data and data.get("greeting"):
            line = data["greeting"]
        elif result.get("text") and not result["text"].lstrip().startswith("{"):
            line = result["text"]
        else:
            line = ""
        if line:
            self.say(line)
        if morning and line:
            self.last_brief_day = today
            st = load_state()
            st["brief_day"] = today
            save_state(st)
            self.vault.brief(line)
        did = (data or {}).get("just_did", "")
        self.vault.log(f"Back at the desk ({reason}" + (f", away {gone} min" if gone >= 5 else "") + (f", after {did}" if did and did != "unknown" else "") + ")")
        if data and data.get("events"):
            n = self.planner.load(data["events"])
            if n:
                _log(f"{n} reminders armed")
        return line

    def auto_welcome(self, gone):
        if gone < AUTO_WELCOME_AFTER or quiet_now():
            return
        quick, finish = self.greet("sat down")
        self.say(quick)
        finish()

    def _plan_refresh(self):
        done = set()
        while True:
            time.sleep(120)
            lt = time.localtime()
            key = (lt.tm_yday, lt.tm_hour)
            if lt.tm_hour in PLAN_REFRESH_HOURS and key not in done:
                done.add(key)
                try:
                    data = parse_json(self.ask(PLAN_PROMPT))
                    if data:
                        self.planner.load(data.get("events"))
                except Exception as e:
                    _log(f"plan refresh: {e}")

    # wind down
    def goodnight(self):
        text = self.ask("Yash is going to bed. In under 45 spoken words: one line on how today went from this log, then tomorrow's first "
                        "event and the time he needs to leave or wake for it, from his Google Calendar. Warm, no lists, no hyphens.\n\n"
                        "Today's log:\n" + (self.vault.today_log(30) or "(empty)"))
        if text and not text.lstrip().startswith("{"):
            self.vault.log("Goodnight. " + text)
            return text
        self.vault.log("Goodnight.")
        return ""

    # voice actions
    def handle(self, action, arg):
        say, v = self.say, self.vault
        if action == "remember":
            v.remember(arg)
            say("Got it. I'll remember that.")
        elif action == "memory_list":
            mem = [re.sub(r" \([A-Z][a-z]{2} \d+\)$", "", l[2:]) for l in v.memory().splitlines()][-5:]
            say("Here's what I've got. " + ". ".join(mem) + "." if mem else "Nothing yet. Say remember that, and then the thing.")
        elif action == "vault_search":
            hits = v.search(arg)
            if not hits:
                return say(f"I didn't find anything about {arg} in your notes.")
            ctx = "\n\n".join(f"[{r}]\n{s}" for r, s in hits)
            ans = self.ask(f"From these excerpts of my Obsidian notes, answer out loud in under 60 words: what did I write about {arg}? "
                           f"Say which note it's in by its name. If they don't answer it, say so.\n\n{ctx}", tools="Read,Grep,Glob")
            say(ans or f"It's in {hits[0][0].rsplit('/', 1)[-1][:-3]}.")
        elif action == "vault_open":
            rel = v.daily()
            if self.launch and v.is_obsidian:
                self.launch(v.uri(rel))
                say("Opening today's note.")
            elif self.launch:
                self.launch(v.path(rel))
                say("Opening today's note. Install Obsidian and open this folder as a vault for the full thing.")
        elif action == "vault_log":
            v.log(arg)
            say("Logged.")
        elif action == "game_result":
            res, us, them, opp = arg
            self.season.add(res, us, them, opp)
            w, l, t = self.season.record()
            word = {"W": "Let's go.", "L": "Tough one. Next game.", "T": "A draw."}[res]
            say(f"{word} Logged it. You're {w} and {l}" + (f" and {t}" if t else "") + ". How did you play? Say log, and then how it went.")
        elif action == "season":
            say(self.season.spoken())
        elif action == "focus":
            self.start_focus(arg)
        elif action == "focus_end":
            self.end_focus(early=True)
        elif action == "what_now":
            say(self.ask("Out loud in under 50 words: what should I do right now? Use my Google Calendar for the rest of today, "
                         "the time now, and what I've told you to remember. Pick ONE thing, say why, and say when I need to stop for "
                         "the next event."))

    def start_focus(self, mins):
        if self.focus_timer:
            self.focus_timer.cancel()
        self.focus_started = time.time()
        if self.screen:
            try:
                self.screen("layout", "focus")
            except Exception as e:
                _log(f"focus layout: {e}")
        if FOCUS_MUSIC and self.launch:
            pass   # jarvis.py plays FOCUS_MUSIC through Spotify
        self.focus_timer = threading.Timer(mins * 60, self.end_focus)
        self.focus_timer.daemon = True
        self.focus_timer.start()
        self.vault.log(f"Focus started, {mins} min")
        self.say(f"Locked in for {mins} minutes. I'll stay quiet.")

    def end_focus(self, early=False):
        if not self.focus_started:
            return self.say("No focus session running.")
        mins = round((time.time() - self.focus_started) / 60)
        if self.focus_timer and early:
            self.focus_timer.cancel()
        self.focus_timer, self.focus_started = None, 0
        total = mins + sum(int(x) for x in re.findall(r"Focus done, (\d+) min", self.vault.read(self.vault.daily_rel())))
        self.vault.log(f"Focus done, {mins} min")
        if self.chime:
            self.chime(988)
        self.say(f"Focus done. {mins} minutes, {total} today. Take a 10 minute break. Say log, and what you got done.")
