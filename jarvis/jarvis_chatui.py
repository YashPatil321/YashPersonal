"""
Atlas chat: a clean window to type to Atlas, instead of the black console.

  "open chat" (or typing mode opens it on its own). Everything Atlas says shows up here as it says it, whether you
  typed, talked, or a routine fired. Toggle "speak replies" if you also want to hear them.
"""

import json
import os
import threading
import time

HERE = os.path.dirname(os.path.abspath(__file__))
FEED = []                    # [{"id", "who": "you"|"atlas", "text", "t"}]
LOCK = threading.Lock()
NEW = threading.Condition(LOCK)
_next = [1]
LISTENERS = []               # fn(who, text) for every line, e.g. Atlas Space turning answers into objects


def add(who, text):
    text = (text or "").strip()
    if not text:
        return
    for fn in LISTENERS:
        try:
            fn(who, text)
        except Exception:
            pass
    with NEW:
        # Atlas speaks in sentences: join the pieces of one answer into one message
        if who == "atlas" and FEED and FEED[-1]["who"] == "atlas" and time.time() - FEED[-1]["t"] < 4:
            FEED[-1]["text"] += " " + text
            FEED[-1]["t"] = time.time()
            FEED[-1]["rev"] = FEED[-1].get("rev", 0) + 1
        else:
            FEED.append({"id": _next[0], "who": who, "text": text, "t": time.time(), "rev": 0})
            _next[0] += 1
            del FEED[:-300]
        NEW.notify_all()


def register(bridge, jarvis, orb_state=lambda: "idle"):
    def send(h, code, body, ctype):
        if isinstance(body, str):
            body = body.encode("utf-8")
        h.send_response(code)
        h.send_header("Content-Type", ctype)
        h.send_header("Content-Length", str(len(body)))
        h.send_header("Cache-Control", "no-store")
        h.end_headers()
        h.wfile.write(body)

    def page(h, q):
        with open(os.path.join(HERE, "chat.html"), encoding="utf-8") as f:
            send(h, 200, f.read(), "text/html; charset=utf-8")

    def post(h, q):
        text = (q.get("text") or "").strip()
        if not text:
            return send(h, 400, "empty", "text/plain")
        add("you", text)

        def run():
            try:
                import jarvis_orb
                jarvis_orb.send("thinking")
                jarvis.remote_ask(text, speak=q.get("speak") == "1")
            except Exception as e:
                add("atlas", f"That broke: {str(e)[:160]}")
            finally:
                try:
                    jarvis_orb.send("idle")
                except Exception:
                    pass
        threading.Thread(target=run, daemon=True).start()
        return send(h, 200, "ok", "text/plain")

    def stream(h, q):
        h.send_response(200)
        h.send_header("Content-Type", "text/event-stream")
        h.send_header("Cache-Control", "no-store")
        h.end_headers()
        seen = {}
        last_state = None
        try:
            while True:
                with NEW:
                    NEW.wait(timeout=0.4)
                    items = [dict(m) for m in FEED if seen.get(m["id"]) != m["rev"]]
                for m in items:
                    seen[m["id"]] = m["rev"]
                st = orb_state()
                if items or st != last_state:
                    last_state = st
                    h.wfile.write(("data: " + json.dumps({"msgs": items, "state": st}) + "\n\n").encode())
                    h.wfile.flush()
        except Exception:
            return

    bridge.routes.update({"/chat": page, "/chat/send": post, "/chat/stream": stream})
