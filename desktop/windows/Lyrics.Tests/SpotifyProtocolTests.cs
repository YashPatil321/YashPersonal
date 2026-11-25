using Wave.Spotify;
using Xunit;

namespace Lyrics.Tests;

public class SpotifyProtocolTests
{
    [Fact]
    public void CodeChallengeMatchesRfc7636Example()
    {
        Assert.Equal("E9Melhoa2OwvFrEMTJguCHaoeK1t8URWbuGJSstw-cM",
            SpotifyProtocol.CodeChallenge("dBjftJeZ4CVP-mB92K27uhbUJU1p1r_wW1gFWFOEjXk"));
    }

    [Fact]
    public void VerifierUsesUnreservedCharacters()
    {
        var v = SpotifyProtocol.RandomString(64);
        Assert.Equal(64, v.Length);
        Assert.Matches("^[A-Za-z0-9._~-]+$", v);
        Assert.NotEqual(v, SpotifyProtocol.RandomString(64));
    }

    [Fact]
    public void AuthorizeUrlCarriesPkceAndScopes()
    {
        var url = SpotifyProtocol.AuthorizeUrl("abc", "CHAL", "st8");
        Assert.StartsWith("https://accounts.spotify.com/authorize?client_id=abc&response_type=code", url);
        Assert.Contains("redirect_uri=http%3A%2F%2F127.0.0.1%3A8765%2Fcallback", url);
        Assert.Contains("code_challenge_method=S256&code_challenge=CHAL", url);
        Assert.Contains("scope=user-read-playback-state%20user-modify-playback-state%20user-read-currently-playing%20user-library-read%20user-library-modify", url);
        Assert.EndsWith("state=st8", url);
    }

    [Fact]
    public void ParsesCallbackQuery()
    {
        Assert.Equal(("A%B", "xyz", null), SpotifyProtocol.ParseCallback("/callback?code=A%25B&state=xyz"));
        Assert.Equal((null, "s", "access_denied"), SpotifyProtocol.ParseCallback("/callback?error=access_denied&state=s"));
        Assert.Equal((null, null, null), SpotifyProtocol.ParseCallback("/favicon.ico"));
    }

    [Fact]
    public void ParsesToken()
    {
        var t = SpotifyProtocol.ParseToken("""{"access_token":"AT","token_type":"Bearer","expires_in":3600,"refresh_token":"RT"}""");
        Assert.Equal(new SpotifyToken("AT", 3600, "RT"), t);
        Assert.Null(SpotifyProtocol.ParseToken("""{"error":"invalid_grant"}"""));
        Assert.Null(SpotifyProtocol.ParseToken("""{"access_token":"AT"}""")!.RefreshToken);
    }

    [Fact]
    public void ParsesTrackPlayback()
    {
        const string json = """
            {"progress_ms":42500,"is_playing":true,
             "item":{"id":"t1","name":"Song","duration_ms":214000,
                     "artists":[{"name":"A"},{"name":"B"}],
                     "album":{"name":"LP","images":[{"url":"https://i/big.jpg","width":640},{"url":"https://i/small.jpg"}]}}}
            """;
        var now = new DateTime(2026, 1, 1, 0, 0, 0, DateTimeKind.Utc);
        var p = SpotifyProtocol.ParsePlayer(json, liked: true, now)!;
        Assert.Equal(new SpotifyPlayback("t1", "Song", "A, B", "LP", "https://i/big.jpg", 214, 42.5, true, true, now), p);
        Assert.Equal("t1", SpotifyProtocol.ItemId(json));
    }

    [Fact]
    public void ParsesEpisodeAndEmptyPlayer()
    {
        const string episode = """
            {"progress_ms":1000,"is_playing":false,
             "item":{"id":"e1","name":"Ep","duration_ms":60000,"show":{"name":"Podcast"},"images":[{"url":"https://i/ep.jpg"}]}}
            """;
        var p = SpotifyProtocol.ParsePlayer(episode, false, DateTime.UtcNow)!;
        Assert.Equal("Podcast", p.Artist);
        Assert.Equal("https://i/ep.jpg", p.ArtUrl);
        Assert.False(p.IsPlaying);

        Assert.Null(SpotifyProtocol.ParsePlayer("""{"is_playing":false,"item":null}""", false, DateTime.UtcNow));
        Assert.Null(SpotifyProtocol.ParsePlayer("", false, DateTime.UtcNow));
    }

    [Fact]
    public void ParsesContainsAndProfile()
    {
        Assert.True(SpotifyProtocol.ParseContains("[true]"));
        Assert.False(SpotifyProtocol.ParseContains("[false]"));
        Assert.Null(SpotifyProtocol.ParseContains("[]"));
        Assert.Equal("Yash", SpotifyProtocol.ParseDisplayName("""{"display_name":"Yash","id":"u"}"""));
    }

    [Fact]
    public void FormBodyEncodes()
    {
        Assert.Equal("grant_type=authorization_code&redirect_uri=http%3A%2F%2F127.0.0.1%3A8765%2Fcallback",
            SpotifyProtocol.FormBody(new Dictionary<string, string>
            {
                ["grant_type"] = "authorization_code",
                ["redirect_uri"] = SpotifyProtocol.RedirectUri,
            }));
    }
}
