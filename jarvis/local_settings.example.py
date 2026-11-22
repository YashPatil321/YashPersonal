# Your own settings. Updates never overwrite this file (it's local_settings.py on your PC).
# Anything here wins over the defaults at the top of jarvis.py and the other jarvis_*.py files.
# Delete a line to go back to the default.

# MIC_DEVICE = 1                 # your Scarlett input number from --devices
# MIC_CHANNEL = 0
# MIC_GAIN = 6.0                 # software gain if the mic is quiet
# SPEAKER_DEVICE = None          # None = Windows default (your monitor)
# CLAP_LEVEL = 0.85
# CLAP_CREST = 4.0
# WAKE_THRESHOLD = 0.5
# SPOTIFY_CLIENT_ID = "9168fe0d1873402497e1738a923b9a76"
# ROOM_PLAYLIST = "https://open.spotify.com/playlist/..."
# ROOM_VOLUME = 35
# NTFY_TOPIC = ""
# CORNER = "bottom right"        # where the orb sits
# AUTO_UPDATE_HOUR = 4           # nightly update check, 24h clock. None to turn off
# PROJECT_ALIASES = {"jarvis": r"C:\jarvis", "solidhauz": r"C:\code\SolidHauzWeb"}
# BROWSER = "chrome"             # or "edge"
# BROWSER_ACCOUNT = "you@gmail.com"   # the profile HQ and sites open in. Run: python jarvis.py --profiles
# BROWSER_PROFILE = "Profile 1"  # or name the profile folder directly
# VAULT = r"C:\Users\you\Documents\Yash"   # your Obsidian vault. Empty = the one Obsidian has open
# AUTO_WELCOME = True            # greet you when you sit back down after 45+ minutes away
# AUTO_WELCOME_AFTER = 45
# FOCUS_MUSIC = "lofi beats"     # played when you say lock in
# QUIET_HOURS = (23, 6)          # no automatic welcomes or reminders overnight
# GAMEDAY_PLAYLIST = "https://open.spotify.com/playlist/..."   # pregame music
# IMPORTANT_SENDERS = ["orielly", "rielly", "roty", "mom@...", "dad@..."]   # mail Jarvis reads out
# WIND_DOWN = "22:30"
# WEEKLY_REVIEW = (6, "18:00")   # Sunday 6 PM
# BREAK_AFTER_HOURS = 3
# PHONE_IP = "192.168.1.50"      # iPhone: Settings, WiFi, (i), turn off Private Address, then reserve the IP in your router
# PARTY_PLAYLIST = "https://open.spotify.com/playlist/..."
# WAKE_PLAYLIST = ""             # alarm music. Empty = your room playlist
# WAKE_VOLUME = (10, 45)
# COUNTDOWNS = {"uc": ("2026-11-30", "UC applications are due"), "signing day": ("2027-02-03", "signing day")}
# PHONE_SHORTCUT = "Jarvis Do"   # the shortcut a phone push runs
# PHONE_SERVER = True            # "Hey Siri, Jarvis" and phone automations
# MIRROR_TO_PHONE = True         # leave reminders and important mail go to your phone when you're away
# VISION = False                 # camera features are on by default, this turns them off
# CAMERA_INDEX = 0
# GESTURES = True
# FACES = True                   # face ID, needs VISION
# AUTO_GUEST = True              # guest mode while anyone else is in view
# AUTO_LOCK = True               # lock the PC if someone else sits there while you're gone
# LOCK_AFTER = 60
# TOUCH_REGION = (0.18, 0.15, 0.82, 0.80)   # smaller box = less reaching
# TOUCH_SMOOTH = 0.35
# DESK_CAMERA_INDEX = 1          # the camera looking down at the desk
# DESK_DISPLAY = None            # which screen is the projector. None = the smallest screen that isn't the main one
# DWELL_SECONDS = 0.6            # how long to hold a finger still to press
# FULL_ACCESS = True             # Claude can do anything on the PC without asking (off in guest mode). False = ask by voice first
