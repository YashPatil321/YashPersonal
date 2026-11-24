"""
Screen control from the command line, for Claude (with full access) and for you.

  python jarvis_ctl.py windows                     every open window: app and title
  python jarvis_ctl.py focus chrome                bring an app (or a window whose title matches) to the front
  python jarvis_ctl.py snap spotify right          zones: left right full center "left third" "right quarter" ...
  python jarvis_ctl.py maximize code | minimize discord | close notepad
  python jarvis_ctl.py keys ctrl+t                 any shortcut: ctrl+shift+t, alt+f4, win+d, enter, f5 ...
  python jarvis_ctl.py type "hello there"          types into the window in front
  python jarvis_ctl.py names                       buttons, links, tabs and menus in the window in front
  python jarvis_ctl.py click "sign in"             clicks the best matching one
  python jarvis_ctl.py clickxy 1200 640            clicks a screen position (pixels)
  python jarvis_ctl.py tabs                        browser tabs
  python jarvis_ctl.py tab-switch gmail | tab-close youtube [--all] | tab-close-others
  python jarvis_ctl.py open https://... | open spotify
  python jarvis_ctl.py screenshot [path]           saves a picture of every screen and prints the path (read it to see)

  Seeing and acting precisely (use these for anything on screen):
  python jarvis_ctl.py look [--ocr]                a screenshot with a coordinate grid (labels are real screen pixels)
                                                   plus a numbered list of what's clickable or typeable in the window in
                                                   front, each with its position (plus text read off the screen when the
                                                   app hides its buttons, or with --ocr). Read the image, then act.
  python jarvis_ctl.py clicknum 12                 clicks item 12 from the last look (the surest way to click)
  python jarvis_ctl.py typeinto 7 "hello"          clicks item 7 (a text box) and types into it
  python jarvis_ctl.py read                        the text in the window in front (a web page, a doc, a chat)
  python jarvis_ctl.py wait "Sign in" [seconds]    waits until something with that name shows up
  python jarvis_ctl.py double 800 400 | right 800 400 | move 800 400
  python jarvis_ctl.py drag 300 300 900 300        press, move, release
  python jarvis_ctl.py scroll down 5 [x y]         scroll (up or down, in notches) where the mouse is or at x y
  After every action, look again to check it worked before you say it's done.
  python jarvis_ctl.py camera [path]               saves a photo from the webcam (what Yash is doing) and prints the path
"""

import os
import re
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)

import jarvis_screen as S   # noqa: E402

VK_NAMES = {"ctrl": "CONTROL", "control": "CONTROL", "shift": "SHIFT", "alt": "MENU", "win": "LWIN", "windows": "LWIN",
            "enter": "RETURN", "return": "RETURN", "tab": "TAB", "esc": "ESCAPE", "escape": "ESCAPE", "space": "SPACE",
            "backspace": "BACK", "delete": 0x2E, "del": 0x2E, "home": 0x24, "end": 0x23, "pageup": "PRIOR", "pagedown": "NEXT",
            "up": 0x26, "down": 0x28, "left": 0x25, "right": 0x27, "insert": 0x2D, "printscreen": 0x2C}


def chord(spec):
    names = []
    for part in spec.lower().replace(" ", "").split("+"):
        if part in VK_NAMES:
            names.append(VK_NAMES[part])
        elif re.fullmatch(r"f([1-9]|1[0-9]|2[0-4])", part):
            names.append(0x6F + int(part[1:]))
        elif len(part) == 1:
            names.append(part.upper())
        else:
            raise SystemExit(f"unknown key: {part}")
    return names


def press(names):
    if not S.IS_WIN:
        print("keys:", names)
        return
    import ctypes
    u = ctypes.windll.user32
    codes = [n if isinstance(n, int) else S.VK[n] if n in S.VK else ord(n) for n in names]
    for c in codes:
        u.keybd_event(c, 0, 0, 0)
    for c in reversed(codes):
        u.keybd_event(c, 0, 2, 0)


def find_window(sc, q):
    h = sc.find(q.lower())
    if h:
        return h
    ql = q.lower()
    for hh, exe, title in sc.windows():
        if ql in title.lower() or ql in exe:
            return hh
    return None


LOOK_FILE = os.path.join(HERE, ".cache", "look.json")


def dpi_aware():
    """Real pixels everywhere (otherwise Windows scaling makes clicks land in the wrong place)."""
    if S.IS_WIN:
        import ctypes
        try:
            ctypes.windll.shcore.SetProcessDpiAwareness(2)
        except Exception:
            try:
                ctypes.windll.user32.SetProcessDPIAware()
            except Exception:
                pass


def mouse(action, x=None, y=None):
    if not S.IS_WIN:
        print("mouse:", action, x, y)
        return
    import ctypes
    u = ctypes.windll.user32
    if x is not None:
        u.SetCursorPos(int(x), int(y))
        time.sleep(0.03)
    flags = {"left": (0x0002, 0x0004), "right": (0x0008, 0x0010)}
    if action in ("click", "double", "right"):
        down, up = flags["right" if action == "right" else "left"]
        for _ in range(2 if action == "double" else 1):
            u.mouse_event(down, 0, 0, 0, 0)
            u.mouse_event(up, 0, 0, 0, 0)
            time.sleep(0.06)


def elements(limit=150):
    """[(n, type, name, x, y)] things you can click or type into in the window in front, with their centers."""
    import jarvis_uia
    auto = jarvis_uia._auto()
    kinds = set(jarvis_uia.CLICKABLE) | {"EditControl", "DocumentControl"}
    out = []
    for c, _ in auto.WalkControl(auto.GetForegroundControl(), maxDepth=30):
        try:
            if c.ControlTypeName not in kinds or c.IsOffscreen:
                continue
            r = c.BoundingRectangle
            if r.width() <= 2 or r.height() <= 2:
                continue
            name = (c.Name or c.AutomationId or "").strip().replace("\n", " ")[:70]
            if not name and c.ControlTypeName not in ("EditControl",):
                continue
            out.append((len(out) + 1, c.ControlTypeName.replace("Control", ""), name, (r.left + r.right) // 2, (r.top + r.bottom) // 2))
        except Exception:
            continue
        if len(out) >= limit:
            break
    return out


def ocr_items(img, ox, oy, start, limit=120):
    """Words and lines read off the screen with Windows' own OCR, for apps the element list can't see into
    (games, canvas apps, remote desktops, images). [(n, 'Text', words, x, y)] in real screen pixels."""
    try:
        import winocr
    except ImportError:
        return []
    try:
        res = winocr.recognize_pil_sync(img, "en") if hasattr(winocr, "recognize_pil_sync") else None
        if res is None:
            import asyncio
            res = asyncio.run(winocr.recognize_pil(img, "en"))
        lines = res.get("lines", []) if isinstance(res, dict) else getattr(res, "lines", [])
    except Exception as e:
        print(f"(OCR failed: {e})")
        return []
    out = []
    for ln in lines:
        words = ln.get("words", []) if isinstance(ln, dict) else getattr(ln, "words", [])
        text = (ln.get("text") if isinstance(ln, dict) else getattr(ln, "text", "")) or ""
        rects = []
        for w in words:
            r = w.get("bounding_rect") if isinstance(w, dict) else getattr(w, "bounding_rect", None)
            if r:
                g = (lambda k: r.get(k) if isinstance(r, dict) else getattr(r, k))
                rects.append((g("x"), g("y"), g("width"), g("height")))
        if not text.strip() or not rects:
            continue
        x1, y1 = min(r[0] for r in rects), min(r[1] for r in rects)
        x2, y2 = max(r[0] + r[2] for r in rects), max(r[1] + r[3] for r in rects)
        out.append((start + len(out), "Text", text.strip()[:70], int(ox + (x1 + x2) / 2), int(oy + (y1 + y2) / 2)))
        if len(out) >= limit:
            break
    return out


def look(path=None):
    """Screenshot with a labeled grid in real screen coordinates, plus the numbered element list."""
    from PIL import ImageGrab, ImageDraw, ImageFont
    import json
    path = path or os.path.join(HERE, ".cache", "look.png")
    os.makedirs(os.path.dirname(path), exist_ok=True)
    img = ImageGrab.grab(all_screens=True)
    ox = oy = 0
    if S.IS_WIN:
        import ctypes
        ox, oy = ctypes.windll.user32.GetSystemMetrics(76), ctypes.windll.user32.GetSystemMetrics(77)
    d = ImageDraw.Draw(img)
    try:
        font = ImageFont.truetype("arial.ttf", 22)
    except Exception:
        font = ImageFont.load_default()
    step = 200
    for gx in range((ox // step) * step, ox + img.width, step):
        d.line([(gx - ox, 0), (gx - ox, img.height)], fill=(255, 80, 60), width=1)
        for gy in range((oy // step) * step, oy + img.height, step * 2):
            d.text((gx - ox + 3, gy - oy + 3), f"{gx},{gy}", fill=(255, 220, 0), font=font)
    for gy in range((oy // step) * step, oy + img.height, step):
        d.line([(0, gy - oy), (img.width, gy - oy)], fill=(255, 80, 60), width=1)
    try:
        els = elements()
    except Exception as e:
        els = []
        print(f"(couldn't list elements: {e})")
    if len(els) < 12 or "--ocr" in sys.argv:   # the app hides its buttons from Windows: read the screen instead
        els += ocr_items(img.copy(), ox, oy, len(els) + 1)
    for n, kind, name, x, y in els:   # number badges on the picture, so it's easy to match
        d.rectangle([x - ox - 14, y - oy - 12, x - ox + 14, y - oy + 12], outline=(0, 255, 160), width=2)
        d.text((x - ox - 10, y - oy - 11), str(n), fill=(0, 255, 160), font=font)
    if img.width > 2400:
        img = img.resize((2400, int(img.height * 2400 / img.width)))
    img.save(path)
    with open(LOOK_FILE, "w", encoding="utf-8") as f:
        json.dump(els, f)
    print(path)
    print("Grid labels and positions below are real screen pixels (use them with clickxy, double, drag...).")
    for n, kind, name, x, y in els:
        print(f"[{n}] {kind} '{name}' at {x},{y}")
    return path


def element_xy(n):
    import json
    with open(LOOK_FILE, encoding="utf-8") as f:
        for e in json.load(f):
            if e[0] == int(n):
                return e[3], e[4], e[2]
    raise SystemExit(f"no item {n} in the last look, run look again")


def read_text(limit=12000):
    """The readable text of the window in front, top to bottom."""
    import jarvis_uia
    auto = jarvis_uia._auto()
    seen, out, total = set(), [], 0
    for c, _ in auto.WalkControl(auto.GetForegroundControl(), maxDepth=40):
        try:
            if c.ControlTypeName not in ("TextControl", "DocumentControl", "EditControl", "HyperlinkControl", "ListItemControl", "HeaderControl"):
                continue
            t = (c.Name or "").strip()
            if not t and c.ControlTypeName in ("EditControl", "DocumentControl"):
                try:
                    t = (c.GetValuePattern().Value or "").strip()
                except Exception:
                    t = ""
            if t and t not in seen and len(t) > 1:
                seen.add(t)
                out.append(t)
                total += len(t)
        except Exception:
            continue
        if total > limit:
            break
    return "\n".join(out)[:limit]


def main(argv):
    if not argv or argv[0] in ("help", "-h", "--help"):
        print(__doc__)
        return 0
    cmd, args = argv[0], argv[1:]
    dpi_aware()
    if cmd == "look":
        look(args[0] if args else None)
        return 0
    if cmd == "clicknum":
        x, y, name = element_xy(args[0])
        mouse("click", x, y)
        print(f"clicked [{args[0]}] {name} at {x},{y}")
        return 0
    if cmd == "typeinto":
        x, y, name = element_xy(args[0])
        mouse("click", x, y)
        time.sleep(0.15)
        S.Screen().type_text(" ".join(args[1:]))
        print(f"typed into [{args[0]}] {name}")
        return 0
    if cmd in ("double", "right", "move"):
        mouse("double" if cmd == "double" else "right" if cmd == "right" else "move", int(args[0]), int(args[1]))
        print(f"{cmd} at {args[0]},{args[1]}")
        return 0
    if cmd == "drag":
        x1, y1, x2, y2 = map(int, args[:4])
        if S.IS_WIN:
            import ctypes
            u = ctypes.windll.user32
            u.SetCursorPos(x1, y1)
            u.mouse_event(0x0002, 0, 0, 0, 0)
            for i in range(1, 21):   # move in steps so apps see a real drag
                u.SetCursorPos(x1 + (x2 - x1) * i // 20, y1 + (y2 - y1) * i // 20)
                time.sleep(0.015)
            u.mouse_event(0x0004, 0, 0, 0, 0)
        print(f"dragged {x1},{y1} to {x2},{y2}")
        return 0
    if cmd == "scroll":
        way = args[0] if args else "down"
        n = int(args[1]) if len(args) > 1 else 3
        if len(args) > 3:
            mouse("move", int(args[2]), int(args[3]))
        if S.IS_WIN:
            import ctypes
            ctypes.windll.user32.mouse_event(0x0800, 0, 0, (120 if way == "up" else -120) * n, 0)
        print(f"scrolled {way} {n}")
        return 0
    if cmd == "read":
        print(read_text())
        return 0
    if cmd == "wait":
        import jarvis_uia
        q, secs = args[0], float(args[1]) if len(args) > 1 else 10
        end = time.time() + secs
        while time.time() < end:
            if jarvis_uia.find_clickable(q) or q.lower() in read_text(4000).lower():
                print(f"found {q}")
                return 0
            time.sleep(0.5)
        print(f"{q} didn't show up in {secs:.0f} seconds")
        return 1
    sc = S.Screen()
    if cmd == "windows":
        for h, exe, title in sc.windows():
            print(f"{exe:28} {title[:100]}")
    elif cmd in ("focus", "maximize", "minimize", "close", "snap"):
        if not args:
            raise SystemExit(f"{cmd} what?")
        h = find_window(sc, args[0])
        if not h:
            raise SystemExit(f"no window for {args[0]}")
        if cmd == "focus":
            print("focused" if sc.focus(h) else "Windows blocked bringing it to the front")
        elif cmd in ("maximize", "minimize"):
            sc.show(h, "max" if cmd == "maximize" else "min")
        elif cmd == "close":
            if S.IS_WIN:
                import ctypes
                ctypes.windll.user32.PostMessageW(h, 0x0010, 0, 0)   # WM_CLOSE: asks it to close, like the X
        else:
            zone = " ".join(args[1:]) or "left"
            if zone not in S.ZONES:
                raise SystemExit("zones: " + ", ".join(S.ZONES))
            sc.place(h, S.zone_rect(sc.work_area(h), zone))
        for p in sc.problems:
            print("problem:", p)
    elif cmd == "keys":
        press(chord(" ".join(args)))
    elif cmd == "type":
        sc.type_text(" ".join(args))
    elif cmd == "names":
        import jarvis_uia
        print("\n".join(jarvis_uia.visible_names(120)))
    elif cmd == "click":
        import jarvis_uia
        name = jarvis_uia.click(" ".join(args))
        print(f"clicked {name}" if name else "nothing matching in the window in front")
    elif cmd == "clickxy":
        x, y = int(args[0]), int(args[1])
        if S.IS_WIN:
            import ctypes
            u = ctypes.windll.user32
            u.SetCursorPos(x, y)
            u.mouse_event(0x0002, 0, 0, 0, 0)
            u.mouse_event(0x0004, 0, 0, 0, 0)
        print(f"clicked {x},{y}")
    elif cmd == "tabs":
        import jarvis_uia
        for _, _, title in jarvis_uia.Tabs().list():
            print(title)
    elif cmd == "tab-switch":
        import jarvis_uia
        print(jarvis_uia.Tabs().switch(" ".join(args)) or "no matching tab")
    elif cmd == "tab-close":
        import jarvis_uia
        every = "--all" in args
        q = " ".join(a for a in args if a != "--all")
        closed = jarvis_uia.Tabs().close(q, every)
        print("closed: " + "; ".join(closed) if closed else "no matching tab")
    elif cmd == "tab-close-others":
        import jarvis_uia
        print(f"closed {jarvis_uia.Tabs().close_others()}")
    elif cmd == "open":
        target = " ".join(args)
        if S.IS_WIN:
            os.startfile(target)
        print("opened", target)
    elif cmd == "camera":
        path = args[0] if args else os.path.join(HERE, ".cache", "camera_ctl.jpg")
        os.makedirs(os.path.dirname(path), exist_ok=True)
        got = None
        try:   # Jarvis holds the camera, so ask it for the picture
            import urllib.request
            import jarvis_phone
            url = f"http://127.0.0.1:{jarvis_phone.PHONE_PORT}/camera.jpg?token={jarvis_phone.token()}"
            opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))
            data = opener.open(url, timeout=10).read()
            with open(path, "wb") as f:
                f.write(data)
            got = path
        except Exception:
            import jarvis_vision   # Jarvis isn't running the camera: grab a frame directly
            got = jarvis_vision.grab_frame(path)
        print(got or "no camera picture: the camera is off, unplugged, or in use")
    elif cmd == "screenshot":
        import jarvis_extras
        path = jarvis_extras.screenshot(args[0] if args else os.path.join(HERE, ".cache", "screen.png"))
        print(path)
    else:
        print(__doc__)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
