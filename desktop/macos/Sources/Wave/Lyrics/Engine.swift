import AppKit
import Combine
import LyricsKit
import QuartzCore
import SharedKit
import SwiftUI

enum LyricStyle: String, Codable, CaseIterable, Identifiable {
    case spotlight = "Spotlight"
    case stack = "Stack"
    case thread = "Thread"
    case terminal = "Terminal"
    case drift = "Drift"
    var id: String { rawValue }

    var blurb: String {
        switch self {
        case .spotlight: return "The line, large, filling word by word."
        case .stack: return "Three words stacked, the newest springs in."
        case .thread: return "A chat bubble for every line."
        case .terminal: return "Typed out at a blinking cursor."
        case .drift: return "Words rise and fade as they are sung."
        }
    }
}

enum LyricFont: String, Codable, CaseIterable, Identifiable {
    case system = "System", rounded = "Rounded", serif = "Serif", mono = "Mono", condensed = "Condensed"
    var id: String { rawValue }

    func font(size: CGFloat, weight: Font.Weight = .bold) -> Font {
        switch self {
        case .system: return .system(size: size, weight: weight, design: .default)
        case .rounded: return .system(size: size, weight: weight, design: .rounded)
        case .serif: return .system(size: size, weight: weight, design: .serif)
        case .mono: return .system(size: size, weight: weight, design: .monospaced)
        case .condensed: return .custom("HelveticaNeue-CondensedBlack", size: size)
        }
    }
}

enum Placement: String, Codable, CaseIterable, Identifiable {
    case top = "Top", center = "Centre", bottom = "Bottom"
    var id: String { rawValue }
}

struct LyraSettings: Codable, Equatable {
    var showLyrics = true
    var style: LyricStyle = .spotlight
    var font: LyricFont = .system
    var size = 1.0
    var textColor = RGBAColor(1, 1, 1)
    var highlightColor = RGBAColor(1.0, 0.42, 0.62)
    var dimColor = RGBAColor(1, 1, 1, 0.38)
    var matchAlbum = false
    var shadow = true
    var placement: Placement = .bottom
    var displays: [String] = []
    var keepAwake = false
    var latency = 0.15
}

extension LyraSettings {
    /// Built from Wave's shared settings dictionary (keys documented in desktop/visuals/core.js).
    init(dict d: [String: Any]) {
        self.init()
        func num(_ k: String) -> Double? { (d[k] as? NSNumber)?.doubleValue }
        showLyrics = d["lyricsEnabled"] as? Bool ?? showLyrics
        if let v = d["lyricsStyle"] as? String, let st = LyricStyle.allCases.first(where: { $0.rawValue.lowercased() == v.lowercased() }) { style = st }
        if let v = d["lyricsFont"] as? String, let f = LyricFont.allCases.first(where: { $0.rawValue.lowercased() == v.lowercased() }) { font = f }
        size = num("lyricsSize") ?? size
        textColor = (d["lyricsText"] as? String).flatMap(RGBAColor.init(hex:)) ?? textColor
        highlightColor = (d["lyricsHighlight"] as? String).flatMap(RGBAColor.init(hex:)) ?? highlightColor
        let dim = num("lyricsDimOpacity") ?? 0.38
        dimColor = RGBAColor(textColor.r, textColor.g, textColor.b, dim)
        matchAlbum = d["lyricsMatchAlbum"] as? Bool ?? matchAlbum
        shadow = d["lyricsShadow"] as? Bool ?? shadow
        switch d["lyricsPlacement"] as? String {
        case "top": placement = .top
        case "center": placement = .center
        default: placement = .bottom
        }
        keepAwake = d["lyricsKeepAwake"] as? Bool ?? keepAwake
        latency = num("lyricsLatency") ?? latency
    }
}

enum LyricsStatus: Equatable {
    case idle, loading, found(LyricsSource), notFound
    var label: String {
        switch self {
        case .idle: return "Waiting for a song"
        case .loading: return "Looking for lyrics…"
        case .found(let s): return "Found (\(s.rawValue.lowercased()))"
        case .notFound: return "No synced lyrics for this song"
        }
    }
}

/// Glues the player to the lyrics: fetches on track change and works out the time to display.
@MainActor
final class LyricsEngine: ObservableObject {
    @Published private(set) var lyrics: Lyrics = .none
    @Published private(set) var status: LyricsStatus = .idle
    @Published var offset: Double = 0

    let nowPlaying: NowPlayingMonitor
    let settings: SettingsStore<LyraSettings>
    private let client = LRCLibClient()
    private var currentKey = ""
    private var fetch: Task<Void, Never>?
    private var bag = Set<AnyCancellable>()
    /// When set and returning a value, used instead of the local player's position (e.g. Spotify's exact progress).
    var positionOverride: (() -> Double?)?

    init(nowPlaying: NowPlayingMonitor, settings: SettingsStore<LyraSettings>) {
        self.nowPlaying = nowPlaying
        self.settings = settings
        nowPlaying.$track
            .sink { [weak self] t in self?.trackChanged(t) }
            .store(in: &bag)
    }

    private func trackChanged(_ track: Track?) {
        guard let track else {
            currentKey = ""
            fetch?.cancel()
            lyrics = .none
            status = .idle
            return
        }
        let key = "\(track.player.rawValue)|\(track.id)"
        guard key != currentKey else { return }
        currentKey = key
        offset = 0
        lyrics = .none
        status = .loading
        fetch?.cancel()
        let q = LRCLibClient.Query(title: track.title, artist: track.artist, album: track.album, duration: track.duration)
        fetch = Task { [weak self, client] in
            let result = await client.lyrics(for: q)
            guard !Task.isCancelled else { return }
            await MainActor.run {
                guard let self, self.currentKey == key else { return }
                self.lyrics = result
                self.status = result.source == .none ? .notFound : .found(result.source)
            }
        }
    }

    /// The lyric clock, including the user's nudge and the latency setting.
    func time(at now: CFTimeInterval = CACurrentMediaTime()) -> Double {
        (positionOverride?() ?? nowPlaying.position(at: now)) + offset + settings.value.latency
    }

    var shouldShow: Bool {
        settings.value.showLyrics && nowPlaying.isPlaying && lyrics.source != .none
    }

    func nudge(_ delta: Double) { offset = (offset + delta).rounded(toPlaces: 2) }
}

extension Double {
    func rounded(toPlaces p: Int) -> Double {
        let m = pow(10, Double(p))
        return (self * m).rounded() / m
    }
}

/// Colours and fonts resolved from settings for the style views.
struct LyricTheme {
    var text: Color
    var highlight: Color
    var dim: Color
    var font: LyricFont
    var scale: CGFloat
    var shadow: Bool

    init(_ s: LyraSettings, albumColors: [NSColor]) {
        text = s.textColor.color
        dim = s.dimColor.color
        if s.matchAlbum, let c = albumColors.first {
            highlight = Color(nsColor: c)
        } else {
            highlight = s.highlightColor.color
        }
        font = s.font
        scale = CGFloat(s.size)
        shadow = s.shadow
    }
}

/// A built-in song so the styles can be previewed with no music on.
enum DemoLyrics {
    static let period = 9.6
    static let lyrics: Lyrics = {
        let texts = ["Every word lights up", "the moment it is sung", "follow along with me", "one word at a time"]
        var lines: [LyricLine] = []
        for (i, t) in texts.enumerated() {
            let start = Double(i) * 2.4
            lines.append(LyricLine(start: start, end: start + 2.2, text: t,
                                   words: LyricsBuilderPublic.interpolate(t, start: start, end: start + 2.0)))
        }
        return Lyrics(source: .wordSynced, lines: lines)
    }()
}

/// Public wrapper so the app target can build demo lines without reaching into LyricsKit internals.
enum LyricsBuilderPublic {
    static func interpolate(_ text: String, start: Double, end: Double) -> [LyricWord] {
        let parts = text.split(separator: " ").map(String.init)
        let weights = parts.map { Double($0.count + 2) }
        let total = weights.reduce(0, +)
        var t = start
        return parts.enumerated().map { i, p in
            let d = (end - start) * weights[i] / total
            defer { t += d }
            return LyricWord(start: t, end: t + d, text: p, spaceAfter: i < parts.count - 1)
        }
    }
}
