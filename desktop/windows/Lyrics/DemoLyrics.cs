namespace Lyrics;

/// <summary>A built-in demo song used by the settings preview, so styles can be tried with no music playing.</summary>
public static class DemoLyrics
{
    /// <summary>Total loop length in seconds, including a short rest at the end.</summary>
    public const double LoopSeconds = 13.0;

    public static LyricsDocument Document { get; } = Build();

    private static LyricsDocument Build()
    {
        (double Start, double End, string Text)[] script =
        {
            (0.4, 3.4, "Light is pouring through the edges"),
            (3.6, 6.4, "every word arrives on time"),
            (6.6, 9.4, "sing along and watch it glow"),
            (9.6, 12.2, "this is how the lyrics flow"),
        };

        var lines = script
            .Select(s => new LyricLine(s.Start, s.End, s.Text, WordTiming.Interpolate(s.Text, s.Start, s.End)))
            .ToList();
        return new LyricsDocument(LyricsSource.WordSynced, lines);
    }
}
