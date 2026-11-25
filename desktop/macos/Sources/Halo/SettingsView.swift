import AppKit
import SharedKit
import SwiftUI

struct HaloSettingsView: View {
    @ObservedObject var settings: SettingsStore<HaloSettings>
    @ObservedObject var nowPlaying: NowPlayingMonitor
    let controller: HaloController
    @State private var launchAtLogin = LoginItem.isEnabled

    private var s: Binding<HaloSettings> { $settings.value }

    var body: some View {
        ScrollView {
            VStack(alignment: .leading, spacing: 22) {
                header
                preview
                SettingsSection("Light") {
                    Toggle("Halo is on", isOn: s.enabled)
                    Picker("Animation", selection: s.mode) {
                        ForEach(GlowMode.allCases) { Text($0.rawValue).tag($0) }
                    }
                    .pickerStyle(.segmented)
                    LabeledSlider("Thickness", value: s.thickness, in: 2...60) { "\(Int($0)) px" }
                    LabeledSlider("Glow", value: s.glow, in: 0...80) { "\(Int($0)) px" }
                    Toggle("Notch compatibility", isOn: s.notchAware)
                }
                SettingsSection("Colour") {
                    Toggle("Match album art", isOn: s.useAlbumColors)
                    Picker("Gradient", selection: s.colorCount) {
                        Text("2 colours").tag(2)
                        Text("3 colours").tag(3)
                    }
                    .pickerStyle(.segmented)
                    HStack(spacing: 18) {
                        ColorPicker("Primary", selection: s.primary.swiftUIColor, supportsOpacity: false)
                        ColorPicker("Secondary", selection: s.secondary.swiftUIColor, supportsOpacity: false)
                        if settings.value.colorCount == 3 {
                            ColorPicker("Third", selection: s.tertiary.swiftUIColor, supportsOpacity: false)
                        }
                    }
                    .opacity(albumActive ? 0.45 : 1)
                    if settings.value.colorCount == 2 {
                        LabeledSlider("Primary / secondary", value: s.split, in: 0.15...0.85) {
                            "\(Int($0 * 100)) / \(100 - Int($0 * 100))"
                        }
                    }
                    if albumActive {
                        Text("Using colours from the current album. Your colours come back when nothing is playing.")
                            .font(.caption).foregroundStyle(.secondary)
                    }
                }
                SettingsSection("Displays") {
                    ForEach(NSScreen.screens, id: \.displayKey) { screen in
                        Toggle(screen.localizedName, isOn: displayBinding(screen.displayKey))
                    }
                    Text("With none ticked, Halo lights every display.")
                        .font(.caption).foregroundStyle(.secondary)
                }
                SettingsSection("General") {
                    Toggle("Launch at login", isOn: $launchAtLogin)
                        .onChange(of: launchAtLogin) { _, on in LoginItem.set(on) }
                    LabeledContent("System audio", value: controller.audioStatus)
                    LabeledContent("Now playing", value: nowPlaying.track.map { "\($0.title) – \($0.artist)" } ?? "Nothing")
                }
            }
            .padding(24)
        }
        .frame(minWidth: 460, minHeight: 600)
    }

    private var albumActive: Bool { settings.value.useAlbumColors && !nowPlaying.artworkColors.isEmpty }

    private var header: some View {
        HStack(alignment: .firstTextBaseline) {
            Text("Halo").font(.system(size: 30, weight: .heavy, design: .rounded))
            Spacer()
            Text(settings.value.enabled ? "Active" : "Off")
                .font(.caption.weight(.semibold))
                .padding(.horizontal, 10).padding(.vertical, 4)
                .background(Capsule().fill(settings.value.enabled ? Color.orange.opacity(0.25) : Color.gray.opacity(0.2)))
        }
    }

    /// A small screen with the glow, so changes are visible without looking at the edge.
    private var preview: some View {
        let colors: [Color] = {
            if albumActive { return nowPlaying.artworkColors.prefix(settings.value.colorCount).map { Color(nsColor: $0) } }
            let v = settings.value
            return ([v.primary, v.secondary, v.tertiary].prefix(v.colorCount)).map(\.color)
        }()
        let gradient = AngularGradient(colors: colors + [colors.first ?? .white], center: .center)
        let scale = 0.35
        return TimelineView(.animation) { ctx in
            let t = ctx.date.timeIntervalSinceReferenceDate
            ZStack {
                RoundedRectangle(cornerRadius: 10).fill(Color.black)
                RoundedRectangle(cornerRadius: 10)
                    .strokeBorder(gradient, lineWidth: settings.value.thickness * scale + 1)
                    .blur(radius: settings.value.glow * scale)
                    .rotationEffect(.degrees(0))
                    .hueRotation(.degrees(settings.value.mode == .still ? 0 : sin(t / 3) * 10))
                RoundedRectangle(cornerRadius: 10)
                    .strokeBorder(gradient, lineWidth: settings.value.thickness * scale + 1)
            }
            .opacity(settings.value.enabled ? 1 : 0.3)
        }
        .frame(height: 220)
        .clipShape(RoundedRectangle(cornerRadius: 10))
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
