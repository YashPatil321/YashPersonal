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


ZIP_URL = "https://codeload.github.com/YashPatil321/YashPersonal/zip/refs/heads/" + BRANCH


def git(*args):
    # safe.directory=*: running as administrator vs as you makes Git refuse a folder "owned by someone else". Don't.
    return subprocess.run(["git", "-c", "safe.directory=*", "-C", REPO, *args], capture_output=True, text=True, timeout=180,
                          creationflags=NO_WINDOW)


def status(ok, error="", source=""):
    """What the last update attempt found, for Jarvis to say out loud if something's wrong."""
    import json
    import time
    try:
        json.dump({"ok": ok, "error": error, "source": source, "when": time.time()}, open(os.path.join(HERE, ".update_status.json"), "w"))
    except OSError:
        pass
    if error:
        print("update:", error)


def sync_source():
    """Gets the newest code and returns the folder holding it. Git first; if Git fails for any reason, a zip from GitHub.
    Returns None only if both fail (offline)."""
    err = ""
    if have_git():
        if not os.path.isdir(os.path.join(REPO, ".git")):
            if os.path.isdir(REPO) and os.listdir(REPO):
                shutil.rmtree(REPO, ignore_errors=True)   # a broken half copy: start clean
            r = subprocess.run(["git", "-c", "safe.directory=*", "clone", "-q", "-b", BRANCH, "https://github.com/YashPatil321/YashPersonal.git", REPO],
                               capture_output=True, text=True, timeout=600, creationflags=NO_WINDOW)
            if r.returncode != 0:
                err = "git clone failed: " + r.stderr.strip()[:160]
        if not err:
            r = git("fetch", "-q", "origin", BRANCH)
            if r.returncode == 0:
                r = git("reset", "-q", "--hard", "origin/" + BRANCH)   # the copy matches GitHub exactly, nothing to merge
            if r.returncode == 0:
                status(True, source="git")
                return os.path.join(REPO, "jarvis")
            err = "git couldn't update: " + (r.stderr.strip() or r.stdout.strip())[:160]
    else:
        err = "Git isn't installed"
    # fallback: download the code as a zip, no Git needed
    try:
        import io
        import urllib.request
        import zipfile
        data = urllib.request.urlopen(ZIP_URL, timeout=120).read()
        dest = os.path.join(HERE, ".cache", "src")
        shutil.rmtree(dest, ignore_errors=True)
        zipfile.ZipFile(io.BytesIO(data)).extractall(dest)
        top = [d for d in os.listdir(dest) if os.path.isdir(os.path.join(dest, d))]
        src = os.path.join(dest, top[0], "jarvis") if top else None
        if src and os.path.isdir(src):
            status(True, error=f"({err}, used the zip download instead)", source="zip")
            return src
        err += "; the zip download had no jarvis folder"
    except Exception as e:
        err += f"; the zip download failed too ({e})"
    status(False, error=err)
    return None


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
    """True if newer code is waiting (anything that differs from what's running here, apart from files Jarvis edited itself)."""
    src = sync_source()
    if not src:
        return False
    keep = local_changes()
    return any(os.path.basename(f) not in keep for f in changed_files(src))


def base_dir():
    """Where the last repo version of each file is kept, for merging Atlas's own edits."""
    return os.path.join(HERE, ".cache", "base")


def save_base(name, src):
    try:
        os.makedirs(base_dir(), exist_ok=True)
        shutil.copy2(src, os.path.join(base_dir(), name))
    except OSError:
        pass


def merge_own_edits(name, mine, theirs):
    """Three way merge (git merge-file): Atlas's edits + the new version, against the version it started from.
    Writes the result and returns True when it's clean and still compiles; otherwise leaves Atlas's file alone."""
    base = os.path.join(base_dir(), name)
    if not os.path.exists(base) or not shutil.which("git"):
        return False
    try:
        r = subprocess.run(["git", "merge-file", "-p", mine, base, theirs], capture_output=True, timeout=60, creationflags=NO_WINDOW)
        if r.returncode != 0:   # conflicts (or an error)
            return False
        tmp = mine + ".merged"
        with open(tmp, "wb") as fh:
            fh.write(r.stdout)
        import py_compile
        try:
            if name.endswith(".py"):
                py_compile.compile(tmp, doraise=True)
        except py_compile.PyCompileError:
            os.remove(tmp)
            return False
        os.replace(tmp, mine)
        save_base(name, theirs)
        return True
    except Exception as e:
        print(f"update: merge of {name} failed: {e}")
        return False


def local_changes():
    """Files Jarvis deliberately edited itself (it records them). Updates leave those alone."""
    import json
    try:
        return set(json.load(open(os.path.join(HERE, ".local_changes.json"))))
    except Exception:
        return set()


def changed_files(src=None):
    src = src or os.path.join(REPO, "jarvis")
    out = []
    for pat in MANAGED:
        for f in glob.glob(os.path.join(src, pat)):
            dst = os.path.join(HERE, os.path.basename(f))
            if not os.path.exists(dst) or not filecmp.cmp(f, dst, shallow=False):
                out.append(f)
    return out


def update():
    src = sync_source()
    if not src:
        print("update: couldn't get the new code, running the current version")
        return 0
    files = changed_files(src)
    for pat in MANAGED:   # remember the repo version of files that match it, so Atlas's later edits can be merged
        for f in glob.glob(os.path.join(src, pat)):
            name = os.path.basename(f)
            dst = os.path.join(HERE, name)
            if not os.path.exists(os.path.join(base_dir(), name)) and os.path.exists(dst) and filecmp.cmp(f, dst, shallow=False):
                save_base(name, f)
    if not files:
        print("update: already up to date")
        if not os.path.exists(os.path.join(HERE, ".version.json")):
            write_version()
        return 0
    old_req = open(os.path.join(HERE, "requirements.txt")).read() if os.path.exists(os.path.join(HERE, "requirements.txt")) else ""
    installed = load_installed()
    keep = local_changes()
    for f in files:
        name = os.path.basename(f)
        dst = os.path.join(HERE, name)
        if name in keep and os.path.exists(dst):
            # Atlas edited this one itself: fold the new version in around its edits when they don't touch the same lines
            if merge_own_edits(name, dst, f):
                print(f"update: merged the new {name} with Atlas's own edits")
            else:
                print(f"update: kept Atlas's own edits to {name} (the new version changes the same lines)")
            continue
        shutil.copy2(f, dst)
        save_base(name, f)
        installed[name] = file_hash(dst)
        print("update: new", name)
    save_installed(installed)
    # first time only: give the person a settings file that updates will never overwrite
    if not os.path.exists(os.path.join(HERE, "local_settings.py")) and os.path.exists(os.path.join(src, "local_settings.example.py")):
        shutil.copy2(os.path.join(src, "local_settings.example.py"), os.path.join(HERE, "local_settings.py"))
        print("update: created local_settings.py, put your mic and speaker settings there")
    if open(os.path.join(HERE, "requirements.txt")).read() != old_req:
        print("update: installing new packages")
        subprocess.run([sys.executable, "-m", "pip", "install", "-q", "-r", os.path.join(HERE, "requirements.txt")], creationflags=NO_WINDOW)
    install_extras()
    write_version()
    return len(files)


def file_hash(p):
    import hashlib
    with open(p, "rb") as f:
        return hashlib.sha256(f.read()).hexdigest()


def load_installed():
    """What each managed file looked like when the updater last put it here."""
    import json
    try:
        return json.load(open(os.path.join(HERE, ".installed.json")))
    except Exception:
        return {}


def save_installed(d):
    import json
    try:
        json.dump(d, open(os.path.join(HERE, ".installed.json"), "w"))
    except OSError:
        pass


def write_version():
    """Records which code is running, so Jarvis can say its version and what's new."""
    import json
    import time
    try:
        head = git("log", "-1", "--format=%H|%cI").stdout.strip().split("|")
        recent = [l for l in git("log", "-8", "--format=%s").stdout.splitlines() if l.strip()]
        if len(head) < 2:   # came from the zip: no history, just the time
            head, recent = ["zip", time.strftime("%Y-%m-%dT%H:%M:%S")], []
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
        try:
            import jarvis_evolve
            jarvis_evolve.boot_guard()   # undo a self edit that keeps Atlas from starting
        except Exception as e:
            print(f"update: boot guard: {e}")
        update()
