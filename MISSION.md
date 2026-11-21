# Mission: Yash's personal AI system

## Who I am
Yash, high school senior in San Diego (North County). I build software and startups, play soccer,
run track, and I'm applying to college. I want a system that runs my time, handles school, and lets
me build fast. I'm moving on from Hearth and the city sim; I want to build new things.

## My setup
- Windows PC: RTX 5070, i7, 32GB RAM
- 49 inch 240Hz OLED monitor, old iPad (for an always on HQ screen), iPhone 14
- Focusrite interface with a Samsung mic, speakers, phone mounts
- Claude Max 5x. I use Claude Code a lot. Claude Duet is installed.
- Connected in claude.ai: Gmail, Google Calendar, Google Drive, GitHub via email
  notifications, Vercel, Supabase, Wispr Flow (dictation, hands free shortcut Ctrl+Win+Space)

## What already exists
1. **Duet** handles my morning brief (8 AM) and check ins (every 3 hours). My old "Senior Year Engine"
   brief tasks are turned off. Don't recreate them.
2. **HQ** (folder `hq/`): my wall dashboard, a claude.ai artifact at
   https://claude.ai/artifact/9ZQx1xYZwPMRDhDuoT5oVE . Live calendar, AI filtered mail, AI task queue,
   GitHub build summary, agent status board. Read `hq/README.md` for how its data layer works.
   It runs inside claude.ai so it uses my connectors and Claude with no API keys. Keep it that way.
3. **Jarvis** (folder `jarvis/`): voice assistant for my PC. Wake word "hey jarvis", faster-whisper on
   GPU, Claude Code CLI as the brain, Kokoro voice, double clap to wake my monitor and open HQ.
   Not installed yet.

## Do this, in order. Check in with me after each step.

### Step 1: Get Jarvis running
- Move `jarvis/` to `C:\jarvis` (or run it from here). Read its README.md and jarvis.py.
- Run setup.bat, fix anything that fails (RTX 50 series needs the CUDA 12.8 PyTorch build).
- Find my Focusrite input and speaker output, set MIC_DEVICE and SPEAKER_DEVICE.
- Test the wake word and double clap with me live and tune thresholds until both are reliable.
- Make it start automatically when I log into Windows (minimized).

### Step 2: Upgrade Jarvis
- "What's my day look like?": read my Google Calendar and answer out loud. Check whether Claude Code
  here can reach my claude.ai connectors (`/mcp`). If not, find the simplest reliable way.
- PC control by voice: open apps and sites, play or pause music, volume, lock screen. Keep a short,
  safe allow list; never delete files or run anything destructive by voice.
- Morning wake: on double clap before noon, also read a 20 second brief (next event, top tasks).
- Let Jarvis post its status to HQ's agent board if there's a clean way; skip if not.

### Step 3: Redesign HQ
Problem: it looks like generic AI sci fi (Orbitron everywhere, glow on everything, clipped corners).
I want it to look like a real design studio built it. Think F1 pit wall telemetry, aircraft glass
cockpit, Teenage Engineering, Nothing OS dot matrix, Apple Watch Ultra night mode. Dark, precise,
glanceable across a room. No pink.
- Make 3 directions as separate files in `hq/` (same data and features, fully different visual language,
  each with a signature element that isn't a generic chart).
- Open each in a browser (preview mode fills sample data), screenshot at 1600x1000, 1180x820, 390x844,
  look critically, fix, and show me.
- When I pick one: make it index.html, polish every detail, test all sizes.
- Never change how data is fetched, the mock data, or payload shapes. One HTML file.
- To publish: tell me, and I'll attach index.html in claude.ai and say "publish this to HQ".
  (If you have the claude-artifacts tools, publish_files to slug 454fab32-dad1-420d-9cb5-ac334dac44dd.)

## How to work with me
- Short, direct, no fluff. No hyphens or em dashes in anything you write to me.
- Make sensible calls yourself instead of asking prep questions. Ask only when it's actually my call.
- Show me screenshots or live tests instead of telling me it works.
