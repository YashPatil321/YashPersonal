"""
Jarvis's memory of your conversations.

  Short term  every exchange (what you said, what Jarvis said, commands, reminders) goes in a running log. The recent
              part rides along with every question to Claude, so Jarvis always knows what you just talked about,
              even after a restart or a fresh Claude session.
  Long term   once a day Jarvis rereads yesterday's conversations and keeps the lasting facts (plans, preferences,
              people, decisions, things to follow up on) in Jarvis/Memory.md in your vault.
  Search      "what did we talk about yesterday", "what did I ask you about Babson". Full transcripts are in
              Jarvis/Conversations/<date>.md in your vault.
"""

import json
import os
import re
import threading
import time

RECENT_HOURS = 8             # how far back the "what we just talked about" context goes
RECENT_CHARS = 2400          # and how much of it, at most
FILLERS = {"One sec.", "On it.", "Checking.", "Give me a second.", "Working on it.", "Looking.", "Checking your calendar.",
           "Looking through your email.", "Checking your Drive.", "Checking the shop.", "Checking Spotify.", "Searching the web.",
           "Reading up on it.", "Taking a look.", "Looking at your screen.", "Reading what's on screen.", "Checking your notes.",
           "Making the change.", "Checking your Claude sessions.", "Checking Vercel.", "Checking the database."}


def _log(msg):
    print(time.strftime("[%H:%M:%S] ") + "memory: " + str(msg), flush=True)


class Conversations:
    def __init__(self, vault=None, folder=None, clock=time.time):
        self.vault, self.clock = vault, clock
        here = os.path.dirname(os.path.abspath(__file__))
        self.path = os.path.join(folder or here, ".conversation.jsonl")
        self.lock = threading.Lock()

    # ---- writing ----
    def add(self, who, text, kind="talk"):
        text = re.sub(r"\s+", " ", (text or "")).strip()
        if not text or text in FILLERS:
            return
        now = self.clock()
        rec = {"t": now, "who": who, "text": text[:1200], "kind": kind}
        with self.lock:
            with open(self.path, "a", encoding="utf-8") as f:
                f.write(json.dumps(rec) + "\n")
            if self.vault:
                try:
                    day = time.strftime("%Y-%m-%d", time.localtime(now))
                    rel = f"Jarvis/Conversations/{day}.md"
                    head = "" if os.path.exists(self.vault.path(rel)) else f"# Conversations, {day}\n\n"
                    name = "**You**" if who == "you" else "**Jarvis**"
                    self.vault._write(rel, head + f"- {time.strftime('%H:%M', time.localtime(now))} {name}: {text}\n")
                except Exception as e:
                    _log(f"vault write: {e}")
        self._trim()

    def _trim(self, keep_days=14):
        """The local log keeps two weeks. The vault keeps everything."""
        try:
            if os.path.getsize(self.path) < 3_000_000:
                return
            cut = self.clock() - keep_days * 86400
            with self.lock:
                rows = [l for l in open(self.path, encoding="utf-8") if json.loads(l).get("t", 0) >= cut]
                with open(self.path, "w", encoding="utf-8") as f:
                    f.writelines(rows)
        except Exception:
            pass

    # ---- reading ----
    def rows(self, since=0.0, until=None):
        until = until or self.clock() + 1
        out = []
        try:
            with open(self.path, encoding="utf-8") as f:
                for line in f:
                    try:
                        r = json.loads(line)
                    except Exception:
                        continue
                    if since <= r.get("t", 0) <= until:
                        out.append(r)
        except FileNotFoundError:
            pass
        return out

    def recent(self, hours=RECENT_HOURS, max_chars=RECENT_CHARS):
        """The last few hours of conversation, newest kept when it's long, as lines for Claude."""
        rows = self.rows(self.clock() - hours * 3600)
        lines, total = [], 0
        for r in reversed(rows):
            line = f"[{time.strftime('%a %H:%M', time.localtime(r['t']))}] {'Yash' if r['who'] == 'you' else 'You (Jarvis)'}: {r['text']}"
            if total + len(line) > max_chars:
                break
            lines.append(line)
            total += len(line)
        return "\n".join(reversed(lines))

    def day_text(self, day):
        """Everything said on one day ('2026-11-22'), for summaries."""
        start = time.mktime(time.strptime(day, "%Y-%m-%d"))
        rows = self.rows(start, start + 86400)
        return "\n".join(f"{time.strftime('%H:%M', time.localtime(r['t']))} {'Yash' if r['who'] == 'you' else 'Jarvis'}: {r['text']}" for r in rows)

    def search(self, query, n=8):
        words = [w for w in re.findall(r"[a-z0-9']+", query.lower()) if len(w) > 2 and w not in STOP]
        if not words:
            return []
        hits = []
        for r in self.rows(0):
            low = r["text"].lower()
            score = sum(1 for w in words if w in low)
            if score:
                hits.append((score, r["t"], r))
        hits.sort(key=lambda h: (-h[0], -h[1]))
        return [h[2] for h in hits[:n]]

    # ---- long term: lasting facts from yesterday, once a day ----
    def digest_day(self, day, ask, brain=None):
        text = self.day_text(day)
        if len(text) < 80:
            return []
        out = ask("Here are Yash's conversations with you (Jarvis) from " + day + ". List only the lasting facts worth "
                  "remembering for weeks: plans, deadlines, preferences, people and who they are, decisions, things he "
                  "wants followed up. Skip small talk, one off commands and anything already obvious. One fact per line, "
                  "each starting with '- ', at most 8 lines. If there's nothing lasting, reply NONE.\n\n" + text[-12000:])
        facts = [l[2:].strip() for l in (out or "").splitlines() if l.strip().startswith("- ")][:8]
        if brain:
            for f in facts:
                brain.vault.remember(f + " (from our talks)")
        return facts


STOP = set("the and for what did you about that this have with from were was are your our all any tell talk talked ask asked said".split())


# Things people say that are usually worth keeping: plans, dates, people, preferences, results, health.
IMPORTANT = re.compile(r"\b(?:i'?m (?:going|visiting|starting|trying|thinking|planning|applying|allergic)|i (?:have|got|need|want|like|love|hate|prefer|"
                       r"decided|started|quit|joined|finished|signed|committed|failed|passed|made|lost|won)|i've (?:been|got|decided)|"
                       r"my (?:\w+ )?(?:is|are|was|will be|starts|ends)|my (?:mom|dad|sister|brother|coach|friend|girlfriend|boyfriend|"
                       r"teacher|counselor|boss|client)|next (?:week|month|year|season)|tomorrow|tonight|this (?:weekend|week)|"
                       r"on (?:monday|tuesday|wednesday|thursday|friday|saturday|sunday)|january|february|march|april|may|june|july|"
                       r"august|september|october|november|december|deadline|due|appointment|interview|tryout|exam|test|birthday|"
                       r"favorite|allergic|injured|hurt|sick|accepted|rejected|offer|scholarship|we (?:won|lost|tied)|from now on|"
                       r"always|never)\b", re.I)


def worth_remembering(text):
    """A quick first pass: does this sound like something lasting? (Claude makes the real call.)"""
    return len(text.split()) >= 4 and bool(IMPORTANT.search(text))


def capture(text, recent, ask, brain, log=_log):
    """Pulls lasting facts out of one thing Yash just said and saves new ones to Memory.md. Runs in the background."""
    if not brain or not worth_remembering(text):
        return []
    out = ask("Yash just said this to you (Jarvis): \"" + text + "\"\nRecent conversation for context:\n" + recent[-1500:] +
              "\n\nDoes it contain a lasting fact worth remembering for weeks (a plan or date, a person and who they are, a "
              "preference, a decision, a result, something about his health, school, soccer, college or SolidHauz)? If yes, "
              "write each fact as one short line starting with '- ', in third person (Yash ...), at most 3 lines. "
              "If it's only a command, a question or small talk, reply NONE.")
    facts = [l[2:].strip() for l in (out or "").splitlines() if l.strip().startswith("- ")][:3]
    have = brain.vault.memory(20000).lower()
    new = [f for f in facts if f.lower()[:60] not in have]
    for f in new:
        brain.vault.remember(f)
        log("remembered: " + f)
    return new


def route_memory(t):
    if re.fullmatch(r"what do you (?:know|remember) about me|what have you (?:learned|remembered) about me|what do you remember", t):
        return ("memory_about", None)
    m = re.fullmatch(r"what did (?:we|i) (?:talk|chat|speak) about(?: (yesterday|today|earlier|this morning|last night|before))?|"
                     r"what were we (?:talking|saying) about|remind me what we (?:talked|said) about(?: (yesterday|today|earlier))?", t)
    if m:
        return ("convo_recap", (m.group(1) or m.group(2) or "today"))
    m = re.fullmatch(r"what did (?:i|we) (?:ask you|say|tell you|talk about|decide) about (.+)|did i (?:ever )?(?:tell|ask) you about (.+)|"
                     r"what did you (?:say|tell me) about (.+)", t)
    if m:
        return ("convo_search", next(g for g in m.groups() if g))
    return None
