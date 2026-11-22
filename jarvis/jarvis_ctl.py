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


def main(argv):
    if not argv or argv[0] in ("help", "-h", "--help"):
        print(__doc__)
        return 0
    cmd, args = argv[0], argv[1:]
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
