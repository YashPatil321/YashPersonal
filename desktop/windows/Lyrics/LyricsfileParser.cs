using System.Globalization;
using System.Text;

namespace Lyrics;

/// <summary>
/// Parses the <c>lines:</c> block of an LRCLIB "lyricsfile" (a small, regular YAML document).
/// This is deliberately not a general YAML parser: it understands block sequences of mappings with plain,
/// 'single' ('' escapes a quote) and "double" (backslash escapes) scalars, plus single-line flow mappings,
/// and stops at the next top-level key (for example <c>plain: |</c>).
/// </summary>
public static class LyricsfileParser
{
    private sealed class RawWord
    {
        public string? Text;
        public double? StartMs;
        public double? EndMs;
    }

    private sealed class RawLine
    {
        public string? Text;
        public double? StartMs;
        public double? EndMs;
        public readonly List<RawWord> Words = new();
    }

    public static LyricsDocument Parse(string yaml)
    {
        var raw = ParseRaw(yaml);
        return Build(raw);
    }

    private static List<RawLine> ParseRaw(string yaml)
    {
        var lines = new List<RawLine>();
        var inLinesBlock = false;
        var lineItemIndent = -1;
        var lineKeyIndent = -1;
        var wordKeyIndent = -1;
        var inWords = false;
        RawLine? line = null;
        RawWord? word = null;

        using var reader = new StringReader(yaml);
        string? rawLine;
        while ((rawLine = reader.ReadLine()) is not null)
        {
            var text = rawLine.TrimEnd('\r');
            var indent = CountIndent(text);
            var content = text.Trim();
            if (content.Length == 0 || content.StartsWith('#')) continue;

            if (!inLinesBlock)
            {
                if (indent == 0 && IsKey(content, "lines", out var inlineValue))
                {
                    inLinesBlock = true;
                    if (inlineValue.StartsWith('[')) break; // "lines: []"
                }
                continue;
            }

            // The next top-level key ends the block.
            if (indent == 0 && !content.StartsWith('-')) break;
            if (content == "---" || content == "...") break;

            var isItem = content == "-" || content.StartsWith("- ", StringComparison.Ordinal);
            if (isItem)
            {
                var rest = content.Length > 1 ? content[2..].Trim() : string.Empty;
                if (line is null || indent <= lineItemIndent)
                {
                    line = new RawLine();
                    lines.Add(line);
                    lineItemIndent = indent;
                    lineKeyIndent = indent + 2;
                    inWords = false;
                    word = null;
                    ApplyInline(rest, (k, v) => SetLineField(line, k, v, ref inWords));
                }
                else if (inWords)
                {
                    word = new RawWord();
                    line.Words.Add(word);
                    wordKeyIndent = indent + 2;
                    ApplyInline(rest, (k, v) => SetWordField(word, k, v));
                }
                continue;
            }

            if (line is null) continue;
            if (!TrySplitKeyValue(content, out var key, out var value)) continue;

            if (inWords && word is not null && indent >= wordKeyIndent)
            {
                SetWordField(word, key, value);
            }
            else if (indent <= lineKeyIndent)
            {
                inWords = false;
                word = null;
                SetLineField(line, key, value, ref inWords);
            }
        }

        return lines;
    }

    private static void ApplyInline(string rest, Action<string, string> set)
    {
        if (rest.Length == 0) return;
        if (rest.StartsWith('{'))
        {
            foreach (var (k, v) in ParseFlowMapping(rest)) set(k, v);
            return;
        }
        if (TrySplitKeyValue(rest, out var key, out var value)) set(key, value);
    }

    private static void SetLineField(RawLine line, string key, string value, ref bool inWords)
    {
        switch (key)
        {
            case "text":
                line.Text = ParseScalar(value);
                break;
            case "start_ms":
                line.StartMs = ParseNumber(value);
                break;
            case "end_ms":
                line.EndMs = ParseNumber(value);
                break;
            case "words":
                var v = StripComment(value).Trim();
                if (v.StartsWith('['))
                {
                    // Flow sequence of flow mappings on one line: [{text: a, start_ms: 1}, ...]
                    foreach (var item in SplitFlowItems(v[1..^(v.EndsWith(']') ? 1 : 0)]))
                    {
                        var w = new RawWord();
                        foreach (var (k, val) in ParseFlowMapping(item)) SetWordField(w, k, val);
                        if (w.Text is not null || w.StartMs is not null) line.Words.Add(w);
                    }
                    inWords = false;
                }
                else
                {
                    inWords = true;
                }
                break;
        }
    }

    private static void SetWordField(RawWord word, string key, string value)
    {
        switch (key)
        {
            case "text":
                word.Text = ParseScalar(value);
                break;
            case "start_ms":
                word.StartMs = ParseNumber(value);
                break;
            case "end_ms":
                word.EndMs = ParseNumber(value);
                break;
        }
    }

    private static LyricsDocument Build(List<RawLine> raw)
    {
        var timed = raw.Where(l => l.StartMs is not null).OrderBy(l => l.StartMs!.Value).ToList();
        var result = new List<LyricLine>(timed.Count);
        var anyRealWords = false;

        for (var i = 0; i < timed.Count; i++)
        {
            var r = timed[i];
            var start = r.StartMs!.Value / 1000.0;
            var nextStart = i + 1 < timed.Count ? timed[i + 1].StartMs!.Value / 1000.0 : (double?)null;

            double end;
            if (r.EndMs is { } endMs && endMs / 1000.0 > start) end = endMs / 1000.0;
            else end = nextStart ?? start + WordTiming.LastLineSeconds;

            var text = r.Text ?? string.Concat(r.Words.Select(w => w.Text ?? string.Empty));
            IReadOnlyList<LyricWord> words;
            var rawWords = r.Words.Where(w => w.StartMs is not null && !string.IsNullOrWhiteSpace(w.Text))
                                  .OrderBy(w => w.StartMs!.Value).ToList();
            if (rawWords.Count > 0)
            {
                words = BuildWords(rawWords, text, end);
                anyRealWords = true;
            }
            else
            {
                words = WordTiming.Interpolate(text, start, end);
            }

            result.Add(new LyricLine(start, end, text.Trim(), words));
        }

        return new LyricsDocument(anyRealWords ? LyricsSource.WordSynced : LyricsSource.LineSynced, result);
    }

    private static IReadOnlyList<LyricWord> BuildWords(List<RawWord> raw, string lineText, double lineEnd)
    {
        var words = new LyricWord[raw.Count];
        var cursor = 0;
        for (var i = 0; i < raw.Count; i++)
        {
            var w = raw[i];
            var rawText = w.Text!;
            var trimmed = rawText.Trim();
            var start = w.StartMs!.Value / 1000.0;
            var nextStart = i + 1 < raw.Count ? raw[i + 1].StartMs!.Value / 1000.0 : lineEnd;
            var end = w.EndMs is { } e && e / 1000.0 > start ? e / 1000.0 : Math.Max(start, nextStart);

            var spaceAfter = rawText.Length > 0 && char.IsWhiteSpace(rawText[^1]);
            var found = lineText.IndexOf(trimmed, cursor, StringComparison.Ordinal);
            if (found >= 0)
            {
                cursor = found + trimmed.Length;
                if (cursor < lineText.Length && char.IsWhiteSpace(lineText[cursor])) spaceAfter = true;
            }
            else if (!spaceAfter)
            {
                spaceAfter = true; // cannot tell; a space is the safer default
            }
            if (i == raw.Count - 1) spaceAfter = false;

            words[i] = new LyricWord(start, end, trimmed, spaceAfter);
        }
        return words;
    }

    // ---------------------------------------------------------------- scalars

    /// <summary>Parses a YAML scalar: plain, 'single' or "double".</summary>
    public static string ParseScalar(string value)
    {
        var v = value.TrimStart();
        if (v.Length == 0) return string.Empty;

        if (v[0] == '\'')
        {
            var sb = new StringBuilder();
            for (var i = 1; i < v.Length; i++)
            {
                if (v[i] == '\'')
                {
                    if (i + 1 < v.Length && v[i + 1] == '\'')
                    {
                        sb.Append('\'');
                        i++;
                        continue;
                    }
                    break;
                }
                sb.Append(v[i]);
            }
            return sb.ToString();
        }

        if (v[0] == '"')
        {
            var sb = new StringBuilder();
            for (var i = 1; i < v.Length; i++)
            {
                var c = v[i];
                if (c == '"') break;
                if (c == '\\' && i + 1 < v.Length)
                {
                    var n = v[++i];
                    switch (n)
                    {
                        case 'n': sb.Append('\n'); break;
                        case 't': sb.Append('\t'); break;
                        case 'r': sb.Append('\r'); break;
                        case '0': sb.Append('\0'); break;
                        case ' ': sb.Append(' '); break;
                        case '/': sb.Append('/'); break;
                        case '\\': sb.Append('\\'); break;
                        case '"': sb.Append('"'); break;
                        case 'x' when i + 2 < v.Length && TryHex(v.AsSpan(i + 1, 2), out var x):
                            sb.Append((char)x); i += 2; break;
                        case 'u' when i + 4 < v.Length && TryHex(v.AsSpan(i + 1, 4), out var u):
                            sb.Append((char)u); i += 4; break;
                        case 'U' when i + 8 < v.Length && TryHex(v.AsSpan(i + 1, 8), out var cp):
                            sb.Append(char.ConvertFromUtf32(cp)); i += 8; break;
                        default: sb.Append(n); break;
                    }
                    continue;
                }
                sb.Append(c);
            }
            return sb.ToString();
        }

        var plain = StripComment(v).Trim();
        return plain is "~" or "null" ? string.Empty : plain;
    }

    private static bool TryHex(ReadOnlySpan<char> s, out int value) =>
        int.TryParse(s, NumberStyles.HexNumber, CultureInfo.InvariantCulture, out value);

    private static double? ParseNumber(string value)
    {
        var s = ParseScalar(value).Trim();
        return double.TryParse(s, NumberStyles.Float, CultureInfo.InvariantCulture, out var d) ? d : null;
    }

    /// <summary>Removes a trailing " # comment" from a plain scalar.</summary>
    private static string StripComment(string v)
    {
        var i = v.IndexOf(" #", StringComparison.Ordinal);
        return i >= 0 ? v[..i] : v;
    }

    private static int CountIndent(string s)
    {
        var n = 0;
        while (n < s.Length && s[n] == ' ') n++;
        return n;
    }

    private static bool IsKey(string content, string key, out string value)
    {
        value = string.Empty;
        if (!TrySplitKeyValue(content, out var k, out var v) || k != key) return false;
        value = v.Trim();
        return true;
    }

    /// <summary>Splits <c>key: value</c>. The key is plain or quoted; the colon must be followed by a space or end.</summary>
    private static bool TrySplitKeyValue(string content, out string key, out string value)
    {
        key = value = string.Empty;
        if (content.Length == 0) return false;

        int colon;
        if (content[0] is '"' or '\'')
        {
            var close = content.IndexOf(content[0], 1);
            if (close < 0) return false;
            colon = content.IndexOf(':', close);
            if (colon < 0) return false;
            key = ParseScalar(content[..(close + 1)]);
        }
        else
        {
            colon = -1;
            for (var i = 0; i < content.Length; i++)
            {
                if (content[i] == ':' && (i + 1 == content.Length || content[i + 1] == ' ' || content[i + 1] == '\t'))
                {
                    colon = i;
                    break;
                }
            }
            if (colon <= 0) return false;
            key = content[..colon].Trim();
        }

        value = colon + 1 < content.Length ? content[(colon + 1)..].Trim() : string.Empty;
        return true;
    }

    // ---------------------------------------------------------------- flow collections

    private static IEnumerable<(string Key, string Value)> ParseFlowMapping(string text)
    {
        var t = text.Trim();
        if (t.StartsWith('{')) t = t[1..];
        if (t.EndsWith('}')) t = t[..^1];
        foreach (var item in SplitFlowItems(t))
        {
            if (TrySplitKeyValue(item.Trim(), out var k, out var v)) yield return (k, v);
        }
    }

    /// <summary>Splits on commas that are outside quotes and nested braces.</summary>
    private static IEnumerable<string> SplitFlowItems(string text)
    {
        var depth = 0;
        char quote = '\0';
        var start = 0;
        for (var i = 0; i < text.Length; i++)
        {
            var c = text[i];
            if (quote != '\0')
            {
                if (quote == '"' && c == '\\') { i++; continue; }
                if (c == quote)
                {
                    if (quote == '\'' && i + 1 < text.Length && text[i + 1] == '\'') { i++; continue; }
                    quote = '\0';
                }
                continue;
            }
            switch (c)
            {
                case '"' or '\'': quote = c; break;
                case '{' or '[': depth++; break;
                case '}' or ']': depth--; break;
                case ',' when depth == 0:
                    yield return text[start..i];
                    start = i + 1;
                    break;
            }
        }
        if (start < text.Length && text[start..].Trim().Length > 0) yield return text[start..];
    }
}
