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


def route_claude(t):
    """t is the already normalized lowercase line. Returns (action, arg) or None."""
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
