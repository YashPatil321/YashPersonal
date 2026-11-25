import AppKit
import LyricsKit
import SharedKit
import SwiftUI

struct LyraSettingsView: View {
    @ObservedObject var settings: SettingsStore<LyraSettings>
    @ObservedObject var engine: LyricsEngine
    @ObservedObject var nowPlaying: NowPlayingMonitor
    @State private var tab = 0

    var body: some View {
        VStack(spacing: 0) {
            Picker("", selection: $tab) {
                Text("Style").tag(0)
                Text("Appearance").tag(1)
                Text("Display").tag(2)
                Text("Status").tag(3)
            }
            .pickerStyle(.segmented)
            .labelsHidden()
            .padding(.horizontal, 24)
            .padding(.top, 34)
            .padding(.bottom, 16)

            ScrollView {
                Group {
                    switch tab {
                    case 0: StyleTab(settings: settings, nowPlaying: nowPlaying)
                    case 1: AppearanceTab(settings: settings)
                    case 2: DisplayTab(settings: settings, engine: engine)
                    default: StatusTab(engine: engine, nowPlaying: nowPlaying)
                    }
                }
                .padding(.horizontal, 24)
                .padding(.bottom, 24)
            }
        }
        .frame(minWidth: 620, minHeight: 600)
    }
}

/// Plays the demo song in a style on loop.
struct StylePreview: View {
    let style: LyricStyle
    let theme: LyricTheme
    var height: CGFloat = 260

    var body: some View {
        TimelineView(.animation) { ctx in
            let t = ctx.date.timeIntervalSinceReferenceDate.truncatingRemainder(dividingBy: DemoLyrics.period)
            LyricStyleView(style: style, lyrics: DemoLyrics.lyrics, t: t, theme: theme)
                .frame(maxWidth: .infinity, maxHeight: .infinity)
        }
        .frame(height: height)
        .background(
            LinearGradient(colors: [Color(red: 0.12, green: 0.1, blue: 0.22), Color(red: 0.05, green: 0.05, blue: 0.08)],
                           startPoint: .topLeading, endPoint: .bottomTrailing)
        )
        .clipShape(RoundedRectangle(cornerRadius: 14, style: .continuous))
    }
}

private struct StyleTab: View {
    @ObservedObject var settings: SettingsStore<LyraSettings>
    @ObservedObject var nowPlaying: NowPlayingMonitor

    var body: some View {
        let theme = LyricTheme(settings.value, albumColors: nowPlaying.artworkColors)
        var small = theme
        small.scale = 0.42
        return VStack(alignment: .leading, spacing: 18) {
            StylePreview(style: settings.value.style, theme: scaled(theme, 0.8))
            Text(settings.value.style.blurb).foregroundStyle(.secondary)
            LazyVGrid(columns: [GridItem(.adaptive(minimum: 170), spacing: 12)], spacing: 12) {
                ForEach(LyricStyle.allCases) { style in
                    Button {
                        settings.value.style = style
                    } label: {
                        VStack(alignment: .leading, spacing: 6) {
                            StylePreview(style: style, theme: small, height: 100)
                                .allowsHitTesting(false)
                            Text(style.rawValue).font(.headline)
                        }
                        .padding(8)
                        .background(
                            RoundedRectangle(cornerRadius: 14, style: .continuous)
                                .strokeBorder(settings.value.style == style ? Color.accentColor : Color.primary.opacity(0.1),
                                              lineWidth: settings.value.style == style ? 2 : 1)
                        )
                    }
                    .buttonStyle(.plain)
                }
            }
        }
    }

    private func scaled(_ t: LyricTheme, _ k: CGFloat) -> LyricTheme {
        var c = t
        c.scale *= k
        return c
    }
}

private struct AppearanceTab: View {
    @ObservedObject var settings: SettingsStore<LyraSettings>
    private var s: Binding<LyraSettings> { $settings.value }

    var body: some View {
        VStack(alignment: .leading, spacing: 22) {
            SettingsSection("Font") {
                Picker("Typeface", selection: s.font) {
                    ForEach(LyricFont.allCases) { Text($0.rawValue).tag($0) }
                }
                .pickerStyle(.segmented)
                LabeledSlider("Size", value: s.size, in: 0.6...2.0) { "\(Int($0 * 100))%" }
                HStack {
                    Spacer()
                    Button("Reset size") { settings.value.size = 1 }
                }
            }
            SettingsSection("Colour") {
                ColorPicker("Sung words", selection: s.textColor.swiftUIColor)
                ColorPicker("Current word", selection: s.highlightColor.swiftUIColor)
                    .disabled(settings.value.matchAlbum)
                ColorPicker("Upcoming words", selection: s.dimColor.swiftUIColor)
                Toggle("Match the album cover", isOn: s.matchAlbum)
                Toggle("Shadow behind the words", isOn: s.shadow)
            }
        }
    }
}

private struct DisplayTab: View {
    @ObservedObject var settings: SettingsStore<LyraSettings>
    @ObservedObject var engine: LyricsEngine
    private var s: Binding<LyraSettings> { $settings.value }

    var body: some View {
        VStack(alignment: .leading, spacing: 22) {
            SettingsSection("Screen") {
                Toggle("Show lyrics", isOn: s.showLyrics)
                Picker("Position", selection: s.placement) {
                    ForEach(Placement.allCases) { Text($0.rawValue).tag($0) }
                }
                .pickerStyle(.segmented)
                Toggle("Keep the screen awake while music plays", isOn: s.keepAwake)
            }
            SettingsSection("Displays") {
                ForEach(NSScreen.screens, id: \.displayKey) { screen in
                    Toggle(screen.localizedName, isOn: displayBinding(screen.displayKey))
                }
                Text("With none ticked, lyrics show on every display.")
                    .font(.caption).foregroundStyle(.secondary)
            }
            SettingsSection("Timing") {
                LabeledSlider("Latency", value: s.latency, in: -0.5...0.8) { String(format: "%+.2f s", $0) }
                HStack {
                    Text("This song")
                    Spacer()
                    Button("Earlier") { engine.nudge(0.25) }
                    Text(String(format: "%+.2f s", engine.offset)).monospacedDigit().frame(width: 64)
                    Button("Later") { engine.nudge(-0.25) }
                }
                Text("Latency applies to every song. The per-song shift resets when the next song starts.")
                    .font(.caption).foregroundStyle(.secondary)
            }
        }
    }

    private func displayBinding(_ key: String) -> Binding<Bool> {
        Binding(
            get: { settings.value.displays.contains(key) },
            set: { on in
                settings.value.displays.removeAll { $0 == key }
                if on { settings.value.displays.append(key) }
            })
    }
}

private struct StatusTab: View {
    @ObservedObject var engine: LyricsEngine
    @ObservedObject var nowPlaying: NowPlayingMonitor
    @State private var resetMessage: String?

    var body: some View {
        VStack(alignment: .leading, spacing: 22) {
            ForEach(Player.allCases) { player in
                let status = nowPlaying.statuses[player] ?? PlayerStatus()
                let isActive = nowPlaying.track?.player == player
                SettingsSection(player.rawValue) {
                    check("\(player.rawValue) is open", ok: status.running,
                          detail: "The player has to be running for Lyra to follow it.")
                    check("Lyra can read what’s playing", ok: status.permission == .granted,
                          pending: status.permission == .unknown,
                          detail: status.permission == .denied
                              ? "Access was turned down. Use the button below, or allow it in System Settings › Privacy & Security › Automation."
                              : "macOS asks the first time Lyra looks at the player.")
                    check("What’s playing", ok: status.track != nil,
                          detail: status.track.map { "\($0.title) – \($0.artist)" } ?? "Nothing")
                    if isActive {
                        check("Lyrics found", ok: isFound, pending: engine.status == .loading, detail: engine.status.label)
                    }
                }
            }
            HStack {
                Button("Ask for permission again") { resetPermissions() }
                if let resetMessage { Text(resetMessage).font(.caption).foregroundStyle(.secondary) }
            }
        }
    }

    private var isFound: Bool {
        if case .found = engine.status { return true }
        return false
    }

    private func check(_ title: String, ok: Bool, pending: Bool = false, detail: String) -> some View {
        HStack(alignment: .top, spacing: 10) {
            Image(systemName: pending ? "circle.dotted" : ok ? "checkmark.circle.fill" : "xmark.circle.fill")
                .foregroundStyle(pending ? Color.secondary : ok ? Color.green : Color.red)
            VStack(alignment: .leading, spacing: 2) {
                Text(title)
                Text(detail).font(.caption).foregroundStyle(.secondary)
            }
        }
    }

    private func resetPermissions() {
        let id = Bundle.main.bundleIdentifier ?? "com.example.lyra"
        let p = Process()
        p.executableURL = URL(fileURLWithPath: "/usr/bin/tccutil")
        p.arguments = ["reset", "AppleEvents", id]
        do {
            try p.run()
            p.waitUntilExit()
            resetMessage = p.terminationStatus == 0 ? "Done. macOS will ask again." : "Couldn’t reset (code \(p.terminationStatus))."
        } catch {
            resetMessage = "Couldn’t reset: \(error.localizedDescription)"
        }
    }
}
