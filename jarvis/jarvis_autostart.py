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
import subprocess
import sys

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


def fix_task(name, runner=None):
    """Asks Windows (one Yes/No prompt) to make the task run only on your desktop."""
    args = f'/Change /TN "{name}" /IT'
    if runner:
        return runner("schtasks.exe", args)
    try:   # your own task can usually be changed without asking
        r = subprocess.run(["schtasks", "/Change", "/TN", name, "/IT"], capture_output=True, text=True, timeout=30, creationflags=NO_WINDOW)
        if r.returncode == 0:
            return True
    except Exception:
        pass
    import ctypes
    r = ctypes.windll.shell32.ShellExecuteW(None, "runas", "schtasks.exe", args, None, 0)
    return r > 32


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


def check(log=print, say=None, runner=None, tasks=None, session=None):
    """Returns a list of problems in plain words. Fixes the task setting when it can."""
    problems = []
    sid = session_id() if session is None else session
    if sid == 0:
        problems.append("I'm running in Windows' background session, so I can't see or control any window. "
                        "My startup task needs to be set to run only when you're logged on.")
    tasks = jarvis_tasks() if tasks is None else tasks
    for t in tasks:
        log(f"autostart task '{t['name']}': logon mode '{t['logon_mode']}'")
        if needs_fix(t) and AUTO_FIX_AUTOSTART:
            asked = fix_task(t["name"], runner)
            log(f"asked Windows to fix task '{t['name']}' to interactive only: {'prompt shown' if asked else 'refused'}")
            if asked:
                problems.append(f"I fixed my startup task so I run on your desktop. Restart me, or the PC, for it to take effect.")
            else:
                problems.append("My startup task runs me in the background where I can't control windows. "
                                "In Task Scheduler, set it to run only when you're logged on.")
    if sid != 0:
        ok, why = can_move_windows()
        if not ok:
            problems.append("I can't move windows. " + why + ". Try running me as administrator.")
    log(f"startup check: session {sid}, admin {is_admin()}, " + ("all good" if not problems else f"{len(problems)} problem(s)"))
    for p in problems:
        log("problem: " + p)
    if problems and say:
        say(problems[0])
    return problems
