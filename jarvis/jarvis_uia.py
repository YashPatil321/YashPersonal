"""
Sees and controls what's inside windows: browser tabs, buttons, links, menus. Uses Windows UI Automation,
the same thing screen readers use, through the `uiautomation` package. Windows only.

  "what tabs do I have open"          reads your Chrome or Edge tabs
  "switch to the Gmail tab"           goes to the best matching tab
  "close the YouTube tab"             closes it (just that one)
  "close all YouTube tabs"            closes every match
  "close the other tabs"              keeps the one you're on
  "click sign in" / "click the play button" / "press the submit button"
                                      clicks the matching button, link, tab or menu item in the window in front
"""

import re
import sys
import time

IS_WIN = sys.platform == "win32"
BROWSER_CLASSES = ("Chrome_WidgetWin_1",)   # Chrome, Edge, Brave, Arc, VS Code all use this class
CLICKABLE = ("ButtonControl", "HyperlinkControl", "MenuItemControl", "TabItemControl", "ListItemControl", "CheckBoxControl",
             "RadioButtonControl", "SplitButtonControl", "TreeItemControl", "ComboBoxControl")
STOP = {"the", "a", "an", "tab", "tabs", "my", "me", "that", "this", "one", "page", "button", "link", "on", "in", "chrome", "edge", "please"}


def _auto():
    import uiautomation as auto   # pip install uiautomation (installed with the other extras)
    return auto


def words(s):
    return [w for w in re.findall(r"[a-z0-9]+", (s or "").lower()) if w not in STOP]


def score(query, title):
    """How well a spoken name matches a tab title or button name. 0 = no match."""
    q, t = words(query), (title or "").lower()
    if not q:
        return 0
    hits = sum(1 for w in q if re.search(r"\b" + re.escape(w), t))
    if hits < len(q) and not (len(q) > 2 and hits >= len(q) - 1):
        return 0
    return hits * 10 - len(t) / 100 + (5 if t.startswith(q[0]) else 0)


def best(query, items, key=lambda x: x):
    ranked = sorted(((score(query, key(i)), n, i) for n, i in enumerate(items)), key=lambda x: (-x[0], x[1]))
    return [i for s, _, i in ranked if s > 0]


def clean_title(name):
    return re.sub(r"\s+-\s+(Memory usage|Audio playing|Camera or microphone recording|Pinned).*$", "", name or "").strip()


# ================= tabs =================
class Tabs:
    """Chrome and Edge tabs, through UI Automation."""
    def windows(self):
        auto = _auto()
        out = []
        for w in auto.GetRootControl().GetChildren():
            try:
                if w.ClassName in BROWSER_CLASSES and w.Name and ("Chrome" in w.Name or "Edge" in w.Name or "Brave" in w.Name):
                    out.append(w)
            except Exception:
                continue
        return out

    def list(self):
        """[(window, tab_control, title)] for every tab in every browser window."""
        auto = _auto()
        out = []
        for w in self.windows():
            for c, _ in auto.WalkControl(w, maxDepth=14):
                if c.ControlTypeName == "TabItemControl" and c.Name:
                    out.append((w, c, clean_title(c.Name)))
        return out

    def switch(self, query):
        hits = best(query, self.list(), key=lambda t: t[2])
        if not hits:
            return None
        w, tab, title = hits[0]
        w.SetActive()
        try:
            tab.GetSelectionItemPattern().Select()
        except Exception:
            tab.Click(simulateMove=False)
        return title

    def close(self, query, every=False):
        hits = best(query, self.list(), key=lambda t: t[2])
        if not hits:
            return []
        closed = []
        for w, tab, title in (hits if every else hits[:1]):
            if self._close_one(w, tab):
                closed.append(title)
            time.sleep(0.15)
        return closed

    def _close_one(self, w, tab):
        auto = _auto()
        btn = None
        for c, _ in auto.WalkControl(tab, maxDepth=3):   # the little x on the tab
            if c.ControlTypeName == "ButtonControl" and (c.Name or "").lower().startswith("close"):
                btn = c
                break
        try:
            if btn:
                btn.GetInvokePattern().Invoke()
                return True
        except Exception:
            pass
        try:   # no x button (pinned or narrow tab): select it, then Ctrl+W
            w.SetActive()
            tab.GetSelectionItemPattern().Select()
            time.sleep(0.15)
            auto.SendKeys("{Ctrl}w", waitTime=0.05)
            return True
        except Exception:
            return False

    def close_others(self):
        tabs = self.list()
        n = 0
        for w, tab, title in tabs:
            try:
                if tab.GetSelectionItemPattern().IsSelected:
                    continue
            except Exception:
                continue
            if self._close_one(w, tab):
                n += 1
        return n


# ================= click anything by name =================
def find_clickable(query, root=None, max_depth=25):
    """The best matching button, link, menu item or tab in the window in front (or root)."""
    auto = _auto()
    root = root or auto.GetForegroundControl()
    items = []
    for c, _ in auto.WalkControl(root, maxDepth=max_depth):
        try:
            if c.ControlTypeName in CLICKABLE and c.Name and not c.IsOffscreen:
                items.append(c)
        except Exception:
            continue
        if len(items) > 4000:
            break
    hits = best(query, items, key=lambda c: c.Name)
    return hits[0] if hits else None


def click(query):
    c = find_clickable(query)
    if not c:
        return None
    for pattern in ("GetInvokePattern", "GetSelectionItemPattern", "GetTogglePattern", "GetExpandCollapsePattern"):
        try:
            p = getattr(c, pattern)()
            if p:
                {"GetInvokePattern": lambda: p.Invoke(), "GetSelectionItemPattern": lambda: p.Select(),
                 "GetTogglePattern": lambda: p.Toggle(), "GetExpandCollapsePattern": lambda: p.Expand()}[pattern]()
                return c.Name
        except Exception:
            continue
    c.Click(simulateMove=False)
    return c.Name


def visible_names(limit=60):
    """Names of the clickable things in the window in front, for Claude to read."""
    auto = _auto()
    out = []
    for c, _ in auto.WalkControl(auto.GetForegroundControl(), maxDepth=25):
        try:
            if c.ControlTypeName in CLICKABLE and c.Name and not c.IsOffscreen:
                out.append(f"{c.ControlTypeName.replace('Control', '')}: {c.Name[:60]}")
        except Exception:
            continue
        if len(out) >= limit:
            break
    return out


# ================= voice =================
def route_uia(t):
    if re.fullmatch(r"(?:what|which) tabs (?:do i have|are|have i got)(?: open)?|list (?:my |the )?tabs|read (?:me )?my tabs|what(?:'s| is) open in chrome", t):
        return ("tabs_list", None)
    m = re.fullmatch(r"close (?:all|every)(?: of)?(?: the| my)? (.+?) tabs?", t)
    if m:
        return ("tab_close", (m.group(1), True))
    if re.fullmatch(r"close (?:all )?(?:the |my )?other tabs|close every other tab|close all tabs but this(?: one)?", t):
        return ("tabs_close_others", None)
    m = re.fullmatch(r"close (?:the |my |that )?(.+?) tab", t)
    if m and m.group(1) not in ("this", "current", "the", "that", "last"):
        return ("tab_close", (m.group(1), False))
    m = re.fullmatch(r"(?:switch|go|jump|flip) (?:to|over to) (?:the |my )?(.+?) tab|(?:open|show|pull up) (?:the |my )?(.+?) tab", t)
    if m:
        q = m.group(1) or m.group(2)
        if q not in ("new", "next", "previous", "last", "a new") and not re.search(r"\bnew\b", q):
            return ("tab_switch", q)
    m = re.fullmatch(r"(?:click|tap|press|hit|select)(?: on)? (?:the )?(.+?)(?: button| link| tab| option)?", t)
    if m and m.group(1) and len(m.group(1).split()) <= 6:
        if m.group(1) in ("play", "pause", "play pause", "resume"):
            return ("play_pause", None)   # "press play" means the music, not a Play button
        return ("ui_click", m.group(1))
    return None


def handle(action, arg, say):
    try:
        _auto()
    except ImportError:
        return say("I need the uiautomation package for that. Say update yourself, or run python update.py dash dash extras.")
    tabs = Tabs()
    if action == "tabs_list":
        ts = tabs.list()
        if not ts:
            return say("I don't see any Chrome or Edge tabs.")
        names = [t[2] for t in ts]
        say(f"{len(names)} tab{'s' if len(names) != 1 else ''}: " + ", ".join(names[:8]) + (f", and {len(names) - 8} more." if len(names) > 8 else "."))
    elif action == "tab_switch":
        title = tabs.switch(arg)
        say(f"{title}." if title else f"I don't see a tab for {arg}.")
    elif action == "tab_close":
        q, every = arg
        closed = tabs.close(q, every)
        if not closed:
            say(f"I don't see a {q} tab.")
        else:
            say("Closed " + (f"{len(closed)} tabs." if len(closed) > 1 else closed[0] + "."))
    elif action == "tabs_close_others":
        n = tabs.close_others()
        say(f"Closed {n} other tab{'s' if n != 1 else ''}." if n else "That's your only tab.")
    elif action == "ui_click":
        name = click(arg)
        say(f"Clicked {name}." if name else f"I don't see {arg} on the screen in front.")
