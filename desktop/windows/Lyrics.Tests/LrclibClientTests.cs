using System.Net;
using System.Text;
using Lyrics;
using Xunit;

namespace Lyrics.Tests;

public class LrclibClientTests
{
    private sealed class FakeHandler : HttpMessageHandler
    {
        private readonly Func<HttpRequestMessage, HttpResponseMessage> _respond;
        public readonly List<string> Requests = new();
        public readonly List<string?> UserAgents = new();

        public FakeHandler(Func<HttpRequestMessage, HttpResponseMessage> respond) => _respond = respond;

        protected override Task<HttpResponseMessage> SendAsync(HttpRequestMessage request, CancellationToken ct)
        {
            Requests.Add(request.RequestUri!.PathAndQuery);
            UserAgents.Add(request.Headers.UserAgent.ToString());
            return Task.FromResult(_respond(request));
        }
    }

    private static HttpResponseMessage Json(string json) =>
        new(HttpStatusCode.OK) { Content = new StringContent(json, Encoding.UTF8, "application/json") };

    private static HttpResponseMessage NotFound() => new(HttpStatusCode.NotFound);

    [Fact]
    public async Task RetriesWithoutAlbumThenSearchesWithinThreeSeconds()
    {
        var handler = new FakeHandler(req =>
        {
            var q = req.RequestUri!.PathAndQuery;
            if (q.StartsWith("/api/get")) return NotFound();
            return Json("""
                [{"id":1,"duration":250,"syncedLyrics":"[00:01.00]wrong"},
                 {"id":2,"duration":201.5,"syncedLyrics":"[00:01.00]right one"}]
                """);
        });
        using var client = new LrclibClient(new HttpClient(handler));

        var doc = await client.GetLyricsAsync(new LyricsQuery("The Artist", "A Song", "Album", 200));

        Assert.Equal(3, handler.Requests.Count);
        Assert.Contains("album_name=Album", handler.Requests[0]);
        Assert.Contains("duration=200", handler.Requests[0]);
        Assert.DoesNotContain("album_name", handler.Requests[1]);
        Assert.StartsWith("/api/search?track_name=A%20Song&artist_name=The%20Artist", handler.Requests[2]);
        Assert.All(handler.UserAgents, ua => Assert.Equal(LrclibClient.UserAgent, ua));
        Assert.Equal("right one", doc.Lines[0].Text);
    }

    [Fact]
    public async Task PrefersLyricsfileWhenWordSyncedAndCachesByArtistTitle()
    {
        var handler = new FakeHandler(_ => Json("""
            {"id":7,"duration":60,"hasWordSync":true,"syncedLyrics":"[00:01.00]lrc",
             "lyricsfile":"lines:\n- text: yaml words\n  start_ms: 1000\n  end_ms: 2000\n  words:\n  - text: 'yaml '\n    start_ms: 1000\n    end_ms: 1500\n  - text: words\n    start_ms: 1500\n    end_ms: 2000\n"}
            """));
        using var client = new LrclibClient(new HttpClient(handler));

        var q = new LyricsQuery("A", "T", "B", 60);
        var doc = await client.GetLyricsAsync(q);
        var again = await client.GetLyricsAsync(q with { Album = "Other" });

        Assert.Same(doc, again);
        Assert.Single(handler.Requests);
        Assert.Equal(LyricsSource.WordSynced, doc.Source);
        Assert.Equal("yaml words", doc.Lines[0].Text);
    }

    [Fact]
    public void BuilderPriority()
    {
        Assert.True(LyricsBuilder.FromRecord(new LrclibRecord { Instrumental = true }).IsInstrumental);
        Assert.Equal(LyricsSource.None, LyricsBuilder.FromRecord(new LrclibRecord { PlainLyrics = "just words" }).Source);
        var lrc = LyricsBuilder.FromRecord(new LrclibRecord { HasWordSync = false, Lyricsfile = "lines:\n- text: x\n  start_ms: 0", SyncedLyrics = "[00:02.00]lrc" });
        Assert.Equal("lrc", lrc.Lines[0].Text);
    }

    [Fact]
    public async Task NetworkErrorsAreNotCached()
    {
        var calls = 0;
        var handler = new FakeHandler(_ =>
        {
            calls++;
            return calls == 1 ? new HttpResponseMessage(HttpStatusCode.InternalServerError) : Json("""{"syncedLyrics":"[00:01.00]ok"}""");
        });
        using var client = new LrclibClient(new HttpClient(handler));
        var q = new LyricsQuery("A", "T", null, 100);

        await Assert.ThrowsAsync<HttpRequestException>(() => client.GetLyricsAsync(q));
        var doc = await client.GetLyricsAsync(q);
        Assert.Equal("ok", doc.Lines[0].Text);
    }
}
