import LyricsKit
import SwiftUI

// MARK: - Helpers

private func clamp01(_ x: Double) -> Double { min(max(x, 0), 1) }
private func easeOut(_ x: Double) -> Double { let p = clamp01(x); return 1 - pow(1 - p, 3) }
private func easeOutBack(_ x: Double) -> Double {
    let p = clamp01(x), c1 = 1.70158, c3 = c1 + 1
    return 1 + c3 * pow(p - 1, 3) + c1 * pow(p - 1, 2)
}
private func lerp(_ a: Double, _ b: Double, _ t: Double) -> Double { a + (b - a) * t }

/// Wraps its children into centred rows, like text.
struct FlowLayout: Layout {
    var spacing: CGFloat
    var lineSpacing: CGFloat
    var alignment: HorizontalAlignment = .center

    private struct Row { var indices: [Int] = []; var width: CGFloat = 0; var height: CGFloat = 0 }

    private func rows(_ maxWidth: CGFloat, _ subviews: Subviews) -> [Row] {
        var rows: [Row] = [Row()]
        for (i, v) in subviews.enumerated() {
            let size = v.sizeThatFits(.unspecified)
            let extra = rows[rows.count - 1].indices.isEmpty ? size.width : size.width + spacing
            if rows[rows.count - 1].width + extra > maxWidth && !rows[rows.count - 1].indices.isEmpty {
                rows.append(Row())
            }
            let gap = rows[rows.count - 1].indices.isEmpty ? 0 : spacing
            rows[rows.count - 1].indices.append(i)
            rows[rows.count - 1].width += gap + size.width
            rows[rows.count - 1].height = max(rows[rows.count - 1].height, size.height)
        }
        return rows
    }

    func sizeThatFits(proposal: ProposedViewSize, subviews: Subviews, cache: inout ()) -> CGSize {
        let r = rows(proposal.width ?? .infinity, subviews)
        let height = r.map(\.height).reduce(0, +) + lineSpacing * CGFloat(max(r.count - 1, 0))
        return CGSize(width: min(r.map(\.width).max() ?? 0, proposal.width ?? .infinity), height: height)
    }

    func placeSubviews(in bounds: CGRect, proposal: ProposedViewSize, subviews: Subviews, cache: inout ()) {
        var y = bounds.minY
        for row in rows(bounds.width, subviews) {
            var x: CGFloat
            switch alignment {
            case .leading: x = bounds.minX
            case .trailing: x = bounds.maxX - row.width
            default: x = bounds.midX - row.width / 2
            }
            for i in row.indices {
                let size = subviews[i].sizeThatFits(.unspecified)
                subviews[i].place(at: CGPoint(x: x, y: y + (row.height - size.height)), proposal: .unspecified)
                x += size.width + spacing
            }
            y += row.height + lineSpacing
        }
    }
}

private extension View {
    func lyricShadow(_ on: Bool) -> some View {
        shadow(color: .black.opacity(on ? 0.6 : 0), radius: 10, x: 0, y: 2)
    }
}

// MARK: - Dispatcher

struct LyricStyleView: View {
    let style: LyricStyle
    let lyrics: Lyrics
    let t: Double
    let theme: LyricTheme

    var body: some View {
        switch style {
        case .spotlight: SpotlightStyle(lyrics: lyrics, t: t, theme: theme)
        case .stack: StackStyle(lyrics: lyrics, t: t, theme: theme)
        case .thread: ThreadStyle(lyrics: lyrics, t: t, theme: theme)
        case .terminal: TerminalStyle(lyrics: lyrics, t: t, theme: theme)
        case .drift: DriftStyle(lyrics: lyrics, t: t, theme: theme)
        }
    }
}

// MARK: - Spotlight

struct SpotlightStyle: View {
    let lyrics: Lyrics
    let t: Double
    let theme: LyricTheme

    var body: some View {
        if let st = lyrics.state(at: t) {
            let line = lyrics.lines[st.lineIndex]
            let size = 44 * theme.scale
            let enter = easeOut((t - line.start + 0.05) / 0.25)
            VStack(spacing: 14 * theme.scale) {
                FlowLayout(spacing: size * 0.26, lineSpacing: size * 0.1) {
                    ForEach(Array(line.words.enumerated()), id: \.offset) { i, w in
                        word(w.text, index: i, state: st, size: size)
                    }
                }
                .frame(maxWidth: 900 * theme.scale)
                if let next = nextLine(after: st.lineIndex) {
                    Text(next.text)
                        .font(theme.font.font(size: size * 0.45, weight: .semibold))
                        .foregroundStyle(theme.dim)
                        .multilineTextAlignment(.center)
                }
            }
            .opacity(enter)
            .offset(y: (1 - enter) * 14)
            .lyricShadow(theme.shadow)
        }
    }

    private func nextLine(after i: Int) -> LyricLine? {
        guard i + 1 < lyrics.lines.count else { return nil }
        let n = lyrics.lines[i + 1]
        return n.isInstrumental ? nil : n
    }

    @ViewBuilder
    private func word(_ text: String, index i: Int, state st: LyricState, size: CGFloat) -> some View {
        let font = theme.font.font(size: size, weight: .heavy)
        if i < st.wordIndex {
            Text(text).font(font).foregroundStyle(theme.text)
        } else if i > st.wordIndex {
            Text(text).font(font).foregroundStyle(theme.dim)
        } else {
            let p = st.wordProgress
            ZStack(alignment: .leading) {
                Text(text).font(font).foregroundStyle(theme.dim)
                Text(text).font(font).foregroundStyle(theme.highlight)
                    .mask(alignment: .leading) {
                        GeometryReader { g in Rectangle().frame(width: g.size.width * p) }
                    }
            }
            .scaleEffect(1 + 0.06 * easeOut(p * 3))
        }
    }
}

// MARK: - Stack

struct StackStyle: View {
    let lyrics: Lyrics
    let t: Double
    let theme: LyricTheme

    private struct Slot { var y: Double; var scale: Double; var opacity: Double }

    var body: some View {
        if let st = lyrics.state(at: t), st.wordIndex >= 0 {
            let words = recentWords(st)
            let size = 64 * theme.scale
            let current = words.last!
            let a = easeOutBack((t - current.start) / 0.28)
            let slots = [Slot(y: 0, scale: 1, opacity: 1),
                         Slot(y: -0.95, scale: 0.6, opacity: 0.6),
                         Slot(y: -1.6, scale: 0.42, opacity: 0.3),
                         Slot(y: -2.1, scale: 0.3, opacity: 0)]
            let entry = Slot(y: 0.8, scale: 0.7, opacity: 0)
            ZStack {
                ForEach(Array(words.enumerated()), id: \.offset) { idx, w in
                    let k = words.count - 1 - idx // 0 = current
                    let from = k == 0 ? entry : slots[k - 1]
                    let to = slots[min(k, slots.count - 1)]
                    Text(w.text)
                        .font(theme.font.font(size: size, weight: .black))
                        .foregroundStyle(k == 0 ? theme.highlight : theme.text)
                        .scaleEffect(lerp(from.scale, to.scale, a))
                        .opacity(clamp01(lerp(from.opacity, to.opacity, a)))
                        .offset(y: lerp(from.y, to.y, a) * size)
                }
            }
            .frame(height: size * 2.8, alignment: .bottom)
            .lyricShadow(theme.shadow)
        }
    }

    /// The current word and up to three before it, across line breaks.
    private func recentWords(_ st: LyricState) -> [LyricWord] {
        var out: [LyricWord] = []
        var li = st.lineIndex, wi = st.wordIndex
        while out.count < 4, li >= 0 {
            let words = lyrics.lines[li].words
            if wi >= 0 && wi < words.count {
                out.insert(words[wi], at: 0)
                wi -= 1
            } else {
                li -= 1
                wi = li >= 0 ? lyrics.lines[li].words.count - 1 : -1
            }
        }
        return out
    }
}

// MARK: - Thread

struct ThreadStyle: View {
    let lyrics: Lyrics
    let t: Double
    let theme: LyricTheme

    var body: some View {
        if let st = lyrics.state(at: t) {
            let size = 22 * theme.scale
            let indices = visibleLines(upTo: st.lineIndex)
            VStack(spacing: 8 * theme.scale) {
                ForEach(indices, id: \.self) { i in
                    bubble(i, state: st, size: size, age: indices.last! - i)
                }
            }
            .frame(width: 560 * theme.scale)
        }
    }

    private func visibleLines(upTo i: Int) -> [Int] {
        var out: [Int] = []
        var k = i
        while k >= 0 && out.count < 3 {
            if !lyrics.lines[k].isInstrumental { out.insert(k, at: 0) }
            k -= 1
        }
        return out
    }

    @ViewBuilder
    private func bubble(_ i: Int, state st: LyricState, size: CGFloat, age: Int) -> some View {
        let line = lyrics.lines[i]
        let right = i % 2 == 1
        let isCurrent = i == st.lineIndex
        let shown: String = isCurrent
            ? line.words.prefix(max(st.wordIndex + 1, 0)).map(\.text).joined(separator: " ")
            : line.text
        let enter = isCurrent ? easeOut((t - line.start) / 0.3) : 1
        Text(shown.isEmpty ? "•••" : shown)
            .font(theme.font.font(size: size, weight: .semibold))
            .foregroundStyle(right ? Color.white : theme.text)
            .padding(.horizontal, 16 * theme.scale)
            .padding(.vertical, 10 * theme.scale)
            .background(
                RoundedRectangle(cornerRadius: 20 * theme.scale, style: .continuous)
                    .fill(right ? theme.highlight : Color(white: 0.2).opacity(0.92))
            )
            .frame(maxWidth: .infinity, alignment: right ? .trailing : .leading)
            .opacity((age == 0 ? 1 : age == 1 ? 0.6 : 0.3) * enter)
            .offset(y: (1 - enter) * 30)
            .shadow(color: .black.opacity(theme.shadow ? 0.35 : 0), radius: 8, y: 3)
    }
}

// MARK: - Terminal

struct TerminalStyle: View {
    let lyrics: Lyrics
    let t: Double
    let theme: LyricTheme

    var body: some View {
        if let st = lyrics.state(at: t) {
            let size = 21 * theme.scale
            let mono = Font.system(size: size, weight: .medium, design: .monospaced)
            VStack(alignment: .leading, spacing: 6 * theme.scale) {
                HStack(spacing: 6) {
                    ForEach([Color.red, .yellow, .green], id: \.self) { c in Circle().fill(c.opacity(0.85)).frame(width: 9, height: 9) }
                    Spacer()
                    Text("lyra").font(.system(size: 11, design: .monospaced)).foregroundStyle(.secondary)
                }
                .padding(.bottom, 4)
                ForEach(previous(st.lineIndex), id: \.self) { i in
                    (Text("> ").foregroundStyle(theme.highlight.opacity(0.6)) + Text(lyrics.lines[i].text).foregroundStyle(theme.dim))
                        .font(mono)
                }
                (Text("> ").foregroundStyle(theme.highlight)
                    + Text(typed(st)).foregroundStyle(theme.text)
                    + Text("█").foregroundStyle(theme.highlight.opacity(Int(t * 2.5) % 2 == 0 ? 1 : 0)))
                    .font(mono)
            }
            .padding(18 * theme.scale)
            .frame(width: 660 * theme.scale, alignment: .leading)
            .background(RoundedRectangle(cornerRadius: 12, style: .continuous).fill(Color.black.opacity(0.72)))
            .overlay(RoundedRectangle(cornerRadius: 12, style: .continuous).strokeBorder(Color.white.opacity(0.1)))
        }
    }

    private func previous(_ i: Int) -> [Int] {
        var out: [Int] = []
        var k = i - 1
        while k >= 0 && out.count < 3 {
            if !lyrics.lines[k].isInstrumental { out.insert(k, at: 0) }
            k -= 1
        }
        return out
    }

    private func typed(_ st: LyricState) -> String {
        let words = lyrics.lines[st.lineIndex].words
        guard st.wordIndex >= 0 else { return "" }
        var s = words.prefix(st.wordIndex).map(\.text).joined(separator: " ")
        let w = words[st.wordIndex].text
        let n = Int((Double(w.count) * min(1, st.wordProgress * 2)).rounded(.up))
        if !s.isEmpty { s += " " }
        return s + String(w.prefix(max(n, 1)))
    }
}

// MARK: - Drift

struct DriftStyle: View {
    let lyrics: Lyrics
    let t: Double
    let theme: LyricTheme

    var body: some View {
        if let st = lyrics.state(at: t) {
            let size = 46 * theme.scale
            ZStack {
                if st.lineIndex > 0, !lyrics.lines[st.lineIndex - 1].isInstrumental {
                    flow(lyrics.lines[st.lineIndex - 1], size: size).offset(y: -size * 1.2)
                }
                flow(lyrics.lines[st.lineIndex], size: size)
            }
            .lyricShadow(theme.shadow)
        }
    }

    private func flow(_ line: LyricLine, size: CGFloat) -> some View {
        FlowLayout(spacing: size * 0.26, lineSpacing: size * 0.1) {
            ForEach(Array(line.words.enumerated()), id: \.offset) { _, w in
                let age = t - w.start
                let appear = easeOutBack(age / 0.18)
                let rise = max(0, age - 0.15) * 22
                let fade = age < 0 ? 0 : clamp01(1 - max(0, age - 0.6) / 1.8)
                Text(w.text)
                    .font(theme.font.font(size: size, weight: .heavy))
                    .foregroundStyle(age < (w.end - w.start) ? theme.highlight : theme.text)
                    .scaleEffect(age < 0 ? 0.6 : 0.6 + 0.4 * appear)
                    .opacity(fade)
                    .offset(y: -rise)
            }
        }
        .frame(maxWidth: 900 * theme.scale)
    }
}
