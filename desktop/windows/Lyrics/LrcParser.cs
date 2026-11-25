using System.Globalization;
using System.Text.RegularExpressions;

namespace Lyrics;

/// <summary>
/// Parses LRC (<c>[mm:ss.xx]text</c>). Enhanced LRC word tags (<c>&lt;mm:ss.xx&gt;</c>) are honoured when present;
/// otherwise word times are interpolated by <see cref="WordTiming.Interpolate"/>.
/// </summary>
public static partial class LrcParser
{
    [GeneratedRegex(@"\[(\d{1,3}):(\d{1,2})(?:[.:](\d{1,3}))?\]")]
    private static partial Regex LineTag();

    [GeneratedRegex(@"<(\d{1,3}):(\d{1,2})(?:[.:](\d{1,3}))?>")]
    private static partial Regex WordTag();

    [GeneratedRegex(@"^\[offset:\s*([+-]?\d+)\s*\]", RegexOptions.IgnoreCase)]
    private static partial Regex OffsetTag();

    private readonly record struct RawLine(double Start, string Body);

    public static LyricsDocument Parse(string lrc)
    {
        var raw = new List<RawLine>();
        double offsetSeconds = 0;

        foreach (var sourceLine in lrc.Split('\n'))
        {
            var line = sourceLine.Trim().TrimEnd('\r');
            if (line.Length == 0) continue;

            var offset = OffsetTag().Match(line);
            if (offset.Success)
            {
                // Positive offsets make lyrics appear sooner.
                offsetSeconds = int.Parse(offset.Groups[1].Value, CultureInfo.InvariantCulture) / 1000.0;
                continue;
            }

            // A line may carry several leading timestamps: [00:12.00][00:40.00]chorus
            var times = new List<double>();
            var pos = 0;
            while (pos < line.Length)
            {
                var m = LineTag().Match(line, pos);
                if (!m.Success || m.Index != pos) break;
                times.Add(ToSeconds(m));
                pos = m.Index + m.Length;
            }
            if (times.Count == 0) continue; // metadata such as [ar:...] or junk

            var body = line[pos..];
            foreach (var t in times) raw.Add(new RawLine(Math.Max(0, t - offsetSeconds), body));
        }

        raw.Sort((a, b) => a.Start.CompareTo(b.Start));

        var lines = new List<LyricLine>(raw.Count);
        var anyWordTags = false;
        for (var i = 0; i < raw.Count; i++)
        {
            var start = raw[i].Start;
            var end = i + 1 < raw.Count
                ? Math.Min(raw[i + 1].Start, start + WordTiming.MaxLrcLineSeconds)
                : start + WordTiming.LastLineSeconds;
            if (end < start) end = start;

            var body = raw[i].Body;
            if (WordTag().IsMatch(body))
            {
                var (text, words) = ParseEnhanced(body, start, end, offsetSeconds);
                if (words.Count > 0)
                {
                    anyWordTags = true;
                    // With word tags the line ends with its last word (an end tag, or the next line's start).
                    lines.Add(new LyricLine(start, Math.Max(start, words[^1].End), text, words));
                    continue;
                }
                body = text;
            }

            var plain = body.Trim();
            lines.Add(new LyricLine(start, end, plain, WordTiming.Interpolate(plain, start, end)));
        }

        return new LyricsDocument(anyWordTags ? LyricsSource.WordSynced : LyricsSource.LineSynced, lines);
    }

    private static (string Text, IReadOnlyList<LyricWord> Words) ParseEnhanced(string body, double lineStart, double lineEnd, double offset)
    {
        // Segments: (time, text). Text before the first tag starts at the line start.
        var segments = new List<(double Time, string Text)>();
        var matches = WordTag().Matches(body);
        var leading = body[..matches[0].Index];
        if (leading.Trim().Length > 0) segments.Add((lineStart, leading));
        for (var i = 0; i < matches.Count; i++)
        {
            var m = matches[i];
            var textStart = m.Index + m.Length;
            var textEnd = i + 1 < matches.Count ? matches[i + 1].Index : body.Length;
            segments.Add((Math.Max(0, ToSeconds(m) - offset), body[textStart..textEnd]));
        }

        var words = new List<LyricWord>();
        for (var i = 0; i < segments.Count; i++)
        {
            var (time, text) = segments[i];
            if (text.Trim().Length == 0)
            {
                // A tag with no text marks the end of the previous word.
                if (words.Count > 0 && time > words[^1].Start && words[^1].End > time)
                    words[^1] = words[^1] with { End = time };
                if (words.Count > 0 && text.Length > 0) words[^1] = words[^1] with { SpaceAfter = true };
                continue;
            }

            var next = i + 1 < segments.Count ? segments[i + 1].Time : lineEnd;
            if (next <= time) next = Math.Max(time, lineEnd);
            var spaceAfter = char.IsWhiteSpace(text[^1]);
            var parts = text.Split((char[]?)null, StringSplitOptions.RemoveEmptyEntries);
            if (parts.Length == 1)
            {
                words.Add(new LyricWord(time, next, parts[0], spaceAfter));
            }
            else
            {
                // Several words inside one tag: share the span by letters.
                var shared = WordTiming.Interpolate(text, time, next);
                for (var k = 0; k < shared.Count; k++)
                    words.Add(shared[k] with { SpaceAfter = k < shared.Count - 1 || spaceAfter });
            }
        }

        if (words.Count > 0) words[^1] = words[^1] with { SpaceAfter = false };
        var lineText = string.Concat(words.Select(w => w.SpaceAfter ? w.Text + " " : w.Text)).Trim();
        return (lineText, words);
    }

    private static double ToSeconds(Match m)
    {
        var minutes = int.Parse(m.Groups[1].Value, CultureInfo.InvariantCulture);
        var seconds = int.Parse(m.Groups[2].Value, CultureInfo.InvariantCulture);
        double fraction = 0;
        if (m.Groups[3].Success)
        {
            var f = m.Groups[3].Value;
            fraction = int.Parse(f, CultureInfo.InvariantCulture) / Math.Pow(10, f.Length);
        }
        return minutes * 60 + seconds + fraction;
    }
}
