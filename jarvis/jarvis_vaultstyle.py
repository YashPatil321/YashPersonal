"""
Makes the Obsidian vault look and work better. Atlas runs it at start and every night; "fix up my vault" runs it now.

  Galaxy       a CSS snippet (atlas-galaxy) that turns the graph into deep space: a starfield behind it, glowing
               star colored nodes, faint nebula links. Folder groups get star colors (blue giants, gold suns, red
               dwarfs, violet nebulas). The rest of Obsidian gets the same look: colored folders, nicer headings.
  Links        the graph only becomes a galaxy when notes connect. Atlas links every note it wrote (chats,
               conversations, research, daily logs) to the people, projects and places you have notes on, plus a
               link to the day it happened. Only the first mention in each note, never inside code or existing links.
  Atlas home   Atlas.md, a dashboard: today, recent research, chats, conversations, people, and Atlas's own memory,
               lessons, personality and changelog. It's the sun the rest orbits.

Obsidian reads the look at start: after the first run, restart Obsidian (or Settings, Appearance, CSS snippets,
reload) and turn on atlas-galaxy if it isn't on.
"""

import json
import os
import re
import time

SNIPPET = "atlas-galaxy"
# folder -> star color. Anything not here stays starlight white.
STAR_COLORS = {
    "Jarvis": "FF6B57", "Claude": "FFB36B", "Claude History": "FFB36B", "Chats": "FFD27A", "Research": "7DF9FF",
    "Daily": "9CC9FF", "Weekly": "C3B1FF", "Weekly Reviews": "C3B1FF", "School": "6F9BFF", "Projects": "B07CFF",
    "Work": "D38CFF", "People": "7CFFB2", "Life": "5EE6D3", "About Me": "FF8FC8", "Soccer": "A6FF6B",
}
LINK_FOLDERS = ("People", "Projects", "School", "Work", "Life", "About Me", "Soccer")   # notes worth linking to
WRITTEN_BY_ATLAS = ("Claude/Chats", "Jarvis/Conversations", "Research", "Daily")

CSS = """/* Atlas galaxy. Made by Atlas; edit freely, it only rewrites this file if you delete it. */
body.theme-dark {
  --atlas-bg: #05060d;
  --interactive-accent: #8ab4ff;
  --text-accent: #9cc9ff;
  --h1-color: #ffd27a; --h2-color: #9cc9ff; --h3-color: #c3b1ff;
}
/* deep space behind the graph: two layers of stars and a nebula glow */
.workspace-leaf-content[data-type="graph"] .view-content,
.workspace-leaf-content[data-type="localgraph"] .view-content {
  background:
    radial-gradient(1px 1px at 12% 18%, #fff 50%, transparent 51%),
    radial-gradient(1px 1px at 72% 34%, #cfe3ff 50%, transparent 51%),
    radial-gradient(1.5px 1.5px at 38% 76%, #fff 50%, transparent 51%),
    radial-gradient(1px 1px at 88% 82%, #ffe9c4 50%, transparent 51%),
    radial-gradient(1px 1px at 56% 8%, #fff 50%, transparent 51%),
    radial-gradient(1.2px 1.2px at 24% 52%, #d6c8ff 50%, transparent 51%),
    radial-gradient(1px 1px at 94% 12%, #fff 50%, transparent 51%),
    radial-gradient(1px 1px at 6% 90%, #cfe3ff 50%, transparent 51%),
    radial-gradient(ellipse 60% 40% at 30% 40%, rgba(120, 80, 255, 0.16), transparent 70%),
    radial-gradient(ellipse 50% 35% at 75% 65%, rgba(40, 160, 255, 0.12), transparent 70%),
    radial-gradient(ellipse 80% 60% at 50% 50%, rgba(255, 140, 90, 0.05), transparent 75%),
    var(--atlas-bg) !important;
  background-size: 220px 220px, 340px 340px, 410px 410px, 290px 290px, 520px 520px, 380px 380px, 610px 610px, 470px 470px,
                   100% 100%, 100% 100%, 100% 100% !important;
}
/* the graph draws with these colors */
.graph-view.color-fill { color: #e8f1ff; }               /* stars without a group: starlight */
.graph-view.color-fill-focused { color: #ffffff; }
.graph-view.color-fill-highlight { color: #ffd27a; }      /* hovered: a sun */
.graph-view.color-fill-tag { color: #7df9ff; }
.graph-view.color-fill-attachment { color: #6b7a99; }
.graph-view.color-fill-unresolved { color: #3d4660; }
.graph-view.color-line { color: rgba(140, 170, 255, 0.16); }   /* faint nebula threads */
.graph-view.color-line-highlight { color: rgba(255, 210, 122, 0.7); }
.graph-view.color-text { color: #c9d6f2; }
.graph-view.color-circle { color: #ffd27a; }
.graph-view.color-arrow { color: rgba(140, 170, 255, 0.4); }
/* folders in the sidebar get their star color */
%FOLDERS%
/* small touches */
.markdown-rendered h1, .cm-header-1 { letter-spacing: 0.5px; }
.callout { border-radius: 10px; }
"""


def _rgb(hexs):
    return int(hexs, 16)


class VaultStyle:
    def __init__(self, vault, log=print):
        self.vault, self.log = vault, log
        self.root = vault.root
        self.obs = os.path.join(self.root, ".obsidian")

    # ---------- look ----------
    def install_look(self):
        if not os.path.isdir(self.obs):
            self.log("vault: no .obsidian folder yet (open the vault in Obsidian once)")
            return False
        snip_dir = os.path.join(self.obs, "snippets")
        os.makedirs(snip_dir, exist_ok=True)
        path = os.path.join(snip_dir, SNIPPET + ".css")
        if not os.path.exists(path):
            folders = "\n".join(f'.nav-folder-title[data-path="{f}"], .nav-folder-title[data-path^="{f}/"] '
                                f'{{ color: #{c}; }}' for f, c in STAR_COLORS.items())
            with open(path, "w", encoding="utf-8") as f:
                f.write(CSS.replace("%FOLDERS%", folders))
        # turn the snippet on
        ap = os.path.join(self.obs, "appearance.json")
        data = self._json(ap)
        snips = data.get("enabledCssSnippets", [])
        if SNIPPET not in snips:
            data["enabledCssSnippets"] = snips + [SNIPPET]
            data.setdefault("theme", "obsidian")
            self._save(ap, data)
        # star colored groups and galaxy physics in the graph, only for folders that exist
        gp = os.path.join(self.obs, "graph.json")
        g = self._json(gp)
        have = {q.get("query") for q in g.get("colorGroups", [])}
        groups = list(g.get("colorGroups", []))
        for folder, color in STAR_COLORS.items():
            q = f'path:"{folder}"'
            if os.path.isdir(os.path.join(self.root, folder)) and q not in have:
                groups.append({"query": q, "color": {"a": 1, "rgb": _rgb(color)}})
        if groups != g.get("colorGroups"):
            g["colorGroups"] = groups
            g.setdefault("nodeSizeMultiplier", 1.15)
            g.setdefault("lineSizeMultiplier", 0.35)
            g.setdefault("textFadeMultiplier", -1.6)
            g.setdefault("centerStrength", 0.35)
            g.setdefault("repelStrength", 16)
            g.setdefault("linkStrength", 0.7)
            g.setdefault("linkDistance", 140)
            g.setdefault("showArrow", False)
            self._save(gp, g)
            self.log(f"vault: graph colored ({len(groups)} groups)")
        return True

    # ---------- links ----------
    def titles(self):
        """{lowercase title: title} for notes worth linking to."""
        out = {}
        for folder in LINK_FOLDERS:
            base = os.path.join(self.root, folder)
            for dirpath, _, files in os.walk(base):
                for f in files:
                    if f.endswith(".md"):
                        t = f[:-3]
                        if len(t) >= 3 and not re.fullmatch(r"\d[\d -]*", t):
                            out[t.lower()] = t
        return out

    def weave(self, max_files=400):
        """Adds [[links]] to the notes Atlas wrote. Returns how many files changed."""
        titles = self.titles()
        if not titles:
            return 0
        pat = re.compile(r"(?<![\w\[])(" + "|".join(re.escape(t) for t in sorted(titles, key=len, reverse=True)) + r")(?![\w\]])", re.I)
        changed = 0
        files = []
        for folder in WRITTEN_BY_ATLAS:
            for dirpath, _, fs in os.walk(os.path.join(self.root, folder)):
                files += [os.path.join(dirpath, f) for f in fs if f.endswith(".md")]
        files.sort(key=lambda p: os.path.getmtime(p), reverse=True)
        for p in files[:max_files]:
            try:
                txt = open(p, encoding="utf-8").read()
            except Exception:
                continue
            new = link_text(txt, pat, titles, own=os.path.basename(p)[:-3])
            new = add_day_link(new, os.path.basename(p), in_daily=os.path.relpath(p, self.root).replace("\\", "/").startswith("Daily/"))
            if new != txt:
                with open(p, "w", encoding="utf-8") as f:
                    f.write(new)
                changed += 1
        if changed:
            self.log(f"vault: linked {changed} notes")
        return changed

    # ---------- home ----------
    def home(self):
        """Atlas.md: the dashboard everything links back to."""
        def recent(folder, n=6):
            fs = []
            for dirpath, _, files in os.walk(os.path.join(self.root, folder)):
                fs += [os.path.join(dirpath, f) for f in files if f.endswith(".md")]
            fs.sort(key=os.path.getmtime, reverse=True)
            return [os.path.relpath(f, self.root)[:-3].replace("\\", "/") for f in fs[:n]]

        def links(items):
            return "\n".join(f"- [[{i}|{i.split('/')[-1]}]]" for i in items) or "- (nothing yet)"
        today = time.strftime("%Y-%m-%d")
        people = [t for t in self.titles().values()][:20]
        body = (f"# Atlas\n\n> [!abstract] {time.strftime('%A, %B %d')}\n> [[Daily/{today}|Today]] · [[Jarvis/Conversations/{today}|"
                "What we talked about today]] · [[Jarvis/Memory|What I remember]] · [[Jarvis/Lessons|What I learned]] · "
                "[[Jarvis/Personality|Who I am]] · [[Jarvis/Changelog|How I changed]]\n\n"
                "## Research\n" + links(recent("Research")) + "\n\n## Claude chats\n" + links(recent("Claude/Chats")) +
                "\n\n## Conversations\n" + links(recent("Jarvis/Conversations", 5)) + "\n\n## Daily\n" + links(recent("Daily", 7)) +
                "\n\n## People and projects\n" + ("\n".join(f"- [[{p}]]" for p in people) or "- (nothing yet)") +
                f"\n\n*Atlas keeps this page up to date. Last update {time.strftime('%H:%M')}.*\n")
        path = os.path.join(self.root, "Atlas.md")
        old = open(path, encoding="utf-8").read() if os.path.exists(path) else ""
        if re.sub(r"Last update \d\d:\d\d", "", old) != re.sub(r"Last update \d\d:\d\d", "", body):
            with open(path, "w", encoding="utf-8") as f:
                f.write(body)
        return path

    def run(self):
        try:
            self.install_look()
        except Exception as e:
            self.log(f"vault look: {e}")
        n = 0
        try:
            n = self.weave()
        except Exception as e:
            self.log(f"vault links: {e}")
        try:
            self.home()
        except Exception as e:
            self.log(f"vault home: {e}")
        return n

    def watch(self):
        time.sleep(120)
        while True:
            self.run()
            time.sleep(3600)

    @staticmethod
    def _json(p):
        try:
            with open(p, encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            return {}

    @staticmethod
    def _save(p, d):
        with open(p, "w", encoding="utf-8") as f:
            json.dump(d, f, indent=2)


PROTECT = re.compile(r"(^---\n.*?\n---\n|```.*?```|`[^`\n]*`|\[\[[^\]]*\]\]|\[[^\]]*\]\([^)]*\)|https?://\S+|^#+ [^\n]*$)", re.S | re.M)


def link_text(txt, pat, titles, own=""):
    """Links the first mention of each title in the parts of the text that aren't code, links, URLs or headings."""
    done, out, pos = set([own.lower()]), [], 0
    for m in PROTECT.finditer(txt):
        out.append(_link_part(txt[pos:m.start()], pat, titles, done))
        out.append(m.group(0))
        pos = m.end()
        for t in re.findall(r"\[\[([^\]|#]+)", m.group(0)):   # already linked: don't link again
            done.add(t.strip().lower())
    out.append(_link_part(txt[pos:], pat, titles, done))
    return "".join(out)


def _link_part(part, pat, titles, done):
    def sub(m):
        key = m.group(1).lower()
        if key in done:
            return m.group(1)
        done.add(key)
        t = titles[key]
        return f"[[{t}]]" if m.group(1) == t else f"[[{t}|{m.group(1)}]]"
    return pat.sub(sub, part)


def add_day_link(txt, filename, in_daily=False):
    """Notes named by date ('2026-11-22 ...') get a link to that day's daily note and to Atlas, once."""
    m = re.match(r"(\d{4}-\d{2}-\d{2})", filename)
    if not m or in_daily or "[[Daily/" in txt or "[[Atlas]]" in txt:
        return txt
    return txt.rstrip("\n") + f"\n\n*Day: [[Daily/{m.group(1)}|{m.group(1)}]] · [[Atlas]]*\n"


# Well known community plugins Atlas installs into the vault (the release files from their GitHub repos).
PLUGINS = {
    "dataview": "blacksmithgu/obsidian-dataview",                       # live dashboards from your notes
    "obsidian-spaced-repetition": "st3v3nmw/obsidian-spaced-repetition",  # the flashcards Atlas writes
    "templater-obsidian": "SilentVoid13/Templater",                      # templates for daily notes
}


def install_plugins(root, log=print, plugins=None):
    """Downloads each plugin's release (main.js, manifest.json, styles.css) into .obsidian/plugins and turns it on.
    Obsidian asks once to turn on community plugins (restricted mode off), then they load."""
    import urllib.request
    obs = os.path.join(root, ".obsidian")
    if not os.path.isdir(obs):
        return []
    done = []
    for pid, repo in (plugins or PLUGINS).items():
        dst = os.path.join(obs, "plugins", pid)
        if os.path.exists(os.path.join(dst, "main.js")):
            done.append(pid)
            continue
        try:
            files = {}
            for name in ("manifest.json", "main.js", "styles.css"):
                url = f"https://github.com/{repo}/releases/latest/download/{name}"
                try:
                    with urllib.request.urlopen(url, timeout=60) as r:
                        files[name] = r.read()
                except Exception:
                    if name != "styles.css":
                        raise
            man = json.loads(files["manifest.json"])
            if man.get("id") != pid:
                log(f"vault: {repo} says its id is {man.get('id')}, skipping")
                continue
            os.makedirs(dst, exist_ok=True)
            for name, data in files.items():
                with open(os.path.join(dst, name), "wb") as f:
                    f.write(data)
            done.append(pid)
            log(f"vault: installed {man.get('name', pid)} {man.get('version', '')}")
        except Exception as e:
            log(f"vault: couldn't install {pid}: {e}")
    cp = os.path.join(obs, "community-plugins.json")
    try:
        on = json.load(open(cp, encoding="utf-8"))
    except Exception:
        on = []
    new = on + [p for p in done if p not in on]
    if new != on:
        with open(cp, "w", encoding="utf-8") as f:
            json.dump(new, f, indent=2)
    return done


def find_note(root, query):
    """The note whose name best matches what you said (path), or None."""
    q = [w for w in re.findall(r"[a-z0-9]+", query.lower()) if w not in ("my", "the", "note", "page", "a")]
    if not q:
        return None
    best, score = None, 0
    for dirpath, dirs, files in os.walk(root):
        dirs[:] = [d for d in dirs if not d.startswith(".")]
        for f in files:
            if not f.endswith(".md"):
                continue
            name = f[:-3].lower()
            s = sum(2 if w in name.split() else 1 if w in name else 0 for w in q) - 0.01 * len(name)
            if s > score:
                best, score = os.path.join(dirpath, f), s
    return best if score >= len(q) * 0.9 else None


def obsidian_open(path, new_tab=False):
    """Opens a note in Obsidian (the obsidian:// link works with any vault)."""
    import urllib.parse
    url = "obsidian://open?path=" + urllib.parse.quote(path.replace("\\", "/"), safe="/:")
    if os.name == "nt":
        os.startfile(url)
    return url


def handle_obsidian(action, arg, root, say):
    if action == "obs_open":
        p = os.path.join(root, "Atlas.md") if arg in ("home", "atlas") else find_note(root, arg)
        if not p:
            return say(f"I don't see a note called {arg}.")
        obsidian_open(p)
        return say(f"{os.path.basename(p)[:-3]} is open.")
    if action == "obs_new":
        name = re.sub(r"[\\/:*?\"<>|#^\[\]]+", " ", arg).strip().title()[:80] or "Untitled"
        folder = os.path.join(root, "Inbox")
        os.makedirs(folder, exist_ok=True)
        p = os.path.join(folder, name + ".md")
        if not os.path.exists(p):
            with open(p, "w", encoding="utf-8") as f:
                f.write(f"# {name}\n\n")
        obsidian_open(p)
        return say(f"New note, {name}, in your Inbox.")
    if action == "obs_daily":
        p = os.path.join(root, "Daily", time.strftime("%Y-%m-%d") + ".md")
        if not os.path.exists(p):
            os.makedirs(os.path.dirname(p), exist_ok=True)
            with open(p, "w", encoding="utf-8") as f:
                f.write(f"# {time.strftime('%A, %B %d')}\n\n")
        obsidian_open(p)
        return say("Today's note is open.")


def route_vault(t):
    m = re.fullmatch(r"open (?:my |the )?(.+?) (?:note|page)(?: in obsidian)?|open (?:my |the )?(.+?) in obsidian|"
                     r"(?:show|pull up) (?:my |the )?(.+?) note", t)
    if m:
        what = next(g for g in m.groups() if g)
        if what in ("atlas home", "home", "atlas"):
            return ("obs_open", "home")
        if what in ("daily", "today's", "todays", "today"):
            return ("obs_daily", None)
        return ("obs_open", what)
    if re.fullmatch(r"open (?:my )?(?:obsidian|vault|second brain|atlas home)", t):
        return ("obs_open", "home")
    m = re.fullmatch(r"(?:new|make a|create a|start a) note (?:called|named|about|on|for) (.+)", t)
    if m:
        return ("obs_new", m.group(1))
    if re.fullmatch(r"open (?:my |today'?s )?daily note|today'?s note", t):
        return ("obs_daily", None)

    if re.fullmatch(r"(?:install|set up|get) (?:my |the )?(?:obsidian )?plugins(?: for obsidian)?|set up (?:my )?obsidian(?: plugins)?", t):
        return ("obs_plugins", None)
    if re.fullmatch(r"(?:fix up|clean up|organi[sz]e|link up|connect|style|update) (?:my )?(?:obsidian|vault|notes)(?: vault)?|"
                    r"make my (?:vault|obsidian|graph) (?:look )?(?:like a galaxy|better|nice)", t):
        return ("vault_fix", None)
    return None
