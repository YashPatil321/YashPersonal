"""
CAD with your hands. A 3D viewer (cad.html) driven by the camera, like Tony Stark's workshop.

Files: STEP / STP / IGES (from Fusion, Onshape, SolidWorks), STL, 3MF, OBJ, GLB / GLTF.
Jarvis looks for them in Downloads, Documents, Desktop, OneDrive and your vault (CAD_FOLDERS).

  one hand pinch and move     spin the model
  two hands pinching          pull apart / push together = zoom, move both = slide it, twist = roll it
  fist and move               move the model around
  both palms open             spread them to explode the parts apart, bring them together to put it back
  quick pinch on a part       select it: name, size, and everything else fades
  open palm swipe             fling it into a spin

Voice: "open my cad" (newest file), "open the cabinet model", "next model", "explode it", "put it back",
"cut it open" / "close the cut", "wireframe" / "solid" / "hologram look", "how big is it", "reset the view",
"hologram the model" (4 views for the pyramid), "save a picture of it", "close the model".
"""

import json
import os
import queue
import re
import threading
import time

HERE = os.path.dirname(os.path.abspath(__file__))
HOME = os.path.expanduser("~")

# ---------------- settings (override in local_settings.py) ----------------
CAD_FOLDERS = [os.path.join(HOME, d) for d in ("Downloads", "Documents", "Desktop", "OneDrive", "OneDrive\\Documents", "OneDrive\\Desktop")]
CAD_EXT = (".step", ".stp", ".iges", ".igs", ".stl", ".3mf", ".obj", ".glb", ".gltf")
CAD_MAX_MB = 200
# ---------------------------------------------------------------------------


def _log(msg):
    print(time.strftime("[%H:%M:%S] ") + "cad: " + str(msg), flush=True)


def find_models(folders=None, limit=300, depth=4):
    """[(path, mtime)] newest first. Skips hidden folders and node_modules."""
    out = []
    for root in folders or CAD_FOLDERS:
        if not os.path.isdir(root):
            continue
        base = root.rstrip("\\/").count(os.sep)
        for dirpath, dirs, files in os.walk(root):
            if dirpath.count(os.sep) - base >= depth:
                dirs[:] = []
            dirs[:] = [d for d in dirs if not d.startswith(".") and d not in ("node_modules", "AppData", "$RECYCLE.BIN")]
            for fn in files:
                if fn.lower().endswith(CAD_EXT):
                    p = os.path.join(dirpath, fn)
                    try:
                        st = os.stat(p)
                    except OSError:
                        continue
                    if st.st_size <= CAD_MAX_MB * 1e6:
                        out.append((p, st.st_mtime))
    out.sort(key=lambda x: -x[1])
    return out[:limit]


def match_model(spoken, models):
    """Best file for 'the cabinet model', 'the gear', 'drone frame'."""
    words = [w for w in re.findall(r"[a-z0-9]+", spoken.lower()) if w not in ("the", "my", "model", "cad", "file", "part", "open", "a")]
    if not words:
        return models[0][0] if models else None
    best, score = None, 0
    for i, (p, _) in enumerate(models):
        name = re.sub(r"[^a-z0-9]+", " ", os.path.splitext(os.path.basename(p))[0].lower())
        s = sum(3 if re.search(r"\b" + re.escape(w), name) else 0 for w in words) - i * 0.001   # newer wins ties
        if s > score:
            best, score = p, s
    return best


def allowed(path, folders=None):
    rp = os.path.realpath(path)
    if not rp.lower().endswith(CAD_EXT) or not os.path.isfile(rp):
        return False
    return any(rp.startswith(os.path.realpath(f) + os.sep) for f in (folders or CAD_FOLDERS) if os.path.isdir(f))


class CadHub:
    """Between Jarvis, the camera and the 3D page."""
    def __init__(self, say=None, folders=None):
        self.say = say or (lambda *_: None)
        self.folders = folders
        self.hands = []          # latest hand landmarks from the camera, set by jarvis_vision
        self.hands_t = 0.0
        self.log = []            # recent commands; every open page (viewer, hologram) gets each one
        self.info = {}           # what the page reports: file, size_mm, parts, selected
        self.current = None
        self.active = False
        self.seq = 0

    def models(self):
        return find_models(self.folders)

    def send(self, cmd, **kw):
        self.seq += 1
        self.log = (self.log + [dict(kw, cmd=cmd, seq=self.seq)])[-50:]

    def open(self, path):
        self.current = path
        self.send("load", path=path, name=os.path.basename(path))

    def set_hands(self, hands):
        self.hands, self.hands_t = hands, time.time()

    def register(self, bridge, folders=None):
        hub = self

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
            with open(os.path.join(HERE, "cad.html"), encoding="utf-8") as f:
                return send(h, 200, f.read(), "text/html; charset=utf-8")

        def stream(h, q):
            h.send_response(200)
            h.send_header("Content-Type", "text/event-stream")
            h.send_header("Cache-Control", "no-store")
            h.end_headers()
            if hub.current:   # a page that opens late still gets the current model
                h.wfile.write(("data: " + json.dumps({"cmd": "load", "path": hub.current, "name": os.path.basename(hub.current)}) + "\n\n").encode())
            last_t, last_seq = 0, hub.seq
            try:
                while True:
                    msgs = [m for m in hub.log if m["seq"] > last_seq]
                    if msgs:
                        last_seq = msgs[-1]["seq"]
                    for m in msgs:
                        h.wfile.write(("data: " + json.dumps(m) + "\n\n").encode())
                    if hub.hands_t != last_t:
                        last_t = hub.hands_t
                        fresh = time.time() - hub.hands_t < 0.5
                        h.wfile.write(("data: " + json.dumps({"hands": hub.hands if fresh else []}) + "\n\n").encode())
                    h.wfile.flush()
                    time.sleep(0.033)
            except Exception:
                return

        def file(h, q):
            p = q.get("path", "")
            if not allowed(p, hub.folders):
                return send(h, 403, "not an allowed CAD file", "text/plain")
            with open(p, "rb") as f:
                return send(h, 200, f.read(), "application/octet-stream")

        def listing(h, q):
            return send(h, 200, json.dumps([{"path": p, "name": os.path.basename(p), "t": t} for p, t in hub.models()[:60]]), "application/json")

        def info(h, q):
            try:
                hub.info = json.loads(q.get("json") or q.get("text") or "{}")
            except Exception:
                pass
            return send(h, 200, "ok", "text/plain")

        def snapshot(h, q):
            import base64
            data = q.get("png", "")
            if data.startswith("data:image/png;base64,"):
                name = os.path.splitext(os.path.basename(hub.current or "model"))[0] + time.strftime(" %Y-%m-%d %H%M") + ".png"
                out = os.path.join(SNAP_DIR, name)
                os.makedirs(SNAP_DIR, exist_ok=True)
                with open(out, "wb") as f:
                    f.write(base64.b64decode(data.split(",", 1)[1]))
                hub.say("Saved a picture of it to your vault.")
                return send(h, 200, out, "text/plain")
            return send(h, 400, "no image", "text/plain")

        bridge.routes.update({"/cad": page, "/cad/stream": stream, "/cad/file": file, "/cad/list": listing,
                              "/cad/info": info, "/cad/snapshot": snapshot})


SNAP_DIR = os.path.join(HERE, "notes", "CAD")   # jarvis.py points this at the vault


def route_cad(t):
    if re.fullmatch(r"(?:open |start |launch )?(?:my )?cad(?: mode| viewer| workshop)?|(?:open|show me|pull up) (?:my )?(?:latest |newest |last )?(?:cad|model|3d model)", t):
        return ("cad_open", None)
    m = re.fullmatch(r"(?:open|show me|pull up|load) (?:the |my )?(.+?) (?:model|cad|part|assembly|file|step file|stl)", t)
    if m:
        return ("cad_open", m.group(1))
    if re.fullmatch(r"(?:next|another|the next) model|switch models?", t):
        return ("cad_next", None)
    if re.fullmatch(r"(?:explode|blow up|break apart|take apart) (?:it|the model|the assembly)|exploded view", t):
        return ("cad_cmd", ("explode", 1))
    if re.fullmatch(r"(?:put it back(?: together)?|collapse it|unexplode|assemble it)", t):
        return ("cad_cmd", ("explode", 0))
    if re.fullmatch(r"(?:cut it open|section view|cross section|slice it)", t):
        return ("cad_cmd", ("section", 1))
    if re.fullmatch(r"(?:close the cut|no section|remove the cut|close it up)", t):
        return ("cad_cmd", ("section", 0))
    if re.fullmatch(r"wireframe(?: mode)?|show (?:the )?wireframe", t):
        return ("cad_cmd", ("look", "wire"))
    if re.fullmatch(r"(?:solid|normal)(?: mode| look)?|show it solid", t):
        return ("cad_cmd", ("look", "solid"))
    if re.fullmatch(r"(?:hologram|holo|blue ?print|glow)(?: look| style| material)", t):
        return ("cad_cmd", ("look", "holo"))
    if re.fullmatch(r"(?:reset|center|fit) (?:the )?(?:view|model|camera)", t):
        return ("cad_cmd", ("reset", 1))
    if re.fullmatch(r"(?:spin it|turntable|auto ?rotate|rotate it)", t):
        return ("cad_cmd", ("spin", 1))
    if re.fullmatch(r"(?:stop spinning|stop (?:the )?rotation|hold still)", t):
        return ("cad_cmd", ("spin", 0))
    if re.fullmatch(r"(?:hologram|holo) (?:the |this )?(?:model|part)|put (?:the |this )?model (?:in|on) the (?:hologram|pyramid)", t):
        return ("cad_holo", None)
    if re.fullmatch(r"how (?:big|large|tall|wide|long) is (?:it|this|the model|the part)|(?:what are the |give me the )?dimensions", t):
        return ("cad_size", None)
    if re.fullmatch(r"what(?:'s| is) (?:this part|selected|that part)|which part is (?:this|that)", t):
        return ("cad_part", None)
    if re.fullmatch(r"(?:save|take) (?:a )?(?:picture|screenshot|render|snapshot) of (?:it|the model|this)", t):
        return ("cad_cmd", ("snapshot", 1))
    if re.fullmatch(r"(?:close|exit|quit) (?:the )?(?:model|cad|cad mode|viewer)|cad (?:mode )?off", t):
        return ("cad_close", None)
    return None
