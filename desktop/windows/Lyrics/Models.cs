namespace Lyrics;

/// <summary>Where the timing of a <see cref="LyricsDocument"/> came from.</summary>
public enum LyricsSource
{
    None,
    LineSynced,
    WordSynced,
}

/// <summary>One sung word. Times are in seconds.</summary>
/// <param name="Text">The word without surrounding whitespace.</param>
/// <param name="SpaceAfter">False when the next word attaches directly (syllables, punctuation).</param>
public sealed record LyricWord(double Start, double End, string Text, bool SpaceAfter = true)
{
    public double Duration => Math.Max(0, End - Start);
}

/// <summary>One lyric line. Times are in seconds.</summary>
public sealed class LyricLine
{
    public LyricLine(double start, double end, string text, IReadOnlyList<LyricWord> words)
    {
        Start = start;
        End = end;
        Text = text;
        Words = words;
    }

    public double Start { get; }
    public double End { get; }
    public string Text { get; }
    public IReadOnlyList<LyricWord> Words { get; }

    /// <summary>An empty line or a lone ♪ is an instrumental gap and shows nothing.</summary>
    public bool IsInstrumental => IsInstrumentalText(Text);

    public static bool IsInstrumentalText(string? text)
    {
        if (string.IsNullOrWhiteSpace(text)) return true;
        var t = text.Trim();
        foreach (var c in t)
        {
            if (c is not ('♪' or '♫' or '♬' or '♩' or ' ')) return false;
        }
        return true;
    }

    public override string ToString() => $"[{Start:0.00}-{End:0.00}] {Text}";
}

/// <summary>The position inside a <see cref="LyricsDocument"/> at a moment in time.</summary>
/// <param name="LineIndex">-1 when no line is current (before the first line, in a gap, or after the end).</param>
/// <param name="WordIndex">-1 when the line is current but its first word has not started.</param>
/// <param name="WordProgress">0..1 through the current word.</param>
public readonly record struct LyricsState(int LineIndex, int WordIndex, double WordProgress)
{
    public static LyricsState None { get; } = new(-1, -1, 0);
    public bool HasLine => LineIndex >= 0;
}

/// <summary>Lyrics for one track: <c>Lyrics { source, lines }</c> in the shared spec.</summary>
public sealed class LyricsDocument
{
    /// <summary>A line stays current for at most this long after its end.</summary>
    public const double LineHoldSeconds = 1.5;

    public LyricsDocument(LyricsSource source, IReadOnlyList<LyricLine> lines, bool isInstrumental = false)
    {
        Source = lines.Count == 0 ? LyricsSource.None : source;
        Lines = lines;
        IsInstrumental = isInstrumental;
    }

    public static LyricsDocument Empty { get; } = new(LyricsSource.None, Array.Empty<LyricLine>());

    public static LyricsDocument Instrumental { get; } = new(LyricsSource.None, Array.Empty<LyricLine>(), isInstrumental: true);

    public LyricsSource Source { get; }
    public IReadOnlyList<LyricLine> Lines { get; }

    /// <summary>LRCLIB marked the track as instrumental.</summary>
    public bool IsInstrumental { get; }

    public bool HasSyncedLyrics => Source != LyricsSource.None && Lines.Count > 0;

    /// <summary>The time until which line <paramref name="index"/> stays current.</summary>
    public double LineVisibleUntil(int index)
    {
        var line = Lines[index];
        var hold = line.End + LineHoldSeconds;
        return index + 1 < Lines.Count ? Math.Min(Lines[index + 1].Start, hold) : hold;
    }

    /// <summary><c>state(at t)</c>: binary search for the current line and word.</summary>
    public LyricsState StateAt(double t)
    {
        if (Lines.Count == 0 || double.IsNaN(t)) return LyricsState.None;

        var lineIndex = LastStartingAtOrBefore(Lines, t, static l => l.Start);
        if (lineIndex < 0) return LyricsState.None;

        var line = Lines[lineIndex];
        if (line.IsInstrumental || t >= LineVisibleUntil(lineIndex)) return LyricsState.None;

        var words = line.Words;
        var wordIndex = LastStartingAtOrBefore(words, t, static w => w.Start);
        if (wordIndex < 0) return new LyricsState(lineIndex, -1, 0);

        var word = words[wordIndex];
        var progress = word.End > word.Start ? (t - word.Start) / (word.End - word.Start) : 1.0;
        return new LyricsState(lineIndex, wordIndex, Math.Clamp(progress, 0, 1));
    }

    /// <summary>Index of the next line with text that starts after <paramref name="t"/>, or -1.</summary>
    public int NextLineAfter(double t)
    {
        var i = LastStartingAtOrBefore(Lines, t, static l => l.Start) + 1;
        for (; i < Lines.Count; i++)
        {
            if (!Lines[i].IsInstrumental) return i;
        }
        return -1;
    }

    /// <summary>Largest index whose key is &lt;= t, or -1. The list must be sorted by key.</summary>
    internal static int LastStartingAtOrBefore<T>(IReadOnlyList<T> items, double t, Func<T, double> key)
    {
        int lo = 0, hi = items.Count - 1, found = -1;
        while (lo <= hi)
        {
            var mid = lo + ((hi - lo) >> 1);
            if (key(items[mid]) <= t)
            {
                found = mid;
                lo = mid + 1;
            }
            else
            {
                hi = mid - 1;
            }
        }
        return found;
    }
}
