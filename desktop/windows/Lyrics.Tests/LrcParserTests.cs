using Lyrics;
using Xunit;

namespace Lyrics.Tests;

public class LrcParserTests
{
    [Fact]
    public void ParsesLineTimesAndInterpolatesWords()
    {
        const string lrc = "[ar:Someone]\n[ti:Song]\n[00:01.00]Hello world\n[00:03.50]Second line here\n[00:20.00]Far away\n";
        var doc = LrcParser.Parse(lrc);

        Assert.Equal(LyricsSource.LineSynced, doc.Source);
        Assert.Equal(3, doc.Lines.Count);

        var first = doc.Lines[0];
        Assert.Equal(1.0, first.Start);
        Assert.Equal(3.5, first.End); // runs to the next line's start
        Assert.Equal(new[] { "Hello", "world" }, first.Words.Select(w => w.Text));
        // Hello = 5+2, world = 5+2: equal halves.
        Assert.Equal(2.25, first.Words[0].End, 6);

        // Capped at start + 8 s.
        Assert.Equal(3.5 + 8, doc.Lines[1].End, 6);
        // Last line: start + 4 s.
        Assert.Equal(24.0, doc.Lines[2].End, 6);
    }

    [Fact]
    public void HandlesFractionFormatsAndRepeatedTimestamps()
    {
        var doc = LrcParser.Parse("[01:02.5]a\n[00:10.123][00:30]chorus\n[00:05:20]colon\n");
        Assert.Equal(new[] { 5.2, 10.123, 30.0, 62.5 }, doc.Lines.Select(l => Math.Round(l.Start, 3)));
        Assert.Equal("chorus", doc.Lines[1].Text);
        Assert.Equal("chorus", doc.Lines[2].Text);
    }

    [Fact]
    public void HonoursEnhancedWordTags()
    {
        var doc = LrcParser.Parse("[00:01.00]<00:01.00>Hel<00:01.40>lo <00:02.00>world<00:03.00>\n[00:05.00]Next");
        Assert.Equal(LyricsSource.WordSynced, doc.Source);
        var line = doc.Lines[0];
        Assert.Equal("Hello world", line.Text);
        Assert.Equal(new[] { "Hel", "lo", "world" }, line.Words.Select(w => w.Text));
        Assert.False(line.Words[0].SpaceAfter);
        Assert.True(line.Words[1].SpaceAfter);
        Assert.Equal(new[] { 1.0, 1.4, 2.0 }, line.Words.Select(w => w.Start));
        Assert.Equal(new[] { 1.4, 2.0, 3.0 }, line.Words.Select(w => w.End));
        // The plain second line is still interpolated.
        Assert.Single(doc.Lines[1].Words);
    }

    [Fact]
    public void AppliesOffsetTag()
    {
        var doc = LrcParser.Parse("[offset:+500]\n[00:02.00]Early");
        Assert.Equal(1.5, doc.Lines[0].Start, 6);
    }

    [Fact]
    public void InstrumentalGapLinesHaveNoWords()
    {
        var doc = LrcParser.Parse("[00:01.00]Sing\n[00:03.00]♪\n[00:06.00]\n[00:09.00]Again");
        Assert.Equal(4, doc.Lines.Count);
        Assert.True(doc.Lines[1].IsInstrumental);
        Assert.Empty(doc.Lines[1].Words);
        Assert.True(doc.Lines[2].IsInstrumental);
    }

    [Fact]
    public void JunkYieldsNoLyrics()
    {
        var doc = LrcParser.Parse("no timestamps here\n[ar:x]");
        Assert.Equal(LyricsSource.None, doc.Source);
        Assert.False(doc.HasSyncedLyrics);
    }

    [Fact]
    public void InterpolationWeightsUseLetterCountPlusTwo()
    {
        var words = WordTiming.Interpolate("I am here!", 0, 10);
        // I=3, am=4, here!=6 (punctuation is not a letter) → total 13
        Assert.Equal(3, words.Count);
        Assert.Equal(10.0 * 3 / 13, words[0].End, 9);
        Assert.Equal(10.0 * 7 / 13, words[1].End, 9);
        Assert.Equal(10.0, words[2].End, 9);
        Assert.Empty(WordTiming.Interpolate("  ", 0, 1));
    }
}
