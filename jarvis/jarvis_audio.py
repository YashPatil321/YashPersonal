"""
Atlas and your music, getting along.

  Knows when music is playing   reads Windows' own output meter (any app: Spotify, YouTube, games), so it never
                                has to guess from the microphone
  While music plays             claps don't count (songs are full of them), and the "keep talking without the name"
                                window is off, so lyrics never turn into commands
  Ducks when you talk to it     the moment you say "Atlas" or "Hey Jarvis", every other app drops to 15% volume, so
                                it can hear you and you can hear it. Your music comes back up a second after it's done.

Uses pycaw (Windows audio). Without it, Spotify's window title tells whether music is playing, and ducking pauses
and resumes with the media key instead.
"""

import sys
import threading
import time

IS_WIN = sys.platform == "win32"
DUCK_TO = 0.15               # other apps' volume while Atlas listens and talks
PLAYING_PEAK = 0.02          # output level that counts as something playing
MY_PROCESSES = {"python.exe", "pythonw.exe", "jarvis.exe", "atlas.exe"}


def _log(msg):
    print(time.strftime("[%H:%M:%S] ") + "audio: " + str(msg), flush=True)


class Ambient:
    def __init__(self, own_voice=lambda: False, spotify_title=None, media_key=None):
        """own_voice(): True while Atlas itself is talking (that's not 'music')."""
        self.own_voice, self.spotify_title, self.media_key = own_voice, spotify_title, media_key
        self.playing = False
        self.ducked = None           # {session name: old volume} or "paused"
        self.lock = threading.Lock()
        self.last_own = 0.0
        self.pycaw = False
        threading.Thread(target=self._watch, daemon=True).start()

    # ---- is music on? ----
    def _meter(self):
        from ctypes import POINTER, cast
        from comtypes import CLSCTX_ALL, CoInitialize
        from pycaw.pycaw import AudioUtilities, IAudioMeterInformation
        CoInitialize()
        dev = AudioUtilities.GetSpeakers()
        iface = dev.Activate(IAudioMeterInformation._iid_, CLSCTX_ALL, None)
        return cast(iface, POINTER(IAudioMeterInformation))

    def _watch(self):
        meter = None
        if IS_WIN:
            try:
                meter = self._meter()
                self.pycaw = True
            except Exception as e:
                _log(f"no output meter ({e}), using Spotify's window to tell if music is on")
        loud_since, quiet_since, last_title = None, None, 0.0
        while True:
            time.sleep(0.25)
            try:
                if self.own_voice():
                    self.last_own = time.time()
                    continue
                if time.time() - self.last_own < 1.0 or self.ducked:
                    continue   # its own voice is still echoing, or the music is ducked on purpose
                if meter is not None:
                    peak = meter.GetPeakValue()
                    now = time.time()
                    if peak > PLAYING_PEAK:
                        loud_since, quiet_since = loud_since or now, None
                        if now - loud_since > 1.0:
                            self.playing = True
                    else:
                        quiet_since, loud_since = quiet_since or now, None
                        if now - quiet_since > 2.0:
                            self.playing = False
                elif self.spotify_title and time.time() - last_title > 3:
                    last_title = time.time()
                    self.playing = bool(self.spotify_title())
            except Exception:
                time.sleep(2)

    # ---- ducking ----
    def duck(self):
        """Every other app quieter (or paused) while Atlas listens and answers."""
        with self.lock:
            if self.ducked or not self.playing:
                return
            if IS_WIN and self.pycaw:
                try:
                    from comtypes import CoInitialize
                    from pycaw.pycaw import AudioUtilities
                    CoInitialize()
                    saved = {}
                    for s in AudioUtilities.GetAllSessions():
                        name = (s.Process.name() if s.Process else "").lower()
                        if not name or name in MY_PROCESSES:
                            continue
                        v = s.SimpleAudioVolume
                        old = v.GetMasterVolume()
                        if old > DUCK_TO:
                            saved[(name, s.ProcessId)] = old
                            v.SetMasterVolume(DUCK_TO, None)
                    self.ducked = saved or None
                    return
                except Exception as e:
                    _log(f"duck: {e}")
            if self.media_key:
                self.media_key("play_pause")
                self.ducked = "paused"

    def unduck(self):
        with self.lock:
            d, self.ducked = self.ducked, None
            if not d:
                return
            if d == "paused":
                if self.media_key:
                    self.media_key("play_pause")
                return
            try:
                from comtypes import CoInitialize
                from pycaw.pycaw import AudioUtilities
                CoInitialize()
                for s in AudioUtilities.GetAllSessions():
                    name = (s.Process.name() if s.Process else "").lower()
                    old = d.get((name, s.ProcessId))
                    if old is not None:
                        s.SimpleAudioVolume.SetMasterVolume(old, None)
            except Exception as e:
                _log(f"unduck: {e}")

    def release_when_idle(self, busy, idle_secs=1.2):
        """Brings the music back once Atlas has been quiet for a moment. busy() is True while listening or talking."""
        def loop():
            quiet = None
            while True:
                time.sleep(0.2)
                if not self.ducked:
                    quiet = None
                    continue
                if busy():
                    quiet = None
                    continue
                quiet = quiet or time.time()
                if time.time() - quiet > idle_secs:
                    self.unduck()
                    quiet = None
        threading.Thread(target=loop, daemon=True).start()
