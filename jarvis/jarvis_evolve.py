"""
Atlas keeps getting better on its own.

  Lessons     when you correct it ("no, I said...", "that's wrong", "you misheard"), it writes down what it got wrong
              in Jarvis/Lessons.md and reads that before every answer. Misheard names go into its speech vocabulary.
  Nightly     around 3 AM, if you're not using the PC, it reads its own log from the last day (failures, things it
              couldn't do, your corrections), picks one or two real problems, and fixes its own code with Claude Code.
              New features go in mods/. You hear what changed the next time it says hi, and it's in Jarvis/Changelog.md.
  On demand   "improve yourself", "work on your swipe detection", "get better at playing music"
  Safety      every change is backed up first. Code that doesn't compile is put back right away. If Atlas can't
              start after a change (crashes three times in a row), the next start puts the old code back by itself.
              "undo your last change" puts it back by voice. "what did you change" / "what have you learned".
"""

import glob
import json
import os
import re
import shutil
import subprocess
import sys
import threading
import time

HERE = os.path.dirname(os.path.abspath(__file__))
BACKUPS = os.path.join(HERE, ".cache", "selfedit")
PENDING = os.path.join(HERE, ".selfedit_pending.json")     # a change that hasn't proven it starts yet
REVERTED = os.path.join(HERE, ".selfedit_reverted.json")   # the boot guard put old code back
STATE = os.path.join(HERE, ".evolve_state.json")

# ---------------- settings (override in local_settings.py) ----------------
EVOLVE = True                # nightly self improvement
EVOLVE_HOUR = 3              # around this hour, when you've been away 30 minutes or more
EVOLVE_MODEL = "opus"        # the model that edits the code: the strongest one, it's not in a hurry
LEARN_FROM_CORRECTIONS = True
# ---------------------------------------------------------------------------

CORRECTION = re.compile(r"^(?:no+[,.]?\s+)?(?:i (?:said|meant|asked)|that'?s (?:wrong|not (?:it|what i (?:said|meant|asked)|right))|"
                        r"you (?:misheard|heard (?:me )?wrong|got (?:it|that) wrong)|wrong (?:one|song|app|thing|window|tab)|"
                        r"not that(?: one)?|i didn'?t (?:say|ask|mean)|why did you|that'?s not what)\b", re.I)


def _log(msg):
    print(time.strftime("[%H:%M:%S] ") + "evolve: " + str(msg), flush=True)


def code_files():
    out = [os.path.join(HERE, f) for f in os.listdir(HERE) if (f.startswith("jarvis") and f.endswith(".py")) or f == "local_settings.py"]
    mods = os.path.join(HERE, "mods")
    if os.path.isdir(mods):
        out += [os.path.join(mods, f) for f in os.listdir(mods) if f.endswith(".py")]
    return out


# ---------------- backups and the boot guard ----------------
def _stamp():
    """A folder name that sorts by time and never repeats, even twice in one second."""
    base, n = time.strftime("%Y%m%d-%H%M%S"), 0
    while os.path.exists(os.path.join(BACKUPS, f"{base}-{n:02d}")):
        n += 1
    return f"{base}-{n:02d}"


def backup(why=""):
    """Copies all of Atlas's code to .cache/selfedit/<time>/. Returns that folder."""
    stamp = _stamp()
    dst = os.path.join(BACKUPS, stamp)
    for p in code_files():
        rel = os.path.relpath(p, HERE)
        os.makedirs(os.path.dirname(os.path.join(dst, rel)), exist_ok=True)
        shutil.copy2(p, os.path.join(dst, rel))
    with open(os.path.join(dst, "_why.txt"), "w", encoding="utf-8") as f:
        f.write(why)
    olds = sorted(glob.glob(os.path.join(BACKUPS, "*")))
    for o in olds[:-15]:   # keep the last 15
        shutil.rmtree(o, ignore_errors=True)
    return dst


def backup_snapshot(snap, why=""):
    """A backup made from file contents captured earlier (before a conversation edited the code)."""
    stamp = _stamp()
    dst = os.path.join(BACKUPS, stamp)
    for p, data in snap.items():
        rel = os.path.relpath(p, HERE)
        os.makedirs(os.path.dirname(os.path.join(dst, rel)), exist_ok=True)
        with open(os.path.join(dst, rel), "wb") as f:
            f.write(data)
    with open(os.path.join(dst, "_why.txt"), "w", encoding="utf-8") as f:
        f.write(why)
    return dst


def restore(folder=None):
    """Puts a backup back (the newest if none given). Files that didn't exist then are removed. Returns the folder."""
    folders = sorted(glob.glob(os.path.join(BACKUPS, "*")))
    folder = folder or (folders[-1] if folders else None)
    if not folder or not os.path.isdir(folder):
        return None
    keep = set()
    for root, _, files in os.walk(folder):
        for f in files:
            if f == "_why.txt":
                continue
            src = os.path.join(root, f)
            rel = os.path.relpath(src, folder)
            keep.add(os.path.normpath(os.path.join(HERE, rel)))
            os.makedirs(os.path.dirname(os.path.join(HERE, rel)), exist_ok=True)
            shutil.copy2(src, os.path.join(HERE, rel))
    for p in code_files():
        if os.path.normpath(p) not in keep and (os.path.basename(p) != "local_settings.py"):
            try:
                os.remove(p)   # a file the change added
            except OSError:
                pass
    return folder


def mark_pending(folder, summary):
    with open(PENDING, "w") as f:
        json.dump({"backup": folder, "summary": summary, "boots": 0, "t": time.time()}, f)


def boot_guard():
    """Run by update.py before every start. A change that keeps Atlas from starting gets undone by itself."""
    try:
        with open(PENDING) as f:
            p = json.load(f)
    except Exception:
        return None
    p["boots"] = p.get("boots", 0) + 1
    if p["boots"] >= 3:
        restore(p.get("backup"))
        os.remove(PENDING)
        with open(REVERTED, "w") as f:
            json.dump({"summary": p.get("summary", ""), "t": time.time()}, f)
        print("evolve: my last change kept me from starting, so I put the old code back")
        return "reverted"
    with open(PENDING, "w") as f:
        json.dump(p, f)
    return "watching"


def confirm_boot():
    """Called once Atlas has been up a couple of minutes: the change works."""
    try:
        os.remove(PENDING)
    except OSError:
        pass


# ---------------- what went wrong lately ----------------
SIGNALS = re.compile(r"failed|error|traceback|exception|couldn'?t|can'?t|didn'?t work|claude wanted to|not on the voice allow|"
                     r"streaming didn'?t|interrupted|i don'?t (?:have|know how)|isn'?t (?:on|set up|running)|no (?:camera|answer)|"
                     r"broke|undo|wrong|misheard", re.I)


def recent_signals(log_file, hours=26, limit=80):
    """Lines from the log worth fixing, plus what you said right before each one."""
    cut = time.time() - hours * 3600
    lines = []
    for path in (log_file + ".old", log_file):
        try:
            with open(path, encoding="utf-8", errors="replace") as f:
                lines += f.readlines()
        except OSError:
            pass
    out, last_you = [], ""
    for ln in lines:
        try:
            t = time.mktime(time.strptime(ln[:19], "%Y-%m-%d %H:%M:%S"))
        except Exception:
            continue
        if t < cut:
            continue
        body = ln[20:].strip()
        if body.startswith("you:"):
            last_you = body
            if CORRECTION.search(body[4:].strip()):
                out.append(body)
            continue
        if SIGNALS.search(body):
            out.append((f"[after '{last_you[4:].strip()[:80]}'] " if last_you else "") + body[:300])
    seen, uniq = set(), []
    for o in out:
        k = re.sub(r"\d+", "#", o)[:120]
        if k not in seen:
            seen.add(k)
            uniq.append(o)
    return uniq[-limit:]


# ---------------- the improver ----------------
RULES = """You are improving Atlas, Yash's voice assistant, by editing its own code. You are running inside its folder.
Read README.md and the module docstrings first so you understand how it is put together.

Rules:
- Make at most two focused improvements. Small, safe, and clearly better beats big and clever.
- Fix root causes of the problems in the signals below. If a signal is noise, ignore it.
- Brand new abilities go in mods/<name>.py (route(t) returns (action, arg) or None for the lowercase spoken line,
  handle(jarvis, action, arg) does it). Edit the main jarvis*.py files only to fix real bugs.
- Never remove or weaken safety: rollback of broken edits, confirmations before sending messages or money,
  guest mode privacy, the face ID enrollment gate. Never touch credentials, tokens or anything in local_settings.py
  except plain settings. Never delete user data, notes or the vault.
- Keep the code style: plain Python, short comments in plain English, no hyphens or em dashes in anything spoken.
- After editing, run: python -m py_compile <each file you changed>   and   python -c "import jarvis"
  If either fails, fix it or undo your change.
- Finish with a reply that starts with CHANGES: and then one or two plain sentences Yash will hear out loud
  (what you improved, in his words, no file names), or NO CHANGES: and why."""


class Evolver:
    def __init__(self, claude_cmd, log_file, vault=None, say=None, news=None, restart=None, idle=None, ask=None, model=None):
        self.claude_cmd, self.log_file, self.vault, self.say = claude_cmd, log_file, vault, say
        self.news, self.restart, self.idle, self.ask = news, restart, idle, ask
        self.model = model or EVOLVE_MODEL
        self.busy = False

    # lessons
    def lessons(self, max_chars=1500):
        if not self.vault:
            return ""
        txt = self.vault.read("Jarvis/Lessons.md") or ""
        lines = [l for l in txt.splitlines() if l.startswith("- ")]
        return "\n".join(lines)[-max_chars:]

    def add_lesson(self, text):
        if not self.vault:
            return
        rel = "Jarvis/Lessons.md"
        if not os.path.exists(self.vault.path(rel)):
            self.vault._write(rel, "# What Atlas has learned\n\nMistakes it made and what you meant. It reads this before it answers. "
                                   "Delete lines freely.\n\n", "w")
        self.vault._write(rel, f"- {text.strip()} ({time.strftime('%b %d')})\n")

    def learn_from(self, said, before_you, before_atlas):
        """You just corrected Atlas. Work out the lesson in the background."""
        if not (LEARN_FROM_CORRECTIONS and self.ask and CORRECTION.search(said or "")):
            return False

        def work():
            out = self.ask(f"Yash is correcting his voice assistant Atlas.\nBefore, Yash said: \"{before_you}\"\nAtlas replied or did: "
                           f"\"{before_atlas}\"\nNow Yash says: \"{said}\"\n\nWrite ONE short lesson for Atlas to remember, like "
                           "'When Yash says X he means Y' or 'Speech recognition hears NAME as WRONG'. If it's a misheard word, "
                           "also add a second line starting with VOCAB: and just the correct word or name. If there's no real "
                           "lesson, reply NONE.")
            out = (out or "").strip()
            if not out or out.upper().startswith("NONE"):
                return
            for line in out.splitlines():
                line = line.strip(" -")
                if line.upper().startswith("VOCAB:"):
                    self.add_vocab(line[6:].strip())
                elif line:
                    self.add_lesson(line)
                    _log("learned: " + line)
        threading.Thread(target=work, daemon=True).start()
        return True

    def add_vocab(self, word):
        word = re.sub(r"[^\w' .-]", "", word).strip()
        if not word:
            return
        path = os.path.join(HERE, ".vocab_learned.txt")
        have = set(open(path, encoding="utf-8").read().split(", ")) if os.path.exists(path) else set()
        if word not in have:
            with open(path, "a", encoding="utf-8") as f:
                f.write((", " if have else "") + word)
            _log("new word for speech recognition: " + word)

    # improving the code
    def improve(self, goal=None, announce=True):
        if self.busy:
            if self.say and announce:
                self.say("I'm already working on myself.")
            return None
        self.busy = True
        try:
            return self._improve(goal, announce)
        finally:
            self.busy = False

    def _improve(self, goal, announce):
        signals = recent_signals(self.log_file)
        lessons = self.lessons()
        if not goal and not signals and not lessons:
            _log("nothing to work on")
            return None
        folder = backup("goal: " + (goal or "nightly"))
        before = {p: open(p, "rb").read() for p in code_files()}
        task = RULES + ("\n\nYash asked you to work on: " + goal if goal else "") + \
            "\n\nSignals from the last day (log lines, with what Yash said just before):\n" + ("\n".join(signals) or "(none)") + \
            "\n\nLessons from his corrections:\n" + (lessons or "(none)")
        cmd = self.claude_cmd + ["-p", "--output-format", "json", "--dangerously-skip-permissions", "--model", self.model,
                                 "--allowedTools", "Read,Edit,Write,MultiEdit,Glob,Grep,Bash"]
        _log("working on myself" + (": " + goal if goal else ""))
        try:
            r = subprocess.run(cmd, cwd=HERE, input=task, capture_output=True, text=True, encoding="utf-8", timeout=1800,
                               creationflags=0x08000000 if sys.platform == "win32" else 0)
            result = (json.loads(r.stdout).get("result") or "") if r.stdout.strip().startswith("{") else r.stdout
        except Exception as e:
            _log(f"improve failed: {e}")
            restore(folder)
            return None
        after = {p: open(p, "rb").read() for p in code_files()}
        changed = sorted(os.path.basename(p) for p in set(before) | set(after) if before.get(p) != after.get(p))
        if not changed:
            _log("no code changed: " + result[:200])
            return None
        ok, why = self.check()
        if not ok:
            restore(folder)
            _log(f"my change broke something ({why}), put the old code back")
            return None
        summary = re.sub(r"^(?:CHANGES|NO CHANGES):\s*", "", result.strip(), flags=re.I)[:400] or "Small fixes."
        for name in changed:
            if name.startswith("jarvis") and name.endswith(".py"):
                mark_local(name)
        mark_pending(folder, summary)
        self.changelog(summary, changed, goal)
        _log("improved: " + summary)
        if self.news is not None:
            self.news.append("I worked on myself: " + summary)
        if announce and self.say:
            self.say(summary + " Restarting to load it.")
        if self.restart:
            self.restart()
        return summary

    def check(self):
        """Everything compiles and Atlas still imports."""
        import py_compile
        for p in code_files():
            try:
                py_compile.compile(p, doraise=True)
            except py_compile.PyCompileError as e:
                return False, f"{os.path.basename(p)} doesn't compile: {str(e)[:120]}"
        try:
            r = subprocess.run([sys.executable, "-c", "import jarvis"], cwd=HERE, capture_output=True, text=True, timeout=180,
                               creationflags=0x08000000 if sys.platform == "win32" else 0)
            if r.returncode != 0:
                return False, "import failed: " + (r.stderr or "").strip().splitlines()[-1][:160] if r.stderr.strip() else "import failed"
        except Exception as e:
            return False, f"import check: {e}"
        return True, ""

    def changelog(self, summary, files, goal):
        if self.vault:
            rel = "Jarvis/Changelog.md"
            if not os.path.exists(self.vault.path(rel)):
                self.vault._write(rel, "# How Atlas changed itself\n\n", "w")
            self.vault._write(rel, f"- {time.strftime('%b %d %H:%M')}" + (f" (you asked: {goal})" if goal else " (overnight)") +
                              f": {summary} [{', '.join(files)}]\n")
        st = load_state()
        st.setdefault("changes", []).append({"t": time.time(), "summary": summary, "files": files, "goal": goal})
        st["changes"] = st["changes"][-30:]
        save_state(st)

    def undo(self):
        folder = restore()
        confirm_boot()
        if not folder:
            return None
        why = open(os.path.join(folder, "_why.txt"), encoding="utf-8").read() if os.path.exists(os.path.join(folder, "_why.txt")) else ""
        shutil.rmtree(folder, ignore_errors=True)   # so a second undo goes one further back
        self.changelog("Undid the last change, back to how it was.", [], "undo")
        return why

    def recap(self, n=3):
        ch = load_state().get("changes", [])[-n:][::-1]
        if not ch:
            return "I haven't changed my own code yet."
        return " ".join(f"{_ago(c['t'])}: {c['summary']}" for c in ch)

    # nightly
    def nightly(self):
        while True:
            time.sleep(600)
            try:
                if not EVOLVE:
                    continue
                lt, st = time.localtime(), load_state()
                today = time.strftime("%Y-%m-%d")
                if lt.tm_hour != EVOLVE_HOUR or st.get("night") == today:
                    continue
                if self.idle and self.idle() < 1800:
                    continue
                st["night"] = today
                save_state(st)
                self.improve(announce=False)
            except Exception as e:
                _log(f"nightly: {e}")


def _ago(t):
    m = int((time.time() - t) / 60)
    return f"{m} minutes ago" if m < 60 else f"{m // 60} hours ago" if m < 1440 else f"{m // 1440} days ago"


def mark_local(name):
    path = os.path.join(HERE, ".local_changes.json")
    try:
        names = set(json.load(open(path)))
    except Exception:
        names = set()
    names.add(name)
    json.dump(sorted(names), open(path, "w"))


def load_state():
    try:
        with open(STATE) as f:
            return json.load(f)
    except Exception:
        return {}


def save_state(st):
    with open(STATE, "w") as f:
        json.dump(st, f)


def route_evolve(t):
    m = re.fullmatch(r"(?:improve|upgrade|fix|update|work on) yourself(?: (?:on|with|so|by|to) (.+))?|get better at (.+)|"
                     r"(?:improve|work on|fix) your (.+)|make yourself better(?: at (.+))?", t)
    if m:
        goal = next((g for g in m.groups() if g), None)
        if goal and re.fullmatch(r"(?:code|self|software)", goal):
            goal = None
        return ("evolve", goal)
    if re.fullmatch(r"undo (?:your|that|the) (?:last )?(?:change|update|edit|improvement)|put (?:your|the) old code back|roll ?back(?: yourself)?", t):
        return ("evolve_undo", None)
    if re.fullmatch(r"what (?:did you|have you) (?:change|changed|improve|improved|fix|fixed)(?: (?:about |in )?yourself)?(?: lately| overnight| last night)?|"
                    r"what'?s new with you|what did you work on(?: last night)?", t):
        return ("evolve_recap", None)
    if re.fullmatch(r"what (?:have you|did you) learn(?:ed|t)?(?: lately| from me)?|what are your lessons", t):
        return ("evolve_lessons", None)
    return None
