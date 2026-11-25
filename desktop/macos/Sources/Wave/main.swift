import AppKit
import Carbon.HIToolbox
import Combine
import QuartzCore
import SharedKit
import WebKit

/// Wave: a music visualizer and clock on the desktop, a full-screen player, and Spotify control.
@MainActor
final class WaveController: NSObject, NSApplicationDelegate, NSMenuDelegate, NSWindowDelegate {
    private let nowPlaying = NowPlayingMonitor()
    private var spotify: SpotifyClient!
    private var tap: AnyObject?
    private var analyzer: AudioAnalyzer?

    private var widget: WebPanel?
    private var clock: WebPanel?
    private var dashboard: WebPanel?
    private var fullscreen: WebPanel?
    private var statusItem: NSStatusItem!
    private var frameTimer: Timer?
    private var bag = Set<AnyCancellable>()
    private var hotKeys: [EventHotKeyRef?] = []
    private var lastTrackJSON = ""
    private var lastBeatSent: CFTimeInterval = 0
    private var widgetsHidden = false
    private var editing = false
    private var cachedArt: (id: String, url: String) = ("", "")

    private let visualsDir: URL = {
        if let url = Bundle.main.url(forResource: "visuals", withExtension: nil) { return url }
        // `swift run` during development: use the folder in the repository.
        return URL(fileURLWithPath: #filePath).deletingLastPathComponent().deletingLastPathComponent()
            .deletingLastPathComponent().deletingLastPathComponent().appendingPathComponent("visuals")
    }()

    // MARK: Settings (JSON dictionary shared with the web engine)

    private var settings: [String: Any] = [:]
    private let settingsKey = "wave.settings"

    private func loadSettings() {
        if let data = UserDefaults.standard.data(forKey: settingsKey),
           let dict = try? JSONSerialization.jsonObject(with: data) as? [String: Any] {
            settings = dict
        }
    }

    private func saveSettings() {
        if let data = try? JSONSerialization.data(withJSONObject: settings) {
            UserDefaults.standard.set(data, forKey: settingsKey)
        }
    }

    private func setting<T>(_ key: String, _ fallback: T) -> T { settings[key] as? T ?? fallback }

    // MARK: Launch

    func applicationDidFinishLaunching(_ notification: Notification) {
        loadSettings()
        spotify = SpotifyClient(clientID: setting("spotifyClientId", ""))
        spotify.startPolling()

        statusItem = NSStatusBar.system.statusItem(withLength: NSStatusItem.variableLength)
        statusItem.button?.image = NSImage(systemSymbolName: "waveform", accessibilityDescription: "Wave")
        let menu = NSMenu()
        menu.delegate = self
        statusItem.menu = menu

        nowPlaying.start()
        if #available(macOS 14.2, *) {
            let t = SystemAudioTap()
            t.start()
            tap = t
            analyzer = t.analyzer
        }

        applyWidgets()
        registerHotKeys()

        Publishers.Merge3(nowPlaying.$track.map { _ in () }, nowPlaying.$artworkColors.map { _ in () }, spotify.$playback.map { _ in () })
            .sink { [weak self] in DispatchQueue.main.async { self?.pushTrack(force: false) } }
            .store(in: &bag)
        Publishers.Merge(spotify.$state.map { _ in () }, spotify.$userName.map { _ in () })
            .sink { [weak self] in DispatchQueue.main.async { self?.pushStatus() } }
            .store(in: &bag)
        NotificationCenter.default.publisher(for: NSApplication.didChangeScreenParametersNotification)
            .sink { [weak self] _ in self?.applyWidgets() }
            .store(in: &bag)

        restartFrameTimer()
        Timer.scheduledTimer(withTimeInterval: 1, repeats: true) { [weak self] _ in
            MainActor.assumeIsolated { self?.pushTrack(force: true); self?.pushStatus() }
        }

        if UserDefaults.standard.object(forKey: "wave.launched") == nil {
            UserDefaults.standard.set(true, forKey: "wave.launched")
            showDashboard()
        }
    }

    private var panels: [WebPanel] { [widget, clock, dashboard, fullscreen].compactMap { $0 } }

    private func makePanel(_ kind: WebPanel.Kind, window: NSWindow) -> WebPanel {
        let panel = WebPanel(kind: kind, window: window, visualsDir: visualsDir)
        panel.onMessage = { [weak self] p, msg in self?.handle(msg, from: p) }
        return panel
    }

    // MARK: Desktop widgets

    private func desktopLevel(_ placement: String) -> NSWindow.Level {
        switch placement {
        case "top": return .floating
        case "normal": return .normal
        default: return NSWindow.Level(rawValue: Int(CGWindowLevelForKey(.desktopWindow)) + 1) // above the wallpaper, below icons
        }
    }

    private func defaultFrame(_ kind: WebPanel.Kind) -> NSRect {
        let vf = NSScreen.main?.visibleFrame ?? NSRect(x: 0, y: 0, width: 1440, height: 900)
        if kind == .clock { return NSRect(x: vf.minX + 40, y: vf.maxY - 260, width: 520, height: 220) }
        return NSRect(x: vf.maxX - 640, y: vf.maxY - 360, width: 600, height: 320)
    }

    private func savedFrame(_ kind: WebPanel.Kind) -> NSRect {
        if let s = UserDefaults.standard.string(forKey: "wave.frame.\(kind.rawValue)") {
            let r = NSRectFromString(s)
            if r.width > 50, NSScreen.screens.contains(where: { $0.frame.intersects(r) }) { return r }
        }
        return defaultFrame(kind)
    }

    private func makeDesktopWindow(_ kind: WebPanel.Kind) -> NSWindow {
        let w = NSWindow(contentRect: savedFrame(kind), styleMask: .borderless, backing: .buffered, defer: false)
        w.isOpaque = false
        w.backgroundColor = .clear
        w.hasShadow = false
        w.ignoresMouseEvents = true
        w.isReleasedWhenClosed = false
        w.collectionBehavior = [.canJoinAllSpaces, .stationary, .ignoresCycle]
        w.delegate = self
        return w
    }

    /// Create, show, hide or re-level the widgets to match settings.
    private func applyWidgets() {
        let wantWidget = setting("widgetEnabled", true) && !widgetsHidden
        let wantClock = setting("clockEnabled", true) && !widgetsHidden
        if wantWidget && widget == nil { widget = makePanel(.widget, window: makeDesktopWindow(.widget)); pushAll(to: widget!) }
        if wantClock && clock == nil { clock = makePanel(.clock, window: makeDesktopWindow(.clock)); pushAll(to: clock!) }
        for (panel, want, placement) in [(widget, wantWidget, setting("widgetPlacement", "wallpaper")),
                                         (clock, wantClock, setting("clockPlacement", "wallpaper"))] {
            guard let panel else { continue }
            if want {
                panel.window.level = editing ? .floating : desktopLevel(placement)
                panel.window.ignoresMouseEvents = !editing
                panel.window.orderFrontRegardless()
            } else {
                panel.window.orderOut(nil)
            }
        }
    }

    private func setEditing(_ on: Bool) {
        editing = on
        applyWidgets()
        for p in [widget, clock].compactMap({ $0 }) where p.window.isVisible {
            p.setEditing(on) { [weak self] in self?.setEditing(false) }
        }
        if !on {
            for p in [widget, clock].compactMap({ $0 }) {
                UserDefaults.standard.set(NSStringFromRect(p.window.frame), forKey: "wave.frame.\(p.kind.rawValue)")
            }
        } else {
            NSApp.activate(ignoringOtherApps: true)
        }
    }

    // MARK: Dashboard and full screen

    func showDashboard() {
        if dashboard == nil {
            let w = NSWindow(contentRect: NSRect(x: 0, y: 0, width: 1060, height: 760),
                             styleMask: [.titled, .closable, .miniaturizable, .resizable, .fullSizeContentView],
                             backing: .buffered, defer: false)
            w.title = "Wave"
            w.titlebarAppearsTransparent = true
            w.backgroundColor = NSColor(red: 0.04, green: 0.04, blue: 0.06, alpha: 1)
            w.minSize = NSSize(width: 720, height: 520)
            w.isReleasedWhenClosed = false
            w.delegate = self
            w.center()
            dashboard = makePanel(.dashboard, window: w)
            pushAll(to: dashboard!)
        }
        NSApp.activate(ignoringOtherApps: true)
        dashboard?.window.makeKeyAndOrderFront(nil)
    }

    func toggleFullscreen() {
        if let fs = fullscreen {
            fs.window.orderOut(nil)
            fullscreen = nil
            return
        }
        let screen = NSScreen.screens.first { $0.frame.contains(NSEvent.mouseLocation) } ?? NSScreen.main!
        let w = KeyableWindow(contentRect: screen.frame, styleMask: .borderless, backing: .buffered, defer: false)
        w.level = .mainMenu + 1
        w.backgroundColor = .black
        w.isReleasedWhenClosed = false
        w.collectionBehavior = [.canJoinAllSpaces, .fullScreenAuxiliary]
        w.setFrame(screen.frame, display: true)
        fullscreen = makePanel(.fullscreen, window: w)
        pushAll(to: fullscreen!)
        NSApp.activate(ignoringOtherApps: true)
        w.makeKeyAndOrderFront(nil)
        w.makeFirstResponder(fullscreen!.webView)
    }

    func windowWillClose(_ notification: Notification) {
        if (notification.object as? NSWindow) === dashboard?.window { dashboard = nil }
    }

    // MARK: Messages from the page

    private func handle(_ msg: [String: Any], from panel: WebPanel) {
        guard let cmd = msg["cmd"] as? String else { return }
        switch cmd {
        case "ready":
            pushAll(to: panel)
        case "set":
            guard let key = msg["key"] as? String else { return }
            settings[key] = msg["value"] ?? NSNull()
            saveSettings()
            for p in panels where p !== panel { p.call("config", [key: settings[key] ?? NSNull()]) }
            applySetting(key)
        case "playpause": media("playpause")
        case "next": media("next")
        case "previous": media("previous")
        case "like": Task { await spotify.toggleLike(); pushTrack(force: true) }
        case "openFullscreen": if fullscreen == nil { toggleFullscreen() }
        case "closeFullscreen": if fullscreen != nil { toggleFullscreen() }
        case "editLayout": setEditing(!editing)
        case "spotifyConnect":
            spotify.clientID = setting("spotifyClientId", "")
            spotify.connect()
        case "spotifyDisconnect": spotify.disconnect()
        case "resetSettings":
            settings = [:]
            saveSettings()
            for p in panels { p.webView.reload() }
            applyWidgets()
        case "quit": NSApp.terminate(nil)
        default: break
        }
    }

    private func applySetting(_ key: String) {
        switch key {
        case "widgetEnabled", "clockEnabled", "widgetPlacement", "clockPlacement": applyWidgets()
        case "launchAtLogin": LoginItem.set(setting("launchAtLogin", false))
        case "fps": restartFrameTimer()
        case "spotifyClientId": spotify.clientID = setting("spotifyClientId", "")
        default: break
        }
    }

    // MARK: Media control

    private func media(_ action: String) {
        if spotify.isConnected, spotify.playback != nil {
            Task {
                switch action {
                case "next": await spotify.next()
                case "previous": await spotify.previous()
                default: await spotify.playPause()
                }
                pushTrack(force: true)
            }
            return
        }
        // Without Spotify sign-in, drive the local player over AppleScript.
        let app = nowPlaying.track?.player ?? (Player.spotify.isRunning ? .spotify : .music)
        let verb = ["next": "next track", "previous": "previous track"][action] ?? "playpause"
        let source = "tell application id \"\(app.bundleID)\" to \(verb)"
        DispatchQueue.global(qos: .userInitiated).async {
            var err: NSDictionary?
            NSAppleScript(source: source)?.executeAndReturnError(&err)
        }
    }

    // MARK: Pushing state to the pages

    private func trackPayload() -> [String: Any]? {
        if let p = spotify.playback, spotify.isConnected {
            let age = Date().timeIntervalSince(p.fetchedAt)
            var t: [String: Any] = [
                "title": p.title, "artist": p.artist, "album": p.album, "isPlaying": p.isPlaying,
                "position": p.position + (p.isPlaying ? age : 0), "duration": p.duration, "liked": p.liked, "source": "spotify",
            ]
            if let u = p.artURL { t["art"] = u.absoluteString }
            if nowPlaying.track?.title == p.title, !nowPlaying.artworkColors.isEmpty { t["colors"] = hexColors() }
            return t
        }
        guard let tr = nowPlaying.track else { return nil }
        var t: [String: Any] = [
            "title": tr.title, "artist": tr.artist, "album": tr.album, "isPlaying": tr.isPlaying,
            "position": nowPlaying.position(), "duration": tr.duration, "liked": false, "source": tr.player.rawValue,
        ]
        if let u = tr.artworkURL { t["art"] = u.absoluteString }
        else if let img = nowPlaying.artwork {
            // Encode Apple Music artwork once per track, not on every push.
            if cachedArt.id != tr.id, let data = img.jpegThumbnail(side: 600) {
                cachedArt = (tr.id, "data:image/jpeg;base64," + data.base64EncodedString())
            }
            if cachedArt.id == tr.id { t["art"] = cachedArt.url }
        }
        if !nowPlaying.artworkColors.isEmpty { t["colors"] = hexColors() }
        return t
    }

    private func hexColors() -> [String] {
        nowPlaying.artworkColors.map { c in
            let s = c.usingColorSpace(.sRGB) ?? c
            return String(format: "#%02x%02x%02x", Int(s.redComponent * 255), Int(s.greenComponent * 255), Int(s.blueComponent * 255))
        }
    }

    private func pushTrack(force: Bool) {
        let payload: Any = trackPayload() ?? NSNull()
        // Compare without position so we only resend when something visible changed (or on the 1 s tick).
        var key = ""
        if var d = payload as? [String: Any] { d["position"] = nil; key = "\(d.description.hashValue)" }
        if !force && key == lastTrackJSON { return }
        lastTrackJSON = key
        for p in panels { p.call("setTrack", payload) }
    }

    private func pushStatus() {
        var audio = "Needs macOS 14.2 or later"
        if #available(macOS 14.2, *), let t = tap as? SystemAudioTap {
            audio = t.lastError.map { "Not available: \($0)" } ?? (t.analyzer.hasRecentAudio ? "Hearing system audio" : "Listening (nothing playing)")
        }
        var sp = "disconnected", err = ""
        switch spotify.state {
        case .connected: sp = "connected"
        case .connecting: sp = "connecting"
        case .error(let e): sp = "error"; err = e
        case .disconnected: sp = "disconnected"
        }
        let version = Bundle.main.object(forInfoDictionaryKey: "CFBundleShortVersionString") as? String ?? "dev"
        let status: [String: Any] = ["spotify": sp, "spotifyUser": spotify.userName, "spotifyError": err, "audio": audio,
                                     "platform": "macOS", "version": version]
        for p in panels { p.call("setStatus", status) }
    }

    private func pushAll(to panel: WebPanel) {
        panel.call("config", settings)
        panel.call("setTrack", trackPayload() ?? NSNull())
        pushStatus()
    }

    private func restartFrameTimer() {
        frameTimer?.invalidate()
        let fps = max(15, min(120, setting("fps", 60.0)))
        let t = Timer(timeInterval: 1 / fps, repeats: true) { [weak self] _ in MainActor.assumeIsolated { self?.frame() } }
        RunLoop.main.add(t, forMode: .common)
        frameTimer = t
    }

    /// Send one audio frame to every visible page.
    private func frame() {
        guard let analyzer else { return }
        let now = CACurrentMediaTime()
        let levels = analyzer.levels(at: now)
        let spec = analyzer.spectrum(at: now)
        let beatAt = analyzer.lastBeatTime
        let beat = beatAt > lastBeatSent && now - beatAt < 0.1
        if beat { lastBeatSent = beatAt }
        let round2: (Float) -> Double = { (Double($0) * 1000).rounded() / 1000 }
        let payload: [String: Any] = [
            "bins": spec.bins.map(round2), "wave": spec.wave.map(round2),
            "level": round2(levels.level), "bass": round2(levels.bass), "mid": round2(levels.mid), "treble": round2(levels.treble),
            "beat": beat,
        ]
        let pauseCovered = setting("pauseWhenCovered", true)
        for p in panels {
            let visible = p.isVisibleOnScreen
            if p.kind == .widget || p.kind == .clock { p.call("setPaused", pauseCovered && !visible && !editing) }
            if visible || p.kind == .fullscreen { p.call("pushAudio", payload) }
        }
    }

    // MARK: Global shortcuts: ⌃⌥F full screen, ⌃⌥M hide/show widgets

    private func registerHotKeys() {
        var spec = EventTypeSpec(eventClass: OSType(kEventClassKeyboard), eventKind: UInt32(kEventHotKeyPressed))
        InstallEventHandler(GetApplicationEventTarget(), { _, event, _ in
            var id = EventHotKeyID()
            GetEventParameter(event, EventParamName(kEventParamDirectObject), EventParamType(typeEventHotKeyID), nil,
                              MemoryLayout<EventHotKeyID>.size, nil, &id)
            DispatchQueue.main.async {
                MainActor.assumeIsolated {
                    if id.id == 1 { waveController.toggleFullscreen() }
                    if id.id == 2 { waveController.toggleWidgets() }
                }
            }
            return noErr
        }, 1, &spec, nil, nil)
        for (i, key) in [(UInt32(1), UInt32(kVK_ANSI_F)), (UInt32(2), UInt32(kVK_ANSI_M))] {
            var ref: EventHotKeyRef?
            RegisterEventHotKey(key, UInt32(controlKey | optionKey), EventHotKeyID(signature: OSType(0x5741_5645), id: i),
                                GetApplicationEventTarget(), 0, &ref)
            hotKeys.append(ref)
        }
    }

    func toggleWidgets() {
        widgetsHidden.toggle()
        applyWidgets()
    }

    // MARK: Menu

    func menuNeedsUpdate(_ menu: NSMenu) {
        menu.removeAllItems()
        let title = spotify.playback.map { "\($0.title) – \($0.artist)" } ?? nowPlaying.track.map { "\($0.title) – \($0.artist)" } ?? "Nothing playing"
        let header = NSMenuItem(title: title, action: nil, keyEquivalent: "")
        header.isEnabled = false
        menu.addItem(header)
        menu.addItem(.separator())
        menu.addItem(ActionMenuItem("Open Wave…", key: ",") { [unowned self] in showDashboard() })
        menu.addItem(ActionMenuItem("Full Screen  ⌃⌥F") { [unowned self] in toggleFullscreen() })
        menu.addItem(ActionMenuItem(widgetsHidden ? "Show Widgets  ⌃⌥M" : "Hide Widgets  ⌃⌥M") { [unowned self] in toggleWidgets() })
        menu.addItem(ActionMenuItem(editing ? "Done Arranging" : "Arrange Widgets") { [unowned self] in setEditing(!editing) })
        menu.addItem(.separator())
        menu.addItem(ActionMenuItem("Play / Pause") { [unowned self] in media("playpause") })
        menu.addItem(ActionMenuItem("Next Track") { [unowned self] in media("next") })
        if spotify.isConnected, let p = spotify.playback {
            menu.addItem(ActionMenuItem(p.liked ? "Remove from Liked Songs" : "Save to Liked Songs") { [unowned self] in
                Task { await spotify.toggleLike(); pushTrack(force: true) }
            })
        }
        menu.addItem(.separator())
        menu.addItem(ActionMenuItem("Quit Wave", key: "q") { NSApp.terminate(nil) })
    }
}

extension NSImage {
    func jpegThumbnail(side: CGFloat) -> Data? {
        let target = NSSize(width: side, height: side)
        let img = NSImage(size: target)
        img.lockFocus()
        draw(in: NSRect(origin: .zero, size: target), from: .zero, operation: .copy, fraction: 1)
        img.unlockFocus()
        guard let tiff = img.tiffRepresentation, let rep = NSBitmapImageRep(data: tiff) else { return nil }
        return rep.representation(using: .jpeg, properties: [.compressionFactor: 0.85])
    }
}

let app = NSApplication.shared
let waveController = MainActor.assumeIsolated { WaveController() }
app.delegate = waveController
app.setActivationPolicy(.accessory)
app.run()
