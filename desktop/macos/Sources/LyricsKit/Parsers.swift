import Foundation

// MARK: - lyricsfile (YAML subset)

/// Parses the `lines:` block of an LRCLIB `lyricsfile`. Handles plain, 'single' and "double" quoted
/// scalars, folded continuation lines, and stops at the next top-level key.
public enum LyricsfileParser {
    public static func parse(_ yaml: String) -> Lyrics {
        var raw: [RawLine] = []
        var current: RawLine?
        var currentWord: RawWord?
        var inLines = false
        var lineItemIndent: Int?

        // A scalar may continue on following lines; collect it before assigning.
        var pendingKey: String?
        var pendingIsWord = false
        var pendingKeyColumn = 0
        var pendingParts: [String] = []

        func flushWord() {
            if let w = currentWord { current?.words.append(w) }
            currentWord = nil
        }
        func flushLine() {
            flushWord()
            if let l = current { raw.append(l) }
            current = nil
        }
        func assign(_ key: String, _ value: String, toWord: Bool) {
            if toWord {
                guard currentWord != nil else { return }
                switch key {
                case "text": currentWord!.text = value
                case "start_ms": currentWord!.start = (Double(value) ?? 0) / 1000
                case "end_ms": currentWord!.end = Double(value).map { $0 / 1000 }
                default: break
                }
            } else {
                guard current != nil else { return }
                switch key {
                case "text": current!.text = value
                case "start_ms": current!.start = (Double(value) ?? 0) / 1000
                case "end_ms": current!.end = Double(value).map { $0 / 1000 }
                default: break
                }
            }
        }
        func flushPending() {
            guard let key = pendingKey else { return }
            assign(key, decodeScalar(pendingParts), toWord: pendingIsWord)
            pendingKey = nil
            pendingParts = []
        }

        for rawLine in yaml.components(separatedBy: "\n") {
            let line = rawLine.hasSuffix("\r") ? String(rawLine.dropLast()) : rawLine
            if line.trimmingCharacters(in: .whitespaces).isEmpty { continue }
            let indent = line.prefix(while: { $0 == " " }).count
            var content = String(line.dropFirst(indent))
            let isDash = content.hasPrefix("- ") || content == "-"

            // Continuation of a multi-line scalar.
            if pendingKey != nil, indent > pendingKeyColumn, !isDash,
               isOpenQuoted(pendingParts) || !looksLikeKey(content) {
                pendingParts.append(content)
                continue
            }
            flushPending()

            if indent == 0 && !isDash {
                if content.hasPrefix("lines:") { inLines = true; continue }
                if inLines { break }
                continue
            }
            guard inLines else { continue }

            var keyColumn = indent
            var startsLineItem = false
            if isDash {
                if lineItemIndent == nil { lineItemIndent = indent }
                if indent == lineItemIndent {
                    flushLine()
                    current = RawLine(start: 0, end: nil, text: "", words: [])
                    startsLineItem = true
                } else {
                    flushWord()
                    currentWord = RawWord(start: 0, end: nil, text: "")
                }
                content = String(content.dropFirst(2))
                keyColumn = indent + 2
            }
            guard let base = lineItemIndent else { continue }
            let isWordKey = !startsLineItem && keyColumn > base + 2
            if !isWordKey && !startsLineItem { flushWord() }

            guard let colon = content.firstIndex(of: ":") else { continue }
            let key = String(content[..<colon]).trimmingCharacters(in: .whitespaces)
            let value = String(content[content.index(after: colon)...]).trimmingCharacters(in: .whitespaces)
            if key == "words" { continue }
            pendingKey = key
            pendingIsWord = isWordKey
            pendingKeyColumn = keyColumn
            pendingParts = [value]
        }
        flushPending()
        flushLine()
        return LyricsBuilder.build(raw, source: .wordSynced)
    }

    private static func looksLikeKey(_ s: String) -> Bool {
        guard let colon = s.firstIndex(of: ":") else { return false }
        let key = s[..<colon]
        guard !key.isEmpty, key.allSatisfy({ $0.isLetter || $0 == "_" }) else { return false }
        let after = s.index(after: colon)
        return after == s.endIndex || s[after] == " "
    }

    private static func isOpenQuoted(_ parts: [String]) -> Bool {
        let joined = parts.joined(separator: "\n")
        guard let first = joined.first, first == "\"" || first == "'" else { return false }
        return !quoteTerminated(joined)
    }

    private static func quoteTerminated(_ s: String) -> Bool {
        let chars = Array(s)
        guard let q = chars.first else { return true }
        var i = 1
        while i < chars.count {
            let c = chars[i]
            if q == "\"" && c == "\\" { i += 2; continue }
            if c == q {
                if q == "'" && i + 1 < chars.count && chars[i + 1] == "'" { i += 2; continue }
                return true
            }
            i += 1
        }
        return false
    }

    static func decodeScalar(_ parts: [String]) -> String {
        guard let first = parts.first?.first else { return "" }
        if first == "\"" {
            // Fold lines: a trailing backslash joins without a space, otherwise one space.
            var joined = ""
            for (i, p) in parts.enumerated() {
                var piece = i == 0 ? p : p.trimmingCharacters(in: .whitespaces)
                if i > 0 {
                    if joined.hasSuffix("\\") { joined.removeLast() } else { joined += " " }
                }
                if i < parts.count - 1 { piece = piece.replacingOccurrences(of: "\\s+$", with: "", options: .regularExpression) }
                joined += piece
            }
            return decodeDoubleQuoted(joined)
        }
        if first == "'" {
            let joined = parts.enumerated().map { $0.offset == 0 ? $0.element : $0.element.trimmingCharacters(in: .whitespaces) }
                .joined(separator: " ")
            let chars = Array(joined.dropFirst())
            var out = ""
            var i = 0
            while i < chars.count {
                if chars[i] == "'" {
                    if i + 1 < chars.count && chars[i + 1] == "'" { out.append("'"); i += 2; continue }
                    break
                }
                out.append(chars[i]); i += 1
            }
            return out
        }
        var plain = parts.map { $0.trimmingCharacters(in: .whitespaces) }.joined(separator: " ")
        if let hash = plain.range(of: " #") { plain = String(plain[..<hash.lowerBound]) }
        return plain
    }

    private static func decodeDoubleQuoted(_ s: String) -> String {
        let chars = Array(s.dropFirst())
        var out = ""
        var i = 0
        while i < chars.count {
            let c = chars[i]
            if c == "\"" { break }
            if c == "\\" && i + 1 < chars.count {
                let n = chars[i + 1]
                i += 2
                switch n {
                case "n": out.append("\n")
                case "t": out.append("\t")
                case "\"": out.append("\"")
                case "\\": out.append("\\")
                case "/": out.append("/")
                case "0": out.append("\0")
                case " ": out.append(" ")
                case "x", "u", "U":
                    let len = n == "x" ? 2 : (n == "u" ? 4 : 8)
                    let hex = String(chars[i..<min(i + len, chars.count)])
                    if let v = UInt32(hex, radix: 16), let scalar = Unicode.Scalar(v) { out.unicodeScalars.append(scalar) }
                    i += len
                default: out.append(n)
                }
                continue
            }
            out.append(c)
            i += 1
        }
        return out
    }
}

// MARK: - LRC

public enum LRCParser {
    public static func parse(_ lrc: String) -> Lyrics {
        var offset = 0.0
        var raw: [RawLine] = []
        let tag = try! NSRegularExpression(pattern: #"\[(\d{1,3}):(\d{1,2}(?:[.:]\d{1,3})?)\]"#)
        let wordTag = try! NSRegularExpression(pattern: #"<(\d{1,3}):(\d{1,2}(?:[.:]\d{1,3})?)>"#)
        var hadWordTags = false

        for rawLine in lrc.components(separatedBy: .newlines) {
            let line = rawLine.trimmingCharacters(in: .whitespaces)
            if line.lowercased().hasPrefix("[offset:") {
                let v = line.dropFirst(8).dropLast().trimmingCharacters(in: .whitespaces)
                offset = (Double(v) ?? 0) / 1000
                continue
            }
            let ns = line as NSString
            let matches = tag.matches(in: line, range: NSRange(location: 0, length: ns.length))
            guard !matches.isEmpty, matches[0].range.location == 0 else { continue }
            // Tags must be contiguous at the start of the line.
            var times: [Double] = []
            var textStart = 0
            for m in matches where m.range.location == textStart {
                times.append(seconds(ns.substring(with: m.range(at: 1)), ns.substring(with: m.range(at: 2))))
                textStart = m.range.location + m.range.length
            }
            let body = ns.substring(from: textStart)

            // Enhanced LRC: <mm:ss.xx>word <mm:ss.xx>word
            let bodyNS = body as NSString
            let wm = wordTag.matches(in: body, range: NSRange(location: 0, length: bodyNS.length))
            var words: [RawWord] = []
            var plainText = body
            if !wm.isEmpty {
                hadWordTags = true
                for (k, m) in wm.enumerated() {
                    let start = seconds(bodyNS.substring(with: m.range(at: 1)), bodyNS.substring(with: m.range(at: 2)))
                    let from = m.range.location + m.range.length
                    let to = k + 1 < wm.count ? wm[k + 1].range.location : bodyNS.length
                    let text = bodyNS.substring(with: NSRange(location: from, length: max(0, to - from)))
                    if text.trimmingCharacters(in: .whitespaces).isEmpty {
                        // A trailing tag marks the end of the previous word.
                        if var last = words.popLast() { last.end = start - offset; words.append(last) }
                        continue
                    }
                    words.append(RawWord(start: start - offset, end: nil, text: text))
                }
                plainText = wordTag.stringByReplacingMatches(in: body, range: NSRange(location: 0, length: bodyNS.length), withTemplate: "")
            }
            for t in times {
                raw.append(RawLine(start: t - offset, end: nil, text: plainText, words: words))
            }
        }
        return LyricsBuilder.build(raw, source: hadWordTags ? .wordSynced : .lineSynced)
    }

    private static func seconds(_ m: String, _ s: String) -> Double {
        (Double(m) ?? 0) * 60 + (Double(s.replacingOccurrences(of: ":", with: ".")) ?? 0)
    }
}
