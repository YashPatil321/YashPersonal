import AppKit
import QuartzCore
import SharedKit

enum GlowMode: String, CaseIterable {
    case music, breathe, still
}

struct GlowSettings: Equatable {
    var enabled = false
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

    /// Built from Wave's shared settings dictionary (keys documented in desktop/visuals/core.js).
    init(_ d: [String: Any] = [:]) {
        enabled = d["glowEnabled"] as? Bool ?? enabled
        mode = (d["glowMode"] as? String).flatMap(GlowMode.init(rawValue:)) ?? mode
        useAlbumColors = d["glowAlbumColors"] as? Bool ?? useAlbumColors
        colorCount = (d["glowColorCount"] as? NSNumber)?.intValue ?? colorCount
        primary = (d["glowPrimary"] as? String).flatMap(RGBAColor.init(hex:)) ?? primary
        secondary = (d["glowSecondary"] as? String).flatMap(RGBAColor.init(hex:)) ?? secondary
        tertiary = (d["glowTertiary"] as? String).flatMap(RGBAColor.init(hex:)) ?? tertiary
        split = (d["glowSplit"] as? NSNumber)?.doubleValue ?? split
        thickness = (d["glowThickness"] as? NSNumber)?.doubleValue ?? thickness
        glow = (d["glowSize"] as? NSNumber)?.doubleValue ?? glow
        notchAware = d["glowNotch"] as? Bool ?? notchAware
    }
}

/// Light along every display edge, coloured by the album and pulsing with the music.
@MainActor
final class GlowFeature {
    private let nowPlaying: NowPlayingMonitor
    private let analyzer: () -> AudioAnalyzer?
    private(set) var settings = GlowSettings()

    private var windows: [(window: OverlayWindow, view: GlowView, screen: NSScreen)] = []
    private var shownColors: [RGBAColor] = []
    private var rotation = 0.0
    private var lastTick = CACurrentMediaTime()
    private var lastHeardMusic = 0.0

    init(nowPlaying: NowPlayingMonitor, analyzer: @escaping () -> AudioAnalyzer?) {
        self.nowPlaying = nowPlaying
        self.analyzer = analyzer
    }

    func apply(_ new: GlowSettings) {
        let rebuild = new.enabled != settings.enabled
        settings = new
        if rebuild { rebuildWindows() }
    }

    func rebuildWindows() {
        for w in windows { w.window.orderOut(nil) }
        windows.removeAll()
        guard settings.enabled else { return }
        for screen in NSScreen.screens {
            let window = OverlayWindow(screen: screen)
            let view = GlowView(frame: NSRect(origin: .zero, size: screen.frame.size))
            window.contentView = view
            window.orderFrontRegardless()
            windows.append((window, view, screen))
        }
    }

    private func targetColors() -> (colors: [RGBAColor], locations: [Double]) {
        let s = settings
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
        return ([base[0], base[0], base[1], base[1], base[0]], [0, split - b, split + b, 1 - b, 1])
    }

    /// Called by Wave's frame timer.
    func tick() {
        let now = CACurrentMediaTime()
        let dt = min(now - lastTick, 0.1)
        lastTick = now
        guard !windows.isEmpty else { return }
        let s = settings

        let target = targetColors()
        if shownColors.count != target.colors.count {
            shownColors = target.colors
        } else {
            let k = min(1, dt * 5) // about a 600 ms cross-fade
            shownColors = zip(shownColors, target.colors).map { $0.mixed(with: $1, k) }
        }

        let levels = analyzer()?.levels(at: now) ?? .silent
        if levels.level > 0.02 && nowPlaying.isPlaying { lastHeardMusic = now }
        var mode = s.mode
        if mode == .music && now - lastHeardMusic > 2 { mode = .breathe }

        var brightness: Double, pulse = 0.0, speed: Double
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
        rotation = (rotation + speed * dt).truncatingRemainder(dividingBy: 1)
        let frame = GlowFrame(colors: shownColors, locations: target.locations, rotation: rotation,
                              brightness: min(1, brightness), pulse: pulse)
        for w in windows {
            w.view.configure(screen: w.screen, thickness: s.thickness, glowRadius: s.glow, notchAware: s.notchAware)
            w.view.render(frame)
        }
    }
}

extension RGBAColor {
    init?(hex: String) {
        var h = hex.trimmingCharacters(in: .whitespaces)
        if h.hasPrefix("#") { h.removeFirst() }
        guard h.count == 6 || h.count == 8, let v = UInt64(h, radix: 16) else { return nil }
        if h.count == 8 {
            self.init(Double((v >> 24) & 255) / 255, Double((v >> 16) & 255) / 255, Double((v >> 8) & 255) / 255, Double(v & 255) / 255)
        } else {
            self.init(Double((v >> 16) & 255) / 255, Double((v >> 8) & 255) / 255, Double(v & 255) / 255)
        }
    }
}
