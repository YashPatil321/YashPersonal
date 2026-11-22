"""
Puts what Jarvis is doing on HQ (the iPad and every screen with HQ open).

HQ lives inside claude.ai, so it can't reach this PC. Instead Jarvis writes one small document,
jarvis/status, into HQ's own database (through Claude Code's ArtifactData tool), and HQ shows it in the
JARVIS cell of the top strip and the Jarvis list in the sessions panel.

What goes up: a one line headline ("Locked in, 32 min left", "In the workshop: drone frame"), the last few
log lines from today ("16:05 Training: run 3 mi"), focus progress, camera on or off, and when it was sent.
Never: mail text, journal entries, notes, screenshots or camera pictures. In guest mode only "Guest mode" goes up.

At most one write every 2 minutes, and only when something changed (plus a heartbeat every 15 minutes so HQ
knows Jarvis is alive). Each write is a short, cheap Claude call.
"""

import json
import os
import re
import subprocess
import sys
import threading
import time

IS_WIN = sys.platform == "win32"
HERE = os.path.dirname(os.path.abspath(__file__))

# ---------------- settings (override in local_settings.py) ----------------
HQ_SYNC = True
HQ_SYNC_URL = "https://claude.ai/artifact/9ZQx1xYZwPMRDhDuoT5oVE"
HQ_SYNC_MIN_GAP = 120        # seconds between writes
HQ_SYNC_HEARTBEAT = 900      # write at least this often while Jarvis runs
HQ_SYNC_MODEL = "haiku"      # a small fast model is plenty for one database write
PRIVATE = ("Mail:", "Journal:", "Note:", "Remembered:", "Clipboard:", "Goodnight.", "Brief:")
# ---------------------------------------------------------------------------


def _log(msg):
    print(time.strftime("[%H:%M:%S] ") + "hq: " + str(msg), flush=True)


def public_events(lines, n=6):
    """Today's log lines that are fine to show on a screen anyone in the room can see."""
    out = []
    for l in lines:
        m = re.match(r"- (\d\d:\d\d) (.+)", l.strip())
        if not m or m.group(2).startswith(PRIVATE):
            continue
        text = re.sub(r"\[\[([^\]|]+)(?:\|[^\]]+)?\]\]", lambda x: x.group(1).split("/")[-1], m.group(2))
        out.append({"t": m.group(1), "text": text[:80]})
    return out[-n:]


class HQSync:
    def __init__(self, jarvis, runner=None, clock=time.time):
        self.j, self.clock = jarvis, clock
        self.runner = runner or self._claude_write
        self.last_sent, self.last_sig, self.lock = 0.0, None, threading.Lock()

    # what HQ shows
    def state(self):
        j = self.j
        b = getattr(j, "brain", None)
        now = self.clock()
        if b and b.guest:
            return {"headline": "Guest mode", "detail": "", "mode": "guest", "events": [], "updated": int(now * 1000)}
        st = {"mode": "idle", "headline": "Standing by", "detail": "", "events": [], "updated": int(now * 1000)}
        if b:
            st["events"] = public_events(b.vault.today_log(30).splitlines())
            if st["events"]:
                st["headline"] = st["events"][-1]["text"]
            if b.focus_started and b.focus_timer:
                total, done = int(b.focus_timer.interval / 60), int((now - b.focus_started) / 60)
                st.update(mode="focus", headline=f"Locked in, {max(0, total - done)} min left", focus={"total": total, "done": done})
            elif now < getattr(b, "hold_until", 0):
                st.update(mode="hold", headline="Do not disturb")
        cad = getattr(j, "cad", None)
        if cad and cad.active and cad.current:
            st.update(mode="cad", headline="In the workshop: " + os.path.splitext(os.path.basename(cad.current))[0])
        v = getattr(j, "vision", None)
        if v:
            st["camera"] = "on" if v.enabled else "off"
            if v.touch:
                st.update(mode="touch", headline="Touch mode")
        desk = getattr(j, "desk", None)
        if desk and desk.running:
            st["desk"] = "on"
        return st

    def _sig(self, st):
        return json.dumps({k: v for k, v in st.items() if k != "updated"}, sort_keys=True)

    def tick(self, force=False):
        """Sends when something changed (at most every MIN_GAP), or as a heartbeat."""
        with self.lock:
            now = self.clock()
            st = self.state()
            sig = self._sig(st)
            changed = sig != self.last_sig
            due = (changed and now - self.last_sent >= HQ_SYNC_MIN_GAP) or now - self.last_sent >= HQ_SYNC_HEARTBEAT
            if not (force or due):
                return False
            ok = self.runner(st)
            if ok:
                self.last_sent, self.last_sig = now, sig
            else:
                self.last_sent = now   # don't hammer on errors, try again next window
            return ok

    def loop(self):
        time.sleep(20)
        while True:
            try:
                self.tick()
            except Exception as e:
                _log(f"sync: {e}")
            time.sleep(30)

    def start(self):
        if HQ_SYNC:
            threading.Thread(target=self.loop, daemon=True).start()
        return self

    # the actual write: Claude Code's ArtifactData tool, as you
    def _claude_write(self, st):
        claude = getattr(self.j, "claude", None)
        if not claude:
            return False
        path = os.path.join(HERE, ".cache", "hq_status.json")
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, "w", encoding="utf-8") as f:
            json.dump(st, f)
        prompt = (f"Use the ArtifactData tool on the artifact {HQ_SYNC_URL}. First: action get, collection 'jarvis', doc_id 'status'. "
                  f"Then: action set, collection 'jarvis', doc_id 'status', file_path '{path}', with if_version set to the version "
                  "the get returned (leave if_version out if the get found no document). If the set says the version changed, get "
                  "again and retry once. Reply with only OK, or the error message.")
        cmd = [claude, "-p", "--output-format", "json", "--model", HQ_SYNC_MODEL, "--allowedTools", "ArtifactData"]
        try:
            r = subprocess.run(cmd, cwd=HERE, input=prompt, capture_output=True, text=True, encoding="utf-8", timeout=120,
                               creationflags=0x08000000 if IS_WIN else 0)
            out = json.loads(r.stdout or "{}").get("result", "") if r.stdout.strip().startswith("{") else (r.stderr or r.stdout)
        except Exception as e:
            _log(f"write failed: {e}")
            return False
        ok = out.strip().upper().startswith("OK")
        _log(("sent: " + st["headline"]) if ok else f"write failed: {out[:200]}")
        return ok
