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

/// Lyrics over every display, lit word by word.
@MainActor
final class LyricsFeature {
    let settings = SettingsStore(key: "wave.lyrics.cache", default: LyraSettings())
    let nowPlaying: NowPlayingMonitor
    let engine: LyricsEngine
    private let keepAwake = KeepAwake()
    private var windows: [OverlayWindow] = []
    private var bag = Set<AnyCancellable>()

    init(nowPlaying: NowPlayingMonitor) {
        self.nowPlaying = nowPlaying
        engine = LyricsEngine(nowPlaying: nowPlaying, settings: settings)
        Publishers.CombineLatest(settings.$value.map(\.keepAwake), nowPlaying.$track.map { $0?.isPlaying ?? false })
            .sink { [weak self] keep, playing in self?.keepAwake.set(keep && playing, reason: "Wave is showing lyrics") }
            .store(in: &bag)
        rebuildWindows()
    }

    func apply(_ new: LyraSettings) {
        if settings.value != new { settings.value = new }
    }

    /// One click-through overlay per display; each hides itself when there is nothing to show.
    func rebuildWindows() {
        for w in windows { w.orderOut(nil) }
        windows = NSScreen.screens.map { screen in
            let w = OverlayWindow(screen: screen, level: .statusBar)
            let host = NSHostingView(rootView: LyricsOverlay(engine: engine, settings: settings, nowPlaying: nowPlaying))
            host.frame = NSRect(origin: .zero, size: screen.frame.size)
            w.contentView = host
            w.orderFrontRegardless()
            return w
        }
    }
}
