import Foundation

public struct LyricWord: Equatable, Sendable {
    public var start: Double
    public var end: Double
    public var text: String
    /// Whether a space follows this word when the line is rendered.
    public var spaceAfter: Bool

    public init(start: Double, end: Double, text: String, spaceAfter: Bool = true) {
        self.start = start
        self.end = end
        self.text = text
        self.spaceAfter = spaceAfter
    }
}

public struct LyricLine: Equatable, Sendable {
    public var start: Double
    public var end: Double
    public var text: String
    public var words: [LyricWord]

    public init(start: Double, end: Double, text: String, words: [LyricWord]) {
        self.start = start
        self.end = end
        self.text = text
        self.words = words
    }

    /// Empty lines and lone music notes are instrumental gaps.
    public var isInstrumental: Bool {
        let t = text.trimmingCharacters(in: .whitespacesAndNewlines)
        return t.isEmpty || t.allSatisfy { $0 == "♪" || $0 == "♫" || $0.isWhitespace }
    }
}

public enum LyricsSource: String, Sendable {
    case wordSynced = "Word by word"
    case lineSynced = "Line by line"
    case none = "None"
}

public struct LyricState: Equatable, Sendable {
    public var lineIndex: Int
    /// -1 before the first word of the line has started.
    public var wordIndex: Int
    /// 0...1 progress through the current word.
    public var wordProgress: Double
}

public struct Lyrics: Equatable, Sendable {
    public var source: LyricsSource
    public var lines: [LyricLine]

    public init(source: LyricsSource, lines: [LyricLine]) {
        self.source = source
        self.lines = lines
    }

    public static let none = Lyrics(source: .none, lines: [])

    /// How long a line may linger after its end when the next line is far away.
    public static let linger: Double = 1.5

    public func state(at t: Double) -> LyricState? {
        guard !lines.isEmpty else { return nil }
        // Binary search: last line whose start <= t.
        var lo = 0, hi = lines.count - 1, found = -1
        while lo <= hi {
            let mid = (lo + hi) / 2
            if lines[mid].start <= t { found = mid; lo = mid + 1 } else { hi = mid - 1 }
        }
        guard found >= 0 else { return nil }
        let line = lines[found]
        if line.isInstrumental { return nil }
        let nextStart = found + 1 < lines.count ? lines[found + 1].start : Double.infinity
        let displayEnd = min(nextStart, line.end + Lyrics.linger)
        guard t < displayEnd else { return nil }

        var wlo = 0, whi = line.words.count - 1, w = -1
        while wlo <= whi {
            let mid = (wlo + whi) / 2
            if line.words[mid].start <= t { w = mid; wlo = mid + 1 } else { whi = mid - 1 }
        }
        var progress = 0.0
        if w >= 0 {
            let word = line.words[w]
            let span = word.end - word.start
            progress = span > 0 ? min(max((t - word.start) / span, 0), 1) : 1
        }
        return LyricState(lineIndex: found, wordIndex: w, wordProgress: progress)
    }
}

// MARK: - Building lines from raw parser output

struct RawWord {
    var start: Double
    var end: Double?
    var text: String
}

struct RawLine {
    var start: Double
    var end: Double?
    var text: String
    var words: [RawWord]
}

enum LyricsBuilder {
    static func build(_ raw: [RawLine], source: LyricsSource) -> Lyrics {
        let sorted = raw.sorted { $0.start < $1.start }
        var lines: [LyricLine] = []
        for (i, r) in sorted.enumerated() {
            let nextStart = i + 1 < sorted.count ? sorted[i + 1].start : nil
            let end = r.end ?? nextStart ?? (r.start + 4)
            let text = r.text.trimmingCharacters(in: .whitespacesAndNewlines)
            var words: [LyricWord]
            if !r.words.isEmpty {
                words = []
                for (j, w) in r.words.enumerated() {
                    let nextWordStart = j + 1 < r.words.count ? r.words[j + 1].start : end
                    let wEnd = w.end ?? nextWordStart
                    words.append(LyricWord(start: w.start, end: max(wEnd, w.start),
                                           text: w.text.trimmingCharacters(in: .whitespacesAndNewlines)))
                }
                words.removeAll { $0.text.isEmpty }
                assignSpacing(&words, lineText: r.text)
            } else {
                words = interpolate(text: text, start: r.start, end: min(end, r.start + 8))
            }
            lines.append(LyricLine(start: r.start, end: end, text: text, words: words))
        }
        return Lyrics(source: lines.isEmpty ? .none : source, lines: lines)
    }

    /// Words share the line's span in proportion to (letters + 2).
    static func interpolate(text: String, start: Double, end: Double) -> [LyricWord] {
        let parts = text.split(whereSeparator: { $0.isWhitespace }).map(String.init)
        guard !parts.isEmpty else { return [] }
        let weights = parts.map { Double($0.filter { $0.isLetter || $0.isNumber }.count + 2) }
        let total = weights.reduce(0, +)
        let span = max(end - start, 0.1)
        var t = start
        var out: [LyricWord] = []
        for (i, p) in parts.enumerated() {
            let d = span * weights[i] / total
            out.append(LyricWord(start: t, end: t + d, text: p, spaceAfter: i < parts.count - 1))
            t += d
        }
        return out
    }

    /// Decide whether each word is followed by a space by walking the line's text.
    static func assignSpacing(_ words: inout [LyricWord], lineText: String) {
        let chars = Array(lineText)
        var cursor = 0
        for i in words.indices {
            let w = Array(words[i].text)
            var matched = false
            if !w.isEmpty, cursor < chars.count {
                var k = cursor
                while k + w.count <= chars.count {
                    if Array(chars[k..<(k + w.count)]) == w {
                        cursor = k + w.count
                        matched = true
                        break
                    }
                    k += 1
                }
            }
            if matched {
                words[i].spaceAfter = cursor < chars.count && chars[cursor].isWhitespace
            } else {
                words[i].spaceAfter = true
            }
        }
        if !words.isEmpty { words[words.count - 1].spaceAfter = false }
    }
}
