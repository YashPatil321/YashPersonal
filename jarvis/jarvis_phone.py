"""
Jarvis and your iPhone, both ways.

PC -> phone (needs the free ntfy app and NTFY_TOPIC):
  "set an alarm on my phone for 6:45", "put my phone on do not disturb for an hour",
  "remind me on my phone to text coach", "timer on my phone for 10 minutes",
  "find my phone", "send this to my phone".
  Apple doesn't let any app set alarms on your phone remotely, so Jarvis sends a push and you tap it once.
  The tap runs your "Jarvis Do" shortcut, which does the real thing on the phone.

Phone -> Jarvis (needs the phone on home WiFi, or Tailscale away from home):
  A small server on your PC that only answers your home network and needs a secret token.
  "Hey Siri, Jarvis" runs a shortcut that asks you what you want, sends it here, and Siri reads the answer.
  Automations on the phone tell Jarvis when you get home, leave, stop your alarm, or go to bed.

Run `python jarvis.py --phone` on the PC for your links and step by step shortcut setup.
"""

import ipaddress
import json
import os
import re
import secrets
import socket
import sys
import threading
import time
import urllib.parse
import urllib.request
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

HERE = os.path.dirname(os.path.abspath(__file__))

# ---------------- settings (override in local_settings.py) ----------------
NTFY_TOPIC = ""              # same topic as in jarvis.py. The ntfy app on your iPhone subscribes to it
PHONE_SHORTCUT = "Jarvis Do" # the shortcut on your phone that a tap runs
PHONE_SERVER = True          # let your phone talk to Jarvis over home WiFi
PHONE_PORT = 8766
ALLOW_TAILSCALE = True       # also answer Tailscale addresses (100.64.0.0/10), for talking to Jarvis away from home
MIRROR_TO_PHONE = True       # when you're away from the desk, leave reminders and important mail also go to your phone
TOKEN_FILE = os.path.join(HERE, ".phone_token")
# ---------------------------------------------------------------------------


def _log(msg):
    print(time.strftime("[%H:%M:%S] ") + "phone: " + str(msg), flush=True)


def token():
    try:
        with open(TOKEN_FILE) as f:
            t = f.read().strip()
            if t:
                return t
    except Exception:
        pass
    t = secrets.token_urlsafe(18)
    with open(TOKEN_FILE, "w") as f:
        f.write(t)
    return t


def lan_ip():
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try:
        s.connect(("10.255.255.255", 1))
        return s.getsockname()[0]
    except Exception:
        return "127.0.0.1"
    finally:
        s.close()


def allowed_client(ip):
    try:
        a = ipaddress.ip_address(ip)
    except ValueError:
        return False
    if a.is_loopback or a.is_private:
        return True
    return ALLOW_TAILSCALE and a in ipaddress.ip_network("100.64.0.0/10")


# ================= PC -> phone =================
def shortcut_url(command):
    return ("shortcuts://run-shortcut?name=" + urllib.parse.quote(PHONE_SHORTCUT) + "&input=text&text=" + urllib.parse.quote(command))


def push(text, title="Jarvis", click=None, priority=3, tags="robot", topic=None, opener=urllib.request.urlopen):
    topic = topic or NTFY_TOPIC
    if not topic:
        return False
    headers = {"Title": title, "Priority": str(priority), "Tags": tags}
    if click:
        headers["Click"] = click
    try:
        opener(urllib.request.Request("https://ntfy.sh/" + topic, data=text.encode("utf-8"), headers=headers), timeout=8)
        return True
    except Exception as e:
        _log(f"push failed: {e}")
        return False


def hhmm_text(hm):
    h, m = int(hm[:2]), hm[3:]
    return f"{h % 12 or 12}:{m} {'AM' if h < 12 else 'PM'}"


def _num(s):
    words = {"a": 1, "an": 1, "one": 1, "two": 2, "three": 3, "five": 5, "ten": 10, "fifteen": 15, "twenty": 20, "thirty": 30,
             "forty five": 45, "half an": 0.5, "an hour": 60}
    s = (s or "").strip()
    if s in words:
        return words[s]
    m = re.search(r"\d+(\.\d+)?", s)
    return float(m.group(0)) if m else None


def parse_clock(h, mm, ap):
    h, mm = int(h), int(mm or 0)
    ap = (ap or "").replace(" ", "")
    if ap == "pm" and h < 12:
        h += 12
    if ap in ("am", "inthemorning") and h == 12:
        h = 0
    return f"{h:02d}:{mm:02d}"


def route_phone(t):
    if "phone" not in t:
        return None
    m = re.search(r"\b(?:set )?(?:an |my )?alarm on my phone (?:for |at )?(\d{1,2})(?:[: ](\d\d))? ?(am|pm|a m|p m|in the morning)?|"
                  r"\bphone alarm (?:for |at )?(\d{1,2})(?:[: ](\d\d))? ?(am|pm|a m|p m)?|"
                  r"\bwake me up at (\d{1,2})(?:[: ](\d\d))? ?(am|pm|a m|p m|in the morning)? on my phone", t)
    if m:
        g = [x for x in m.groups()]
        trip = next(g[i:i + 3] for i in (0, 3, 6) if g[i])
        return ("phone", ("alarm", parse_clock(*trip)))
    m = re.search(r"\b(?:put |turn |set )?my phone (?:on |to )?(?:do not disturb|dnd|focus)(?: mode)?(?: for (.+?) (minutes?|hours?))?$", t)
    if m:
        mins = 60 if not m.group(1) else int((_num(m.group(1)) or 1) * (60 if m.group(2)[0] == "h" else 1))
        return ("phone", ("dnd", mins))
    if re.search(r"\b(?:turn off|take my phone off) (?:do not disturb|dnd|focus)\b|\bmy phone off (?:do not disturb|dnd)\b", t):
        return ("phone", ("dnd_off", None))
    m = re.search(r"\btimer on my phone (?:for )?(.+?) (seconds?|minutes?|hours?)\b|\bphone timer (?:for )?(.+?) (seconds?|minutes?|hours?)\b", t)
    if m:
        n, unit = (m.group(1), m.group(2)) if m.group(1) else (m.group(3), m.group(4))
        if _num(n) is not None:
            return ("phone", ("timer", int(_num(n) * {"s": 1, "m": 60, "h": 3600}[unit[0]])))
    m = re.fullmatch(r"remind me on my phone (?:to |that |about )?(.+?)(?: (?:at (\d{1,2})(?:[: ](\d\d))? ?(am|pm|a m|p m)?|in (.+?) (minutes?|hours?)))?", t)
    if m:
        what = m.group(1)
        when = ""
        if m.group(2):
            when = parse_clock(m.group(2), m.group(3), m.group(4))
        elif m.group(5) and _num(m.group(5)) is not None:
            when = time.strftime("%H:%M", time.localtime(time.time() + _num(m.group(5)) * (60 if m.group(6)[0] == "m" else 3600)))
        return ("phone", ("remind", (what, when)))
    if re.search(r"\b(?:find|ring|ping|where'?s|where is) my phone\b", t):
        return ("phone", ("find", None))
    m = re.fullmatch(r"send (?:this|that|it|my clipboard) to my phone|(?:send|text) my phone (.+)", t)
    if m:
        return ("phone", ("send", m.group(1)))
    if re.search(r"\b(?:set up|connect) my phone\b|\bphone setup\b", t):
        return ("phone", ("setup", None))
    return None


class Phone:
    def __init__(self, say, clipboard=None):
        self.say, self.clipboard = say, clipboard

    def handle(self, arg):
        kind, val = arg
        say = self.say
        if not NTFY_TOPIC and kind != "setup":
            return say("Your phone isn't connected yet. Install ntfy on your iPhone and set NTFY_TOPIC. Run jarvis dot py dash dash phone on the PC for the steps.")
        if kind == "alarm":
            ok = push(f"Tap to set your alarm for {hhmm_text(val)}", "Alarm " + hhmm_text(val), shortcut_url(f"alarm|{val}|Jarvis"), 4, "alarm_clock")
            say(f"Sent to your phone. Tap it to set the {hhmm_text(val)} alarm." if ok else "I couldn't reach your phone.")
        elif kind == "dnd":
            until = time.strftime("%H:%M", time.localtime(time.time() + val * 60))
            ok = push(f"Tap for Do Not Disturb until {hhmm_text(until)}", "Do Not Disturb", shortcut_url(f"dnd|{until}"), 4, "no_bell")
            say("Tap the notification to turn on Do Not Disturb." if ok else "I couldn't reach your phone.")
        elif kind == "dnd_off":
            ok = push("Tap to turn Do Not Disturb off", "Do Not Disturb off", shortcut_url("dnd_off"), 4, "bell")
            say("Tap it to turn Do Not Disturb off." if ok else "I couldn't reach your phone.")
        elif kind == "timer":
            mins = max(1, round(val / 60))
            ok = push(f"Tap to start a {mins} minute timer", "Timer", shortcut_url(f"timer|{val}"), 4, "timer_clock")
            say(f"Tap it to start the {mins} minute timer." if ok else "I couldn't reach your phone.")
        elif kind == "remind":
            what, when = val
            cmd = f"remind|{what}|{when}"
            ok = push(what + (f" at {hhmm_text(when)}" if when else ""), "Reminder", shortcut_url(cmd), 4, "pushpin")
            say("Sent. Tap it and it goes in Reminders." if ok else "I couldn't reach your phone.")
        elif kind == "find":
            ok = push("Jarvis is looking for you. Here's your phone.", "FIND MY PHONE", None, 5, "rotating_light,loudspeaker")
            say("Pinging it as loud as I can. If it's on silent, use Find My on icloud dot com." if ok else "I couldn't reach your phone.")
        elif kind == "send":
            text = val or (self.clipboard() if self.clipboard else "")
            if not text:
                return say("There's nothing on your clipboard.")
            link = re.search(r"https?://\S+", text)
            ok = push(text[:3500], "From your PC", link.group(0) if link else None, 3, "computer")
            say("Sent to your phone." if ok else "I couldn't reach your phone.")
        elif kind == "setup":
            say("On the PC, run jarvis dot py dash dash phone. It shows your links and how to build the two shortcuts.")


# ================= phone -> Jarvis =================
class Bridge:
    """ask(text) -> spoken answer as text. event(name) -> text. Only your home network, only with the token."""
    def __init__(self, ask, event, port=None):
        self.ask, self.event, self.port, self.tok = ask, event, port or PHONE_PORT, token()
        self.routes = {}   # extra pages, e.g. the projected desk: path -> fn(handler, params)

    def start(self):
        bridge = self

        class H(BaseHTTPRequestHandler):
            def log_message(self, *a):
                pass

            def _reply(self, code, text):
                body = text.encode("utf-8")
                self.send_response(code)
                self.send_header("Content-Type", "text/plain; charset=utf-8")
                self.send_header("Content-Length", str(len(body)))
                self.end_headers()
                self.wfile.write(body)

            def _params(self):
                u = urllib.parse.urlparse(self.path)
                q = {k: v[0] for k, v in urllib.parse.parse_qs(u.query).items()}
                n = int(self.headers.get("Content-Length") or 0)
                if n:
                    raw = self.rfile.read(min(n, 20000)).decode("utf-8", "ignore")
                    try:
                        q.update({k: str(v) for k, v in json.loads(raw).items()})
                    except Exception:
                        q.setdefault("text", raw)
                return u.path, q

            def _go(self):
                if not allowed_client(self.client_address[0]):
                    return self._reply(403, "Not from your home network.")
                path, q = self._params()
                if not secrets.compare_digest(q.get("token", ""), bridge.tok):
                    return self._reply(401, "Wrong token.")
                try:
                    if path == "/ask":
                        text = (q.get("text") or "").strip()
                        return self._reply(200, bridge.ask(text, q.get("speak") == "1") if text else "Say something after Jarvis.")
                    if path == "/event":
                        return self._reply(200, bridge.event((q.get("name") or "").lower()))
                    if path in bridge.routes:
                        return bridge.routes[path](self, q)
                    if path == "/ping":
                        return self._reply(200, "Jarvis is online.")
                    return self._reply(404, "Unknown.")
                except Exception as e:
                    _log(f"bridge: {e}")
                    return self._reply(500, "Something broke on the PC.")

            do_GET = do_POST = _go

        self.server = ThreadingHTTPServer(("0.0.0.0", self.port), H)
        threading.Thread(target=self.server.serve_forever, daemon=True).start()
        _log(f"phone bridge on http://{lan_ip()}:{self.port}")
        return self


def setup_text():
    ip, tok = lan_ip(), token()
    base = f"http://{ip}:{PHONE_PORT}"
    return f"""
Jarvis phone setup
==================

Your PC: {base}   token: {tok}
Test from your phone's Safari on home WiFi: {base}/ping?token={tok}
(Windows may ask to allow Python on private networks the first time. Say Allow.)

A. PC to phone (alarms, Do Not Disturb, timers, reminders, find my phone)
  1. Install ntfy from the App Store, tap +, and subscribe to your private topic:  {NTFY_TOPIC or "yash-jarvis-" + secrets.token_hex(6)}
  2. That's it, Jarvis already uses that topic. (To use a different one, set NTFY_TOPIC in local_settings.py.)
  3. Shortcuts app, new shortcut named exactly:  {PHONE_SHORTCUT}
       Receive Text input from Share Sheet / Quick Actions (turn on "Show in Share Sheet" is not needed)
       Split Text  (Shortcut Input)  by Custom  |
       Get Item from List  First Item           -> call it Cmd
       Get Item from List  Item at Index 2      -> call it A
       Get Item from List  Item at Index 3      -> call it B
       If Cmd is alarm      -> Create Alarm at A, label B          (Clock app action)
       If Cmd is dnd        -> Set Focus Do Not Disturb On, Until Time A
       If Cmd is dnd_off    -> Set Focus Do Not Disturb Off
       If Cmd is timer      -> Start Timer for A seconds
       If Cmd is remind     -> Add New Reminder A, alert at B (if B has any value)
  Then "set an alarm on my phone for 6:45" sends a push. Tap it and the alarm is set.

B. Phone to Jarvis ("Hey Siri, Jarvis")
  New shortcut named:  Jarvis
       Dictate Text  (Stop Listening: After Pause)
       Get Contents of URL  {base}/ask   Method POST, Request Body JSON:
            token = {tok}
            text  = Dictated Text
       Speak Text  (Contents of URL)
  Now "Hey Siri, Jarvis", then talk. Anything you can say to Jarvis works, and Siri reads the answer.
  Add speak = 1 to the JSON to also have Jarvis say it out loud in your room.

C. Automations (Shortcuts, Automation tab, Run Immediately, notify off)
       Arrive at Home        -> Get Contents of URL  {base}/event?name=home&token={tok}
       Leave Home            -> Get Contents of URL  {base}/event?name=leave&token={tok}
       Alarm is Stopped      -> Get Contents of URL  {base}/event?name=awake&token={tok}
       Sleep Focus turns on  -> Get Contents of URL  {base}/event?name=bed&token={tok}
  Home: Jarvis knows you're back and greets you with that. Awake: your room wakes up and gives the brief.
  Bed: music off, monitors off, tomorrow's first leave time.

Away from home: install Tailscale on the PC and phone, and use the PC's Tailscale address instead of {ip}.
"""
