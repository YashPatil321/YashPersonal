using Lyrics;
using Xunit;

namespace Lyrics.Tests;

public class LyricsfileParserTests
{
    private static LyricsDocument LoadFixture()
    {
        var path = Path.Combine(AppContext.BaseDirectory, "fixtures", "lyricsfile-sample.yaml");
        return LyricsfileParser.Parse(File.ReadAllText(path));
    }

    [Fact]
    public void ParsesAllLinesAndStopsAtPlainBlock()
    {
        var doc = LoadFixture();
        Assert.Equal(LyricsSource.WordSynced, doc.Source);
        Assert.Equal(4, doc.Lines.Count);
        Assert.DoesNotContain(doc.Lines, l => l.Text.Contains("plain", StringComparison.Ordinal));
        Assert.Equal(new[] { 1.0, 4.0, 7.0, 10.0 }, doc.Lines.Select(l => l.Start));
    }

    [Fact]
    public void FirstLineHasExplicitWords()
    {
        var line = LoadFixture().Lines[0];
        Assert.Equal("Hello there world", line.Text);
        Assert.Equal(1.0, line.Start);
        Assert.Equal(3.0, line.End);
        Assert.Equal(new[] { "Hello", "there", "world" }, line.Words.Select(w => w.Text));
        Assert.Equal(new[] { 1.0, 1.5, 2.0 }, line.Words.Select(w => w.Start));
        Assert.Equal(new[] { 1.5, 2.0, 3.0 }, line.Words.Select(w => w.End));
    }

    [Fact]
    public void HandlesSingleQuoteEscapesAndDoubleQuoteBackslashEscapes()
    {
        var line = LoadFixture().Lines[1];
        Assert.Equal("It's a \"test\" line", line.Text);
        Assert.Equal(new[] { "It's", "a", "\"test\"", "line" }, line.Words.Select(w => w.Text));
        // "a" has no trailing space in the YAML, but the line text has one after it.
        Assert.True(line.Words[1].SpaceAfter);
        Assert.False(line.Words[^1].SpaceAfter);
        Assert.Equal(4.6, line.Words[2].Start, 6);
        Assert.Equal(5.2, line.Words[2].End, 6);
    }

    [Fact]
    public void LineWithoutWordsGetsInterpolatedWords()
    {
        var line = LoadFixture().Lines[2];
        Assert.Equal("No words here, just a line", line.Text);
        Assert.Equal(7.0, line.Start);
        Assert.Equal(9.0, line.End);
        Assert.Equal(new[] { "No", "words", "here,", "just", "a", "line" }, line.Words.Select(w => w.Text));
        Assert.Equal(7.0, line.Words[0].Start, 6);
        Assert.Equal(9.0, line.Words[^1].End, 6);
        // Weights are letterCount + 2: No=4, words=7, here,=6, just=6, a=3, line=6 → total 32 over 2 s.
        Assert.Equal(7.0 + 2.0 * 4 / 32, line.Words[0].End, 6);
        Assert.Equal(7.0 + 2.0 * 11 / 32, line.Words[1].End, 6);
        for (var i = 1; i < line.Words.Count; i++) Assert.Equal(line.Words[i - 1].End, line.Words[i].Start, 9);
    }

    [Fact]
    public void LastLineWithoutEndLastsFourSeconds()
    {
        var line = LoadFixture().Lines[3];
        Assert.Equal("Last line without an end", line.Text);
        Assert.Equal(10.0, line.Start);
        Assert.Equal(14.0, line.End);
        Assert.Equal(5, line.Words.Count);
        Assert.Equal(14.0, line.Words[^1].End, 6);
    }

    [Fact]
    public void MissingEndUsesNextLineStart()
    {
        const string yaml = """
            lines:
              - text: one
                start_ms: 500
              - text: two
                start_ms: 2500
                end_ms: 3000
            """;
        var doc = LyricsfileParser.Parse(yaml);
        Assert.Equal(2, doc.Lines.Count);
        Assert.Equal(2.5, doc.Lines[0].End);
        Assert.Equal(LyricsSource.LineSynced, doc.Source);
    }

    [Fact]
    public void ParsesFlowMappingWordsAndComments()
    {
        const string yaml = """
            version: '1.0'
            lines:
            # a comment
            - text: 'Go go'
              start_ms: 0
              end_ms: 1000
              words:
              - {text: 'Go ', start_ms: 0, end_ms: 500}
              - {text: "go", start_ms: 500, end_ms: 1000}
            other: true
            """;
        var doc = LyricsfileParser.Parse(yaml);
        var line = Assert.Single(doc.Lines);
        Assert.Equal(new[] { "Go", "go" }, line.Words.Select(w => w.Text));
        Assert.Equal(0.5, line.Words[1].Start);
    }

    [Theory]
    [InlineData("plain text", "plain text")]
    [InlineData("'it''s'", "it's")]
    [InlineData("\"say \\\"hi\\\"\"", "say \"hi\"")]
    [InlineData("\"tab\\tnew\\\\\"", "tab\tnew\\")]
    [InlineData("\"\\u00e9t\\u00e9\"", "été")]
    [InlineData("value # comment", "value")]
    [InlineData("'# not a comment'", "# not a comment")]
    public void ParsesScalars(string raw, string expected) =>
        Assert.Equal(expected, LyricsfileParser.ParseScalar(raw));

    [Fact]
    public void EmptyDocumentHasNoLyrics()
    {
        var doc = LyricsfileParser.Parse("version: '1.0'\nplain: |\n  hi\n");
        Assert.Equal(LyricsSource.None, doc.Source);
        Assert.Empty(doc.Lines);
    }
}
