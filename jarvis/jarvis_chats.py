"""
Your claude.ai chats, searchable by voice.

claude.ai has no way for a program to read your chats live, but it lets you download all of them: Settings,
Privacy, Export data. You get an email with a link to a zip. Download it and Atlas does the rest:

  - it notices the zip in your Downloads folder (checks every few minutes) and imports every chat
  - each chat becomes a note in your vault, Claude/Chats/<date> <title>.md, so Obsidian and Atlas can both read them
  - "what did I ask Claude about the Babson essay"      finds the chats and answers from them
  - "search my Claude chats for supabase"               same, out loud
  - "what were my last Claude chats about"              the newest few
  - "import my Claude chats"                            imports the newest export right now
  - "how do I export my Claude chats"                   opens the export page and says what to click
  - after an import it also keeps the lasting facts from your newest chats in Memory.md

Export again whenever you want it up to date (once a week is plenty). Nothing leaves your PC.
"""

import glob
import json
import os
import re
import time
import zipfile

HERE = os.path.dirname(os.path.abspath(__file__))
INDEX = os.path.join(HERE, ".cache", "claude_chats.json")
STATE = os.path.join(HERE, ".cache", "claude_chats_state.json")
VAULT_FOLDER = "Claude/Chats"
EXPORT_PAGE = "https://claude.ai/settings/data-privacy-controls"
STOP = set("the and for what did you about that this have with from were was are your our all any tell talk ask asked said "
           "claude chat chats my me i to of in on a an it is".split())


def _log(msg):
    print(time.strftime("[%H:%M:%S] ") + "chats: " + str(msg), flush=True)


def downloads_dir():
    return os.path.join(os.path.expanduser("~"), "Downloads")


def find_exports(folder=None):
    """Zips in Downloads that hold a claude.ai export (they contain conversations.json), newest first."""
    out = []
    for z in glob.glob(os.path.join(folder or downloads_dir(), "*.zip")):
        try:
            if os.path.getsize(z) > 2_000_000_000:
                continue
            with zipfile.ZipFile(z) as zf:
                if any(n.endswith("conversations.json") for n in zf.namelist()):
                    out.append(z)
        except Exception:
            continue
    return sorted(out, key=os.path.getmtime, reverse=True)


def _msg_text(m):
    t = m.get("text") or ""
    if not t and isinstance(m.get("content"), list):
        t = "\n".join(c.get("text", "") for c in m["content"] if isinstance(c, dict) and c.get("type") == "text")
    return t.strip()


def parse_export(path):
    """[{id, title, created, updated, messages: [(who, text)]}] from an export zip or a conversations.json."""
    if path.endswith(".zip"):
        with zipfile.ZipFile(path) as zf:
            name = next(n for n in zf.namelist() if n.endswith("conversations.json"))
            data = json.loads(zf.read(name).decode("utf-8"))
    else:
        with open(path, encoding="utf-8") as f:
            data = json.load(f)
    chats = []
    for c in data if isinstance(data, list) else data.get("conversations", []):
        msgs = [("you" if m.get("sender") == "human" else "claude", _msg_text(m)) for m in c.get("chat_messages") or []]
        msgs = [(w, t) for w, t in msgs if t]
        if not msgs:
            continue
        chats.append({"id": c.get("uuid", ""), "title": (c.get("name") or msgs[0][1][:60]).strip() or "Untitled",
                      "created": c.get("created_at", ""), "updated": c.get("updated_at") or c.get("created_at", ""), "messages": msgs})
    chats.sort(key=lambda c: c["updated"], reverse=True)
    return chats


def _safe(name):
    return re.sub(r"[\\/:*?\"<>|#^\[\]]+", " ", name).strip()[:80] or "Untitled"


def write_vault(chats, vault):
    """One markdown note per chat. Rewrites only chats that changed."""
    n = 0
    for c in chats:
        day = (c["created"] or "")[:10] or "undated"
        rel = f"{VAULT_FOLDER}/{day} {_safe(c['title'])}.md"
        body = (f"# {c['title']}\n\nclaude.ai chat, started {day}, last message {(c['updated'] or '')[:10]}. "
                f"[Open](https://claude.ai/chat/{c['id']})\n\n" +
                "\n\n".join(f"**{'You' if w == 'you' else 'Claude'}:** {t}" for w, t in c["messages"]) + "\n")
        p = vault.path(rel)
        try:
            if os.path.exists(p) and open(p, encoding="utf-8").read() == body:
                continue
        except Exception:
            pass
        vault._write(rel, body, "w")
        n += 1
    return n


def save_index(chats):
    os.makedirs(os.path.dirname(INDEX), exist_ok=True)
    with open(INDEX, "w", encoding="utf-8") as f:
        json.dump(chats, f)


def load_index():
    try:
        with open(INDEX, encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return []


def search(chats, query, n=4):
    """Best matching chats for some spoken words: title hits count triple. [(score, chat, best excerpt)]."""
    words = [w for w in re.findall(r"[a-z0-9']+", query.lower()) if len(w) > 2 and w not in STOP]
    if not words:
        return []
    out = []
    for c in chats:
        title = c["title"].lower()
        score, best, best_s = 0, "", 0
        for w in words:
            if w in title:
                score += 3
        for who, t in c["messages"]:
            low = t.lower()
            s = sum(1 for w in words if w in low)
            score += min(s, 3) * 0.5
            if s > best_s:
                best_s, best = s, t
        if score:
            out.append((score, c, best[:1500]))
    out.sort(key=lambda x: (x[0], x[1]["updated"]), reverse=True)
    return out[:n]


class Chats:
    def __init__(self, say, ask, vault=None, remember=None, open_url=None):
        self.say, self.ask, self.vault, self.remember, self.open_url = say, ask, vault, remember, open_url

    def _state(self):
        try:
            with open(STATE) as f:
                return json.load(f)
        except Exception:
            return {}

    def import_latest(self, quiet=False, force=False):
        zips = find_exports()
        if not zips:
            if not quiet:
                self.guide()
            return 0
        z, st = zips[0], self._state()
        stamp = f"{os.path.basename(z)}|{os.path.getmtime(z)}"
        if st.get("imported") == stamp and not force:
            if not quiet:
                self.say(f"Your newest export is already in. {len(load_index())} chats. Export again on claude.ai for newer ones.")
            return 0
        chats = parse_export(z)
        save_index(chats)
        wrote = write_vault(chats, self.vault) if self.vault else 0
        with open(STATE, "w") as f:
            json.dump({"imported": stamp, "at": time.time(), "count": len(chats)}, f)
        _log(f"imported {len(chats)} chats from {os.path.basename(z)} ({wrote} notes written)")
        self.say(f"Imported {len(chats)} Claude chats. Ask me about any of them.")
        self.learn(chats[:15])
        return len(chats)

    def learn(self, chats):
        """Lasting facts about Yash from his newest chats go in Memory.md, the same way spoken ones do."""
        if not self.remember or not chats:
            return
        text = "\n\n".join(f"Chat '{c['title']}' ({c['updated'][:10]}): " +
                           " | ".join(t[:300] for w, t in c["messages"] if w == "you")[:900] for c in chats)
        out = self.ask("These are the questions Yash asked Claude in his newest claude.ai chats. List only lasting facts about "
                       "him worth remembering for weeks (plans, deadlines, projects, decisions, people, preferences), one per "
                       "line starting with '- ', at most 6, third person. If nothing lasting, reply NONE.\n\n" + text[-9000:])
        for line in (out or "").splitlines():
            if line.strip().startswith("- "):
                self.remember(line.strip()[2:] + " (from his Claude chats)")

    def guide(self):
        if self.open_url:
            self.open_url(EXPORT_PAGE)
        self.say("I opened the export page. Click Export data. Claude emails you a link, download the zip, "
                 "and I'll pick it up from your Downloads folder by myself.")

    def answer(self, query):
        chats = load_index()
        if not chats:
            self.say("I haven't seen your Claude chats yet.")
            return self.guide()
        hits = search(chats, query)
        if not hits:
            return self.say(f"Nothing in your Claude chats about {query}.")
        ctx = "\n\n".join(f"Chat '{c['title']}', {c['updated'][:10]}:\n" + "\n".join(
            f"{'Yash' if w == 'you' else 'Claude'}: {t[:700]}" for w, t in c["messages"][:6]) + f"\nMost relevant part: {ex}"
            for _, c, ex in hits)
        self.say(self.ask(f"Yash asks about his past claude.ai chats: '{query}'. Answer out loud in under 70 words from these "
                          f"chats, saying roughly when. If they don't answer it, say what they do cover.\n\n{ctx[-12000:]}"))

    def recent(self, n=4):
        chats = load_index()
        if not chats:
            self.say("I haven't seen your Claude chats yet.")
            return self.guide()
        self.say("Your newest Claude chats: " + "; ".join(f"{c['title']}, {c['updated'][:10]}" for c in chats[:n]) + ".")

    def watch(self):
        """Picks up a new export from Downloads on its own."""
        while True:
            time.sleep(240)
            try:
                self.import_latest(quiet=True)
            except Exception as e:
                _log(f"watch: {e}")

    def handle(self, action, arg):
        if action == "chats_search":
            self.answer(arg)
        elif action == "chats_recent":
            self.recent()
        elif action == "chats_import":
            self.import_latest(force=True)
        elif action == "chats_guide":
            self.guide()


def route_chats(t):
    m = re.fullmatch(r"what (?:did|have) i (?:ask|asked|tell|told|talk to|talked to|say to|said to) claude about (.+)|"
                     r"(?:search|check|look through|look in) (?:my )?(?:claude )?chats (?:for|about) (.+)|"
                     r"did i (?:ever )?(?:ask|talk to) claude about (.+)|what did claude (?:say|tell me) about (.+)|"
                     r"find (?:my |the )?(?:claude )?chat (?:about|where i asked about) (.+)", t)
    if m:
        return ("chats_search", next(g for g in m.groups() if g))
    if re.fullmatch(r"what (?:were|are|was) my (?:last|latest|recent|newest) (?:few )?claude chats?(?: about)?|"
                    r"(?:list|read) my (?:recent |latest )?claude chats", t):
        return ("chats_recent", None)
    if re.fullmatch(r"(?:import|load|sync|update|refresh) my (?:claude )?chats", t):
        return ("chats_import", None)
    if re.fullmatch(r"how do i (?:export|download|get) my (?:claude )?chats(?: to you| in)?|export my (?:claude )?chats", t):
        return ("chats_guide", None)
    return None
