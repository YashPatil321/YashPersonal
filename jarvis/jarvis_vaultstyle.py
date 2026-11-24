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


def route_vault(t):
    if re.fullmatch(r"(?:fix up|clean up|organi[sz]e|link up|connect|style|update) (?:my )?(?:obsidian|vault|notes)(?: vault)?|"
                    r"make my (?:vault|obsidian|graph) (?:look )?(?:like a galaxy|better|nice)", t):
        return ("vault_fix", None)
    return None
