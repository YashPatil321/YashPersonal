import AppKit
import Combine
import QuartzCore
import SharedKit
import SwiftUI

enum GlowMode: String, Codable, CaseIterable, Identifiable {
    case music = "Music Sync"
    case breathe = "Breathe"
    case still = "Static"
    var id: String { rawValue }
}

struct HaloSettings: Codable, Equatable {
    var enabled = true
    var mode: GlowMode = .music
    var useAlbumColors = true
    var colorCount = 2
    var primary = RGBAColor(1.0, 0.18, 0.42)
    var secondary = RGBAColor(0.22, 0.45, 1.0)
    var tertiary = RGBAColor(0.62, 0.3, 1.0)
    var split = 0.6
    var thickness = 10.0
    var glow = 36.0
    var notchAware = true
    var displays: [String] = []
}

@MainActor
final class HaloController: NSObject, NSApplicationDelegate, NSMenuDelegate {
    let settings = SettingsStore(key: "halo.settings", default: HaloSettings())
    let nowPlaying = NowPlayingMonitor()
    private var tap: AnyObject?
    private var analyzer: AudioAnalyzer?

    private var statusItem: NSStatusItem!
    private var windows: [(window: OverlayWindow, view: GlowView, screen: NSScreen)] = []
    private var timer: Timer?
    private var bag = Set<AnyCancellable>()
    private lazy var settingsWindow = SettingsWindowController(title: "Halo", size: NSSize(width: 460, height: 720)) { [unowned self] in
        AnyView(HaloSettingsView(settings: self.settings, nowPlaying: self.nowPlaying, controller: self))
    }

    // Animation state
    private var shownColors: [RGBAColor] = []
    private var rotation = 0.0
    private var lastTick = CACurrentMediaTime()
    private var lastHeardMusic = 0.0

    func applicationDidFinishLaunching(_ notification: Notification) {
        statusItem = NSStatusBar.system.statusItem(withLength: NSStatusItem.variableLength)
        statusItem.button?.image = NSImage(systemSymbolName: "rectangle.dashed", accessibilityDescription: "Halo")
        let menu = NSMenu()
        menu.delegate = self
        statusItem.menu = menu

        nowPlaying.start()
        startAudio()
        rebuildWindows()

        NotificationCenter.default.publisher(for: NSApplication.didChangeScreenParametersNotification)
            .sink { [weak self] _ in self?.rebuildWindows() }
            .store(in: &bag)
        settings.$value
            .map { [$0.enabled ? "1" : "0"] + $0.displays }
            .removeDuplicates()
            .dropFirst()
            .sink { [weak self] _ in DispatchQueue.main.async { self?.rebuildWindows() } }
            .store(in: &bag)

        let t = Timer(timeInterval: 1.0 / 60, repeats: true) { [weak self] _ in
            MainActor.assumeIsolated { self?.tick() }
        }
        RunLoop.main.add(t, forMode: .common)
        timer = t

        if UserDefaults.standard.object(forKey: "halo.launched") == nil {
            UserDefaults.standard.set(true, forKey: "halo.launched")
            showSettings()
        }
    }

    private func startAudio() {
        if #available(macOS 14.2, *) {
            let t = SystemAudioTap()
            t.start()
            tap = t
            analyzer = t.analyzer
        }
    }

    var audioStatus: String {
        if #available(macOS 14.2, *), let t = tap as? SystemAudioTap {
            if let e = t.lastError { return "Not available: \(e)" }
            return t.analyzer.hasRecentAudio ? "Hearing your music" : "Listening (nothing playing)"
        }
        return "Needs macOS 14.2 or later"
    }

    func rebuildWindows() {
        for w in windows { w.window.orderOut(nil) }
        windows.removeAll()
        guard settings.value.enabled else { return }
        for screen in NSScreen.selected(settings.value.displays) {
            let window = OverlayWindow(screen: screen)
            let view = GlowView(frame: NSRect(origin: .zero, size: screen.frame.size))
            window.contentView = view
            window.orderFrontRegardless()
            windows.append((window, view, screen))
        }
    }

    func showSettings() { settingsWindow.show() }

    // MARK: Animation

    private func targetColors() -> (colors: [RGBAColor], locations: [Double]) {
        let s = settings.value
        var base: [RGBAColor]
        if s.useAlbumColors, !nowPlaying.artworkColors.isEmpty {
            base = nowPlaying.artworkColors.prefix(s.colorCount).map { RGBAColor($0) }
        } else {
            base = [s.primary, s.secondary, s.tertiary]
        }
        while base.count < 3 { base.append(base.last ?? s.primary) }
        let b = 0.08
        if s.colorCount >= 3 {
            let third = 1.0 / 3
            return ([base[0], base[0], base[1], base[1], base[2], base[2], base[0]],
                    [0, third - b, third + b, 2 * third - b, 2 * third + b, 1 - b, 1])
        }
        let split = min(max(s.split, 0.15), 0.85)
        return ([base[0], base[0], base[1], base[1], base[0]],
                [0, split - b, split + b, 1 - b, 1])
    }

    private func tick() {
        let now = CACurrentMediaTime()
        let dt = min(now - lastTick, 0.1)
        lastTick = now
        guard !windows.isEmpty else { return }
        let s = settings.value

        let target = targetColors()
        if shownColors.count != target.colors.count {
            shownColors = target.colors
        } else {
            // About a 600 ms cross-fade.
            let k = min(1, dt * 5)
            shownColors = zip(shownColors, target.colors).map { $0.mixed(with: $1, k) }
        }

        let levels = analyzer?.levels(at: now) ?? .silent
        if levels.level > 0.02 && nowPlaying.isPlaying { lastHeardMusic = now }
        var mode = s.mode
        if mode == .music && now - lastHeardMusic > 2 { mode = .breathe }

        var brightness: Double
        var pulse = 0.0
        var speed: Double
        switch mode {
        case .music:
            brightness = 0.35 + 0.45 * Double(levels.bass) + 0.25 * Double(levels.beat)
            pulse = Double(levels.beat)
            speed = 0.04 + 0.25 * Double(levels.mid)
        case .breathe:
            brightness = 0.55 + 0.25 * sin(2 * .pi * now / 4)
            speed = 0.03
        case .still:
            brightness = 0.8
            speed = 0
        }
        brightness = min(1, brightness)
        rotation = (rotation + speed * dt).truncatingRemainder(dividingBy: 1)

        let frame = GlowFrame(colors: shownColors, locations: target.locations,
                              rotation: rotation, brightness: brightness, pulse: pulse)
        for w in windows {
            w.view.configure(screen: w.screen, thickness: s.thickness, glowRadius: s.glow, notchAware: s.notchAware)
            w.view.render(frame)
        }
    }

    // MARK: Menu

    func menuNeedsUpdate(_ menu: NSMenu) {
        menu.removeAllItems()
        let s = settings.value
        let header = NSMenuItem(title: nowPlaying.track.map { "\($0.title) – \($0.artist)" } ?? "Nothing playing",
                                action: nil, keyEquivalent: "")
        header.isEnabled = false
        menu.addItem(header)
        menu.addItem(.separator())
        menu.addItem(ActionMenuItem("Enabled", state: s.enabled) { [unowned self] in settings.value.enabled.toggle() })
        let modeItem = NSMenuItem(title: "Mode", action: nil, keyEquivalent: "")
        let modes = NSMenu()
        for m in GlowMode.allCases {
            modes.addItem(ActionMenuItem(m.rawValue, state: s.mode == m) { [unowned self] in settings.value.mode = m })
        }
        modeItem.submenu = modes
        menu.addItem(modeItem)
        menu.addItem(ActionMenuItem("Use Album Colours", state: s.useAlbumColors) { [unowned self] in
            settings.value.useAlbumColors.toggle()
        })
        menu.addItem(.separator())
        menu.addItem(ActionMenuItem("Settings…", key: ",") { [unowned self] in showSettings() })
        menu.addItem(ActionMenuItem("Quit Halo", key: "q") { NSApp.terminate(nil) })
    }
}

let app = NSApplication.shared
let controller = MainActor.assumeIsolated { HaloController() }
app.delegate = controller
app.setActivationPolicy(.accessory)
app.run()
