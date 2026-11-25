using Lyrics;
using Xunit;

namespace Lyrics.Tests;

public class StateAtTests
{
    private static LyricsDocument Doc() => LrcParser.Parse(
        "[00:01.00]<00:01.00>one <00:02.00>two<00:03.00>\n" +
        "[00:10.00]three four\n" +
        "[00:11.00]♪\n" +
        "[00:14.00]five\n");

    [Fact]
    public void BeforeFirstLineIsNone()
    {
        Assert.Equal(LyricsState.None, Doc().StateAt(0.5));
        Assert.Equal(LyricsState.None, LyricsDocument.Empty.StateAt(5));
        Assert.Equal(LyricsState.None, Doc().StateAt(double.NaN));
    }

    [Fact]
    public void FindsWordAndProgress()
    {
        var s = Doc().StateAt(1.5);
        Assert.Equal(0, s.LineIndex);
        Assert.Equal(0, s.WordIndex);
        Assert.Equal(0.5, s.WordProgress, 6);

        s = Doc().StateAt(2.0);
        Assert.Equal(1, s.WordIndex);
        Assert.Equal(0.0, s.WordProgress, 6);
    }

    [Fact]
    public void ExactLineStartIsThatLine()
    {
        var s = Doc().StateAt(10.0);
        Assert.Equal(1, s.LineIndex);
        Assert.Equal(0, s.WordIndex);
    }

    [Fact]
    public void LineHoldsForOneAndAHalfSecondsAfterEnd()
    {
        // Line 0 ends at 3.0 (its last word tag), so it stays current until 4.5, then there is a gap until 10.
        var doc = Doc();
        var held = doc.StateAt(4.4);
        Assert.Equal(0, held.LineIndex);
        Assert.Equal(1, held.WordIndex);
        Assert.Equal(1.0, held.WordProgress);
        Assert.Equal(LyricsState.None, doc.StateAt(4.6));
        Assert.Equal(LyricsState.None, doc.StateAt(9.99));
    }

    [Fact]
    public void NextLineStartEndsTheLineEvenWithinHold()
    {
        // Line 1 (10 → 11) would hold until 12.5 but the ♪ line starts at 11.
        var doc = Doc();
        Assert.Equal(1, doc.StateAt(10.99).LineIndex);
        Assert.Equal(LyricsState.None, doc.StateAt(11.0)); // instrumental gap shows nothing
        Assert.Equal(LyricsState.None, doc.StateAt(13.5));
        Assert.Equal(3, doc.StateAt(14.1).LineIndex);
    }

    [Fact]
    public void AfterLastLineIsNone()
    {
        var doc = Doc();
        Assert.Equal(3, doc.StateAt(18.0 + 1.49).LineIndex); // 14 + 4 + 1.5
        Assert.Equal(LyricsState.None, doc.StateAt(19.6));
    }

    [Fact]
    public void LineBeforeItsFirstWordHasNoWord()
    {
        var doc = LrcParser.Parse("[00:01.00]<00:02.00>late");
        var s = doc.StateAt(1.5);
        Assert.Equal(0, s.LineIndex);
        Assert.Equal(-1, s.WordIndex);
    }

    [Fact]
    public void NextLineAfterSkipsInstrumentals()
    {
        var doc = Doc();
        Assert.Equal(0, doc.NextLineAfter(0));
        Assert.Equal(3, doc.NextLineAfter(10.5));
        Assert.Equal(-1, doc.NextLineAfter(15));
    }

    [Fact]
    public void BinarySearchMatchesLinearScanOnDemo()
    {
        var doc = DemoLyrics.Document;
        for (var t = -1.0; t < DemoLyrics.LoopSeconds + 2; t += 0.01)
        {
            var expectedLine = -1;
            for (var i = 0; i < doc.Lines.Count; i++)
                if (doc.Lines[i].Start <= t && t < doc.LineVisibleUntil(i)) expectedLine = i;
            Assert.Equal(expectedLine, doc.StateAt(t).LineIndex);
        }
    }
}
