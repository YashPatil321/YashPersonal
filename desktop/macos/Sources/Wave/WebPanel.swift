import AppKit
import WebKit

/// A window hosting one view of the Wave web engine (desktop/visuals) in a WKWebView.
@MainActor
final class WebPanel: NSObject {
    enum Kind: String { case widget, clock, dashboard, fullscreen }

    let kind: Kind
    let window: NSWindow
    let webView: WKWebView
    private var ready = false
    private var queued: [String] = []
    var onMessage: ((WebPanel, [String: Any]) -> Void)?
    private var editOverlay: EditOverlay?

    init(kind: Kind, window: NSWindow, visualsDir: URL) {
        self.kind = kind
        self.window = window
        let config = WKWebViewConfiguration()
        config.preferences.setValue(true, forKey: "allowFileAccessFromFileURLs")
        config.mediaTypesRequiringUserActionForPlayback = []
        let controller = WKUserContentController()
        config.userContentController = controller
        webView = WKWebView(frame: window.contentView?.bounds ?? .zero, configuration: config)
        super.init()
        controller.add(WeakHandler(self), name: "wave")
        webView.autoresizingMask = [.width, .height]
        if kind != .dashboard {
            webView.setValue(false, forKey: "drawsBackground")
            webView.underPageBackgroundColor = .clear
        }
        let container = NSView(frame: window.contentView?.bounds ?? .zero)
        container.autoresizingMask = [.width, .height]
        webView.frame = container.bounds
        container.addSubview(webView)
        window.contentView = container

        let index = visualsDir.appendingPathComponent("index.html")
        var comps = URLComponents(url: index, resolvingAgainstBaseURL: false)!
        comps.queryItems = [URLQueryItem(name: "mode", value: kind.rawValue)]
        webView.loadFileURL(comps.url!, allowingReadAccessTo: visualsDir)
    }

    func handle(_ message: WKScriptMessage) {
        guard let body = message.body as? [String: Any] else { return }
        if body["cmd"] as? String == "ready" {
            ready = true
            for js in queued { webView.evaluateJavaScript(js) }
            queued.removeAll()
        }
        onMessage?(self, body)
    }

    /// Calls `Wave.<fn>(<json>)` in the page.
    func call(_ fn: String, _ payload: Any) {
        guard let data = try? JSONSerialization.data(withJSONObject: payload, options: [.fragmentsAllowed]),
              let json = String(data: data, encoding: .utf8) else { return }
        let js = "Wave.\(fn)(\(json))"
        if ready { webView.evaluateJavaScript(js) } else if fn != "pushAudio" { queued.append(js) }
    }

    var isVisibleOnScreen: Bool {
        window.isVisible && window.occlusionState.contains(.visible)
    }

    // MARK: Arrange mode

    func setEditing(_ on: Bool, onDone: @escaping () -> Void) {
        if on {
            let overlay = EditOverlay(frame: window.contentView!.bounds, title: kind == .clock ? "Clock" : "Visualizer", onDone: onDone)
            overlay.autoresizingMask = [.width, .height]
            window.contentView?.addSubview(overlay)
            editOverlay = overlay
        } else {
            editOverlay?.removeFromSuperview()
            editOverlay = nil
        }
    }
}

/// Avoids a retain cycle between WKUserContentController and the panel.
private final class WeakHandler: NSObject, WKScriptMessageHandler {
    weak var target: WebPanel?
    init(_ t: WebPanel) { target = t }
    func userContentController(_ ucc: WKUserContentController, didReceive message: WKScriptMessage) {
        MainActor.assumeIsolated { target?.handle(message) }
    }
}

/// Drawn over a widget while arranging: drag to move, drag the corner to resize, Done to finish.
final class EditOverlay: NSView {
    private let onDone: () -> Void
    private var resizing = false
    private var startFrame = NSRect.zero
    private var startMouse = NSPoint.zero
    private let title: String

    init(frame: NSRect, title: String, onDone: @escaping () -> Void) {
        self.onDone = onDone
        self.title = title
        super.init(frame: frame)
        let done = NSButton(title: "Done", target: self, action: #selector(finish))
        done.bezelStyle = .rounded
        done.keyEquivalent = "\r"
        done.frame = NSRect(x: 12, y: frame.height - 40, width: 80, height: 28)
        done.autoresizingMask = [.maxXMargin, .minYMargin]
        addSubview(done)
    }

    required init?(coder: NSCoder) { fatalError("not used") }

    @objc private func finish() { onDone() }

    override func draw(_ dirtyRect: NSRect) {
        NSColor.black.withAlphaComponent(0.25).setFill()
        let path = NSBezierPath(roundedRect: bounds.insetBy(dx: 2, dy: 2), xRadius: 14, yRadius: 14)
        path.fill()
        NSColor.white.withAlphaComponent(0.8).setStroke()
        path.lineWidth = 2
        path.setLineDash([8, 6], count: 2, phase: 0)
        path.stroke()
        let grip = NSBezierPath()
        for k in stride(from: 6.0, through: 18.0, by: 6.0) {
            grip.move(to: NSPoint(x: bounds.maxX - k - 4, y: 4))
            grip.line(to: NSPoint(x: bounds.maxX - 4, y: k + 4))
        }
        grip.lineWidth = 2
        grip.stroke()
        let attrs: [NSAttributedString.Key: Any] = [.font: NSFont.systemFont(ofSize: 13, weight: .semibold), .foregroundColor: NSColor.white]
        ("Drag to move · corner to resize · " + title as NSString).draw(at: NSPoint(x: 104, y: bounds.height - 34), withAttributes: attrs)
    }

    override func mouseDown(with event: NSEvent) {
        let p = convert(event.locationInWindow, from: nil)
        resizing = p.x > bounds.maxX - 30 && p.y < 30
        startFrame = window?.frame ?? .zero
        startMouse = NSEvent.mouseLocation
    }

    override func mouseDragged(with event: NSEvent) {
        guard let window else { return }
        let m = NSEvent.mouseLocation
        let dx = m.x - startMouse.x, dy = m.y - startMouse.y
        if resizing {
            let w = max(240, startFrame.width + dx)
            let h = max(120, startFrame.height - dy)
            window.setFrame(NSRect(x: startFrame.minX, y: startFrame.maxY - h, width: w, height: h), display: true)
        } else {
            window.setFrameOrigin(NSPoint(x: startFrame.minX + dx, y: startFrame.minY + dy))
        }
    }

    override func resetCursorRects() {
        addCursorRect(NSRect(x: bounds.maxX - 30, y: 0, width: 30, height: 30), cursor: .crosshair)
        addCursorRect(bounds, cursor: .openHand)
    }
}

/// A borderless window that can still take keyboard focus (needed for the full-screen player).
final class KeyableWindow: NSWindow {
    override var canBecomeKey: Bool { true }
    override var canBecomeMain: Bool { true }
}
