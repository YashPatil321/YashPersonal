"""
The learning system: Atlas builds a wiki that grows from what you show it, and turns it into studying for you.
It follows the LLM wiki idea (Karpathy's pattern, the same one claude-obsidian packages): sources come in, Atlas
writes linked notes with citations, answers come out of the notes, and nothing gets saved unless you meant it.

  Feeding it (each runs in the background, then tells you what it learned):
    "learn this <link>"                     reads the page and files it into the wiki
    "learn what's on my screen"             the page, doc or chat in front of you
    "learn my clipboard"                    whatever you copied
    "learn this: <anything you say>"        straight from your mouth
    PDFs, docs and articles dropped in Wiki/Inbox in the vault get filed on their own, then moved to Wiki/Sources
  Asking it:
    "what does my wiki say about X" / "what do I know about X"   answers only from your notes, with which ones
  Studying:
    "make flashcards on X"                  writes cards (Spaced Repetition plugin format) into Study/X.md
    "quiz me on X"                          asks one question at a time out loud; just answer (no need to say Atlas),
                                            it grades you, explains misses and keeps score in the card file
  Upkeep (nightly): broken links, orphan notes, notes missing a summary get fixed or listed in Wiki/Health.md.
"""

import os
import re
import shutil
import time

WIKI = "Wiki"
STUDY = "Study"

RULES = (f"You maintain Yash's knowledge wiki in his Obsidian vault, folder {WIKI}/. Conventions: one note per idea, person, "
         "place, product or topic, named plainly (Title Case, no dates). Each note starts with frontmatter (type, tags, "
         "sources, updated), then a 2 line summary, then sections. Link every related idea as [[Note Name]], create notes "
         "for important new ideas, and add to existing notes instead of duplicating them (read them first; never delete "
         "or rewrite what Yash wrote, only append or fix clearly wrong facts). Cite sources at the bottom of each note. "
         f"Keep {WIKI}/Index.md as a map of the wiki grouped by topic. No hyphens or em dashes in prose.")


def learn_prompt(source_kind, payload, vault_root):
    w = os.path.join(vault_root, WIKI)
    how = {
        "url": f"Read this page with WebFetch (follow 1 or 2 key links if they matter): {payload}",
        "text": f"Yash told you this to learn: \"{payload}\"",
        "screen": "Run jarvis_ctl.py read to get the text of the window in front of Yash (and jarvis_ctl.py look if you need to "
                  "see it), and learn what's there.",
        "clipboard": f"This is what Yash copied:\n---\n{payload[:12000]}\n---",
        "file": f"Read this file: {payload}",
    }[source_kind]
    return (RULES + f"\n\nThe wiki folder is {w}.\n\nTask: {how}\nFile what's worth knowing into the wiki (usually 1 to 4 notes), "
            "linked into what's already there and into Index.md. Then reply with one or two plain spoken sentences: what "
            "you learned and which notes it went into.")


def ask_prompt(question, vault_root):
    return (f"Answer from Yash's own notes only: grep and read his vault at {vault_root} (the {WIKI} folder first). Don't "
            f"change any files. Question: {question}\nReply in under 70 spoken words, say which notes it came from, and "
            "say plainly if his notes don't cover it.")


def cards_prompt(topic, vault_root):
    return (f"Make study flashcards for Yash on: {topic}. Use his notes in {vault_root} (the {WIKI} and School folders) and, "
            "if they're thin, reliable sources from the web. Write them to "
            f"{os.path.join(vault_root, STUDY, safe(topic) + '.md')} for the Obsidian Spaced Repetition plugin: a #flashcards "
            "tag at the top, then one card per line as Question::Answer (or ?? on its own line for longer answers), 15 to 30 "
            "cards, from basics to hard, each answer short enough to say out loud. Link related notes as [[links]] in a "
            "Related section. Reply with one spoken sentence: how many cards and where.")


def quiz_prompt(topic, vault_root):
    return (f"Quiz Yash out loud on: {topic}. Use the cards in {os.path.join(vault_root, STUDY)} (make a few from his notes if "
            "there are none). Ask ONE question now, nothing else. When he answers next, say right or wrong in a few words, "
            "give the right answer in one sentence if he missed it, then ask the next question. Mix in ones he missed before. "
            "After 10 questions or when he says stop, give the score and append a line to the card file under a ## Quiz log "
            "heading: date, score, the ones he missed.")


def safe(name):
    return re.sub(r"[\\/:*?\"<>|#^\[\]]+", " ", name).strip()[:60] or "Topic"


class Learner:
    def __init__(self, vault, start_job, ask_fg, clipboard=None, log=print):
        """start_job(label, prompt): runs in the background and speaks the result. ask_fg(prompt): answers now."""
        self.vault, self.start_job, self.ask_fg, self.clipboard, self.log = vault, start_job, ask_fg, clipboard, log

    def handle(self, action, arg):
        root = self.vault.root
        if action == "learn":
            kind, payload = arg
            if kind == "clipboard":
                payload = (self.clipboard() if self.clipboard else "") or ""
                if not payload.strip():
                    return "Your clipboard's empty."
            self.start_job("learn " + (payload[:40] if kind in ("url", "text") else kind), learn_prompt(kind, payload, root))
            return "Learning it. I'll tell you what went in."
        if action == "wiki_ask":
            return self.ask_fg(ask_prompt(arg, root))
        if action == "cards":
            self.start_job("flashcards on " + arg, cards_prompt(arg, root))
            return f"Making flashcards on {arg}."
        if action == "quiz":
            return self.ask_fg(quiz_prompt(arg, root))
        return None

    def inbox(self):
        """Files dropped in Wiki/Inbox get learned, then moved to Wiki/Sources so they're kept."""
        box = self.vault.path(f"{WIKI}/Inbox")
        os.makedirs(box, exist_ok=True)
        done = self.vault.path(f"{WIKI}/Sources")
        for f in sorted(os.listdir(box)):
            p = os.path.join(box, f)
            if os.path.isfile(p) and not f.startswith(".") and time.time() - os.path.getmtime(p) > 30:
                os.makedirs(done, exist_ok=True)
                dst = os.path.join(done, f)
                shutil.move(p, dst)
                self.start_job("learn " + f, learn_prompt("file", dst, self.vault.root))
                self.log(f"learn: filing {f}")

    def lint_prompt(self):
        return (RULES + f"\n\nNightly upkeep of {os.path.join(self.vault.root, WIKI)}: fix broken [[links]] (point them at the "
                "right note or create a stub), link orphan notes from Index.md or a related note, add missing summaries "
                f"and frontmatter. Write what you found and fixed to {WIKI}/Health.md (replace it). Reply with one sentence.")

    def watch(self, quiet_hours=(2, 5)):
        last_lint = ""
        while True:
            time.sleep(300)
            try:
                self.inbox()
                lt = time.localtime()
                day = time.strftime("%Y-%m-%d")
                if quiet_hours[0] <= lt.tm_hour <= quiet_hours[1] and last_lint != day and os.path.isdir(self.vault.path(WIKI)):
                    last_lint = day
                    self.start_job("wiki upkeep", self.lint_prompt(), quiet=True)
            except Exception as e:
                self.log(f"learn watch: {e}")


def route_learn(t):
    m = re.fullmatch(r"(?:learn|remember|save|file|study) (?:this|that)(?: link| page| article)?:? (https?://\S+|\S+\.(?:com|org|edu|io|ai|net|dev)\S*)", t)
    if m:
        u = m.group(1)
        return ("learn", ("url", u if u.startswith("http") else "https://" + u))
    if re.fullmatch(r"(?:learn|read and learn|study|save to (?:my )?wiki|file) (?:what'?s|what is) on (?:my |the )?screen|learn (?:this|that) (?:page|article|doc|chat)", t):
        return ("learn", ("screen", ""))
    if re.fullmatch(r"(?:learn|file|save to (?:my )?wiki) (?:my |the |what'?s (?:in|on) my )?clipboard|learn what i (?:just )?copied", t):
        return ("learn", ("clipboard", ""))
    m = re.fullmatch(r"learn (?:this|that):? (.{12,})", t)
    if m and not m.group(1).startswith(("page", "article", "doc", "chat")):
        return ("learn", ("text", m.group(1)))
    m = re.fullmatch(r"what does my (?:wiki|notes?|second brain) say about (.+)|what do i know about (.+)|"
                     r"(?:check|search) my wiki (?:for|about) (.+)", t)
    if m and (m.group(1) or m.group(2) or m.group(3)) not in ("me", "myself"):
        return ("wiki_ask", next(g for g in m.groups() if g))
    m = re.fullmatch(r"(?:make|create|build|write) (?:me )?(?:some )?flash ?cards (?:on|about|for) (.+)", t)
    if m:
        return ("cards", m.group(1))
    m = re.fullmatch(r"quiz me(?: on| about)? (.+)|test me on (.+)|let'?s (?:study|review) (.+)", t)
    if m:
        return ("quiz", next(g for g in m.groups() if g))
    return None
