"""
Keeps C:\\jarvis up to date with the repo, without touching your own settings.

  python update.py            pull the repo, copy new code into this folder, install new packages
  python update.py --check    only say whether an update is waiting (exit code 10 if yes)

start.bat runs this before every launch, so a restart is an update. Jarvis also restarts itself
at night, or when you say "hey jarvis, update yourself", when something new is waiting.

Never overwritten: local_settings.py (your mic, gain, speaker, playlist), CLAUDE.md (your notes),
notes/, .venv/, .session.json, .spotify.json, and any .bat file you changed.
"""

import filecmp
import glob
import os
import shutil
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.environ.get("JARVIS_REPO", r"C:\yash-system")      # where you cloned YashPatil321/YashPersonal
BRANCH = os.environ.get("JARVIS_BRANCH", "claude/hopeful-bohr-1ramsu")
MANAGED = ["jarvis.py", "jarvis_*.py", "update.py", "requirements.txt", "requirements-extras.txt", "*.html", "README.md", "HANDOFF.md"]
NO_WINDOW = 0x08000000 if sys.platform == "win32" else 0


def git(*args):
    return subprocess.run(["git", "-C", REPO, *args], capture_output=True, text=True, timeout=120, creationflags=NO_WINDOW)


def have_git():
    return shutil.which("git") is not None


def ensure_repo():
    """The local copy of the code that updates come from. Made automatically the first time."""
    if os.path.isdir(os.path.join(REPO, ".git")):
        return True
    if not have_git():
        print("update: Git isn't installed, so I can't update. Run the installer (install.ps1) once.")
        return False
    print(f"update: no copy of the code at {REPO} yet, getting it now")
    r = subprocess.run(["git", "clone", "-q", "-b", BRANCH, "https://github.com/YashPatil321/YashPersonal.git", REPO],
                       capture_output=True, text=True, timeout=600, creationflags=NO_WINDOW)
    if r.returncode != 0:
        print("update: couldn't download the code:", r.stderr.strip()[:200])
        return False
    return True


def waiting():
    """True if the remote has commits this machine doesn't."""
    if not os.path.isdir(os.path.join(REPO, ".git")):
        return have_git()   # never set up: an update is definitely waiting
    if git("fetch", "-q", "origin", BRANCH).returncode != 0:
        return False
    local, remote = git("rev-parse", "HEAD").stdout.strip(), git("rev-parse", "origin/" + BRANCH).stdout.strip()
    return bool(remote) and local != remote or bool(changed_files())


def changed_files():
    src = os.path.join(REPO, "jarvis")
    out = []
    for pat in MANAGED:
        for f in glob.glob(os.path.join(src, pat)):
            dst = os.path.join(HERE, os.path.basename(f))
            if not os.path.exists(dst) or not filecmp.cmp(f, dst, shallow=False):
                out.append(f)
    return out


def update():
    if not ensure_repo():
        return 0
    git("checkout", "-q", BRANCH)
    r = git("pull", "-q", "--ff-only", "origin", BRANCH)
    if r.returncode != 0:
        print("update: could not pull (offline or local changes in the repo); running the current version.", r.stderr.strip()[:200])
    files = changed_files()
    if not files:
        print("update: already up to date")
        if not os.path.exists(os.path.join(HERE, ".version.json")):
            write_version()
        return 0
    old_req = open(os.path.join(HERE, "requirements.txt")).read() if os.path.exists(os.path.join(HERE, "requirements.txt")) else ""
    for f in files:
        shutil.copy2(f, os.path.join(HERE, os.path.basename(f)))
        print("update: new", os.path.basename(f))
    # first time only: give the person a settings file that updates will never overwrite
    if not os.path.exists(os.path.join(HERE, "local_settings.py")) and os.path.exists(os.path.join(REPO, "jarvis", "local_settings.example.py")):
        shutil.copy2(os.path.join(REPO, "jarvis", "local_settings.example.py"), os.path.join(HERE, "local_settings.py"))
        print("update: created local_settings.py, put your mic and speaker settings there")
    if open(os.path.join(HERE, "requirements.txt")).read() != old_req:
        print("update: installing new packages")
        subprocess.run([sys.executable, "-m", "pip", "install", "-q", "-r", os.path.join(HERE, "requirements.txt")], creationflags=NO_WINDOW)
    install_extras()
    write_version()
    return len(files)


def write_version():
    """Records which code is running, so Jarvis can say its version and what's new."""
    import json
    import time
    try:
        head = git("log", "-1", "--format=%H|%cI").stdout.strip().split("|")
        recent = [l for l in git("log", "-8", "--format=%s").stdout.splitlines() if l.strip()]
        when = time.strftime("%b %d at %I:%M %p", time.strptime(head[1][:19], "%Y-%m-%dT%H:%M:%S")).replace(" 0", " ")
        with open(os.path.join(HERE, ".version.json"), "w", encoding="utf-8") as f:
            json.dump({"commit": head[0], "when": when, "recent": recent}, f)
        print(f"update: now on the version from {when}")
    except Exception as e:
        print("update: couldn't record the version:", e)


def install_extras(pip_run=None, force=False):
    """Camera and screenshot packages, one at a time. A package that fails just stays off, and isn't retried
    for a week (so a package that can't install on this PC never slows every start down). --extras forces a retry."""
    import json
    import time
    path = os.path.join(HERE, "requirements-extras.txt")
    if not os.path.exists(path):
        return []
    import importlib.util
    mods = {"pillow": "PIL", "opencv-python": "cv2", "mediapipe": "mediapipe", "uiautomation": "uiautomation"}
    failed_file = os.path.join(HERE, ".extras_failed.json")
    try:
        failed = json.load(open(failed_file))
    except Exception:
        failed = {}
    done = []
    for line in open(path):
        pkg = line.split("#")[0].strip()
        if not pkg or importlib.util.find_spec(mods.get(pkg, pkg)):
            continue
        if not force and time.time() - failed.get(pkg, 0) < 7 * 86400:
            continue
        print(f"update: installing {pkg} (one time, can take a few minutes)", flush=True)
        r = (pip_run or (lambda p: subprocess.run([sys.executable, "-m", "pip", "install", "-q", p], creationflags=NO_WINDOW, timeout=1800)))(pkg)
        if getattr(r, "returncode", 0) == 0:
            done.append(pkg)
            failed.pop(pkg, None)
        else:
            print(f"update: {pkg} didn't install, that feature stays off. Retry with: python update.py --extras")
            failed[pkg] = time.time()
    try:
        json.dump(failed, open(failed_file, "w"))
    except OSError:
        pass
    return done


if __name__ == "__main__":
    if "--check" in sys.argv:
        w = waiting()
        print("update waiting" if w else "up to date")
        sys.exit(10 if w else 0)
    if "--extras" in sys.argv:
        install_extras(force=True)
    else:
        update()
