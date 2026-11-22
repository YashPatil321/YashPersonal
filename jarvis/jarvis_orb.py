"""
The Jarvis orb: a small ring of dots in the corner of your screen, in the same dot style as HQ.

  idle       dim ember ring, one dot slowly breathing (Jarvis is running and listening for the wake word)
  listening  the whole ring lights up and pulses (talk now)
  thinking   a comet of dots spins (transcribing or asking Claude)
  speaking   the ring ripples like a sound wave
  error      amber, for a few seconds
  off        disappears

Always on top, ignores clicks (they go straight through to whatever is under it), no taskbar icon.
Jarvis starts it automatically. Run on its own to test: python jarvis_orb.py --demo
Jarvis talks to it over a local UDP port; nothing leaves the PC.
"""

import math
import socket
import sys
import time

PORT = 47777
SIZE = 72            # pixels
MARGIN = 18          # from the screen edge
CORNER = "bottom right"   # top left, top right, bottom left, bottom right
N = 18               # dots in the ring
KEY = "#010101"      # transparent color

COL = {"idle": ("#5e3e35", "#ad8679"), "listening": ("#ff5a43", "#fff1ea"), "thinking": ("#ff8a6e", "#fff1ea"),
       "speaking": ("#ff5a43", "#ffd2c4"), "error": ("#ffb84d", "#ffe3b0")}


LAST = {"state": "idle", "t": 0.0}   # the projected desk and hologram read this


def send(state):
    """Called from Jarvis. Silent if the orb isn't running."""
    import time as _t
    LAST.update(state=state, t=_t.time())
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.sendto(state.encode(), ("127.0.0.1", PORT))
        s.close()
    except Exception:
        pass


def mix(a, b, t):
    a, b = [int(a[i:i + 2], 16) for i in (1, 3, 5)], [int(b[i:i + 2], 16) for i in (1, 3, 5)]
    return "#%02x%02x%02x" % tuple(int(a[i] + (b[i] - a[i]) * max(0, min(1, t))) for i in range(3))


def run(demo=False):
    import tkinter as tk
    root = tk.Tk()
    root.overrideredirect(True)
    root.attributes("-topmost", True)
    try:
        root.attributes("-transparentcolor", KEY)
    except tk.TclError:
        pass
    sw, sh = root.winfo_screenwidth(), root.winfo_screenheight()
    x = MARGIN if "left" in CORNER else sw - SIZE - MARGIN
    y = MARGIN if "top" in CORNER else sh - SIZE - MARGIN - 48   # clear of the taskbar
    root.geometry(f"{SIZE}x{SIZE}+{x}+{y}")
    c = tk.Canvas(root, width=SIZE, height=SIZE, bg=KEY, highlightthickness=0)
    c.pack()
    if sys.platform == "win32":
        import ctypes
        hwnd = ctypes.windll.user32.GetParent(root.winfo_id())
        ex = ctypes.windll.user32.GetWindowLongW(hwnd, -20)
        ctypes.windll.user32.SetWindowLongW(hwnd, -20, ex | 0x80000 | 0x20 | 0x80)   # layered, click through, tool window

    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    sock.bind(("127.0.0.1", PORT))
    sock.setblocking(False)
    st = {"state": "idle", "since": time.time()}
    R, r0 = SIZE / 2 - 8, 3.2
    dots = []
    for i in range(N):
        a = i / N * 2 * math.pi - math.pi / 2
        cx, cy = SIZE / 2 + R * math.cos(a), SIZE / 2 + R * math.sin(a)
        dots.append((c.create_oval(cx - r0, cy - r0, cx + r0, cy + r0, outline="", fill=COL["idle"][0]), cx, cy))
    core = c.create_oval(SIZE / 2 - 4, SIZE / 2 - 4, SIZE / 2 + 4, SIZE / 2 + 4, outline="", fill=COL["idle"][0])
    demo_seq = ["idle", "listening", "thinking", "speaking", "error"]

    def frame():
        try:
            while True:
                msg = sock.recv(64).decode().strip()
                if msg == "quit":
                    root.destroy()
                    return
                if msg.startswith("hold:"):
                    st["hold"], st["hold_t"] = float(msg[5:]), time.time()
                elif msg.startswith("gesture:"):
                    st["flash"], st["flash_t"] = msg[8:], time.time()
                else:
                    st["state"], st["since"] = msg, time.time()
        except BlockingIOError:
            pass
        except Exception:
            pass
        t = time.time()
        if demo:
            st["state"] = demo_seq[int(t / 2.5) % len(demo_seq)]
        s = st["state"]
        if s == "error" and t - st["since"] > 4:
            s = st["state"] = "idle"
        if s == "off":
            root.withdraw()
        else:
            root.deiconify()
            base, hi = COL.get(s, COL["idle"])
            for i, (d, cx, cy) in enumerate(dots):
                if s == "idle":
                    k = 0.15 + 0.35 * max(0, math.sin(t * 1.2)) * (i == int(t / 3) % N)
                elif s == "listening":
                    k = 0.65 + 0.35 * math.sin(t * 6)
                elif s == "thinking":
                    k = max(0.0, 1 - ((i - t * 14) % N) / 6)
                elif s == "speaking":
                    k = 0.45 + 0.55 * max(0, math.sin(t * 9 + i * 0.9)) * (0.6 + 0.4 * math.sin(t * 3.1 + i))
                else:
                    k = 0.8
                c.itemconfig(d, fill=mix(base, hi, k))
                sz = r0 * (1 + (0.35 * k if s != "idle" else 0))
                c.coords(d, cx - sz, cy - sz, cx + sz, cy + sz)
            c.itemconfig(core, fill=mix(base, hi, 0.9 if s in ("listening", "speaking") else 0.25))
            # hand feedback on top: the ring fills clockwise while you hold a gesture, and flashes when one fires
            if t - st.get("hold_t", 0) < 0.25:
                lit = int(st["hold"] * N + 0.5)
                for i, (d, cx, cy) in enumerate(dots):
                    if i < lit:
                        c.itemconfig(d, fill="#fff1ea")
            ft = t - st.get("flash_t", 0)
            if ft < 0.6:
                g = st.get("flash", "")
                for i, (d, cx, cy) in enumerate(dots):
                    if g in ("swipe_right", "swipe_left", "dial_up", "dial_down"):
                        # a wave of light running the way you moved
                        pos = (i / N) if g in ("swipe_right", "dial_up") else 1 - i / N
                        k = max(0.0, 1 - abs(pos - ft / 0.5) * 4)
                    else:
                        k = 1 - ft / 0.6
                    if k > 0.05:
                        c.itemconfig(d, fill=mix("#ff5a43", "#ffffff", k))
        root.after(33, frame)

    frame()
    root.mainloop()


if __name__ == "__main__":
    if "--quit" in sys.argv:
        send("quit")
    else:
        run(demo="--demo" in sys.argv)
