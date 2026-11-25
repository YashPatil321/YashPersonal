import AppKit
import Combine
import LyricsKit
import SharedKit
import SwiftUI

/// The click-through layer that shows the lyrics on one display.
struct LyricsOverlay: View {
    @ObservedObject var engine: LyricsEngine
    @ObservedObject var settings: SettingsStore<LyraSettings>
    @ObservedObject var nowPlaying: NowPlayingMonitor

    var body: some View {
        let s = settings.value
        let theme = LyricTheme(s, albumColors: nowPlaying.artworkColors)
        let show = engine.shouldShow
        TimelineView(.animation(minimumInterval: nil, paused: !show)) { _ in
            LyricStyleView(style: s.style, lyrics: engine.lyrics, t: engine.time(), theme: theme)
        }
        .opacity(show ? 1 : 0)
        .animation(.easeInOut(duration: 0.3), value: show)
        .frame(maxWidth: .infinity, maxHeight: .infinity, alignment: alignment(s.placement))
        .padding(.vertical, 90)
        .padding(.horizontal, 60)
    }

    private func alignment(_ p: Placement) -> Alignment {
        switch p {
        case .top: return .top
        case .center: return .center
        case .bottom: return .bottom
        }
    }
}

@MainActor
final class LyraController: NSObject, NSApplicationDelegate, NSMenuDelegate {
    let settings = SettingsStore(key: "lyra.settings", default: LyraSettings())
    let nowPlaying = NowPlayingMonitor()
    lazy var engine = LyricsEngine(nowPlaying: nowPlaying, settings: settings)
    private let keepAwake = KeepAwake()

    private var statusItem: NSStatusItem!
    private var windows: [OverlayWindow] = []
    private var bag = Set<AnyCancellable>()
    private lazy var settingsWindow = SettingsWindowController(title: "Lyra", size: NSSize(width: 620, height: 640)) { [unowned self] in
        AnyView(LyraSettingsView(settings: self.settings, engine: self.engine, nowPlaying: self.nowPlaying))
    }

    func applicationDidFinishLaunching(_ notification: Notification) {
        statusItem = NSStatusBar.system.statusItem(withLength: NSStatusItem.variableLength)
        statusItem.button?.image = NSImage(systemSymbolName: "quote.bubble", accessibilityDescription: "Lyra")
        let menu = NSMenu()
        menu.delegate = self
        statusItem.menu = menu

        nowPlaying.start()
        _ = engine
        rebuildWindows()

        NotificationCenter.default.publisher(for: NSApplication.didChangeScreenParametersNotification)
            .sink { [weak self] _ in self?.rebuildWindows() }
            .store(in: &bag)
        settings.$value.map(\.displays).removeDuplicates().dropFirst()
            .sink { [weak self] _ in DispatchQueue.main.async { self?.rebuildWindows() } }
            .store(in: &bag)
        Publishers.CombineLatest(settings.$value.map(\.keepAwake), nowPlaying.$track.map { $0?.isPlaying ?? false })
            .sink { [weak self] keep, playing in self?.keepAwake.set(keep && playing, reason: "Lyra is showing lyrics") }
            .store(in: &bag)

        if UserDefaults.standard.object(forKey: "lyra.launched") == nil {
            UserDefaults.standard.set(true, forKey: "lyra.launched")
            showSettings()
        }
    }

    func rebuildWindows() {
        for w in windows { w.orderOut(nil) }
        windows = NSScreen.selected(settings.value.displays).map { screen in
            let w = OverlayWindow(screen: screen, level: .statusBar)
            let host = NSHostingView(rootView: LyricsOverlay(engine: engine, settings: settings, nowPlaying: nowPlaying))
            host.frame = NSRect(origin: .zero, size: screen.frame.size)
            w.contentView = host
            w.orderFrontRegardless()
            return w
        }
    }

    func showSettings() { settingsWindow.show() }

    func menuNeedsUpdate(_ menu: NSMenu) {
        menu.removeAllItems()
        let s = settings.value
        let header = NSMenuItem(title: nowPlaying.track.map { "\($0.title) – \($0.artist)" } ?? "Nothing playing",
                                action: nil, keyEquivalent: "")
        header.isEnabled = false
        menu.addItem(header)
        let status = NSMenuItem(title: engine.status.label, action: nil, keyEquivalent: "")
        status.isEnabled = false
        menu.addItem(status)
        menu.addItem(.separator())
        menu.addItem(ActionMenuItem("Show Lyrics", key: "l", state: s.showLyrics) { [unowned self] in
            settings.value.showLyrics.toggle()
        })
        menu.addItem(.separator())
        for style in LyricStyle.allCases {
            menu.addItem(ActionMenuItem(style.rawValue, state: s.style == style) { [unowned self] in settings.value.style = style })
        }
        menu.addItem(.separator())
        let offset = engine.offset == 0 ? "" : String(format: "  (%+.2f s)", engine.offset)
        menu.addItem(ActionMenuItem("Lyrics Earlier" + offset, key: "[") { [unowned self] in engine.nudge(0.25) })
        menu.addItem(ActionMenuItem("Lyrics Later", key: "]") { [unowned self] in engine.nudge(-0.25) })
        menu.addItem(ActionMenuItem("Keep Screen Awake", state: s.keepAwake) { [unowned self] in settings.value.keepAwake.toggle() })
        menu.addItem(.separator())
        menu.addItem(ActionMenuItem("Settings…", key: ",") { [unowned self] in showSettings() })
        menu.addItem(ActionMenuItem("Quit Lyra", key: "q") { NSApp.terminate(nil) })
    }
}

let app = NSApplication.shared
let controller = MainActor.assumeIsolated { LyraController() }
app.delegate = controller
app.setActivationPolicy(.accessory)
app.run()
