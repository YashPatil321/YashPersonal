# Yash's system: setup

Four pieces. Do them in this order. Total time about 30 minutes.

| Device | What it runs | Link or folder |
|---|---|---|
| Windows PC + 49 inch OLED | Jarvis (voice, claps, PC control) and HQ in a window | `C:\jarvis` |
| iPad on the stand | HQ wall dashboard | https://claude.ai/artifact/9ZQx1xYZwPMRDhDuoT5oVE |
| iPhone | HQ and the day plan as home screen apps, push on clap | https://claude.ai/artifact/6ukAC2x6XKNKVJjMyrXm4i |
| Google Calendar | the source of truth: school, games, leave times | already filled in |

---

## 1. PC: one command

Open PowerShell (Start, type PowerShell) and paste:

```
irm https://raw.githubusercontent.com/YashPatil321/YashPersonal/claude/hopeful-bohr-1ramsu/jarvis/install.ps1 | iex
```

That installs or updates Jarvis in `C:\jarvis`, makes it start when you log in (a shortcut named Jarvis in
`shell:startup`), and starts it. From then on it updates itself. The older manual steps are below if you need them.

## 1. PC: update Jarvis (10 minutes, at the PC)

Your local Claude Code session already has Jarvis running with your mic, speaker and window layout.
The new features (Claude control, timers, Spotify, walk in scene, goodnight) are in this repo and
need merging into your copy.

1. Open Windows Terminal.
2. Run:
   ```
   cd C:\jarvis
   claude
   ```
3. Paste this:
   > Get jarvis/HANDOFF.md, jarvis/jarvis_claude.py and jarvis/jarvis_room.py from the GitHub repo
   > YashPatil321/YashPersonal, branch claude/hopeful-bohr-1ramsu. Follow HANDOFF.md, keep my hardware
   > tuning (gain, Scarlett input, monitor output, window tiling, scheduled task), then run the live tests with me.
4. It will set Windows to never sleep while the monitor still turns off (that is what lets a clap
   work after you walk in), and walk you through the tests: "what was I working on", "open claude
   code in jarvis", a timer, and a full clap wake.

### Updates are automatic after this
- Jarvis pulls the newest code every time it starts, and at 4 AM restarts itself into anything new.
- Say "hey jarvis, update yourself" to get a change right away.
- Your own settings live in `C:\jarvis\local_settings.py` and are never overwritten.
- HQ and the day plan update on every screen by themselves when they're republished.

## 2. iPad: make it a wall screen (5 minutes)

1. Plug it in on the stand.
2. Settings, Display & Brightness, Auto-Lock: **Never**.
3. Open the HQ link in Safari, signed in to claude.ai.
4. Tap once and **Allow** everything it asks for: Google Calendar, Gmail, SolidHauz, Claude Code
   Remote, and the live connection to your other screens. These are read only except Add to
   calendar on coach cards, which only runs when you tap it.
5. Share button, **Add to Home Screen**, open it from there (no Safari bars).
6. Optional, to pin it: Settings, Accessibility, Guided Access on. In HQ, triple click the top button, Start.
7. Optional, real dimming at night. Shortcuts app, Automation, New Automation, Time of Day:
   - 11:30 PM daily, Run Immediately, action **Set Brightness** 0 percent
   - 6:45 AM daily, Run Immediately, action **Set Brightness** 70 percent

What it does on its own: wakes itself at 6:45 AM and 3:45 PM, goes dark 11:30 PM to 6:45 AM,
dims after 20 quiet minutes, and plays the wake sequence when you clap (Jarvis opens HQ on the PC,
which signals the iPad).

## 3. iPhone (3 minutes)

1. Open the HQ link and the day plan link in Safari, Share, **Add to Home Screen** for each.
2. Optional push on clap: install the free **ntfy** app, subscribe to a long random topic name
   (for example `yash-hq-` plus random letters), then put that name in `NTFY_TOPIC` at the top of
   `C:\jarvis\jarvis.py`.

## 4. Spotify full control (optional, 5 minutes, needs Premium)

Play, pause and skip work with no setup. To have Jarvis play a specific song or your room playlist:

1. developer.spotify.com/dashboard, Create app. Redirect URI `http://127.0.0.1:8765/callback`, tick Web API.
2. Copy the Client ID into `SPOTIFY_CLIENT_ID` in `jarvis.py`.
3. In `C:\jarvis` run `.venv\Scripts\python jarvis.py --spotify-login` and approve.
4. Paste your room playlist link into `ROOM_PLAYLIST` in `jarvis_room.py`.

---

## 5. Obsidian, Jarvis's memory (5 minutes)

1. Download Obsidian from obsidian.md and install it on the PC.
2. Create new vault, name it `Yash`, put it in `Documents`.
3. Restart Jarvis. It finds the vault by itself (check with `python jarvis.py --doctor`, line `vault`).
4. Optional, notes on your phone and iPad: Obsidian Sync (about $4 a month), or put the vault in iCloud Drive
   with iCloud for Windows and open the same folder in Obsidian on iPhone.

From then on Jarvis writes a daily note every day, keeps what you tell it to remember, logs games and focus
sessions, and greets you based on what you were just doing. See the Memory section in `jarvis/README.md`.

---

## Soccer schedule watch (2 minutes, optional)

Claude's safety check would not let the cloud session create an unattended job that writes to your
calendar, so create it yourself:

1. claude.ai/code, Scheduled tasks (Routines), New.
2. Schedule: daily at 3:47 PM and 8:47 PM. Connectors: Gmail and Google Calendar.
3. Paste this as the prompt:

> Keep my Google Calendar in sync with my Del Norte Boys Varsity Soccer schedule. Head coach David
> O'Rielly (spelled Rielly), assistant Coach Tim Roty. Coach emails usually
> come forwarded by my dad or mom (add their email addresses here). Search Gmail from the
> last 14 days for orielly OR rielly OR Roty OR "Coach Tim" OR "DN Boys", read each thread in full,
> and pull out every future practice, game or meeting with a date and time. Skip anything already on
> my calendar (same day, within 30 minutes). Add the rest: titles like "Varsity soccer practice",
> 2 hours if no end time, Del Norte High School, 16601 Nighthawk Ln, San Diego for home, reminders
> 120 and 30 minutes, colorId 10. For a game, also add a "Leave for game" block that gets me there
> one hour before kickoff, counting drive time from 4S Ranch with traffic. Never delete or edit
> existing events, never send email. End with a short summary of what you added.

---

## Daily use

| You | It happens |
|---|---|
| Walk in, clap twice | monitor wakes, windows tile, music starts, greeting, iPad HQ wakes |
| "hey jarvis, what's my day look like" | spoken rundown from your calendar |
| "hey jarvis, open claude code in solidhauz" | new terminal tab in that project |
| "hey jarvis, set a timer for 25 minutes" | chime and voice when done |
| "hey jarvis, goodnight" | music off, monitors off |
| Glance at the iPad | what's on, what's next, leave time, tasks, mail, SolidHauz |
| Coach emails a new schedule | HQ shows a From Coach card, tap Add |
| Sunday 6 PM | plan the week with the day plan page |
