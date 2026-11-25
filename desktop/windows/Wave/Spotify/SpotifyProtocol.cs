using System.Security.Cryptography;
using System.Text;
using System.Text.Json;

namespace Wave.Spotify;

/// <summary>A snapshot of <c>GET /me/player</c>.</summary>
public sealed record SpotifyPlayback(
    string Id,
    string Title,
    string Artist,
    string Album,
    string? ArtUrl,
    double Duration,
    double Position,
    bool IsPlaying,
    bool Liked,
    DateTime FetchedAtUtc);

/// <summary>A token endpoint response.</summary>
public sealed record SpotifyToken(string AccessToken, double ExpiresIn, string? RefreshToken);

/// <summary>
/// The platform-neutral parts of the Spotify Authorization Code + PKCE flow and Web API parsing (no client secret).
/// Mirrors desktop/macos/Sources/SharedKit/Spotify.swift. Compiled into the Linux test project.
/// </summary>
public static class SpotifyProtocol
{
    public const string DefaultClientId = "9168fe0d1873402497e1738a923b9a76";
    public const string RedirectUri = "http://127.0.0.1:8765/callback";
    public const int RedirectPort = 8765;
    public const string AuthorizeEndpoint = "https://accounts.spotify.com/authorize";
    public const string TokenEndpoint = "https://accounts.spotify.com/api/token";
    public const string ApiBase = "https://api.spotify.com/v1";

    public static readonly string Scopes = string.Join(' ',
        "user-read-playback-state", "user-modify-playback-state", "user-read-currently-playing",
        "user-library-read", "user-library-modify");

    private const string VerifierAlphabet = "ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789-._~";

    /// <summary>A random string of PKCE "unreserved" characters (RFC 7636 allows 43 to 128).</summary>
    public static string RandomString(int length)
    {
        var chars = new char[length];
        for (var i = 0; i < length; i++) chars[i] = VerifierAlphabet[RandomNumberGenerator.GetInt32(VerifierAlphabet.Length)];
        return new string(chars);
    }

    /// <summary>S256 code challenge: base64url(SHA-256(verifier)) without padding.</summary>
    public static string CodeChallenge(string verifier) => Base64Url(SHA256.HashData(Encoding.ASCII.GetBytes(verifier)));

    public static string Base64Url(byte[] data) =>
        Convert.ToBase64String(data).Replace('+', '-').Replace('/', '_').TrimEnd('=');

    /// <summary>RFC 3986 unreserved characters stay; everything else is percent-encoded (spaces as %20).</summary>
    public static string FormEncode(string s) => Uri.EscapeDataString(s);

    public static string FormBody(IEnumerable<KeyValuePair<string, string>> form) =>
        string.Join("&", form.Select(kv => $"{FormEncode(kv.Key)}={FormEncode(kv.Value)}"));

    public static string AuthorizeUrl(string clientId, string challenge, string state)
    {
        var q = new[]
        {
            ("client_id", clientId),
            ("response_type", "code"),
            ("redirect_uri", RedirectUri),
            ("code_challenge_method", "S256"),
            ("code_challenge", challenge),
            ("scope", Scopes),
            ("state", state),
        };
        return AuthorizeEndpoint + "?" + string.Join("&", q.Select(p => $"{p.Item1}={FormEncode(p.Item2)}"));
    }

    /// <summary>Reads <c>code</c>, <c>state</c> and <c>error</c> from the redirect's query string.</summary>
    public static (string? Code, string? State, string? Error) ParseCallback(string pathAndQuery)
    {
        string? code = null, state = null, error = null;
        var q = pathAndQuery.IndexOf('?');
        if (q < 0) return (null, null, null);
        foreach (var part in pathAndQuery[(q + 1)..].Split('&', StringSplitOptions.RemoveEmptyEntries))
        {
            var eq = part.IndexOf('=');
            var key = Uri.UnescapeDataString(eq < 0 ? part : part[..eq]);
            var value = eq < 0 ? string.Empty : Uri.UnescapeDataString(part[(eq + 1)..].Replace('+', ' '));
            switch (key)
            {
                case "code": code = value; break;
                case "state": state = value; break;
                case "error": error = value; break;
            }
        }
        return (code, state, error);
    }

    public static SpotifyToken? ParseToken(string json)
    {
        using var doc = JsonDocument.Parse(json);
        var root = doc.RootElement;
        if (root.ValueKind != JsonValueKind.Object || !root.TryGetProperty("access_token", out var at) || at.ValueKind != JsonValueKind.String)
            return null;
        var expires = root.TryGetProperty("expires_in", out var e) && e.ValueKind == JsonValueKind.Number ? e.GetDouble() : 3600;
        var refresh = root.TryGetProperty("refresh_token", out var r) && r.ValueKind == JsonValueKind.String ? r.GetString() : null;
        return new SpotifyToken(at.GetString()!, expires, refresh);
    }

    /// <summary>Parses <c>GET /me/player</c>. Null when nothing is loaded (no item or no id). Tracks and episodes.</summary>
    public static SpotifyPlayback? ParsePlayer(string json, bool liked, DateTime fetchedAtUtc)
    {
        if (string.IsNullOrWhiteSpace(json)) return null;
        using var doc = JsonDocument.Parse(json);
        var root = doc.RootElement;
        if (root.ValueKind != JsonValueKind.Object || !root.TryGetProperty("item", out var item) || item.ValueKind != JsonValueKind.Object)
            return null;
        var id = Str(item, "id");
        if (string.IsNullOrEmpty(id)) return null;

        string artist;
        if (item.TryGetProperty("artists", out var artists) && artists.ValueKind == JsonValueKind.Array)
            artist = string.Join(", ", artists.EnumerateArray().Select(a => Str(a, "name")).Where(n => !string.IsNullOrEmpty(n)));
        else if (item.TryGetProperty("show", out var show) && show.ValueKind == JsonValueKind.Object)
            artist = Str(show, "name") ?? string.Empty;
        else
            artist = string.Empty;

        string album = string.Empty;
        string? art = null;
        if (item.TryGetProperty("album", out var alb) && alb.ValueKind == JsonValueKind.Object)
        {
            album = Str(alb, "name") ?? string.Empty;
            art = FirstImage(alb);
        }
        art ??= FirstImage(item);

        return new SpotifyPlayback(
            id!,
            Str(item, "name") ?? string.Empty,
            artist,
            album,
            art,
            Num(item, "duration_ms") / 1000,
            Num(root, "progress_ms") / 1000,
            root.TryGetProperty("is_playing", out var p) && p.ValueKind == JsonValueKind.True,
            liked,
            fetchedAtUtc);
    }

    /// <summary>The id of the item in a <c>/me/player</c> response, without building a playback.</summary>
    public static string? ItemId(string json)
    {
        if (string.IsNullOrWhiteSpace(json)) return null;
        using var doc = JsonDocument.Parse(json);
        return doc.RootElement.ValueKind == JsonValueKind.Object && doc.RootElement.TryGetProperty("item", out var item) &&
               item.ValueKind == JsonValueKind.Object ? Str(item, "id") : null;
    }

    /// <summary>Parses <c>/me/tracks/contains</c> (<c>[true]</c>).</summary>
    public static bool? ParseContains(string json)
    {
        using var doc = JsonDocument.Parse(json);
        var root = doc.RootElement;
        if (root.ValueKind != JsonValueKind.Array || root.GetArrayLength() == 0) return null;
        var first = root[0];
        return first.ValueKind switch { JsonValueKind.True => true, JsonValueKind.False => false, _ => null };
    }

    public static string? ParseDisplayName(string json)
    {
        using var doc = JsonDocument.Parse(json);
        return doc.RootElement.ValueKind == JsonValueKind.Object ? Str(doc.RootElement, "display_name") : null;
    }

    private static string? FirstImage(JsonElement owner)
    {
        if (!owner.TryGetProperty("images", out var images) || images.ValueKind != JsonValueKind.Array) return null;
        foreach (var img in images.EnumerateArray())
        {
            var url = Str(img, "url");
            if (!string.IsNullOrEmpty(url)) return url;
        }
        return null;
    }

    private static string? Str(JsonElement e, string name) =>
        e.ValueKind == JsonValueKind.Object && e.TryGetProperty(name, out var v) && v.ValueKind == JsonValueKind.String ? v.GetString() : null;

    private static double Num(JsonElement e, string name) =>
        e.TryGetProperty(name, out var v) && v.ValueKind == JsonValueKind.Number ? v.GetDouble() : 0;
}
