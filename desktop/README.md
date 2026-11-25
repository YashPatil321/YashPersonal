# Halo, Lyra and Wave: desktop music apps

Three menu-bar / system-tray apps that react to whatever is playing on your computer.

| App | What it does |
| --- | --- |
| **Halo** | Draws a soft light around the edges of your screen. The colours follow the album art and the glow pulses with the music. |
| **Lyra** | Floats the lyrics of the current song over your screen and lights each word at the moment it is sung. |
| **Wave** | A music visualizer that lives on your wallpaper, plus a desktop clock, a full-screen player and Spotify control. It has 12 visualizers, themes and album-colour mood sync. |

## Download

Every push builds installers in GitHub Actions (**Actions › Desktop apps › latest run › Artifacts**):

* `WaveSuite-macOS`: a .dmg with Halo, Lyra and Wave. Drag them to Applications. The first time, right-click an app and
  choose **Open** (the apps are not notarized).
* `WaveSuite-Windows`: `WaveSuite-Setup.exe`, which installs all three apps with Start menu shortcuts.

## Spotify

Wave follows any player with no sign-in. That is Spotify and Apple Music over AppleScript on a Mac, and anything in the
media flyout on Windows. **Connect Spotify** in Wave's dashboard adds:

* liking the song,
* playback control on any device,
* sharp cover art,
* exact song position.

Sign-in uses Authorization Code + PKCE against the Spotify app already set up for Jarvis (redirect
`http://127.0.0.1:8765/callback`), so no secret ships in the app. While a Spotify app is in development mode, only accounts
added under *User Management* on developer.spotify.com can sign in. To use your own app instead, paste its Client ID
in the dashboard's Spotify tab.

Both apps ship for **macOS** (Swift, `desktop/macos`) and **Windows** (C# / WPF, `desktop/windows`).
They are original apps. They follow one shared spec (this file), so they behave the same on both platforms.

---

## Building

Builds run in GitHub Actions (`.github/workflows/desktop.yml`) on a real Mac and a real Windows machine.
Each run uploads `Halo-macOS.zip`, `Lyra-macOS.zip`, `Halo-Windows.zip` and `Lyra-Windows.zip` as artifacts.

### macOS (needs Xcode 16 or later, macOS 14.2 or later)

```bash
cd desktop/macos
./scripts/bundle.sh          # builds both apps into desktop/macos/build/*.app
open build/Halo.app
```

The apps are ad-hoc signed, not notarized. The first time, right-click the app and choose **Open**. You can also run
`xattr -dr com.apple.quarantine Halo.app`.

### Windows (needs the .NET 8 SDK on Windows 10 22H2 or Windows 11)

```powershell
cd desktop\windows
dotnet publish Halo\Halo.csproj -c Release -r win-x64 --self-contained -p:PublishSingleFile=true -o out\Halo
dotnet publish Lyra\Lyra.csproj -c Release -r win-x64 --self-contained -p:PublishSingleFile=true -o out\Lyra
dotnet publish Wave\Wave.csproj -c Release -r win-x64 --self-contained -p:PublishSingleFile=true -o out\Wave
iscc installer\WaveSuite.iss   # Inno Setup 6, builds out\WaveSuite-Setup.exe
```

---

## Shared spec

### 1. Now playing

Both apps watch the current track and poll it about every 500 ms. A track snapshot has these fields:
`player` (Spotify / Apple Music / other), `title`, `artist`, `album`, `durationSec`, `positionSec`, `isPlaying`,
`artwork` (an image, which may be missing) and `trackId` (any string that changes when the track changes).

* **macOS**: AppleScript to `com.spotify.client` and `com.apple.Music`. A player is only queried when it is already
  running, so the script never launches an app. Spotify gives an `artwork url`; Music gives `data of artwork 1`.
  The first call makes macOS show an Automation permission prompt.
* **Windows**: `GlobalSystemMediaTransportControlsSessionManager` (any app in the Windows media flyout).
  The thumbnail comes from the session's media properties.
* **Position extrapolation**: players only report position every so often. Between polls,
  `position = lastReportedPosition + (now - lastReportTime)` while playing. Snap to the reported value when the
  difference is over 0.35 s, and ease toward it otherwise, so the lyrics never jump backwards by a tiny amount.

### 2. System audio analysis (Halo)

* **macOS 14.2+**: Core Audio process tap (`CATapDescription` with a stereo global tap that excludes no process,
  plus a private aggregate device). macOS asks for *System Audio Recording* permission. The mic is never used.
* **Windows**: WASAPI loopback capture (NAudio `WasapiLoopbackCapture`).
* **Analysis**, per block of 1024 mono samples:
  1. Hann window, then FFT. Band energies: **bass** 20 to 150 Hz, **mid** 150 to 2000 Hz, **treble** 2000 to 8000 Hz.
  2. Normalise each band against a running peak: `peak = max(value, peak * 0.995)`, then `norm = value / max(peak, 1e-4)`.
  3. Smooth each band: attack 0.5, release 0.08 (`s += (x - s) * (x > s ? 0.5 : 0.08)`).
  4. **Beat**: `bassFlux = max(0, bass - previousBass)`. It is a beat when `bassFlux > 1.5 * mean(last 43 flux values)`,
     `bassNorm > 0.3`, and at least 250 ms have passed since the last beat. A beat sets `beat = 1`, which decays
     by a factor of 0.88 every 1/60 s.
  5. Publish `{ level, bass, mid, treble, beat }`, each from 0 to 1.

### 3. Halo: the glow

* There is one transparent, borderless, click-through overlay window per selected display. It sits above full-screen
  apps (mac: `.screenSaver` level plus `canJoinAllSpaces`/`fullScreenAuxiliary`; Windows: topmost with
  `WS_EX_TRANSPARENT | WS_EX_LAYERED | WS_EX_TOOLWINDOW | WS_EX_NOACTIVATE`).
* It draws a rounded rectangle stroke that hugs the display edge. The stroke uses an angular gradient of 2 or 3
  colours, plus a blurred copy underneath for the glow.
  * `thickness` 2 to 60 px (default 10). `glow` (blur radius) 0 to 80 px (default 36). Corner radius is 10 px on mac
    and 0 on Windows.
  * **Notch** (mac only, when the display has `auxiliaryTopLeftArea`): with *Notch compatibility* on, the top edge
    detours down and around the notch instead of running behind it.
* **Animation modes**
  * *Music Sync*: `brightness = 0.35 + 0.45 * bass + 0.25 * beat`, and `width = thickness * (1 + 0.6 * beat)`.
    The gradient rotates at `0.04 + 0.25 * mid` turns per second. With nothing playing it falls back to Breathe.
  * *Breathe*: `brightness = 0.55 + 0.25 * sin(2π t / 4 s)`, slow rotation of 0.03 turns per second.
  * *Static*: brightness 0.8, no rotation.
* **Colours**: *Match album art* (on by default) takes the 2 or 3 most vibrant dominant colours from the artwork.
  When there is no artwork it falls back to the custom colours. *Custom* uses colour pickers for primary, secondary and
  tertiary, with a primary/secondary split slider (default 60/40). Colour changes cross-fade over 600 ms.
* **Menu**: Enabled on/off, Mode, Use album colours, Settings…, Quit.
* **Settings window**: everything above, plus a display checklist and "Launch at login".

### 4. Lyra: the lyrics

#### Fetching

`GET https://lrclib.net/api/get?artist_name=&track_name=&album_name=&duration=` (duration in whole seconds).
On a 404, retry without `album_name`. If that fails too, call `GET /api/search?track_name=&artist_name=` and take the
first result whose duration is within 3 s. Send `User-Agent: Lyra/1.0 (desktop lyrics app)`. Cache results by
`artist|title` for the session.

The response JSON has `instrumental`, `syncedLyrics` (LRC), `plainLyrics`, `hasWordSync` and `lyricsfile`, in
priority order:

1. **`lyricsfile`** when `hasWordSync` is true. It is YAML with a `lines:` list. Each line has `text`, `start_ms`,
   optional `end_ms`, and an optional `words:` list of `{text, start_ms, end_ms}`. Scalars may be plain, `'single'`
   (`''` escapes a quote) or `"double"` (backslash escapes). Parse only the `lines:` block and stop at the next
   top-level key (for example `plain: |`). See `desktop/fixtures/lyricsfile-sample.yaml`; both platforms test against it.
2. **`syncedLyrics`** (LRC): `[mm:ss.xx]text` lines. Enhanced LRC `<mm:ss.xx>` word tags are honoured if present.
   Otherwise word times are **interpolated**: each line runs from its start to the next line's start (capped at
   start + 8 s), and its words share that span in proportion to `letterCount + 2` per word.
3. `plainLyrics` / none: show "No synced lyrics for this song" in the status panel and show nothing on screen.

A line with no `end_ms` ends at the next line's start (or `start + 4 s` for the last line).
An empty-text line or `♪` is an instrumental gap and shows nothing.

#### Model

`Lyrics { source: wordSynced | lineSynced | none, lines: [Line] }`,
`Line { start, end, text, words: [Word] }`, `Word { start, end, text }` with times in seconds.
`state(at t) → (lineIndex, wordIndex, wordProgress 0..1)`. Lookup is by binary search. A line stays current until the
next line starts, or until its end + 1.5 s, whichever comes first.

#### Timing offset

The user can nudge by ±0.25 s per click. The offset resets when the track changes. A global "lyrics latency" setting
is added on top (default +0.15 s, so words light slightly early, which reads as on time).

#### Overlay

A click-through, transparent window on the chosen display(s), above full-screen apps. Placement is Bottom (default),
Centre or Top. It fades in and out over 300 ms. It is hidden when nothing is playing or there are no lyrics.

#### Styles (5, on both platforms)

| Style | Look |
| --- | --- |
| **Spotlight** | The current line, large and centred. Sung words are full colour, upcoming words are dim, and the current word fills left to right with a gentle scale-up. The next line shows small underneath. |
| **Stack** | Three words stacked vertically. The current word is big; the previous one shrinks upward and fades. Each new word springs in from below. |
| **Thread** | Chat bubbles, one per line. The newest bubble slides up from the bottom and words appear inside it as they are sung. The previous 2 bubbles stay above it, faded. Alternate lines sit left (grey) or right (accent). |
| **Terminal** | Monospaced text on a dark translucent panel. Each line is typed out as it is sung, after a `>` prompt, with a blinking block cursor. The previous 3 lines stay above. |
| **Drift** | Each word appears where the previous one left off, then floats upward and fades out over about 2 s, so a line leaves a trail. |

#### Appearance settings

* **Font**: System (default), Rounded, Serif, Mono and Condensed. Mac uses SF Pro, SF Rounded, New York, SF Mono and
  Helvetica Neue Condensed; Windows uses Segoe UI, Segoe UI Variable Display/Arial Rounded fallback, Georgia, Cascadia
  Mono/Consolas and Bahnschrift Condensed.
* **Size**: 0.6 to 2.0 scale (default 1.0). The base is 44 pt for Spotlight.
* **Colours**: Text (sung), Highlight (current word), Dim (upcoming). There is also a *Match album art* toggle, which
  sets the highlight to the most vibrant artwork colour.
* **Shadow** toggle (default on) for legibility over any wallpaper.

#### Menu / window

* **Menu**: Show lyrics on/off, the 5 styles (with a check on the current one), Earlier (−0.25 s), Later (+0.25 s),
  Keep screen awake, Settings…, Quit.
* **Settings window** has four tabs:
  * *Style*: a live preview that plays a built-in demo line on loop, so it works with no music.
  * *Appearance*: the font, size and colour settings above.
  * *Display*: placement, display checklist, keep awake and latency.
  * *Status*: a checklist per player. It shows whether the player is running, whether Lyra can read it (mac
    Automation permission), what is playing (title – artist), and whether lyrics were found (word-synced /
    line-synced / none). On mac there is a "Ask for permission again" button that runs
    `tccutil reset AppleEvents <bundle id>`.
* **Keep screen awake**: while music plays, mac holds an `IOPMAssertion` and Windows calls `SetThreadExecutionState`.

### 5. Persistence

Settings persist as JSON in the user's settings store: mac uses `UserDefaults`; Windows uses
`%APPDATA%\Halo\settings.json` and `%APPDATA%\Lyra\settings.json`. Saves are debounced by 500 ms.

### 6. Wave

The visuals are one web engine in `desktop/visuals` (plain HTML, canvas and JS, no build step). It is shared by both
native shells: WKWebView on macOS and WebView2 on Windows. Open `desktop/visuals/index.html?mode=dashboard` in a browser
to try it with demo audio. The modes are `widget`, `clock`, `fullscreen`, `dashboard` and `gallery`.

**Host → page** (call in the page):

| Call | Purpose |
| --- | --- |
| `Wave.config(obj)` | Settings, full or partial. Keys are listed in `Wave.DEFAULTS` in `core.js`. |
| `Wave.setTrack(obj \| null)` | `{title, artist, album, art (URL or data URL), colors: [hex], isPlaying, position, duration, liked, source}` |
| `Wave.setStatus(obj)` | `{spotify: connected\|connecting\|disconnected\|error, spotifyUser, spotifyError, audio, platform, version}` |
| `Wave.pushAudio(obj)` | Every frame: `{bins: 64 log-spaced values 0..1 (40 Hz to 16 kHz), wave: 128 samples -1..1, level, bass, mid, treble, beat: bool}` |
| `Wave.setPaused(bool)` | Stop drawing while covered. |

**Page → host** (`webkit.messageHandlers.wave` / `chrome.webview.postMessage`), as `{cmd, ...}`:

| `cmd` | Meaning |
| --- | --- |
| `ready` | The page loaded. |
| `set` | `{key, value}`. Persist it and broadcast `config({key: value})` to the other pages. |
| `playpause`, `next`, `previous`, `like` | Media and Spotify actions. |
| `openFullscreen`, `closeFullscreen` | The full-screen player. |
| `editLayout` | Arrange mode: bring the widgets forward, then drag to move or resize. |
| `spotifyConnect`, `spotifyDisconnect`, `resetSettings`, `quit` | Spotify sign-in and app actions. |

**Native duties**:

* **Widget windows**: visualizer and clock.
  * Wallpaper placement: macOS uses window level `desktopWindow + 1`. Windows re-parents into the WorkerW behind the
    desktop icons, and re-attaches if Explorer restarts.
  * The other placements are *always on top* and *normal*. Frames persist.
* **Full-screen window**: shortcuts are Ctrl+Alt+F (⌃⌥F) for full screen and Ctrl+Alt+M (⌃⌥M) to show or hide the widgets.
* **System audio spectrum**: Core Audio tap / WASAPI loopback, fed in at the chosen frame rate.
* **Now playing**: AppleScript / SMTC, merged with Spotify Web API data when connected.
* **Spotify PKCE sign-in** with a loopback listener on port 8765.
  * Refresh token storage: Keychain on mac, DPAPI-protected file on Windows.
  * API calls: `/me/player` polled every second, `/me/tracks/contains`, `PUT`/`DELETE /me/tracks`,
    `/me/player/play|pause|next|previous`.

### 7. Not included

Unlike some commercial apps in this category, neither app draws over the **macOS lock screen**. That needs private
SkyLight APIs that change between macOS releases and are not allowed in signed apps. There is no licensing or payment
system either.
