namespace Lyrics;

/// <summary>Word-time interpolation for lines that only have a line timestamp.</summary>
public static class WordTiming
{
    /// <summary>Longest span a line-synced LRC line is given before the next one.</summary>
    public const double MaxLrcLineSeconds = 8.0;

    /// <summary>Length of the last line when nothing follows it.</summary>
    public const double LastLineSeconds = 4.0;

    /// <summary>
    /// Splits <paramref name="text"/> on whitespace and shares <c>[start, end]</c> between the words in proportion
    /// to <c>letterCount + 2</c> per word.
    /// </summary>
    public static IReadOnlyList<LyricWord> Interpolate(string text, double start, double end)
    {
        if (LyricLine.IsInstrumentalText(text)) return Array.Empty<LyricWord>();

        var parts = text.Split((char[]?)null, StringSplitOptions.RemoveEmptyEntries);
        if (parts.Length == 0) return Array.Empty<LyricWord>();

        var weights = new double[parts.Length];
        double total = 0;
        for (var i = 0; i < parts.Length; i++)
        {
            weights[i] = LetterCount(parts[i]) + 2;
            total += weights[i];
        }

        var span = Math.Max(0, end - start);
        var words = new LyricWord[parts.Length];
        var cursor = start;
        for (var i = 0; i < parts.Length; i++)
        {
            var wordEnd = i == parts.Length - 1 ? end : cursor + span * weights[i] / total;
            words[i] = new LyricWord(cursor, wordEnd, parts[i], SpaceAfter: i < parts.Length - 1);
            cursor = wordEnd;
        }
        return words;
    }

    public static int LetterCount(string word)
    {
        var n = 0;
        foreach (var c in word)
        {
            if (char.IsLetterOrDigit(c)) n++;
        }
        return n;
    }
}
