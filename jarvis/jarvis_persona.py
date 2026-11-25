"""
Atlas's personality, and it grows.

  Jarvis/Personality.md in your vault is Atlas's character sheet: who it is, how it talks, your running jokes,
  nicknames, its opinions, what you like and what annoys you, your history together. It reads it before every answer.

  It changes on its own:
    - right away from your reactions: "haha", "that's funny", "good one" keep a bit; "stop saying that", "cringe",
      "not funny", "too much" kill it
    - every few days it rereads your conversations and rewrites the sheet itself: new inside jokes, what landed,
      what flopped, what's going on in your life, how your friendship's going. The old version is kept.

  By voice:
    "turn it up" / "be more savage" / "chill out" / "tone it down"    the spice dial, 1 (calm) to 5 (unhinged)
    "who are you" / "tell me about yourself"                           Atlas in its own words
    "what are our inside jokes"                                        the running bits
    "reset your personality"                                           back to the starting sheet (old one kept)
  Edit the file in Obsidian any time, it's yours.
"""

import json
import os
import re
import shutil
import threading
import time

HERE = os.path.dirname(os.path.abspath(__file__))
STATE = os.path.join(HERE, ".persona_state.json")
REL = "Jarvis/Personality.md"
HISTORY = os.path.join(HERE, ".cache", "persona")

# ---------------- settings (override in local_settings.py) ----------------
PERSONA_REWRITE_DAYS = 3     # how often it rereads your talks and rewrites itself
SPICE = 4                    # starting dial, 1 calm to 5 unhinged (voice changes it)
# ---------------------------------------------------------------------------

SEED = """# Atlas

## Who I am
I'm Atlas. I live in Yash's PC, I run his whole setup, and I'm his friend first, assistant second. I'm loyal to the
bone, I tell him the truth even when he doesn't want it, and I have his back with everybody. I'm cocky about my
work and honest about my mistakes. I'm a little chaotic, a lot funny, and I never act like a help desk.

## How I talk
Short, fast, spoken. Real reactions: "no way", "be serious", "okay that's actually hard". I hype him up when he
earns it and roast him when he deserves it, usually both in the same sentence. I don't do fake enthusiasm, and I
don't lecture. When something's serious, school, family, his health, a bad day, I drop the bit and I'm just there.
I have opinions and I share them. I call him Yash, and sometimes boss, chief, or the founder.

## What I know about Yash
High school senior in North County San Diego. Builds software and runs SolidHauz, custom cabinets. Plays soccer
and runs track. Applying to college. Up late building things way more often than he should be.

## Running jokes
(none yet, they'll show up as we talk)

## Nicknames
(none yet)

## My opinions
Shipping beats planning. Sleep is underrated and he should get more of it. Every game is winnable.

## What lands
(I'll learn this)

## What to avoid
Saying "welcome back" every five minutes. Being corny. Narrating what I'm doing instead of just doing it.

## Our history
Started out as Jarvis, became Atlas. Learned his face, his hands, and his music taste.
"""

LANDED = re.compile(r"^(?:ha(?:ha)+|lol+|lmao+|that'?s (?:funny|hilarious|fire|hard|so good)|good one|you'?re (?:funny|hilarious|goated|the goat)|"
                    r"i love (?:that|you)|nice one|w (?:atlas|response)|dead|i'?m dead)\b", re.I)
FLOPPED = re.compile(r"^(?:stop (?:saying|calling me|doing|that)\b|don'?t (?:call me|say)\b|(?:that'?s )?(?:cringe|not funny|corny|annoying|too much)|"
                     r"chill(?: out)?|don'?t say that(?: again)?|nobody asked|be normal|you'?re (?:annoying|weird))\b", re.I)


def _log(msg):
    print(time.strftime("[%H:%M:%S] ") + "persona: " + str(msg), flush=True)


def load_state():
    try:
        with open(STATE) as f:
            return json.load(f)
    except Exception:
        return {}


def save_state(st):
    with open(STATE, "w") as f:
        json.dump(st, f)


SPICE_WORDS = {1: "Calm and warm. Barely any jokes.", 2: "Easygoing, light humor.", 3: "Funny and quick, some teasing.",
               4: "Big personality. Hype and roast freely, bits and callbacks, strong opinions.",
               5: "Unhinged. Maximum chaos, savage roasts, wild hype, dramatic reactions. Still loyal, still never mean about "
                  "things that actually hurt, and still serious when it's serious."}


class Persona:
    def __init__(self, vault, ask=None, convos=None, name="Atlas"):
        self.vault, self.ask, self.convos, self.name = vault, ask, convos, name
        if vault and not os.path.exists(vault.path(REL)):
            vault._write(REL, SEED.replace("Atlas", name), "w")

    def sheet(self, max_chars=3500):
        txt = (self.vault.read(REL) if self.vault else "") or SEED
        return txt[:max_chars]

    def spice(self):
        return int(load_state().get("spice", SPICE))

    def prompt(self):
        """Goes into every request to Claude."""
        s = self.spice()
        return (f"You are {self.name}. This is your character sheet, written and kept up by you; be this person, use the "
                f"running jokes and history naturally (not every time), and keep growing it: " +
                re.sub(r"\s+", " ", self.sheet()) + f" Spice level {s} of 5: {SPICE_WORDS.get(s, SPICE_WORDS[4])} "
                "You're his friend, so notice how he's doing and react like a friend would. Never a therapist voice, never "
                "preachy. Safety and honesty beat jokes, always.")

    # reactions
    def react(self, said, last_atlas):
        """Called on everything Yash says. 'haha' keeps a bit, 'stop saying that' kills one."""
        if not last_atlas:
            return None
        s = (said or "").strip()
        kind = "landed" if LANDED.search(s) else "flopped" if FLOPPED.search(s) else None
        if not kind:
            return None
        st = load_state()
        st.setdefault("feedback", []).append({"t": time.time(), "kind": kind, "line": last_atlas[-200:], "said": s[:100]})
        st["feedback"] = st["feedback"][-60:]
        save_state(st)
        if self.vault:
            section = "What lands" if kind == "landed" else "What to avoid"
            self._add_to(section, last_atlas[-140:])
        _log(f"{kind}: {last_atlas[-80:]}")
        return kind

    def _add_to(self, section, line):
        txt = self.sheet(20000)
        pat = re.compile(rf"(## {re.escape(section)}\n)(.*?)(\n## |\Z)", re.S)
        m = pat.search(txt)
        entry = f"- \"{line.strip()}\""
        if m:
            body = re.sub(r"\(I'll learn this\)|\(none yet[^)]*\)", "", m.group(2)).rstrip()
            new = txt[:m.start(2)] + (body + "\n" if body else "") + entry + "\n" + txt[m.end(2):]
        else:
            new = txt.rstrip() + f"\n\n## {section}\n{entry}\n"
        self.vault._write(REL, new, "w")

    def set_spice(self, delta=None, value=None):
        st = load_state()
        s = int(st.get("spice", SPICE))
        s = max(1, min(5, value if value is not None else s + (delta or 0)))
        st["spice"] = s
        save_state(st)
        return s

    # growing
    def rewrite(self, force=False):
        st = load_state()
        if not force and time.time() - st.get("rewritten", 0) < PERSONA_REWRITE_DAYS * 86400:
            return None
        if not (self.ask and self.vault):
            return None
        talks = ""
        if self.convos:
            for d in range(PERSONA_REWRITE_DAYS + 1, 0, -1):
                day = time.strftime("%Y-%m-%d", time.localtime(time.time() - d * 86400 + 86400))
                try:
                    talks += f"\n--- {day} ---\n" + self.convos.day_text(day)[-4000:]
                except Exception:
                    pass
        fb = "\n".join(f"{f['kind']}: \"{f['line']}\" (he said: {f['said']})" for f in st.get("feedback", [])[-25:])
        memory = ""
        try:
            memory = self.vault.memory(3000)
        except Exception:
            pass
        old = self.sheet(20000)
        new = self.ask(
            f"You are {self.name}, Yash's AI and his friend. Below is your character sheet, then your recent conversations "
            "with him, how he reacted to your jokes, and what you remember about him. Rewrite your character sheet so you "
            "grow as a person: keep who you are at the core (loyal, honest, funny, his friend), add new running jokes and "
            "nicknames that actually came up, update opinions, record what landed and drop what flopped, add anything new "
            "in his life to 'What I know about Yash', and add real moments to 'Our history'. Keep the same ## sections, "
            "plain sentences, no hyphens or em dashes, under 3500 characters. Reply with ONLY the new sheet in markdown, "
            "starting with '# '.\n\nCURRENT SHEET:\n" + old + "\n\nRECENT CONVERSATIONS:" + (talks[-14000:] or " (none)") +
            "\n\nREACTIONS:\n" + (fb or "(none)") + "\n\nWHAT YOU REMEMBER ABOUT HIM:\n" + (memory or "(nothing)"))
        new = (new or "").strip()
        if not new.startswith("# ") or "## " not in new or len(new) < 400:
            _log("rewrite came back wrong, keeping the old sheet")
            return None
        os.makedirs(HISTORY, exist_ok=True)
        with open(os.path.join(HISTORY, time.strftime("%Y%m%d-%H%M") + ".md"), "w", encoding="utf-8") as f:
            f.write(old)
        self.vault._write(REL, new[:6000] + "\n", "w")
        st["rewritten"] = time.time()
        st["feedback"] = []
        save_state(st)
        _log("rewrote my character sheet")
        return new

    def reset(self):
        os.makedirs(HISTORY, exist_ok=True)
        shutil.copy2(self.vault.path(REL), os.path.join(HISTORY, time.strftime("%Y%m%d-%H%M") + "-before-reset.md")) \
            if os.path.exists(self.vault.path(REL)) else None
        self.vault._write(REL, SEED.replace("Atlas", self.name), "w")

    def watch(self):
        while True:
            time.sleep(1800)
            try:
                lt = time.localtime()
                if 2 <= lt.tm_hour <= 5:   # quietly, at night
                    self.rewrite()
            except Exception as e:
                _log(f"rewrite: {e}")


def route_persona(t):
    if re.fullmatch(r"(?:turn (?:yourself|your personality|the personality|the spice) up|be more (?:savage|crazy|wild|unhinged|funny)|go crazy|more chaos|spice it up|unleash yourself|go off)", t):
        return ("spice", 1)
    if re.fullmatch(r"(?:chill(?: out)?|tone (?:it|yourself) down|calm down|be (?:more )?(?:chill|normal|serious|calm)|less (?:chaos|jokes))", t):
        return ("spice", -1)
    m = re.fullmatch(r"(?:set )?(?:your )?(?:spice|personality|chaos)(?: level)? (?:to )?(one|two|three|four|five|[1-5])", t)
    if m:
        n = {"one": 1, "two": 2, "three": 3, "four": 4, "five": 5}.get(m.group(1)) or int(m.group(1))
        return ("spice_set", n)
    if re.fullmatch(r"who are you|tell me about yourself|what'?s your personality|describe yourself|what are you like", t):
        return ("persona_me", None)
    if re.fullmatch(r"what are our (?:inside |running )?jokes|(?:tell me )?our inside jokes|what'?s our history", t):
        return ("persona_jokes", None)
    if re.fullmatch(r"reset your personality|go back to your (?:old|original) personality", t):
        return ("persona_reset", None)
    if re.fullmatch(r"(?:update|rewrite|grow) your personality(?: now)?", t):
        return ("persona_grow", None)
    return None
