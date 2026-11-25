using System.Collections.Concurrent;
using System.Globalization;
using System.Net;
using System.Text.Json;
using System.Text.Json.Serialization;

namespace Lyrics;

/// <summary>A record from the LRCLIB API.</summary>
public sealed class LrclibRecord
{
    [JsonPropertyName("id")] public long Id { get; set; }
    [JsonPropertyName("trackName")] public string? TrackName { get; set; }
    [JsonPropertyName("artistName")] public string? ArtistName { get; set; }
    [JsonPropertyName("albumName")] public string? AlbumName { get; set; }
    [JsonPropertyName("duration")] public double? Duration { get; set; }
    [JsonPropertyName("instrumental")] public bool Instrumental { get; set; }
    [JsonPropertyName("plainLyrics")] public string? PlainLyrics { get; set; }
    [JsonPropertyName("syncedLyrics")] public string? SyncedLyrics { get; set; }
    [JsonPropertyName("hasWordSync")] public bool? HasWordSync { get; set; }
    [JsonPropertyName("lyricsfile")] public string? Lyricsfile { get; set; }
}

/// <summary>What to look up.</summary>
public sealed record LyricsQuery(string Artist, string Title, string? Album, double DurationSec)
{
    public string CacheKey => $"{Artist.Trim().ToLowerInvariant()}|{Title.Trim().ToLowerInvariant()}";
}

/// <summary>
/// Client for <c>https://lrclib.net</c>: <c>/api/get</c> with album, then without album, then <c>/api/search</c>
/// taking the first result whose duration is within 3 s. Results are cached by <c>artist|title</c> for the session.
/// </summary>
public sealed class LrclibClient : IDisposable
{
    public const string UserAgent = "Lyra/1.0 (desktop lyrics app)";
    public const double SearchDurationTolerance = 3.0;

    private static readonly JsonSerializerOptions JsonOptions = new()
    {
        PropertyNameCaseInsensitive = true,
        NumberHandling = JsonNumberHandling.AllowReadingFromString,
    };

    private readonly HttpClient _http;
    private readonly bool _ownsHttp;
    private readonly ConcurrentDictionary<string, Task<LyricsDocument>> _cache = new();

    public LrclibClient(HttpClient? http = null, Uri? baseAddress = null)
    {
        _ownsHttp = http is null;
        _http = http ?? new HttpClient { Timeout = TimeSpan.FromSeconds(12) };
        _http.BaseAddress ??= baseAddress ?? new Uri("https://lrclib.net/");
        if (!_http.DefaultRequestHeaders.UserAgent.Any())
            _http.DefaultRequestHeaders.TryAddWithoutValidation("User-Agent", UserAgent);
    }

    /// <summary>Fetches and parses lyrics, using the session cache. Failed lookups (network errors) are not cached.</summary>
    public Task<LyricsDocument> GetLyricsAsync(LyricsQuery query, CancellationToken ct = default)
    {
        var task = _cache.GetOrAdd(query.CacheKey, _ => FetchAndParseAsync(query, CancellationToken.None));
        if (task.IsFaulted || task.IsCanceled)
        {
            // Failed synchronously before the cache held it: drop it so the next call retries.
            _cache.TryRemove(new KeyValuePair<string, Task<LyricsDocument>>(query.CacheKey, task));
        }
        return ct.CanBeCanceled ? task.WaitAsync(ct) : task;
    }

    /// <summary>Clears the session cache.</summary>
    public void ClearCache() => _cache.Clear();

    private async Task<LyricsDocument> FetchAndParseAsync(LyricsQuery query, CancellationToken ct)
    {
        try
        {
            var record = await FindAsync(query, ct).ConfigureAwait(false);
            return record is null ? LyricsDocument.Empty : LyricsBuilder.FromRecord(record);
        }
        catch
        {
            _cache.TryRemove(query.CacheKey, out _);
            throw;
        }
    }

    /// <summary>The lookup chain from the spec. Returns null when nothing matched.</summary>
    public async Task<LrclibRecord?> FindAsync(LyricsQuery q, CancellationToken ct = default)
    {
        var duration = ((int)Math.Round(q.DurationSec)).ToString(CultureInfo.InvariantCulture);

        if (!string.IsNullOrWhiteSpace(q.Album))
        {
            var withAlbum = await GetAsync(
                $"api/get?artist_name={Esc(q.Artist)}&track_name={Esc(q.Title)}&album_name={Esc(q.Album!)}&duration={duration}", ct)
                .ConfigureAwait(false);
            if (withAlbum is not null) return withAlbum;
        }

        var withoutAlbum = await GetAsync(
            $"api/get?artist_name={Esc(q.Artist)}&track_name={Esc(q.Title)}&duration={duration}", ct).ConfigureAwait(false);
        if (withoutAlbum is not null) return withoutAlbum;

        using var resp = await _http.GetAsync($"api/search?track_name={Esc(q.Title)}&artist_name={Esc(q.Artist)}", ct)
                                    .ConfigureAwait(false);
        if (resp.StatusCode == HttpStatusCode.NotFound) return null;
        resp.EnsureSuccessStatusCode();
        await using var stream = await resp.Content.ReadAsStreamAsync(ct).ConfigureAwait(false);
        var results = await JsonSerializer.DeserializeAsync<List<LrclibRecord>>(stream, JsonOptions, ct).ConfigureAwait(false);
        return results?.FirstOrDefault(r =>
            r.Duration is { } d && (q.DurationSec <= 0 || Math.Abs(d - q.DurationSec) <= SearchDurationTolerance));
    }

    /// <summary>GET a single record; null on 404 (or a 4xx that means "no match").</summary>
    private async Task<LrclibRecord?> GetAsync(string url, CancellationToken ct)
    {
        using var resp = await _http.GetAsync(url, ct).ConfigureAwait(false);
        if (resp.StatusCode is HttpStatusCode.NotFound or HttpStatusCode.BadRequest) return null;
        resp.EnsureSuccessStatusCode();
        await using var stream = await resp.Content.ReadAsStreamAsync(ct).ConfigureAwait(false);
        return await JsonSerializer.DeserializeAsync<LrclibRecord>(stream, JsonOptions, ct).ConfigureAwait(false);
    }

    private static string Esc(string s) => Uri.EscapeDataString(s.Trim());

    public void Dispose()
    {
        if (_ownsHttp) _http.Dispose();
    }
}

/// <summary>Turns an LRCLIB record into a <see cref="LyricsDocument"/> using the spec's priority order.</summary>
public static class LyricsBuilder
{
    public static LyricsDocument FromRecord(LrclibRecord r)
    {
        if (r.Instrumental) return LyricsDocument.Instrumental;

        // 1. lyricsfile when hasWordSync
        if (r.HasWordSync == true && !string.IsNullOrWhiteSpace(r.Lyricsfile))
        {
            try
            {
                var doc = LyricsfileParser.Parse(r.Lyricsfile!);
                if (doc.HasSyncedLyrics) return doc;
            }
            catch (Exception)
            {
                // fall through to LRC
            }
        }

        // 2. syncedLyrics (LRC)
        if (!string.IsNullOrWhiteSpace(r.SyncedLyrics))
        {
            var doc = LrcParser.Parse(r.SyncedLyrics!);
            if (doc.HasSyncedLyrics) return doc;
        }

        // 3. plain / none
        return LyricsDocument.Empty;
    }
}
