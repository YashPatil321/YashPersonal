import AppKit
import QuartzCore
import SharedKit

/// What the glow should look like on this frame.
struct GlowFrame {
    var colors: [RGBAColor]
    var locations: [Double]
    var rotation: Double      // turns, 0...1
    var brightness: Double    // 0...1
    var pulse: Double         // 0...1, extra burst on beats
}

/// Draws the light around one display with Core Animation.
///
/// Three conic gradients share the colours. Each is masked by a stroke that hugs the display edge:
/// a crisp core, a soft glow (the mask's own shadow gives the falloff) and a wider pulse layer that flashes on beats.
final class GlowView: NSView {
    private let core = CAGradientLayer()
    private let glow = CAGradientLayer()
    private let pulse = CAGradientLayer()
    private let coreMask = CAShapeLayer()
    private let glowMask = CAShapeLayer()
    private let pulseMask = CAShapeLayer()

    private var geometryKey = ""

    override init(frame: NSRect) {
        super.init(frame: frame)
        // Layer-hosting view: assign the layer first, then turn layers on.
        layer = CALayer()
        wantsLayer = true
        layer?.backgroundColor = .clear
        for (g, m) in [(pulse, pulseMask), (glow, glowMask), (core, coreMask)] {
            g.type = .conic
            g.startPoint = CGPoint(x: 0.5, y: 0.5)
            g.mask = m
            m.fillColor = nil
            m.strokeColor = NSColor.black.cgColor
            m.shadowColor = NSColor.black.cgColor
            m.shadowOffset = .zero
            layer?.addSublayer(g)
        }
    }

    required init?(coder: NSCoder) { fatalError("not used") }

    override var isFlipped: Bool { false }

    /// Rebuild the edge path when size, thickness, glow or notch change.
    func configure(screen: NSScreen, thickness: Double, glowRadius: Double, notchAware: Bool) {
        let key = "\(bounds.size)|\(thickness)|\(glowRadius)|\(notchAware)"
        guard key != geometryKey else { return }
        geometryKey = key

        CATransaction.begin()
        CATransaction.setDisableActions(true)
        let path = Self.edgePath(in: bounds, screen: screen, inset: thickness / 2, notchAware: notchAware)
        for (g, m) in [(core, coreMask), (glow, glowMask), (pulse, pulseMask)] {
            g.frame = bounds
            m.frame = bounds
            m.path = path
        }
        coreMask.lineWidth = thickness
        coreMask.shadowOpacity = 0

        glowMask.lineWidth = thickness
        glowMask.shadowRadius = glowRadius
        glowMask.shadowOpacity = glowRadius > 0 ? 1 : 0

        pulseMask.lineWidth = thickness * 1.6
        pulseMask.shadowRadius = max(glowRadius * 1.5, 8)
        pulseMask.shadowOpacity = 1
        // The masks only change here, so rasterising keeps the per-frame cost to compositing.
        for m in [glowMask, pulseMask] {
            m.shouldRasterize = true
            m.rasterizationScale = screen.backingScaleFactor
        }
        CATransaction.commit()
    }

    func render(_ f: GlowFrame) {
        CATransaction.begin()
        CATransaction.setDisableActions(true)
        let colors = f.colors.map(\.cgColor)
        let locations = f.locations.map { NSNumber(value: $0) }
        let angle = f.rotation * 2 * .pi
        let end = CGPoint(x: 0.5 + 0.5 * cos(angle), y: 0.5 + 0.5 * sin(angle))
        for g in [core, glow, pulse] {
            g.colors = colors
            g.locations = locations
            g.endPoint = end
        }
        core.opacity = Float(min(1, f.brightness + 0.2))
        glow.opacity = Float(f.brightness)
        pulse.opacity = Float(f.pulse * f.brightness)
        CATransaction.commit()
    }

    /// A rounded rectangle along the display edge. With a notch, the top edge dips around it.
    static func edgePath(in rect: CGRect, screen: NSScreen, inset i: CGFloat, notchAware: Bool) -> CGPath {
        let w = rect.width, h = rect.height
        let outer: CGFloat = screen.isBuiltIn ? 10 : 0
        var points: [(CGPoint, CGFloat)] = [
            (CGPoint(x: i, y: i), outer),
            (CGPoint(x: w - i, y: i), outer),
            (CGPoint(x: w - i, y: h - i), outer),
        ]
        if notchAware, let left = screen.auxiliaryTopLeftArea, let right = screen.auxiliaryTopRightArea {
            let x1 = left.maxX - screen.frame.minX
            let x2 = right.minX - screen.frame.minX
            let notchBottom = h - screen.safeAreaInsets.top
            if x2 > x1, notchBottom > 0 {
                points += [
                    (CGPoint(x: x2 + i, y: h - i), 6),
                    (CGPoint(x: x2 + i, y: notchBottom - i), 10),
                    (CGPoint(x: x1 - i, y: notchBottom - i), 10),
                    (CGPoint(x: x1 - i, y: h - i), 6),
                ]
            }
        }
        points.append((CGPoint(x: i, y: h - i), outer))

        let path = CGMutablePath()
        let n = points.count
        // Start halfway along the last edge so every corner can be rounded with tangent arcs.
        let start = CGPoint(x: (points[n - 1].0.x + points[0].0.x) / 2, y: (points[n - 1].0.y + points[0].0.y) / 2)
        path.move(to: start)
        for k in 0..<n {
            let corner = points[k].0
            let next = points[(k + 1) % n].0
            let r = points[k].1
            if r > 0 {
                path.addArc(tangent1End: corner, tangent2End: next, radius: r)
            } else {
                path.addLine(to: corner)
            }
        }
        path.closeSubpath()
        return path
    }
}

extension NSScreen {
    var isBuiltIn: Bool {
        let id = (deviceDescription[NSDeviceDescriptionKey("NSScreenNumber")] as? NSNumber)?.uint32Value ?? 0
        return CGDisplayIsBuiltin(id) != 0
    }
}
