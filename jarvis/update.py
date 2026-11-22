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


def waiting():
    """True if the remote has commits this machine doesn't."""
    if not os.path.isdir(os.path.join(REPO, ".git")):
        return False
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
    if not os.path.isdir(os.path.join(REPO, ".git")):
        print(f"update: no repo at {REPO}. Clone it once:  git clone -b {BRANCH} https://github.com/YashPatil321/YashPersonal.git {REPO}")
        return 0
    git("checkout", "-q", BRANCH)
    r = git("pull", "-q", "--ff-only", "origin", BRANCH)
    if r.returncode != 0:
        print("update: could not pull (offline or local changes in the repo); running the current version.", r.stderr.strip()[:200])
    files = changed_files()
    if not files:
        print("update: already up to date")
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
    return len(files)


def install_extras(pip_run=None):
    """Camera and screenshot packages, one at a time. A package that fails just stays off."""
    path = os.path.join(HERE, "requirements-extras.txt")
    if not os.path.exists(path):
        return []
    import importlib.util
    mods = {"pillow": "PIL", "opencv-python": "cv2", "mediapipe": "mediapipe"}
    done = []
    for line in open(path):
        pkg = line.split("#")[0].strip()
        if not pkg or importlib.util.find_spec(mods.get(pkg, pkg)):
            continue
        print(f"update: installing {pkg}")
        r = (pip_run or (lambda p: subprocess.run([sys.executable, "-m", "pip", "install", "-q", p], creationflags=NO_WINDOW)))(pkg)
        if getattr(r, "returncode", 0) == 0:
            done.append(pkg)
        else:
            print(f"update: {pkg} didn't install, that feature stays off")
    return done


if __name__ == "__main__":
    if "--check" in sys.argv:
        w = waiting()
        print("update waiting" if w else "up to date")
        sys.exit(10 if w else 0)
    if "--extras" in sys.argv:
        install_extras()
    else:
        update()
