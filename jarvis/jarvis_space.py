"""
Atlas Space: a glass workspace on your Jarvis monitor (or the projected mat), with objects you grab with your hands.

Everything Atlas does can land here as a glass object: answers, lists, plans, images, links, your next event, music,
timers. Your hands are tracked completely (all 21 points of each, drawn live as glass hands) and you work with the
objects directly:

  three finger squeeze (thumb, index, middle together)   grab the object under your hand, move it, let go to throw it
  squeeze one object with both hands                     pull apart / push together to resize, twist to rotate
  pinch (thumb + index)                                  press a button on an object
  flick an object hard off the edge                      dismiss it
  both open hands, pull them together                    gather everything into a stack in front of you
  both open hands, push them apart                       spread everything out in a grid
Mouse and touch work too (drag, scroll to resize, double click to close).

By voice or chat: "desk mode" / "open the space", "pull everything together", "spread it out", "clear the space",
"show me <anything> on the space" (Atlas builds the objects). Claude can put objects here with jarvis_ctl.py space.

Settings (local_settings.py):
  JARVIS_DISPLAY = None    which screen is the Jarvis monitor (0, 1, 2...). None = the projector if there is one,
                           else the smallest screen that isn't your main one, else the main one
  SPACE_HANDS = "auto"     "webcam": hands in the air in front of the monitor camera. "desk": hands on the mat under
                           the desk camera (needs the desk calibrated). "auto": the mat when Space is on the projector
                           and the desk is calibrated, else the webcam
  SPACE_REGION = (0.15, 0.12, 0.85, 0.82)   the part of the webcam picture that maps to the whole screen
"""

import json
import os
import re
import threading
import time

HERE = os.path.dirname(os.path.abspath(__file__))

JARVIS_DISPLAY = None
SPACE_HANDS = "auto"
SPACE_REGION = (0.15, 0.12, 0.85, 0.82)


def _log(msg):
    print(time.strftime("[%H:%M:%S] ") + "space: " + str(msg), flush=True)


CURRENT = None   # the Space, for routing voice commands about its objects
WIDGETS = {"core": ("core", "atlas", "clock"), "next": ("next", "next up", "up next"), "music": ("music", "player", "song"),
           "timer": ("timer", "focus"), "agenda": ("agenda", "calendar", "schedule", "day"),
           "system": ("system", "computer", "pc", "stats"), "notes": ("notes", "inbox", "note")}
SPOTS = {"top left": (.17, .2), "top right": (.83, .2), "bottom left": (.17, .8), "bottom right": (.83, .8), "top": (.5, .16),
         "bottom": (.5, .84), "left": (.15, .5), "right": (.85, .5), "center": (.5, .5), "middle": (.5, .5)}


class Space:
    def __init__(self):
        global CURRENT
        CURRENT = self
        self.objects = []          # [{"id", "kind", ...data}]
        self.events = []           # [(seq, event)] recent, for the stream
        self.seq = 0
        self.hands = []            # [{"pts": [[x, y] * 21], "label": ""}] in screen 0..1
        self.hands_t = 0.0
        self.hands_seq = 0
        self.active = False        # a Space page is open
        self.last_seen_page = 0.0
        self.source = "webcam"
        self.cond = threading.Condition()
        self.reply_id = None
        self._next = 1

    # ---------- objects ----------
    def _emit(self, ev):
        with self.cond:
            self.seq += 1
            self.events.append((self.seq, ev))
            self.events = self.events[-200:]
            self.cond.notify_all()

    def add(self, kind, **data):
        obj = {"id": f"o{self._next}", "kind": kind, **{k: v for k, v in data.items() if v not in (None, "", [])}}
        self._next += 1
        self.objects = (self.objects + [obj])[-40:]
        self._emit({"type": "add", "obj": obj})
        return obj["id"]

    def update(self, oid, **patch):
        for o in self.objects:
            if o["id"] == oid:
                o.update(patch)
                self._emit({"type": "update", "id": oid, "patch": patch})
                return True
        return False

    def command(self, what, **more):
        if what == "clear":
            self.objects = [o for o in self.objects if o.get("pinned")]
        if what == "close" and more.get("id"):
            self.objects = [o for o in self.objects if o["id"] != more["id"]]
        self._emit({"type": "cmd", "do": what, **more})

    def find(self, name):
        """The object a spoken name means: a built in widget, else the newest object whose title or kind matches."""
        n = re.sub(r"^(?:the|my|that|this)\s+", "", name.lower().strip())
        n = re.sub(r"\s+(?:card|widget|panel|object|window|box|thing)$", "", n)
        for wid, words in WIDGETS.items():
            if n in words:
                return wid
        for o in reversed(self.objects):
            hay = " ".join(str(o.get(k, "")) for k in ("title", "label", "kind", "q")).lower()
            if n and (n in hay or all(w in hay for w in n.split())):
                return o["id"]
        if n in ("last", "last one", "newest", "it", "that", "this") and self.objects:
            return self.objects[-1]["id"]
        return None

    # ---------- what Atlas says becomes objects ----------
    def on_chat(self, who, text):
        """jarvis_chatui feeds every line here. A request opens a reply card; Atlas's answer fills it in."""
        if not self.active:
            return
        if who == "you":
            self.reply_id = self.add("reply", q=text, text="")
        elif who == "atlas":
            if self.reply_id and self.update(self.reply_id, text=text):
                return
            self.reply_id = self.add("reply", text=text)

    # ---------- hands ----------
    def wants_webcam(self):
        return self.active and self.source == "webcam"

    def wants_desk(self):
        return self.active and self.source == "desk"

    def feed_webcam(self, hands):
        """hands: [landmarks] from the monitor webcam, already mirrored (your right is the screen's right)."""
        x0, y0, x1, y1 = SPACE_REGION
        out = [{"pts": [[round((x - x0) / (x1 - x0), 4), round((y - y0) / (y1 - y0), 4)] for x, y in lm]} for lm in hands]
        self._hands(out)

    def feed_desk(self, hands):
        """hands: [[(x, y) on the mat 0..1 or None] * 21] from the desk camera."""
        out = []
        for pts in hands:
            if any(p is None for p in pts):
                continue
            out.append({"pts": [[round(p[0], 4), round(p[1], 4)] for p in pts]})
        self._hands(out)

    def _hands(self, out):
        with self.cond:
            self.hands, self.hands_t = out, time.time()
            self.hands_seq += 1
            self.cond.notify_all()

    # ---------- web ----------
    def register(self, bridge, act=None, open_url=None):
        space = self

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
            with open(os.path.join(HERE, "space.html"), encoding="utf-8") as f:
                send(h, 200, f.read(), "text/html; charset=utf-8")

        def state(h, q):
            send(h, 200, json.dumps({"objects": space.objects, "seq": space.seq, "source": space.source}), "application/json")

        def stream(h, q):
            h.send_response(200)
            h.send_header("Content-Type", "text/event-stream")
            h.send_header("Cache-Control", "no-store")
            h.end_headers()
            space.active, space.last_seen_page = True, time.time()
            seen_ev, seen_hands = space.seq, -1
            try:
                while True:
                    with space.cond:
                        space.cond.wait(timeout=0.5)
                        evs = [e for s, e in space.events if s > seen_ev]
                        seen_ev = space.seq
                        hands = None
                        if space.hands_seq != seen_hands:
                            seen_hands = space.hands_seq
                            hands = space.hands if time.time() - space.hands_t < 0.5 else []
                    msg = {}
                    if evs:
                        msg["ev"] = evs
                    if hands is not None:
                        msg["hands"] = hands
                    if msg or True:
                        msg["src"] = space.source
                        h.wfile.write(("data: " + json.dumps(msg) + "\n\n").encode())
                        h.wfile.flush()
                    space.last_seen_page = time.time()
            except Exception:
                return
            finally:
                if time.time() - space.last_seen_page > 2:
                    space.active = False

        def push(h, q):
            kind = q.pop("kind", "card")
            q.pop("token", None)
            for k in ("items",):
                if isinstance(q.get(k), str):
                    try:
                        q[k] = json.loads(q[k])
                    except Exception:
                        q[k] = [i.strip() for i in q[k].split("\n") if i.strip()]
            oid = space.add(kind, **q)
            send(h, 200, oid, "text/plain")

        def cmd(h, q):
            space.command(q.get("do", ""))
            send(h, 200, "ok", "text/plain")

        def do(h, q):   # buttons on objects
            what = q.get("say", "")
            if q.get("url") and open_url:
                threading.Thread(target=open_url, args=(q["url"],), daemon=True).start()
            elif what and act:
                threading.Thread(target=act, args=(what,), daemon=True).start()
            send(h, 200, "ok", "text/plain")

        bridge.routes.update({"/space": page, "/space/state": state, "/space/stream": stream,
                              "/space/push": push, "/space/cmd": cmd, "/space/do": do})

    # keep "active" honest when the page closes without a clean disconnect
    def watch(self):
        while True:
            time.sleep(2)
            if self.active and time.time() - self.last_seen_page > 3:
                self.active = False


def jarvis_screen(mons, projector=None):
    """The Jarvis monitor: JARVIS_DISPLAY, else the projector, else the smallest non main screen, else the main one."""
    if JARVIS_DISPLAY is not None and JARVIS_DISPLAY < len(mons):
        return mons[JARVIS_DISPLAY]
    if projector:
        return projector
    others = [m for m in mons if not m[4]]
    if others:
        return min(others, key=lambda m: m[2] * m[3])
    return next((m for m in mons if m[4]), None)


def route_space(t):
    sp = CURRENT
    if sp is not None and sp.active:   # talking about something on the glass screen
        m = re.fullmatch(r"(?:close|remove|hide|dismiss|get rid of|throw away|kill) (.+)", t)
        if m and sp.find(m.group(1)):
            return ("space_obj", ("close", sp.find(m.group(1)), None))
        m = re.fullmatch(r"(?:move|put|send|drag|slide) (.+?) (?:to |into |in )?(?:the )?(" + "|".join(SPOTS) + r")(?: corner| side| of the screen)?", t)
        if m and sp.find(m.group(1)):
            return ("space_obj", ("move", sp.find(m.group(1)), m.group(2)))
        m = re.fullmatch(r"(?:make|scale) (.+?) (bigger|larger|huge|smaller|tiny|normal(?: size)?)", t) or \
            re.fullmatch(r"(zoom in on|blow up|shrink) (.+)", t)
        if m:
            name, how = (m.group(1), m.group(2)) if not m.group(1).startswith(("zoom", "blow", "shrink")) else (m.group(2), m.group(1))
            if sp.find(name):
                return ("space_obj", ("scale", sp.find(name), how))
        m = re.fullmatch(r"(?:bring up|focus on|pull up|show me|open) (.+)", t)
        if m and sp.find(m.group(1)) and sp.find(m.group(1)) in WIDGETS or (m and any(o["id"] == sp.find(m.group(1)) for o in sp.objects)):
            return ("space_obj", ("front", sp.find(m.group(1)), None))
        m = re.fullmatch(r"(?:add|put|show)(?: me)? (?:my |the )?(agenda|calendar|schedule|system stats|system|stats|notes|inbox|timer|music|clock)(?: (?:on|to) (?:the )?(?:space|jarvis screen|screen|glass))?", t)
        if m:
            wid = next(w for w, words in WIDGETS.items() if m.group(1).split()[0] in words or m.group(1) in words)
            return ("space_obj", ("widget", wid, None))
    if re.fullmatch(r"(?:open|start|show|launch) (?:the |atlas )?space|space mode|(?:open )?atlas space|workspace mode", t):
        return ("space_open", None)
    if re.fullmatch(r"(?:close|stop|hide) (?:the )?space|space off", t):
        return ("space_close", None)
    if re.fullmatch(r"(?:pull|bring|gather) (?:everything|it all|all of it|them all|it) (?:together|in|here|to me)|gather (?:up|everything)|stack (?:everything|it all)(?: up)?", t):
        return ("space_cmd", "gather")
    if re.fullmatch(r"(?:spread|lay) (?:everything|it all|them|it) (?:out|apart)|spread out|scatter(?: everything)?|organize the space", t):
        return ("space_cmd", "scatter")
    if re.fullmatch(r"(?:clear|clean|empty|wipe) (?:the |my )?(?:space|desk|board)", t):
        return ("space_cmd", "clear")
    return None
