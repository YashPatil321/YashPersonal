"""
Jarvis checks how it was started and fixes what would stop it from controlling your screen.

Runs once at every start (a second or two, in the background):
  1. Is Jarvis on your desktop? If Windows started it in the background session (session 0), it can't see or
     touch any window. That happens when a Task Scheduler task is set to "Run whether user is logged on or not".
  2. If a Jarvis task exists in Task Scheduler with that setting, it switches it to "Run only when user is
     logged on". Windows asks you once to allow it (a Yes/No prompt).
  3. Can it actually move a window? It nudges a window to the spot it's already in. If Windows says no,
     you hear why.
Problems go to jarvis.log and get said out loud once, so they never fail silently again.
"""

import csv
import io
import json
import os
import subprocess
import sys
import time

IS_WIN = sys.platform == "win32"
NO_WINDOW = 0x08000000 if IS_WIN else 0

AUTO_FIX_AUTOSTART = True    # fix a misconfigured Jarvis task in Task Scheduler (asks Windows for permission once)


def session_id():
    if not IS_WIN:
        return 1
    import ctypes
    from ctypes import wintypes
    sid = wintypes.DWORD()
    ctypes.windll.kernel32.ProcessIdToSessionId(ctypes.windll.kernel32.GetCurrentProcessId(), ctypes.byref(sid))
    return sid.value


def is_admin():
    if not IS_WIN:
        return False
    import ctypes
    try:
        return bool(ctypes.windll.shell32.IsUserAnAdmin())
    except Exception:
        return False


def parse_tasks(csv_text):
    """Rows from `schtasks /Query /FO CSV /V` that start Jarvis: [{name, run, logon_mode, run_level}]."""
    out, seen = [], set()
    for row in csv.DictReader(io.StringIO(csv_text)):
        run = (row.get("Task To Run") or "").strip()
        name = (row.get("TaskName") or "").strip()
        if not name or name == "TaskName" or name in seen:
            continue
        if "jarvis" in run.lower() or "jarvis" in name.lower():
            seen.add(name)
            out.append({"name": name, "run": run, "logon_mode": (row.get("Logon Mode") or "").strip()})
    return out


def jarvis_tasks():
    if not IS_WIN:
        return []
    try:
        r = subprocess.run(["schtasks", "/Query", "/FO", "CSV", "/V"], capture_output=True, text=True, timeout=30,
                           creationflags=NO_WINDOW, errors="ignore")
        return parse_tasks(r.stdout)
    except Exception:
        return []


def needs_fix(task):
    """True when the task can start Jarvis in the background session, where it can't touch the desktop."""
    mode = task["logon_mode"].lower()
    return bool(mode) and mode != "interactive only"


def startup_shortcut():
    """The Startup folder shortcut install.ps1 makes. When it exists, a Jarvis task is just a duplicate."""
    return os.path.exists(os.path.join(os.environ.get("APPDATA", ""), "Microsoft", "Windows", "Start Menu", "Programs", "Startup", "Jarvis.lnk"))


def task_args(name, delete):
    return ["/Delete", "/TN", name, "/F"] if delete else ["/Change", "/TN", name, "/IT"]


def fix_quietly(name, delete):
    """Your own task can usually be changed without asking."""
    try:
        r = subprocess.run(["schtasks"] + task_args(name, delete), capture_output=True, text=True, timeout=30, creationflags=NO_WINDOW)
        return r.returncode == 0
    except Exception:
        return False


def ask_windows(name, delete):
    """Shows Windows' Yes/No prompt. Jarvis runs minimized, and Windows won't pop a prompt over other apps for a
    minimized program, so bring the Jarvis window up first. Otherwise it only flashes a shield in the taskbar."""
    import ctypes
    k, u = ctypes.windll.kernel32, ctypes.windll.user32
    con = k.GetConsoleWindow()
    if con:
        u.ShowWindow(con, 9)
        u.SetForegroundWindow(con)
    args = " ".join(f'"{a}"' if " " in a or a.startswith("\\") else a for a in task_args(name, delete))
    return ctypes.windll.shell32.ShellExecuteW(con or None, "runas", "schtasks.exe", args, None, 0) > 32


def can_move_windows():
    """Nudges a normal window to where it already is. (ok, reason)"""
    if not IS_WIN:
        return True, ""
    import ctypes
    from ctypes import wintypes
    import jarvis_screen
    u, k = ctypes.windll.user32, ctypes.windll.kernel32
    for h, exe, title in jarvis_screen.Screen().windows():
        if not exe or exe in ("explorer.exe", "textinputhost.exe", "applicationframehost.exe") or u.IsIconic(h) or u.IsZoomed(h):
            continue
        r = wintypes.RECT()
        if not u.GetWindowRect(h, ctypes.byref(r)):
            continue
        ok = u.SetWindowPos(h, 0, r.left, r.top, r.right - r.left, r.bottom - r.top, 0x0004 | 0x0010)   # same spot, no z order, no activate
        if ok:
            return True, ""
        err = k.GetLastError()
        return False, f"Windows refused to move {exe} (error {err})"
    return True, "no window to test with"


def _asked_today(mark=False):
    path = os.path.join(os.path.dirname(os.path.abspath(__file__)), ".autostart.json")
    today = time.strftime("%Y-%m-%d")
    try:
        with open(path) as f:
            last = json.load(f).get("asked")
    except Exception:
        last = None
    if mark:
        with open(path, "w") as f:
            json.dump({"asked": today}, f)
    return last == today


def check(log=print, say=None, tasks=None, session=None, quiet=None, ask=None, requery=None, wait=60, shortcut=None):
    """Returns a list of problems in plain words. Fixes a background-only Jarvis task when it can, and only
    says it's fixed after checking Windows really changed it."""
    quiet, ask, requery = quiet or fix_quietly, ask or ask_windows, requery or jarvis_tasks
    problems = []
    sid = session_id() if session is None else session
    if sid == 0:
        problems.append("I'm running in Windows' background session, so I can't see or control any window.")
    tasks = jarvis_tasks() if tasks is None else tasks
    dup = startup_shortcut() if shortcut is None else shortcut
    dup = dup or any(not needs_fix(t) for t in tasks)   # a good "Jarvis" task already starts me
    bad = [t for t in tasks if needs_fix(t)]
    for t in tasks:
        log(f"autostart task '{t['name']}': logon mode '{t['logon_mode']}'" + (" (needs fixing)" if t in bad else ""))
    if bad and AUTO_FIX_AUTOSTART:
        delete = dup   # the Startup shortcut already starts me, so the old task only starts a second, hidden copy
        what = "delete my old startup task" if delete else "fix my startup task"
        left = [t for t in bad if not quiet(t["name"], delete)]
        if left and not _asked_today():
            _asked_today(mark=True)
            if say:
                say(f"Windows needs your OK to {what}. Click Yes on the prompt. If you don't see one, click the flashing shield in the taskbar.")
            for t in left:
                ask(t["name"], delete)
            deadline = time.time() + wait
            while time.time() < deadline:
                still = {x["name"] for x in requery() if needs_fix(x)}
                left = [t for t in left if t["name"] in still]
                if not left:
                    break
                time.sleep(3)
        if left:
            names = ", ".join(t["name"].lstrip("\\") for t in left)
            problems.insert(0, f"My old startup task, {names}, still runs me in the background. Delete it in Task Scheduler, "
                            "or run PowerShell as administrator and paste the line from the Jarvis log.")
            log("fix: Get-ScheduledTask | Where-Object TaskName -match 'jarvis' | Unregister-ScheduledTask -Confirm:$false")
        else:
            problems.insert(0, "Fixed my startup task. Restart the PC once and screen control will work." if sid == 0 else
                            "Cleaned up an old startup task. Restart the PC once to be safe.")
    if sid != 0:
        ok, why = can_move_windows()
        if not ok:
            problems.append("I can't move windows. " + why + ". Try running me as administrator.")
    log(f"startup check: session {sid}, admin {is_admin()}, " + ("all good" if not problems else f"{len(problems)} note(s)"))
    for p in problems:
        log("startup: " + p)
    if problems and say:
        say(problems[0])
    return problems
