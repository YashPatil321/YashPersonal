"""
Atlas says what actually happened, and can take it back.

  Honest results   opening an app is checked against the real windows: "Spotify's open" only once a Spotify
                   window shows up; if nothing appears in a few seconds it says so. If the app is already running
                   it brings that window to the front instead of starting a second copy.
  Undo             "undo that" / "take that back" reverses the last thing Atlas did: volume, pause or play, skip,
                   an app it opened (closes it), a tab it closed (reopens it), a focus session, a routine, a fact it
                   remembered, a gesture shortcut, standby. "Undo your last change" is still the one for its code.
  Memory, editable every fact in Memory.md and every lesson, listed in the command center with a delete button
                   ("open the command center", then Memory), or by voice: "forget that I ..." .
"""

import os
import re
import threading
import time


def _log(msg):
    print(time.strftime("[%H:%M:%S] ") + "trust: " + str(msg), flush=True)


# ---------------- honest app launches ----------------
def _windows():
    try:
        import jarvis_screen
        return jarvis_screen.Screen().windows()
    except Exception:
        return None


def _matches(name, exe, title):
    n = re.sub(r"[^a-z0-9]", "", name.lower())
    e = re.sub(r"[^a-z0-9]", "", exe.lower().replace(".exe", ""))
    t = title.lower()
    return bool(n) and (n in e or e.startswith(n[:5]) or name.lower() in t)


def find_window(name, wins=None):
    wins = _windows() if wins is None else wins
    for h, exe, title in wins or []:
        if _matches(name, exe, title):
            return h
    return None


def verify_open(name, before, timeout=8.0, wins=_windows, sleep=time.sleep):
    """True once a new window for the app shows up, False if none does in time, None if windows can't be read."""
    known = {h for h, _, _ in (before or [])}
    end = time.time() + timeout
    while time.time() < end:
        now = wins()
        if now is None:
            return None
        for h, exe, title in now:
            if h not in known and _matches(name, exe, title):
                return h
        sleep(0.4)
    return False


# ---------------- undo ----------------
class UndoLog:
    def __init__(self, limit=20):
        self.items, self.limit, self.lock = [], limit, threading.Lock()

    def push(self, label, fn):
        with self.lock:
            self.items = (self.items + [(time.time(), label, fn)])[-self.limit:]

    def pop(self, max_age=1800):
        with self.lock:
            while self.items:
                t, label, fn = self.items.pop()
                if time.time() - t <= max_age:
                    return label, fn
        return None


# ---------------- memory you can edit ----------------
def facts(vault):
    """[{'kind': 'memory'|'lesson', 'text': ...}] from Memory.md and Lessons.md."""
    out = []
    for kind, rel in (("memory", "Jarvis/Memory.md"), ("lesson", "Jarvis/Lessons.md")):
        for line in (vault.read(rel) or "").splitlines():
            if line.startswith("- "):
                out.append({"kind": kind, "text": line[2:].strip()})
    return out


def forget(vault, text, kind=None):
    """Removes the lines that match (exactly, or every word of a spoken phrase). Returns how many."""
    n = 0
    words = [w for w in re.findall(r"[a-z0-9']+", text.lower()) if len(w) > 2]
    for k, rel in (("memory", "Jarvis/Memory.md"), ("lesson", "Jarvis/Lessons.md")):
        if kind and kind != k:
            continue
        txt = vault.read(rel) or ""
        if not txt:
            continue
        keep = []
        for line in txt.splitlines():
            body = line[2:].strip() if line.startswith("- ") else None
            hit = body is not None and (body == text.strip() or (words and all(w in body.lower() for w in words)))
            if hit:
                n += 1
            else:
                keep.append(line)
        if len(keep) != len(txt.splitlines()):
            vault._write(rel, "\n".join(keep) + "\n", "w")
    return n


def route_trust(t):
    if re.fullmatch(r"undo(?: (?:that|it|the last thing|what you (?:just )?did))?|take (?:that|it) back|reverse (?:that|it)|never mind,? undo (?:that|it)", t):
        return ("undo_action", None)
    m = re.fullmatch(r"forget (?:that )?(?:i |my |about )?(.{6,})", t)
    if m and not re.search(r"\b(?:face|gesture|sign|routine|job)\b", m.group(1)):
        return ("forget_fact", m.group(1))
    return None


# ---------------- Telegram: Atlas on your phone ----------------
class Telegram:
    """Your private Telegram bot, answered by Atlas on your PC (while it's on). Text it, or send a voice note.
    Setup: message @BotFather in Telegram, /newbot, copy the token into local_settings.py as TELEGRAM_TOKEN,
    restart Atlas, then send your bot the /pair code shown in the Atlas window. Only your chat is ever answered."""
    def __init__(self, token, chat_id, ask, transcribe_file=None, save_chat=None, log=_log):
        self.token, self.chat_id, self.ask, self.transcribe_file = token, int(chat_id or 0), ask, transcribe_file
        self.save_chat, self.log = save_chat, log
        self.code = str(int.from_bytes(os.urandom(3), "big") % 900000 + 100000)
        self.offset = 0

    def api(self, method, data=None, files=None, timeout=40):
        import json
        import urllib.parse
        import urllib.request
        url = f"https://api.telegram.org/bot{self.token}/{method}"
        if files:
            boundary = "atlas" + os.urandom(8).hex()
            body = b""
            for k, v in (data or {}).items():
                body += f"--{boundary}\r\nContent-Disposition: form-data; name=\"{k}\"\r\n\r\n{v}\r\n".encode()
            for k, path in files.items():
                body += (f"--{boundary}\r\nContent-Disposition: form-data; name=\"{k}\"; filename=\"{os.path.basename(path)}\"\r\n"
                         "Content-Type: application/octet-stream\r\n\r\n").encode() + open(path, "rb").read() + b"\r\n"
            body += f"--{boundary}--\r\n".encode()
            req = urllib.request.Request(url, data=body, headers={"Content-Type": "multipart/form-data; boundary=" + boundary})
        else:
            req = urllib.request.Request(url, data=urllib.parse.urlencode(data or {}).encode())
        with urllib.request.urlopen(req, timeout=timeout) as r:
            return json.loads(r.read())

    def send(self, text, chat=None):
        if not (chat or self.chat_id):
            return False
        try:
            self.api("sendMessage", {"chat_id": chat or self.chat_id, "text": text[:4000]})
            return True
        except Exception as e:
            self.log(f"telegram send: {e}")
            return False

    def send_file(self, path, caption=""):
        try:
            self.api("sendDocument", {"chat_id": self.chat_id, "caption": caption[:900]}, files={"document": path}, timeout=120)
            return True
        except Exception as e:
            self.log(f"telegram file: {e}")
            return False

    def handle(self, msg):
        chat = (msg.get("chat") or {}).get("id")
        text = (msg.get("text") or "").strip()
        if not self.chat_id:
            if text == f"/pair {self.code}":
                self.chat_id = chat
                if self.save_chat:
                    self.save_chat(chat)
                self.send("Paired. It's Atlas. Text me or send a voice note any time your PC is on.", chat)
                self.log("telegram paired")
            return
        if chat != self.chat_id:
            return   # someone else found the bot: ignore them completely
        if msg.get("voice") and self.transcribe_file:
            try:
                f = self.api("getFile", {"file_id": msg["voice"]["file_id"]})["result"]["file_path"]
                import urllib.request
                path = os.path.join(os.path.dirname(os.path.abspath(__file__)), ".cache", "tg_voice.ogg")
                os.makedirs(os.path.dirname(path), exist_ok=True)
                urllib.request.urlretrieve(f"https://api.telegram.org/file/bot{self.token}/{f}", path)
                text = self.transcribe_file(path)
            except Exception as e:
                self.log(f"telegram voice: {e}")
                return self.send("I couldn't hear that voice note. Try typing it.")
        if not text or text.startswith("/start"):
            return self.send("Hey. Ask me anything or tell me what to do on your PC.")
        self.api("sendChatAction", {"chat_id": chat, "action": "typing"})
        try:
            reply = self.ask(text) or "Done."
        except Exception as e:
            reply = f"Something broke: {e}"
        self.send(reply)

    def run(self):
        if not self.chat_id:
            self.log(f"Telegram: send your bot this to pair it with Atlas:  /pair {self.code}")
        while True:
            try:
                r = self.api("getUpdates", {"offset": self.offset, "timeout": 30, "allowed_updates": '["message"]'}, timeout=45)
                for u in r.get("result", []):
                    self.offset = u["update_id"] + 1
                    if u.get("message"):
                        threading.Thread(target=self.handle, args=(u["message"],), daemon=True).start()
            except Exception as e:
                self.log(f"telegram: {str(e)[:120]}")
                time.sleep(15)
