# Jarvis

Say "hey jarvis" (or clap twice), hear a chime, talk, get a spoken answer. Runs on your PC.

## Setup (once, about 15 minutes)

1. Install Python 3.12 from python.org (check "Add to PATH").
2. Make sure Claude Code works: open a terminal, type `claude`, log in with your Max account.
3. Put this folder at `C:\jarvis` and double click `setup.bat`. It installs everything
   (CUDA 12.8 PyTorch for the RTX 5070) and finishes with a checkup.
4. Read the checkup. Every line should say PASS. It also lists your claude.ai connectors and the
   exact tool names. If they differ from `CONNECTOR_TOOLS` at the top of `jarvis.py`, paste them in.
5. Optional: install espeak-ng (link at the end of setup) for the best voice.
6. Double click `install-autostart.bat` so Jarvis starts minimized when you log in.

The Focusrite is found by name. If the checkup says no Focusrite, run
`.venv\Scripts\python jarvis.py --devices` and put its number in `MIC_DEVICE`.
If your mic is plugged into input 2, set `MIC_CHANNEL = 1`.

## Use

- Clap twice: wakes the monitor, opens HQ full screen, says hi. Before noon it also reads a short
  morning brief (first event, how many more, mail that needs you). Once a day.
- "hey jarvis" then anything. It remembers the conversation between questions and restarts.

Instant voice commands (no Claude, nothing destructive is possible):

| Say | Does |
|---|---|
| pause, play music, resume | Spotify play or pause (media key) |
| next song, skip, previous song | track controls |
| volume up, turn it down by 20, set volume to 40, mute | system volume |
| play Drake on Spotify, play my lofi playlist | plays it (with Spotify connected) or opens the search |
| what's playing | reads the current song |
| open Spotify, Chrome, VS Code, Discord, Steam, Notepad, Explorer, Settings, Terminal | opens the app |
| open YouTube, Gmail, Calendar, Drive, GitHub, Vercel, Supabase, Claude, Common App | opens the site |
| open HQ | wakes the room |
| lock the screen | locks Windows |
| new conversation, go to sleep | resets context, quits |

Claude control (all projects are found automatically from your Claude Code history):

| Say | Does |
|---|---|
| open claude code in solidhauz | new terminal tab with Claude Code in that project |
| continue my jarvis session | reopens the last conversation there |
| tell claude in hq to fix the footer | starts Claude Code on that task, you approve changes in the terminal |
| ask solidhauz what's left on the todo list | Claude reads the project (read only) and answers out loud |
| what was I working on | your three most recent Claude Code sessions |
| new claude chat about college essays | opens claude.ai with the question typed in |
| open claude, open cowork | opens the Claude desktop app |
| open claude code on the web | your cloud sessions |

Walk in: while Jarvis runs the PC never sleeps (the monitor still does). Clap twice or say
"hey jarvis, I'm home": monitor wakes, windows tile, your room playlist starts, greeting, and HQ
on the iPad wakes from standby. Set `ROOM_PLAYLIST` in `jarvis_room.py`.

More instant commands:

| Say | Does |
|---|---|
| what time is it | tells you |
| set a timer for 10 minutes | chimes and tells you when done |
| remind me in 20 minutes to stretch | spoken reminder |
| take a note call coach about Saturday | adds it to notes/inbox.md |
| goodnight | pauses music, turns the monitors off |
| turn off the monitor | monitors off |
| what are my sessions doing | status of your cloud Claude Code sessions |
| tell the godot session to push the branch | asks you to confirm, then sends it |

On a clap Jarvis also plays a short power up sound, and if `NTFY_TOPIC` is set your iPhone gets a push
(install the free ntfy app, subscribe to a long random topic name, paste it at the top of jarvis.py).

Screen control (from a fixed list, nothing destructive):

| Say | Does |
|---|---|
| put chrome on the left, move spotify to the right third | snaps the window (left, right, thirds, quarters, center, full, corners) |
| maximize chrome, minimize discord, show desktop | window size |
| switch to claude, focus vs code | brings the app forward, opens it if needed |
| room layout, coding layout, school layout, focus layout | arranges several windows at once |
| type see you at practice comma bro | types into the active window, punctuation by name |
| press enter, new tab, close tab, copy, paste, undo, save, refresh, screenshot | safe keys only |
| start dictation | Wispr Flow hands free |

Spotify (Premium + Client ID): "play gods plan by drake", "play drake", "play some sza", "play my gym playlist",
"play my liked songs", "play the album utopia", "play something chill", "queue sicko mode", "play blinding lights next".
Spotify opens by itself if it isn't running.

WhatsApp: "whatsapp mom I'm on my way", "send a whatsapp to dad saying practice ends at 9". Jarvis reads it back and sends only
after you say yes. Put numbers in `WHATSAPP_CONTACTS` in local_settings.py. Needs WhatsApp Desktop. Reading messages is not possible:
no connector or app lets anything read your personal WhatsApp or iMessage.

The walk in: double clap plays a 2.6 second cinematic sound (preview: wake-sound-preview.wav) while HQ opens with its full screen
takeover on the PC and the iPad.

The orb: a small dot ring in the bottom right corner. Dim when idle, pulses when listening, spins while thinking,
ripples while talking, amber on an error. Clicks pass through it. Turn it off with `ORB = False`, move it with `CORNER`
in `jarvis_orb.py`, preview it with `python jarvis_orb.py --demo`.

Everything else goes to Claude Code, which can search the web, read your calendar and mail, and
write files only inside `notes/`, and read your vault. It cannot run commands or change other files.

## Memory, Obsidian and knowing what's going on

Jarvis keeps everything in your Obsidian vault as plain Markdown (`jarvis_brain.py`). Install Obsidian,
make a vault (for example `Documents\Yash`), and Jarvis finds it by itself. Set `VAULT` in
`local_settings.py` to pick a different one. With no Obsidian it uses `C:\jarvis\notes`.

| Say | What happens |
|---|---|
| clap, or sit back down after 45+ minutes | "welcome back from practice", what's next, when to leave. Reads your calendar and how long you were gone |
| "remember that coach wants me at left back" | saved to `Jarvis/Memory.md`, and every answer knows it from then on |
| "what did I write about Babson" | searches the whole vault, answers out loud with the note name |
| "take a note buy cleats" | `Jarvis/Inbox.md` as a checkbox, plus today's log |
| "log practice was rough, fitness day" | a line in today's daily note |
| "open my daily note" | today's note in Obsidian (`Daily/2026-11-22.md`) |
| "we won 3 1 against San Pasqual" | `Soccer/Season 2026-27.md` table, says your record |
| "what's our record" | wins and losses so far |
| "lock in for an hour" | focus layout, quiet, logged, chime at the end with today's total |
| "what should I work on tonight" | picks one thing from your calendar and memory |
| "goodnight" | recap of today and tomorrow's first leave time, written to the daily note |
| "I scored two goals" / "I had an assist" | season stats, "what's our record" includes them |
| "hype me up" / "pregame" | pregame playlist (`GAMEDAY_PLAYLIST`) and a hype line with kickoff and leave time |
| "bring back my stuff" / "where was I" | brings back the windows you had open before you left |
| "anything at the shop" | SolidHauz today: jobs behind, leads, payments, urgent first |
| "what's due" | deadlines for the next 7 days plus your open inbox items, and the one thing for tonight |
| "anything important" | checks mail from coaches, parents and SolidHauz right now |
| "what are my streaks" | focus days, nights in bed before 11, days logged |
| "weekly review" | writes `Weekly/2026-W47.md` and reads you the summary |

Reminders come on their own: 30 and 10 minutes before every "Leave for ..." block, then "time to go",
and before practices, games and other events. No automatic talking from 11 PM to 6 AM (`QUIET_HOURS`).
On its own it also: says "Game day" on game mornings and plays the pregame playlist, reads you mail that matters
(coaches, parents, SolidHauz, Babson) every 15 minutes or holds it until you're back, tells you to take a break
after 3 hours straight, nudges you to wind down at 10:30, and does a weekly review Sunday at 6 PM.
Focus sessions hold everything except leave reminders. With `PHONE_IP` set it knows when you got home.
Every wake writes a line to the daily note, so the vault becomes a journal of your days without trying.

## Extras (`jarvis_extras.py`)

| Say | What happens |
|---|---|
| "what's the weather" / "weather at 7" / "do I need a jacket" | live weather for 4S Ranch, no key needed. Also in every welcome |
| "house party protocol" | party playlist (`PARTY_PLAYLIST`), volume 80, notifications off for 3 hours |
| "clean slate" | minimizes everything |
| "gaming mode" | Steam and Discord, holds everything but leave times for 2 hours |
| "study mode" | school layout plus a 50 minute focus session |
| "movie mode" | music off, quiet for 3 hours |
| "guest mode" / "guest mode off" | nothing private out loud while friends are over |
| "journal" | talk for up to 3 minutes; cleaned up, titled and saved to `Journal/` in the vault |
| "screen time" / "how long was I on YouTube" | tracked all day from the window you're using. Logged at goodnight |
| "how many days until UC apps" | countdowns (`COUNTDOWNS`), or anything on your calendar |
| "I ran 3 miles in 24 minutes" / "I lifted" | `Training/2026-27.md` with pace; "how many miles this week" |
| "summarize my clipboard" / "save my clipboard" | explains what you copied, or saves it to your inbox |
| "what am I looking at" / "explain this error" | screenshots your screens and explains. Homework gets hints, not answers |
| "wake me up at 6:45" | music fades in on the PC, then the morning brief and weather. Survives restarts |
| "roast me" / "how am I doing" | a friendly roast, or an honest check in, from your screen time, streaks and season |

During a focus session, if you sit on YouTube, Instagram or TikTok for 90 seconds, Jarvis calls you out.

## Your iPhone (`jarvis_phone.py`)

Run `python jarvis.py --phone` for your links, your token and the step by step shortcut setup.

| Say | What happens |
|---|---|
| "set an alarm on my phone for 6:45" | a push on your phone, one tap sets the alarm |
| "put my phone on do not disturb for 2 hours" / "turn off do not disturb on my phone" | tap and Focus changes |
| "timer on my phone for 10 minutes" | tap and the timer starts |
| "remind me on my phone to text coach at 5" | tap and it goes in Reminders with an alert |
| "find my phone" | the loudest push ntfy can send |
| "send this to my phone" / "text my phone ..." | your clipboard or the words go to your phone, links open on tap |

Apple doesn't let anything set an alarm on your iPhone from outside it. A push you tap once, which runs your
`Jarvis Do` shortcut, is as close as it gets.

The other way round: "Hey Siri, Jarvis" runs a shortcut that sends what you say to Jarvis on the PC and Siri
reads you the answer. Anything you can say to Jarvis works. Phone automations tell Jarvis when you get home,
leave, stop your alarm (your room wakes up and gives the brief) or start Sleep Focus (goodnight).
When you're away from the desk, leave reminders and important mail also go to your phone.
The PC only answers your home network (and Tailscale) with the secret token in `.phone_token`.

## Camera: hand gestures, presence, rep counting (`jarvis_vision.py`)

Any USB webcam on top of the monitor. Everything runs on your PC with MediaPipe. No picture is saved or sent.

Setup: plug in a webcam. That's it. Everything is on by default: the camera packages install themselves on the
next update (or the first time the camera starts), the models download once, and if no camera is plugged in
Jarvis checks again every minute. `python jarvis.py --vision` opens a test window that shows your hand and the
gesture it reads (Q to quit). Turn pieces off in `local_settings.py`: `VISION`, `FACES`, `GESTURES`, `AUTO_GUEST`, `AUTO_LOCK`.

| Do | What happens |
|---|---|
| peace sign | Jarvis starts listening, no wake word |
| open palm, hold | play or pause |
| swipe right / left with an open hand | next / previous song |
| point up / down, hold | volume up / down, keeps going while you hold |
| thumbs up | yes, to anything Jarvis asked you to confirm |
| fist, hold | mute |
| wave | wakes the room, like a double clap |
| walk in and sit down | the camera sees you, so the welcome back happens on its own |
| "count my pushups" / "count my squats" / "count my curls" | counts out loud, "done" logs the set to Training |
| "touch mode" / "touch mode off" | control the whole screen with your hands, see below |
| "camera off" / "camera on" | pauses the camera completely |
| "what gestures can I use" | reads this list |

### Touch mode (`jarvis_touch.py`)

Say "touch mode". Your hand in the air becomes a mouse for the whole ultrawide.

| Do | What happens |
|---|---|
| move your hand | the cursor follows your knuckles, so pinching doesn't make it jump |
| pinch thumb and index | click. Twice fast = double click |
| pinch and hold, then move | drag: select text, move files, sliders |
| pinch thumb and middle | right click |
| fist | grab the window under the cursor and carry it. Open your hand to drop it |
| fist, then throw left or right | snaps the window to that half of the screen |
| two fingers up, move up or down | scroll |
| both hands pinching, pull apart or push together | zoom in or out (browser, VS Code, Figma) |
| open palm for 2 seconds | leaves touch mode |

Tune it in `local_settings.py`: `TOUCH_REGION` (how far you have to reach), `TOUCH_SMOOTH`, `SCROLL_SPEED`.

### Face ID (`jarvis_faces.py`)

Only fingerprints of faces (128 numbers each) are kept in `.cache/faces`, never pictures.

| Say | What happens |
|---|---|
| "learn my face" | look at the camera for 6 seconds, turn your head a bit. Do it once in daylight and once at night |
| "this is my mom" / "meet Arjun" / "learn dad's face" | they look at the camera, Jarvis remembers them |
| "who's here" / "who am I" / "who do you know" | says who it sees or knows |
| "forget mom's face" | deletes them |

Then: only your face counts as you being at the desk, so welcomes are for you. People it knows get a
"Hey Mom". Anyone else in view turns on guest mode until they leave (`AUTO_GUEST`). If someone who isn't
you sits at your PC for a minute while you're gone, it locks the screen and pings your phone (`AUTO_LOCK`).

## Spotify, full control (optional, 5 minutes, needs Spotify Premium)

Media keys work out of the box. To play a specific song by name:

1. Go to developer.spotify.com/dashboard, Create app. Redirect URI: `http://127.0.0.1:8765/callback`.
   Check "Web API". Save.
2. Copy the Client ID into `SPOTIFY_CLIENT_ID` at the top of `jarvis.py`.
3. Run `.venv\Scripts\python jarvis.py --spotify-login` and approve in the browser.

## Tuning (do this live)

Run `.venv\Scripts\python jarvis.py --levels`. It prints a live meter: peak, crest (sharpness) and the
wake word score, and marks claps and wakes.

- Claps missed: lower `CLAP_LEVEL` (try 0.25) or `CLAP_CREST` (try 3.5).
- Talking or music sets it off: raise `CLAP_LEVEL` to 0.5 or `CLAP_CREST` to 5.
- Wake word false triggers: raise `WAKE_THRESHOLD` to 0.6 or 0.7. Missed: lower to 0.4.
- Cuts you off mid sentence: raise `SILENCE_SECONDS` to 1.8.

Other tests: `--say "hello"` (voice), `--ask "what's my day look like"` (brain, no mic), `--doctor` (everything).

## What to expect

Commands are instant. Claude answers take a few seconds, mostly Claude Code starting up, and use your
Max plan. If the GPU path fails, Whisper falls back to CPU on its own and the checkup tells you.
