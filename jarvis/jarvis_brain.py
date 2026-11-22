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
GAMEDAY_PLAYLIST = ""        # Spotify link or name for "pregame" and game day mornings, e.g. "pregame hype"
WIND_DOWN = "22:30"          # nightly wind down nudge if you're at the desk. None = off
WEEKLY_REVIEW = (6, "18:00") # Sunday (Mon=0 ... Sun=6) at 6 PM: weekly review into Weekly/. None = off
BREAK_AFTER_HOURS = 3        # nudge to take a break after this long at the desk without one
MAIL_WATCH_MINUTES = 15      # check for mail that matters this often (7 AM to 10 PM). None = off
# who counts as important: coaches, parents, SolidHauz. Add your parents' emails in local_settings.py
IMPORTANT_SENDERS = ["orielly", "rielly", "roty"]
IMPORTANT_TOPICS = ["soccer", "DN Boys", "SolidHauz", "quote", "deposit", "Babson", "admission"]
SHOP_TOOLS = "mcp__claude_ai_Solidhauz__today,mcp__claude_ai_Solidhauz__business_overview,mcp__claude_ai_Solidhauz__jobs_behind"
PHONE_IP = ""                # optional: your iPhone's fixed IP on home WiFi, so Jarvis knows when you get home
GAME_BAG = "cleats, shin guards, both jerseys, water and your warmup"
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

    def add_stat(self, kind, n=1):
        if not os.path.exists(self.v.path(SEASON_NOTE)):
            self.v._write(SEASON_NOTE, "# Del Norte Varsity Soccer 2026-27\n\n| Date | Opponent | Result | Score | Notes |\n|---|---|---|---|---|\n", "w")
        self.v._write(SEASON_NOTE, f"\n- stat: {n} {kind} ({self.v.now('%b %d').replace(' 0', ' ')})\n")
        self.v.log(f"{n} {kind}{'s' if n != 1 else ''}")

    def stats(self):
        out = {"goal": 0, "assist": 0, "clean sheet": 0}
        for m in re.finditer(r"^- stat: (\d+) (goal|assist|clean sheet)", self.v.read(SEASON_NOTE), re.M):
            out[m.group(2)] += int(m.group(1))
        return out

    def spoken(self):
        w, l, t = self.record()
        if not (w or l or t):
            return "No games logged yet. After a game say, we won 2 1 against whoever."
        st = self.stats()
        extra = ""
        if st["goal"] or st["assist"]:
            extra = f" You've got {st['goal']} goal{'s' if st['goal'] != 1 else ''} and {st['assist']} assist{'s' if st['assist'] != 1 else ''}."
        return f"You're {w} and {l}" + (f" and {t}" if t else "") + " this season." + extra


# ================= streaks and weekly =================
def day_notes(vault, days, today=None):
    """[(date_str, text)] for the last `days` days, newest first."""
    base = today or time.time()
    out = []
    for i in range(days):
        d = time.strftime("%Y-%m-%d", time.localtime(base - i * 86400))
        out.append((d, vault.read(vault.daily_rel(d))))
    return out


def focus_minutes(text):
    return sum(int(x) for x in re.findall(r"Focus done, (\d+) min", text))


def bed_time(text):
    m = re.findall(r"^- (\d\d):(\d\d) Goodnight", text, re.M)
    return (int(m[-1][0]), int(m[-1][1])) if m else None


def streaks(vault, today=None):
    """{'focus': days in a row with 25+ focus minutes, 'early bed': goodnights before 11 PM, 'logged': days with any log}"""
    notes = day_notes(vault, 60, today)
    tests = {
        "focus": lambda t: focus_minutes(t) >= 25,
        "early bed": lambda t: (lambda b: b is not None and (b[0] < 23 and b[0] >= 18))(bed_time(t)),
        "logged": lambda t: "\n- " in t,
    }
    out = {}
    for name, ok in tests.items():
        n, start = 0, 0
        if not ok(notes[0][1]):
            start = 1   # today isn't over yet, count from yesterday
        for _, text in notes[start:]:
            if not ok(text):
                break
            n += 1
        out[name] = n
    return out


def streak_line(st):
    bits = []
    if st.get("focus", 0) >= 2:
        bits.append(f"{st['focus']} days locked in")
    if st.get("early bed", 0) >= 2:
        bits.append(f"{st['early bed']} nights in bed before 11")
    return ("Streaks: " + " and ".join(bits) + ".") if bits else ""


def week_digest(vault, today=None):
    lines = []
    for d, text in reversed(day_notes(vault, 7, today)):
        logs = [l[2:] for l in text.splitlines() if l.startswith("- ")]
        if logs:
            lines.append(f"{d}: " + " | ".join(logs[:25]))
    return "\n".join(lines)


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
        self.active_since = clock()
        self.arrived_at = None  # when your phone joined home WiFi

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
            if self.away:
                self.active_since = now - idle
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


def phone_home(ip, timeout_ms=800):
    if not ip:
        return None
    import subprocess
    args = ["ping", "-n", "1", "-w", str(timeout_ms), ip] if IS_WIN else ["ping", "-c", "1", "-W", "1", ip]
    try:
        return subprocess.run(args, capture_output=True, timeout=5, creationflags=0x08000000 if IS_WIN else 0).returncode == 0
    except Exception:
        return None


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
    if presence.arrived_at and time.time() - presence.arrived_at < 3 * 3600:
        parts.append("His phone joined home WiFi at " + time.strftime("%I:%M %p", time.localtime(presence.arrived_at)).lstrip("0") + ".")
    if presence.before_leaving:
        parts.append("Before he left, his screen had: " + "; ".join(presence.before_leaving[:6]) + ".")
    log = vault.today_log() if vault else ""
    if log:
        parts.append("Today's log so far:\n" + log)
    if morning:
        parts.append("This is his first wake of the day, so fold in a short morning brief: his first event and leave time, how many "
                     "other events, and any unread email from a real person that needs him.")
    parts.append("If he has a game today, open with 'Game day.' and the kickoff and leave time. If he just came back from practice or "
                 "a game, ask how it went in a few words and nudge food, water or stretching. If he was gone for days, catch him up. "
                 "If something at SolidHauz is urgent today (use the SolidHauz tools if you have them), mention it in one short line, "
                 "otherwise skip the shop. If it is after 10 PM, keep it short and point him to bed.")
    parts.append(
        "Reply with ONLY a JSON object, no other text: "
        '{"greeting": "what Jarvis says out loud, under 55 words, warm and natural, like a friend who knows his day. '
        "Name what he just did if you can tell (for example: welcome back from practice, how did the game go). "
        "Then the next thing he needs and when to leave. No hyphens, no lists, no markdown.\", "
        '"just_did": "practice | game | school | other | unknown", "game_today": true or false, '
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
    def __init__(self, say, chime=None, clock=time.time, timer=threading.Timer, busy=lambda: False):
        self.say, self.chime, self.clock, self.timer, self.busy = say, chime, clock, timer, busy
        self.armed = {}

    @staticmethod
    def alerts(ev):
        """[(minutes_before, line)] for one event."""
        title = (ev.get("title") or "").strip()
        low = title.lower()
        if ev.get("leave") or low.startswith("leave"):
            what = re.sub(r"^leave (for )?", "", title, flags=re.I) or "it"
            what = re.sub(r"^(game|practice|school)\b", r"the \1", what, flags=re.I)
            pack = f" Pack {GAME_BAG}." if "game" in what.lower() else " Start packing."
            return [(30, f"Heads up. You leave for {what} in 30 minutes.{pack}"),
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
        urgent = line.lower().startswith(("time to go", "leave in", "heads up. you leave"))
        if (quiet_now() or self.busy()) and not urgent:
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
    m = re.fullmatch(r"i (?:scored|got|had) (a|an|one|two|three|four|\d+)? ?(goals?|assists?|clean sheet)(?: today| tonight)?", t)
    if m:
        kind = m.group(2).rstrip("s") if m.group(2) != "clean sheet" else "clean sheet"
        return ("stat", (kind, int(_num(m.group(1) or "one"))))
    if re.fullmatch(r"i scored(?: today| tonight)?", t):
        return ("stat", ("goal", 1))
    if re.search(r"\b(?:what are|how are|check) my streaks?\b|\bmy streaks\b", t):
        return ("streaks", None)
    if re.fullmatch(r"(?:hype me up|pregame|pre game|game day mode|get me hyped|pump me up)", t):
        return ("pregame", None)
    if re.fullmatch(r"(?:bring back|restore|reopen) my (?:stuff|windows|screen|work)|put (?:everything|my stuff) back|where was i", t):
        return ("restore", None)
    if re.search(r"\b(?:anything (?:at|from) the shop|how'?s (?:the shop|solid ?hauz)|shop update|solid ?hauz update|what'?s going on (?:at|with) (?:the shop|solid ?hauz))\b", t):
        return ("shop", None)
    if re.search(r"\bwhat(?:'?s| is| do i have) due\b|\bany (?:deadlines|homework)\b|\bwhat'?s coming up\b", t):
        return ("due", None)
    if re.fullmatch(r"(?:do (?:my |the |a )?)?weekly review|how was my week|review my week", t):
        return ("weekly", None)
    if re.fullmatch(r"(?:any|check (?:my |for )?)(?:important|new important) (?:mail|email|emails|messages)|anything important(?: in my (?:mail|email))?|(?:any )?(?:mail|email) that matters", t):
        return ("mail_check", None)
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
        self.planner = Planner(say, chime, busy=lambda: self.held())
        self.focus_timer = None
        self.focus_started = 0
        self.news = []            # important mail held while you were away or focusing
        self.play = None          # play(query) through Spotify, set by jarvis.py
        self.restore_windows = None   # restore(titles) -> count, set by jarvis.py
        self.last_break_nudge = 0
        self.fact_sources = []    # callables returning extra lines for the welcome (weather, screen time)
        self.guest = False        # guest mode: nothing private out loud
        self.hold_until = 0       # protocols hold notifications until this time
        self.last_brief_day = load_state().get("brief_day")

    def hold(self, secs):
        self.hold_until = time.time() + secs if secs else 0

    def held(self):
        return bool(self.focus_started) or time.time() < self.hold_until

    def start(self):
        if AUTO_WELCOME:
            self.presence.on_return = self.auto_welcome
        threading.Thread(target=self.presence.watch, daemon=True).start()
        threading.Thread(target=self._plan_refresh, daemon=True).start()
        threading.Thread(target=self._routines, daemon=True).start()
        _log(f"vault: {self.vault.root}" + ("" if self.vault.is_obsidian else " (not an Obsidian vault yet, it still works)"))

    def context_for_claude(self):
        """Added to every Claude prompt so answers know what Jarvis knows."""
        mem = self.vault.memory()
        if self.guest:
            return " Guests are in the room. Never read emails, messages, grades or private notes out loud; offer to show them on screen instead."
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
        facts = []
        for src in self.fact_sources:
            try:
                f = src()
                if f:
                    facts.append(f)
            except Exception:
                pass
        if facts:
            prompt = prompt.replace("\n\nReply with ONLY", "\n\n" + "\n".join(facts) + "\n\nReply with ONLY", 1)
        if self.guest:
            prompt += "\n\nGuests are in the room: no email, no private details, just a friendly hello and the time."
        result = {}

        def work():
            try:
                result["text"] = self.ask(prompt, tools=SHOP_TOOLS)
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
        if data and data.get("game_today") and morning and GAMEDAY_PLAYLIST and self.play:
            threading.Thread(target=self.play, args=(GAMEDAY_PLAYLIST,), daemon=True).start()
        self.flush_news()
        return line

    def flush_news(self):
        if self.news and not self.held() and not self.guest:
            items, self.news = self.news[:3], self.news[3:]
            self.say("While you were out. " + " ".join(items))

    def present(self):
        return self.presence.idle() < 10 * 60 and not self.presence.away

    # background routines: wind down, weekly review, breaks, mail, phone
    def _routines(self):
        done, last_mail, phone_was = set(), 0, None
        while True:
            time.sleep(60)
            try:
                lt = time.localtime()
                hm, today = time.strftime("%H:%M", lt), time.strftime("%Y-%m-%d", lt)
                if WIND_DOWN and hm == WIND_DOWN and ("wind", today) not in done and self.present():
                    done.add(("wind", today))
                    self.wind_down()
                if WEEKLY_REVIEW and lt.tm_wday == WEEKLY_REVIEW[0] and hm >= WEEKLY_REVIEW[1] and ("week", today) not in done and self.present():
                    done.add(("week", today))
                    self.weekly(spoken=True)
                active_h = (time.time() - self.presence.active_since) / 3600
                if (BREAK_AFTER_HOURS and active_h >= BREAK_AFTER_HOURS and not self.focus_started and self.present()
                        and time.time() - self.last_break_nudge > 3600 and not quiet_now()):
                    self.last_break_nudge = time.time()
                    self.say(f"You've been at the desk {int(active_h)} hours straight. Stand up, water, ten minutes away from the screen.")
                if MAIL_WATCH_MINUTES and 7 <= lt.tm_hour < 22 and time.time() - last_mail > MAIL_WATCH_MINUTES * 60:
                    last_mail = time.time()
                    self.check_mail()
                if PHONE_IP:
                    home = phone_home(PHONE_IP)
                    if home and phone_was is False:
                        self.presence.arrived_at = time.time()
                        self.vault.log("Got home")
                    if home is not None:
                        phone_was = home
            except Exception as e:
                _log(f"routines: {e}")

    def check_mail(self, spoken_if_none=False):
        st = load_state()
        seen = set(st.get("mail_seen", []))
        q = "newer_than:1d -category:promotions -category:social (" + " OR ".join(
            [f"from:{x}" for x in IMPORTANT_SENDERS] + [f'"{x}"' if " " in x else x for x in IMPORTANT_TOPICS]) + ")"
        text = self.ask(f"Search my Gmail with this query: {q}\nSkip newsletters, receipts and automated mail. Reply with ONLY JSON: "
                        '{"items": [{"id": "the thread id", "line": "one spoken sentence: who it is from and what they need"}]} '
                        "Newest first, at most 5. Empty list if nothing real.")
        data = parse_json(text) or {}
        fresh = [i for i in data.get("items", []) if i.get("id") and i["id"] not in seen and i.get("line")]
        if fresh:
            st["mail_seen"] = (list(seen) + [i["id"] for i in fresh])[-300:]
            save_state(st)
            for i in fresh:
                self.vault.log("Mail: " + i["line"])
            lines = [i["line"] for i in fresh]
            if self.present() and not self.held() and not self.guest and not quiet_now():
                if self.chime:
                    self.chime(740)
                self.say(" ".join(lines[:3]))
            else:
                self.news += lines
        elif spoken_if_none:
            self.say("Nothing important in your mail today.")
        return fresh

    def wind_down(self):
        st = streak_line(streaks(self.vault))
        text = self.ask("It's wind down time for Yash. In under 45 spoken words: tomorrow's first event and when he needs to wake or "
                        "leave, from his Google Calendar, and tell him to start getting ready for bed. Warm, no hyphens."
                        + (f" Mention this: {st}" if st else ""))
        if text:
            self.say(text)
            self.vault.log("Wind down")

    def weekly(self, spoken=True):
        digest = week_digest(self.vault)
        season = self.season.spoken()
        st = streaks(self.vault)
        focus_total = sum(focus_minutes(t) for _, t in day_notes(self.vault, 7))
        text = self.ask(
            "Write my weekly review as an Obsidian note in Markdown with these sections: Wins, What slipped, Soccer, Next week (from my "
            "Google Calendar, the next 7 days, with leave times for games), One focus for next week. Keep it tight. Then on the very "
            "last line write SPOKEN: and a 50 word spoken summary with no hyphens.\n\n"
            f"Season: {season}\nFocus minutes this week: {focus_total}\nStreaks: {st}\nDaily logs:\n{digest or '(no logs yet)'}")
        body, _, spoken_part = (text or "").rpartition("SPOKEN:")
        if not body:
            body, spoken_part = text or "", ""
        rel = f"Weekly/{time.strftime('%G-W%V')}.md"
        self.vault._write(rel, f"---\ntags: [weekly]\n---\n# Week {time.strftime('%V')}, {time.strftime('%B %d').replace(' 0', ' ')}\n\n" + body.strip() + "\n", "w")
        self.vault.log(f"Weekly review written to {rel}")
        if spoken:
            self.say((spoken_part.strip() or "Your weekly review is in Obsidian.") + " The full review is in your Weekly folder.")
        return rel

    def auto_welcome(self, gone):
        if gone < AUTO_WELCOME_AFTER or quiet_now() or self.held():
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
        st = streak_line(streaks(self.vault))
        if text and not text.lstrip().startswith("{"):
            self.vault.log("Goodnight. " + text)
            return text + (" " + st if st else "")
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
        elif action == "stat":
            kind, n = arg
            self.season.add_stat(kind, n)
            st = self.season.stats()
            hype = {"goal": "Let's go.", "assist": "Nice ball.", "clean sheet": "Wall."}[kind]
            say(f"{hype} That's {st['goal']} goals and {st['assist']} assists this season.")
        elif action == "streaks":
            st = streaks(self.vault)
            say(f"Focus streak {st['focus']} days. In bed before 11, {st['early bed']} nights. You've logged {st['logged']} days in a row.")
        elif action == "pregame":
            if GAMEDAY_PLAYLIST and self.play:
                threading.Thread(target=self.play, args=(GAMEDAY_PLAYLIST,), daemon=True).start()
            say(self.ask("Hype Yash up for his game in under 40 spoken words, like a teammate, not a coach. Use his next game from his "
                         "Google Calendar (opponent, kickoff) and his season record: " + self.season.spoken() +
                         " No hyphens, no cringe, end with the leave time."))
        elif action == "restore":
            titles = self.presence.before_leaving
            if not titles:
                return say("I don't have a snapshot from before you left.")
            n = self.restore_windows(titles) if self.restore_windows else 0
            names = sorted({t.split(":", 1)[0] for t in titles})[:4]
            say(f"Brought back {n} windows." if n else "Before you left you had " + ", ".join(names) + " open.")
        elif action == "shop":
            say(self.ask("Out loud in under 60 words: what's happening at SolidHauz today. Jobs behind, new leads, payments, consults "
                         "today, anything urgent first. Use the SolidHauz tools.", tools=SHOP_TOOLS))
        elif action == "due":
            inbox = [l for l in v.read(f"{JARVIS_FOLDER}/Inbox.md").splitlines() if l.startswith("- [ ]")][-10:]
            say(self.ask("Out loud in under 60 words: what's due for me in the next 7 days from my Google Calendar (all day Due events "
                         "and deadlines), soonest first, then the one thing to do tonight. Open items from my inbox:\n"
                         + ("\n".join(inbox) or "(none)")))
        elif action == "weekly":
            say("Pulling your week together.")
            self.weekly(spoken=True)
        elif action == "mail_check":
            say("Checking.")
            fresh = self.check_mail(spoken_if_none=True)
            if fresh and (not self.present() or self.focus_started):
                self.news, lines = [], self.news
                say(" ".join(lines[:3]))
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
        st = streak_line(streaks(self.vault))
        self.say(f"Focus done. {mins} minutes, {total} today. " + (st + " " if st else "") + "Take a 10 minute break. Say log, and what you got done.")
        self.flush_news()
