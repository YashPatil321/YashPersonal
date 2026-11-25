"""
Routines: things Atlas does on a schedule, set up and changed by voice.

  "every friday at 5 remind me to send the report"                 says it at that time
  "every weekday at 8:30 tell me the weather and my agenda"         does it (any command or question) at that time
  "every day at 10 pm tell me to plug in my phone"
  "every monday and wednesday at 6 pm remind me practice gear"
  "every 2 hours between 9 and 5 remind me to drink water"
  "what are my routines" / "delete the report routine" / "clear my routines"
  "don't talk to me unprompted between 11 and 7"   quiet hours: nothing Atlas starts on its own speaks in that
                                                   window (a routine you set inside it still rings, you chose that time)

A routine that comes due while Atlas is busy waits; if it's more than an hour late it's skipped and logged.
"""

import json
import os
import re
import threading
import time

HERE = os.path.dirname(os.path.abspath(__file__))
FILE = os.path.join(HERE, ".routines.json")
DAYS = ["monday", "tuesday", "wednesday", "thursday", "friday", "saturday", "sunday"]
NUM = {"one": 1, "two": 2, "three": 3, "four": 4, "five": 5, "six": 6, "seven": 7, "eight": 8, "nine": 9, "ten": 10,
       "eleven": 11, "twelve": 12, "fifteen": 15, "twenty": 20, "thirty": 30, "forty five": 45, "noon": 12, "midnight": 0}


def _log(msg):
    print(time.strftime("[%H:%M:%S] ") + "routines: " + str(msg), flush=True)


def parse_time(s):
    """'5', '5 pm', '8:30', '8 30 am', 'noon', '17:00' -> (h, m) in 24h, or None. Bare hours 1 to 6 count as PM."""
    s = s.strip().lower().replace(".", "")
    if s in ("noon", "midday"):
        return 12, 0
    if s == "midnight":
        return 0, 0
    m = re.fullmatch(r"(\d{1,2}|[a-z]+)(?:[: ](\d{2}))?\s*(am|pm|in the morning|in the evening|at night|tonight)?", s)
    if not m:
        return None
    h = int(m.group(1)) if m.group(1).isdigit() else NUM.get(m.group(1))
    if h is None or h > 23:
        return None
    mi = int(m.group(2) or 0)
    ap = m.group(3) or ""
    if ap in ("pm", "in the evening", "at night", "tonight") and h < 12:
        h += 12
    elif ap in ("am", "in the morning") and h == 12:
        h = 0
    elif not ap and 1 <= h <= 6:
        h += 12   # "at 5" means the afternoon
    return h, mi


def parse_days(s):
    s = s.lower()
    if re.search(r"\b(?:day|daily|night|morning|evening)\b", s) and not re.search(r"\bweek(?:day|end)", s):
        return list(range(7))
    if "weekday" in s:
        return [0, 1, 2, 3, 4]
    if "weekend" in s:
        return [5, 6]
    got = [i for i, d in enumerate(DAYS) if re.search(r"\b" + d[:3] + r"(?:" + d[3:] + r")?s?\b", s)]
    return got or None


def route_routines(t):
    m = re.fullmatch(r"(?:every|each) (.+?) at (.+?) (remind me (?:to |about |that )?|tell me (?:to )?|say |do |run |play |check |give me |read me )(.+)", t)
    if m:
        days, tm = parse_days(m.group(1)), parse_time(m.group(2))
        if tm and tm[0] < 12 and re.search(r"\b(?:night|evening)\b", m.group(1)):
            tm = (tm[0] + 12, tm[1])   # "every night at 11" is 11 PM
        verb, rest = m.group(3).strip(), m.group(4).strip()
        if days is not None and tm:
            say = verb.startswith(("remind", "say")) or (verb.startswith("tell me") and not re.match(r"(?:the|my|what|how|about)\b", rest))
            what = rest if say or verb.startswith(("tell", "give", "read")) else (verb + " " + rest).strip()
            if not say and verb.startswith(("tell", "give", "read")):
                what = "tell me " + rest
            return ("routine_add", {"days": days, "h": tm[0], "m": tm[1], "kind": "say" if say else "do", "text": what})
    m = re.fullmatch(r"every (\w+) (?:hours?|minutes?)(?: between (.+?) and (.+?))? (?:remind me (?:to )?|tell me (?:to )?|say )(.+)", t)
    if m:
        n = int(m.group(1)) if m.group(1).isdigit() else NUM.get(m.group(1), 1 if m.group(1) in ("hour", "an", "a") else None)
        unit = 60 if "hour" in t.split(" between")[0].split(m.group(1), 1)[1] else 1
        if n:
            a = parse_time(m.group(2)) if m.group(2) else (0, 0)
            b = parse_time(m.group(3)) if m.group(3) else (23, 59)
            return ("routine_add", {"every": n * unit, "from": a, "to": b, "kind": "say", "text": m.group(4), "days": list(range(7))})
    m = re.fullmatch(r"(?:don'?t|do not) (?:talk to me|bother me|speak) (?:unprompted |on your own )?(?:between|from) (.+?) (?:and|to|until) (.+)", t)
    if m:
        a, b = parse_time(m.group(1)), parse_time(m.group(2))
        if a and b:
            # "between 11 and 7" means 11 PM to 7 AM
            if a[0] < 12 and b[0] <= a[0] and not re.search(r"am|morning", m.group(1)):
                a = (a[0] + 12 if a[0] < 12 else a[0], a[1])
            if b[0] >= 12 and b[0] - 12 < a[0] - 12 and not re.search(r"pm|evening|night", m.group(2)):
                b = (b[0] - 12, b[1])
            return ("quiet_set", (a[0], b[0]))
    if re.fullmatch(r"(?:what are|list|read me|tell me) my routines|what routines do i have|what'?s scheduled", t):
        return ("routine_list", None)
    m = re.fullmatch(r"(?:delete|remove|cancel|stop) (?:the |my )?(.+?) routine", t)
    if m:
        return ("routine_del", m.group(1))
    if re.fullmatch(r"(?:clear|delete|remove) (?:all )?(?:of )?my routines", t):
        return ("routine_del", "*")
    return None


def describe(r):
    if "every" in r:
        n = r["every"]
        when = f"every {n // 60} hours" if n % 60 == 0 and n >= 120 else "every hour" if n == 60 else f"every {n} minutes"
    else:
        d = r["days"]
        days = "every day" if len(d) == 7 else "weekdays" if d == [0, 1, 2, 3, 4] else "weekends" if d == [5, 6] else \
            " and ".join(DAYS[i].title() + "s" for i in d)
        h, m = r["h"], r["m"]
        when = f"{days} at {(h % 12) or 12}{':%02d' % m if m else ''} {'PM' if h >= 12 else 'AM'}"
    return f"{when}: {you(r['text'])}"


def you(text):
    """'plug in my phone' -> 'plug in your phone', for saying it back to you."""
    swap = {"my": "your", "me": "you", "i": "you", "i'm": "you're", "mine": "yours", "myself": "yourself"}
    return re.sub(r"\b(my|me|i|i'm|mine|myself)\b", lambda m: swap[m.group(1).lower()], text, flags=re.I)


class Routines:
    def __init__(self, say, run_command, busy=lambda: False, log=_log):
        """say(text) speaks; run_command(text) handles it like you said it; busy() is True while you're talking to Atlas."""
        self.say, self.run_command, self.busy, self.log = say, run_command, busy, log
        self.items = self._load()

    def _load(self):
        try:
            with open(FILE, encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            return []

    def _save(self):
        with open(FILE, "w", encoding="utf-8") as f:
            json.dump(self.items, f, indent=1)

    def add(self, r):
        r = dict(r, id=int(time.time() * 1000), last=0)
        self.items.append(r)
        self._save()
        return describe(r)

    def remove(self, words):
        if words == "*":
            n, self.items = len(self.items), []
            self._save()
            return n
        ws = [w for w in re.findall(r"[a-z0-9]+", words.lower()) if w not in ("the", "my", "a")]
        keep = [r for r in self.items if not all(w in (r["text"] + " " + describe(r)).lower() for w in ws)]
        n = len(self.items) - len(keep)
        self.items = keep
        self._save()
        return n

    def due(self, now=None):
        """Routines due now (and not already run for this slot)."""
        now = now or time.time()
        lt = time.localtime(now)
        out = []
        for r in self.items:
            if lt.tm_wday not in r.get("days", list(range(7))):
                continue
            if "every" in r:
                a, b = r["from"], r["to"]
                mins = lt.tm_hour * 60 + lt.tm_min
                if not (a[0] * 60 + a[1] <= mins <= b[0] * 60 + b[1]):
                    continue
                if now - r.get("last", 0) >= r["every"] * 60 - 30 and lt.tm_min % min(r["every"], 60) == (a[1] % min(r["every"], 60)):
                    out.append(r)
            else:
                slot = time.mktime((lt.tm_year, lt.tm_mon, lt.tm_mday, r["h"], r["m"], 0, 0, 0, -1))
                if 0 <= now - slot <= 3600 and r.get("last", 0) < slot:
                    out.append(r)
        return out

    def fire(self, r, now=None):
        r["last"] = now or time.time()
        self._save()
        self.log("running: " + describe(r))
        if r["kind"] == "say":
            self.say("Hey, reminder: " + you(r["text"]).rstrip(".") + ".")
        else:
            self.run_command(r["text"])

    def watch(self):
        while True:
            time.sleep(20)
            try:
                for r in self.due():
                    waited = 0
                    while self.busy() and waited < 600:   # don't cut into a conversation
                        time.sleep(5)
                        waited += 5
                    self.fire(r)
            except Exception as e:
                self.log(f"watch: {e}")
