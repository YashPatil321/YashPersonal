"""
Voice control for Claude: Claude Code sessions, background questions, claude.ai chats.

What Jarvis can do here (all from an allow list, nothing destructive):
  "open claude code in hq"              new terminal tab, Claude Code in that project
  "continue my jarvis session"          reopens the last Claude Code conversation in that project
  "tell claude in hq to fix the footer" new tab, Claude Code starts on that task (you watch and approve)
  "ask hq what's left on the todo list" Claude reads that project (read only) and answers out loud
  "what was I working on"               reads your most recent Claude Code sessions
  "new claude chat about college essays" opens claude.ai with your words typed in
  "open claude", "open cowork"          opens the Claude desktop app
  "open claude code on the web"         opens claude.ai/code (your cloud sessions)

Cloud (Claude Code on the web, runs on Anthropic's machines even with your PC off):
  "start a cloud session on solidhauz to fix the quote page"   claude --cloud in that project
  "tell the cloud session to also add tests"                    follow up to the last one (or name it)
  "what cloud sessions did you start"                           the ones Atlas started, newest first
  "pull down the solidhauz cloud session"                       claude --teleport in a terminal
  "turn on remote control for hq"                               drive a local session from your phone
  "open my claude chats"                                        claude.ai/recents (chats have no API to read)

Projects are found automatically from your Claude Code history (every folder you've used claude in).
Add nicknames in PROJECT_ALIASES.
"""

import glob
import json
import os
import re
import subprocess
import sys
import time
import urllib.parse

IS_WIN = sys.platform == "win32"
CLAUDE_HOME = os.path.join(os.path.expanduser("~"), ".claude")

# spoken nickname -> folder. Anything here wins over auto discovery.
PROJECT_ALIASES = {
    "jarvis": r"C:\jarvis",
    # "hq": r"C:\code\yash-hq",
    # "solidhauz": r"C:\code\SolidHauzWeb",
}


def _spoken(name):
    """Folder name -> how you'd say it: 'SolidHauzWeb' -> 'solid hauz web', 'ocs_backend' -> 'ocs backend'."""
    s = re.sub(r"([a-z])([A-Z])", r"\1 \2", os.path.basename(name.rstrip("\\/")))
    return re.sub(r"[\W_]+", " ", s).strip().lower()


def discover_projects(home=CLAUDE_HOME):
    """Every folder Claude Code has run in, newest first, read from the 'cwd' in its session files."""
    found = {}
    for f in glob.glob(os.path.join(home, "projects", "*", "*.jsonl")):
        try:
            mt = os.path.getmtime(f)
            with open(f, encoding="utf-8", errors="ignore") as fh:
                for _, line in zip(range(40), fh):
                    cwd = json.loads(line).get("cwd")
                    if cwd:
                        if cwd not in found or found[cwd] < mt:
                            found[cwd] = mt
                        break
        except Exception:
            continue
    return [p for p, _ in sorted(found.items(), key=lambda x: -x[1])]


def project_index(home=CLAUDE_HOME):
    idx = {}
    for p in discover_projects(home):
        idx.setdefault(_spoken(p), p)
        idx.setdefault(_spoken(p).replace(" ", ""), p)
    for k, v in PROJECT_ALIASES.items():
        idx[k.lower()] = v
    return idx


def match_project(spoken, idx):
    """Best project for what you said: exact, then squashed, then 'starts with', then 'contains'."""
    s = re.sub(r"^(the|my)\s+", "", spoken.lower().strip())
    s = re.sub(r"\s+(project|repo|folder|session)$", "", s)
    if not s:
        return None
    for key in (s, s.replace(" ", "")):
        if key in idx:
            return idx[key]
    for k, v in idx.items():
        if k.startswith(s) or s.startswith(k):
            return v
    for k, v in idx.items():
        if s in k:
            return v
    return None


def clean_task(text):
    """Keep only plain words and light punctuation, so a task can never become a shell command."""
    t = re.sub(r"[^A-Za-z0-9 ,.?'!]", " ", text)
    return re.sub(r"\s+", " ", t).strip()[:400]


CLOUD_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), ".cloud_sessions.json")
URL_RE = re.compile(r"https://claude\.ai/code/[\w\-/]+")
ID_RE = re.compile(r"\b(session_[A-Za-z0-9]+|cse_[A-Za-z0-9]+)\b")


def load_cloud():
    try:
        with open(CLOUD_FILE, encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return []


def save_cloud(rows):
    with open(CLOUD_FILE, "w", encoding="utf-8") as f:
        json.dump(rows[-40:], f, indent=1)


def pick_cloud(rows, name=None):
    """The session that best matches a spoken name (project or task words), else the newest."""
    if not rows:
        return None
    if not name:
        return rows[-1]
    words = [w for w in re.findall(r"[a-z0-9]+", name.lower()) if w not in ("the", "my", "session", "cloud", "last", "latest")]
    if not words:
        return rows[-1]
    scored = [(sum(w in (r.get("project", "") + " " + r.get("task", "")).lower() for w in words), i, r) for i, r in enumerate(rows)]
    best = max(scored, key=lambda x: (x[0], x[1]))
    return best[2] if best[0] else None


def route_cloud(t):
    m = re.fullmatch(r"(?:start|kick off|launch|spin up|open|make|create) (?:a |an )?(?:new )?(?:cloud|web|remote) (?:claude )?(?:code )?(?:session|task|agent)"
                     r" (?:in|on|for) (.+?) (?:to|that|and|which) (.+)", t) \
        or re.fullmatch(r"(?:have|get|tell) (?:a )?(?:cloud |web )?claude (?:in the cloud |on the web )?(?:to )?(.+?) (?:to|and) (.+?) in the cloud", t)
    if m:
        return ("cloud_new", (m.group(1), m.group(2)))
    m = re.fullmatch(r"(?:in the cloud|on the web),? (?:have claude |tell claude to )?(.+) (?:in|on|for) (?:the )?(\w+(?: \w+)?)(?: project| repo)?", t)
    if m:
        return ("cloud_new", (m.group(2), m.group(1)))
    m = re.fullmatch(r"(?:tell|message|send|ask) (?:the |my )?(?:last |latest |newest )?(?:(.+?) )?cloud session (?:to |that |this )?(.+)", t)
    if m:
        return ("cloud_send", (m.group(1), m.group(2)))
    if re.fullmatch(r"(?:what|which) cloud sessions (?:did you start|are (?:running|going|there))|(?:list|show) (?:my |the )?cloud sessions|my cloud sessions", t):
        return ("cloud_list", None)
    m = re.fullmatch(r"(?:pull|bring) (?:down |back )?(?:the |my )?(?:last |latest )?(?:(.+?) )?cloud session(?: down| here| back)?|teleport (?:the |my )?(?:last )?(.+?)?(?: cloud)? session", t)
    if m:
        return ("cloud_pull", m.group(1) or m.group(2))
    m = re.fullmatch(r"(?:turn on|start|enable) remote control (?:for|in|on) (.+)|let me (?:control|drive) (.+?) from my phone", t)
    if m:
        return ("cc_remote", m.group(1) or m.group(2))
    if re.fullmatch(r"(?:open|show)(?: me)? my (?:claude )?(?:chats|chat history|conversations)|open claude (?:history|recents|chats)", t):
        return ("chats_open", None)
    return None


def route_claude(t):
    """t is the already normalized lowercase line. Returns (action, arg) or None."""
    r = route_cloud(t)
    if r:
        return r
    if re.fullmatch(r"open claude code on the web|open (?:my )?cloud sessions|open claude code web", t):
        return ("cc_web", None)
    m = re.fullmatch(r"(?:open|start|launch) (?:a )?(?:new )?claude code(?: session)? (?:in|for|on) (.+)", t) \
        or re.fullmatch(r"(?:open|start) (.+?) in claude code", t)
    if m:
        return ("cc_open", m.group(1))
    m = re.fullmatch(r"(?:continue|resume|pick up|reopen) (?:my |the )?(?:last )?(.+?) (?:session|chat|conversation)", t) \
        or re.fullmatch(r"(?:continue|resume) (?:working on |work on )?(.+?)(?: in claude code)?", t)
    if m and m.group(1) not in ("the", "my", "last") and not re.search(r"\b(music|song|spotify|playing|track|playback)\b", m.group(1)):
        return ("cc_continue", m.group(1))
    m = re.fullmatch(r"(?:tell|have|get) claude(?: code)? (?:in|on|for) (.+?) (?:to )?(.+)", t)
    if m:
        return ("cc_task", (m.group(1), m.group(2)))
    m = re.fullmatch(r"(?:ask|check) (.+?) (?:project )?((?:what|whether|if|how|where|which|why|is|are|does|do)\b.*)", t)
    if m and not re.search(r"\b(weather|time|day|calendar|email|mail)\b", m.group(1)):
        return ("cc_ask", (m.group(1), m.group(2)))
    if re.search(r"\bwhat (was|am) i working on\b|\b(list|what are) my (claude code |recent )?sessions\b", t):
        return ("cc_recent", None)
    m = re.fullmatch(r"(?:new|start a|open a|start a new) claude chat(?: about| on| for)? ?(.*)", t)
    if m:
        return ("chat_new", m.group(1))
    if re.fullmatch(r"open (?:the )?claude(?: app| desktop)?|open cowork|start (?:a )?cowork(?: chat| session)?", t):
        return ("claude_app", None)
    return None


def recent_sessions(home=CLAUDE_HOME, n=3):
    """Newest Claude Code sessions: project and the first thing you asked."""
    files = sorted(glob.glob(os.path.join(home, "projects", "*", "*.jsonl")), key=os.path.getmtime, reverse=True)[:n]
    out = []
    for f in files:
        cwd, first = None, None
        try:
            with open(f, encoding="utf-8", errors="ignore") as fh:
                for _, line in zip(range(200), fh):
                    d = json.loads(line)
                    cwd = cwd or d.get("cwd")
                    msg = d.get("message") or {}
                    if not first and d.get("type") == "user" and msg.get("role") == "user":
                        c = msg.get("content")
                        text = c if isinstance(c, str) else " ".join(x.get("text", "") for x in c if isinstance(x, dict) and x.get("type") == "text")
                        if text and not text.startswith("<"):
                            first = text
                    if cwd and first:
                        break
        except Exception:
            continue
        out.append({"project": _spoken(cwd or f), "path": cwd, "first": (first or "").strip()[:90],
                    "ago_min": int((time.time() - os.path.getmtime(f)) / 60)})
    return out


def _ago(m):
    return f"{m} minutes ago" if m < 60 else f"{m // 60} hours ago" if m < 1440 else f"{m // 1440} days ago"


class ClaudeControl:
    def __init__(self, say, pc, claude_bin, home=CLAUDE_HOME, runner=None):
        self.say, self.pc, self.claude, self.home = say, pc, claude_bin, home
        self.run = runner or self._terminal

    def _terminal(self, folder, args, title):
        """New Windows Terminal tab in that folder. Falls back to a plain console window."""
        if not IS_WIN:
            print("[terminal]", folder, args)
            return
        if os.path.exists(os.path.expandvars(r"%LOCALAPPDATA%\Microsoft\WindowsApps\wt.exe")):
            subprocess.Popen(["wt", "-w", "0", "nt", "--title", title, "-d", folder, "cmd", "/k", self.claude] + args)
        else:
            subprocess.Popen(["cmd", "/c", "start", title, "/d", folder, "cmd", "/k", self.claude] + args)

    def _project(self, spoken):
        p = match_project(spoken, project_index(self.home))
        if not p or not os.path.isdir(p):
            self.say(f"I don't know a project called {spoken}.")
            return None
        return p

    def handle(self, action, arg):
        if action.startswith("cloud_") or action in ("cc_remote", "chats_open"):
            return self.handle_cloud(action, arg)
        if action == "cc_open":
            p = self._project(arg)
            if p:
                self.run(p, [], "Claude " + _spoken(p))
                self.say(f"Claude Code is open in {_spoken(p)}.")
        elif action == "cc_continue":
            p = self._project(arg)
            if p:
                self.run(p, ["--continue"], "Claude " + _spoken(p))
                self.say(f"Picking up where you left off in {_spoken(p)}.")
        elif action == "cc_task":
            name, task = arg
            p, task = self._project(name), clean_task(task)
            if p and task:
                self.run(p, [task], "Claude " + _spoken(p))
                self.say(f"Claude is on it in {_spoken(p)}. Check the terminal to approve changes.")
        elif action == "cc_ask":
            name, q = arg
            p = self._project(name)
            if p:
                self.say("Checking.")
                self.say(self.ask_readonly(p, clean_task(q)))
        elif action == "cc_recent":
            rs = recent_sessions(self.home)
            if not rs:
                self.say("I don't see any Claude Code sessions yet.")
            else:
                self.say(" ".join(f"{r['project']}, {_ago(r['ago_min'])}" + (f": {r['first']}." if r['first'] else ".") for r in rs))
        elif action == "chat_new":
            q = clean_task(arg)
            self.pc.open_url("https://claude.ai/new" + ("?q=" + urllib.parse.quote(q) if q else ""))
            self.say("New Claude chat is open." + (" Your question is typed in." if q else ""))
        elif action == "claude_app":
            exe = os.path.expandvars(r"%LOCALAPPDATA%\AnthropicClaude\claude.exe")
            if IS_WIN and os.path.exists(exe):
                subprocess.Popen([exe])
            else:
                self.pc.open_url("https://claude.ai")
            self.say("Opening Claude.")
        elif action == "cc_web":
            self.pc.open_url("https://claude.ai/code")
            self.say("Opening your cloud sessions.")

    # ---- cloud ----
    def _cli(self, args, folder, stdin_text=None, timeout=180):
        return subprocess.run([self.claude] + args, cwd=folder, input=stdin_text if stdin_text is not None else "",
                              capture_output=True, text=True, encoding="utf-8", timeout=timeout,
                              creationflags=0x08000000 if IS_WIN else 0)

    def cloud_new(self, spoken, task):
        p = self._project(spoken)
        task = clean_task(task)
        if not p or not task:
            return
        self.say(f"Starting a cloud session on {_spoken(p)}.")
        try:
            r = self._cli(["--cloud", task], p)
            out = (r.stdout or "") + (r.stderr or "")
        except Exception as e:
            out, r = str(e), None
        url, sid = URL_RE.search(out), ID_RE.search(out)
        if url or sid:
            rows = load_cloud()
            rows.append({"id": sid.group(1) if sid else url.group(0).rstrip("/").rsplit("/", 1)[-1], "url": url.group(0) if url else "",
                         "project": _spoken(p), "folder": p, "task": task, "t": time.time()})
            save_cloud(rows)
            self.say(f"It's running in the cloud. It keeps going even if your PC is off. Say tell the cloud session, to add to it.")
        elif r is not None and r.returncode == 0:
            self.say("It started, but I couldn't read its link back. It's on claude.ai under Code.")
            self.pc.open_url("https://claude.ai/code")
        else:
            # it needs the project on GitHub and Claude Code logged in with your claude.ai account
            last = out.strip().splitlines()[-1][:140] if out.strip() else "no answer from Claude Code"
            self.say("The cloud session didn't start. " + last)

    def cloud_send(self, name, msg):
        s = pick_cloud(load_cloud(), name)
        msg = clean_task(msg)
        if not s:
            return False
        r = self._cli(["-p", "--cloud", s["id"], "--output-format", "json"], s.get("folder") or os.getcwd(), stdin_text=msg, timeout=90)
        try:
            ok = json.loads(r.stdout).get("ok")
        except Exception:
            ok = False
        self.say(f"Sent to the {s['project']} session." if ok else "That didn't go through. " + (r.stderr or "").strip()[:120])
        return True

    def cloud_list(self):
        rows = load_cloud()[-5:][::-1]
        if not rows:
            self.say("I haven't started any cloud sessions yet. Opening the list on claude.ai.")
        else:
            now = time.time()
            self.say("Newest first: " + "; ".join(f"{r['project']}, {_ago(int((now - r['t']) / 60))}, {r['task'][:60]}" for r in rows)
                     + ". Opening them on claude.ai so you can see where each one is.")
        self.pc.open_url("https://claude.ai/code")

    def handle_cloud(self, action, arg):
        if action == "cloud_new":
            self.cloud_new(*arg)
        elif action == "cloud_send":
            if not self.cloud_send(*arg):
                return False   # not one Atlas started: let the connector path try
        elif action == "cloud_list":
            self.cloud_list()
        elif action == "cloud_pull":
            s = pick_cloud(load_cloud(), arg)
            if not s:
                self.say("I don't know that session. Opening the picker.")
                self.run(os.path.expanduser("~"), ["--teleport"], "Teleport")
            else:
                self.run(s.get("folder") or os.path.expanduser("~"), ["--teleport", s["id"]], "Teleport " + s["project"])
                self.say(f"Pulling the {s['project']} session into a terminal.")
        elif action == "cc_remote":
            p = self._project(arg)
            if p:
                self.run(p, ["--remote-control", _spoken(p)], "Remote " + _spoken(p))
                self.say(f"Remote control is on for {_spoken(p)}. Open the Claude app on your phone to drive it.")
        elif action == "chats_open":
            self.pc.open_url("https://claude.ai/recents")
            self.say("Your Claude chats are open. I can read what's on screen if you ask.")
        return True

    def ask_readonly(self, folder, question):
        """Claude Code reads the project (no edits, no commands) and answers in spoken style."""
        r = subprocess.run([self.claude, "-p", "--output-format", "json", "--allowedTools", "Read,Grep,Glob",
                            "--append-system-prompt", "Answer in two or three plain spoken sentences. No markdown, no lists, no code."],
                           cwd=folder, input=question, capture_output=True, text=True, encoding="utf-8", timeout=240,
                           creationflags=0x08000000 if IS_WIN else 0)
        try:
            return json.loads(r.stdout).get("result") or "No answer came back."
        except Exception:
            return "I couldn't get an answer from that project."
