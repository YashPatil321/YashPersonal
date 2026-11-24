"""
The room scene: what happens when you walk in and clap (or say "hey jarvis, wake up").

  1. keep_awake() runs at startup: the PC never sleeps while Jarvis runs, but the monitor still
     turns off on its own. A sleeping PC can't hear anything, so this is what makes walk in wake work.
  2. scene(): wake the monitor, open HQ (which also wakes HQ on the iPad), arrange the windows,
     start your room playlist on the PC speakers, say hi.
"""

import sys
import time

IS_WIN = sys.platform == "win32"

# Your room playlist. Paste a Spotify playlist link or URI. Empty = just resume whatever was last playing.
ROOM_PLAYLIST = ""          # e.g. "https://open.spotify.com/playlist/37i9dQZF1DX0XUsuxWHRQd"
ROOM_VOLUME = 35            # percent, Spotify volume for the walk in (needs Spotify connected)
ROOM_SHUFFLE = True


def keep_awake():
    """Tell Windows the system is in use so it won't sleep. The display can still turn off."""
    if IS_WIN:
        import ctypes
        ES_CONTINUOUS, ES_SYSTEM_REQUIRED = 0x80000000, 0x00000001
        ctypes.windll.kernel32.SetThreadExecutionState(ES_CONTINUOUS | ES_SYSTEM_REQUIRED)
        return True
    return False


def playlist_uri(s):
    s = (s or "").strip()
    if s.startswith("spotify:"):
        return s
    if "open.spotify.com/" in s:
        kind, sid = s.split("open.spotify.com/", 1)[1].split("?")[0].split("/")[:2]
        return f"spotify:{kind}:{sid}"
    return ""


def start_music(pc, spotify, log=print, wait=12.0):
    """Start the room playlist on this PC. With Spotify connected: exact playlist, shuffle, volume.
    Without: open Spotify and press play, which resumes whatever you played last."""
    uri = playlist_uri(ROOM_PLAYLIST)
    if spotify is not None and spotify.ready:
        try:
            pc.launch("spotify:")
            dev = None
            t0 = time.time()
            while time.time() - t0 < wait and not dev:   # the desktop app takes a few seconds to show up
                devs = spotify._api("GET", "/me/player/devices").get("devices", [])
                dev = next((d for d in devs if d.get("type") == "Computer"), None)
                if not dev:
                    time.sleep(1.0)
            q = ("?device_id=" + dev["id"]) if dev else ""
            if ROOM_SHUFFLE:
                try:
                    spotify._api("PUT", "/me/player/shuffle?state=true" + ("&device_id=" + dev["id"] if dev else ""))
                except Exception:
                    pass
            spotify._api("PUT", "/me/player/play" + q, {"context_uri": uri} if uri else {})
            try:
                spotify.volume(ROOM_VOLUME)
            except Exception:
                pass
            return "playlist" if uri else "resumed"
        except Exception as e:
            log(f"spotify api: {e}")
    pc.launch(uri or "spotify:")
    time.sleep(4.0)
    pc.key("play_pause")
    return "media key"
