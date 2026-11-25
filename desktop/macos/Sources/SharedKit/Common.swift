import AppKit
import Combine
import IOKit.pwr_mgt
import ServiceManagement
import SwiftUI

// MARK: - Colour

public struct RGBAColor: Codable, Equatable, Sendable {
    public var r: Double, g: Double, b: Double, a: Double

    public init(_ r: Double, _ g: Double, _ b: Double, _ a: Double = 1) {
        self.r = r; self.g = g; self.b = b; self.a = a
    }

    public init(_ color: NSColor) {
        let c = color.usingColorSpace(.sRGB) ?? .white
        self.init(Double(c.redComponent), Double(c.greenComponent), Double(c.blueComponent), Double(c.alphaComponent))
    }

    public var nsColor: NSColor { NSColor(srgbRed: r, green: g, blue: b, alpha: a) }
    public var cgColor: CGColor { nsColor.cgColor }
    public var color: Color { Color(nsColor: nsColor) }

    public func mixed(with other: RGBAColor, _ t: Double) -> RGBAColor {
        RGBAColor(r + (other.r - r) * t, g + (other.g - g) * t, b + (other.b - b) * t, a + (other.a - a) * t)
    }

    public func scaled(_ k: Double) -> RGBAColor { RGBAColor(r * k, g * k, b * k, a) }
}

extension Binding where Value == RGBAColor {
    /// Bridges a stored colour to SwiftUI's ColorPicker.
    public var swiftUIColor: Binding<Color> {
        Binding<Color>(get: { wrappedValue.color },
                       set: { wrappedValue = RGBAColor(NSColor($0)) })
    }
}

public enum ColorExtractor {
    /// The most vibrant dominant colours of an image, brightened enough to glow.
    public static func vibrantColors(from image: NSImage, count: Int) -> [NSColor] {
        let side = 24
        guard let cg = image.cgImage(forProposedRect: nil, context: nil, hints: nil),
              let ctx = CGContext(data: nil, width: side, height: side, bitsPerComponent: 8, bytesPerRow: side * 4,
                                  space: CGColorSpace(name: CGColorSpace.sRGB)!,
                                  bitmapInfo: CGImageAlphaInfo.premultipliedLast.rawValue)
        else { return [] }
        ctx.interpolationQuality = .medium
        ctx.draw(cg, in: CGRect(x: 0, y: 0, width: side, height: side))
        guard let data = ctx.data else { return [] }
        let px = data.bindMemory(to: UInt8.self, capacity: side * side * 4)

        // Weighted hue histogram, 18 bins.
        let bins = 18
        var weight = [Double](repeating: 0, count: bins)
        var sums = [(h: Double, s: Double, b: Double)](repeating: (0, 0, 0), count: bins)
        for i in 0..<(side * side) {
            let c = NSColor(srgbRed: CGFloat(px[i * 4]) / 255, green: CGFloat(px[i * 4 + 1]) / 255,
                            blue: CGFloat(px[i * 4 + 2]) / 255, alpha: 1)
            var h: CGFloat = 0, s: CGFloat = 0, b: CGFloat = 0, a: CGFloat = 0
            c.getHue(&h, saturation: &s, brightness: &b, alpha: &a)
            let w = Double(s * s * b) + 0.0001
            let bin = min(bins - 1, Int(h * CGFloat(bins)))
            weight[bin] += w
            sums[bin].h += Double(h) * w; sums[bin].s += Double(s) * w; sums[bin].b += Double(b) * w
        }
        var order = Array(0..<bins).sorted { weight[$0] > weight[$1] }
        // Keep picked hues apart from each other.
        var picked: [Int] = []
        while let next = order.first, picked.count < count {
            order.removeFirst()
            if weight[next] < 0.001 { break }
            if picked.contains(where: { min(abs($0 - next), bins - abs($0 - next)) < 2 }) { continue }
            picked.append(next)
        }
        var colors = picked.map { bin -> NSColor in
            let w = weight[bin]
            let s = max(0.55, min(1, sums[bin].s / w))
            let b = max(0.8, sums[bin].b / w)
            return NSColor(hue: sums[bin].h / w, saturation: s, brightness: b, alpha: 1)
        }
        // A greyscale cover: fall back to soft white plus a cool tint.
        if colors.isEmpty {
            colors = [NSColor(white: 0.95, alpha: 1), NSColor(hue: 0.6, saturation: 0.35, brightness: 1, alpha: 1)]
        }
        while colors.count < count, let last = colors.last {
            var h: CGFloat = 0, s: CGFloat = 0, b: CGFloat = 0, a: CGFloat = 0
            last.usingColorSpace(.sRGB)?.getHue(&h, saturation: &s, brightness: &b, alpha: &a)
            colors.append(NSColor(hue: (h + 0.12).truncatingRemainder(dividingBy: 1), saturation: s, brightness: b, alpha: 1))
        }
        return colors
    }
}

// MARK: - Overlay windows

/// A transparent, click-through window that covers a display and floats above full-screen apps.
public final class OverlayWindow: NSWindow {
    public init(screen: NSScreen, level: NSWindow.Level = .screenSaver) {
        super.init(contentRect: screen.frame, styleMask: .borderless, backing: .buffered, defer: false)
        isOpaque = false
        backgroundColor = .clear
        hasShadow = false
        ignoresMouseEvents = true
        isReleasedWhenClosed = false
        self.level = level
        collectionBehavior = [.canJoinAllSpaces, .stationary, .fullScreenAuxiliary, .ignoresCycle]
        animationBehavior = .none
        setFrame(screen.frame, display: false)
    }

    public override var canBecomeKey: Bool { false }
    public override var canBecomeMain: Bool { false }
}

extension NSScreen {
    /// Stable-enough identifier for remembering which displays the user picked.
    public var displayKey: String {
        let id = (deviceDescription[NSDeviceDescriptionKey("NSScreenNumber")] as? NSNumber)?.uint32Value ?? 0
        if let uuid = CGDisplayCreateUUIDFromDisplayID(id)?.takeRetainedValue() {
            return CFUUIDCreateString(nil, uuid) as String
        }
        return "\(id)"
    }

    /// Screens to draw on: the chosen ones, or every screen when nothing is chosen.
    public static func selected(_ keys: [String]) -> [NSScreen] {
        let chosen = screens.filter { keys.contains($0.displayKey) }
        return chosen.isEmpty ? screens : chosen
    }
}

// MARK: - Settings persistence

/// Codable settings saved as JSON in UserDefaults, with a 500 ms debounce.
@MainActor
public final class SettingsStore<Value: Codable & Equatable>: ObservableObject {
    @Published public var value: Value
    private let key: String
    private var cancellable: AnyCancellable?

    public init(key: String, default defaultValue: Value) {
        self.key = key
        if let data = UserDefaults.standard.data(forKey: key),
           let decoded = try? JSONDecoder().decode(Value.self, from: data) {
            value = decoded
        } else {
            value = defaultValue
        }
        cancellable = $value
            .removeDuplicates()
            .debounce(for: .milliseconds(500), scheduler: RunLoop.main)
            .sink { [key] v in
                if let data = try? JSONEncoder().encode(v) { UserDefaults.standard.set(data, forKey: key) }
            }
    }
}

// MARK: - Login item, keep awake

public enum LoginItem {
    public static var isEnabled: Bool { SMAppService.mainApp.status == .enabled }

    public static func set(_ enabled: Bool) {
        do {
            if enabled { try SMAppService.mainApp.register() } else { try SMAppService.mainApp.unregister() }
        } catch {
            NSLog("Login item change failed: \(error)")
        }
    }
}

public final class KeepAwake {
    private var assertion: IOPMAssertionID = 0
    private var active = false

    public init() {}

    public func set(_ on: Bool, reason: String) {
        if on == active { return }
        if on {
            active = IOPMAssertionCreateWithName(kIOPMAssertionTypePreventUserIdleDisplaySleep as CFString,
                                                 IOPMAssertionLevel(kIOPMAssertionLevelOn),
                                                 reason as CFString, &assertion) == kIOReturnSuccess
        } else {
            IOPMAssertionRelease(assertion)
            active = false
        }
    }
}

// MARK: - Settings window helper

@MainActor
public final class SettingsWindowController {
    private var window: NSWindow?
    private let title: String
    private let size: NSSize
    private let makeView: () -> AnyView

    public init(title: String, size: NSSize, content: @escaping () -> AnyView) {
        self.title = title
        self.size = size
        self.makeView = content
    }

    public func show() {
        if window == nil {
            let w = NSWindow(contentRect: NSRect(origin: .zero, size: size),
                             styleMask: [.titled, .closable, .miniaturizable, .fullSizeContentView],
                             backing: .buffered, defer: false)
            w.title = title
            w.titlebarAppearsTransparent = true
            w.isReleasedWhenClosed = false
            w.contentViewController = NSHostingController(rootView: makeView())
            w.setContentSize(size)
            w.center()
            window = w
        }
        NSApp.activate(ignoringOtherApps: true)
        window?.makeKeyAndOrderFront(nil)
    }
}

/// A menu item that runs a closure.
public final class ActionMenuItem: NSMenuItem {
    private let handler: () -> Void

    public init(_ title: String, key: String = "", state: Bool = false, handler: @escaping () -> Void) {
        self.handler = handler
        super.init(title: title, action: #selector(fire), keyEquivalent: key)
        target = self
        self.state = state ? .on : .off
    }

    required init(coder: NSCoder) { fatalError("not used") }

    @objc private func fire() { handler() }
}

/// Shared look for the settings windows.
public struct SettingsSection<Content: View>: View {
    let title: String
    let content: Content

    public init(_ title: String, @ViewBuilder content: () -> Content) {
        self.title = title
        self.content = content()
    }

    public var body: some View {
        VStack(alignment: .leading, spacing: 10) {
            Text(title.uppercased())
                .font(.system(size: 11, weight: .semibold))
                .foregroundStyle(.secondary)
                .tracking(0.6)
            VStack(alignment: .leading, spacing: 12) { content }
                .padding(14)
                .frame(maxWidth: .infinity, alignment: .leading)
                .background(RoundedRectangle(cornerRadius: 12).fill(Color.primary.opacity(0.05)))
        }
    }
}

public struct LabeledSlider: View {
    let title: String
    @Binding var value: Double
    let range: ClosedRange<Double>
    let format: (Double) -> String

    public init(_ title: String, value: Binding<Double>, in range: ClosedRange<Double>, format: @escaping (Double) -> String) {
        self.title = title
        _value = value
        self.range = range
        self.format = format
    }

    public var body: some View {
        VStack(alignment: .leading, spacing: 4) {
            HStack {
                Text(title)
                Spacer()
                Text(format(value)).foregroundStyle(.secondary).monospacedDigit()
            }
            Slider(value: $value, in: range)
        }
    }
}
