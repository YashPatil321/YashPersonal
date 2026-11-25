using System.Diagnostics;
using System.Windows;
using System.Windows.Media;
using Lyra.Styles;
using Lyrics;
using Microsoft.Win32;
using Shared.Imaging;
using Shared.NowPlaying;
using Shared.Overlay;
using Shared.Settings;
using Shared.Ui;

namespace Lyra;

public enum LyricsStatus
{
    Idle,
    Searching,
    Found,
    NotFound,
    Instrumental,
    Error,
}

/// <summary>
/// Ties now-playing to lyrics: fetches from LRCLIB on track change, keeps the timing offset, decides when the overlay
/// shows, holds the keep-awake request, and builds frames for the overlay windows.
/// </summary>
public sealed class LyraController : IDisposable
{
    public const double NudgeSeconds = 0.25;
    private static readonly TimeSpan RetryAfter = TimeSpan.FromSeconds(30);

    private LyraSettings _settings = new();
    private readonly PositionClock _spotifyClock = new();
    private string? _spotifyTitle;
    private readonly NowPlayingService _nowPlaying;
    private readonly LrclibClient _client = new();
    private readonly Dictionary<string, LyricsOverlayWindow> _windows = new();
    private readonly Stopwatch _wall = Stopwatch.StartNew();
    private CancellationTokenSource? _fetch;
    private DateTime _lastFailure;
    private Color? _albumHighlight;
    private LyricsLook? _look;

    public LyraController(NowPlayingService nowPlaying)
    {
        _nowPlaying = nowPlaying;
        _nowPlaying.TrackChanged += (_, _) => OnTrackChanged();
        _nowPlaying.ArtworkChanged += (_, _) => OnArtworkChanged();
        _nowPlaying.Updated += (_, _) => OnUpdated();
        Accent.Changed += (_, _) => _look = null;
        SystemEvents.DisplaySettingsChanged += OnDisplaysChanged;
    }

    private LyraSettings S => _settings;

    /// <summary>Applies new settings (style, look, placement, keep awake).</summary>
    public void Apply(LyraSettings settings)
    {
        _settings = settings;
        Apply();
    }

    public LyricsDocument Lyrics { get; private set; } = LyricsDocument.Empty;
    public LyricsStatus Status { get; private set; } = LyricsStatus.Idle;
    public string? StatusDetail { get; private set; }

    /// <summary>The user's nudge for this track (resets on track change).</summary>
    public double Offset { get; private set; }

    public NowPlayingService NowPlaying => _nowPlaying;

    /// <summary>Raised when lyrics, status or offset change.</summary>
    public event EventHandler? Changed;

    /// <summary>Lyrics time: extrapolated position + nudge offset + global latency.</summary>
    public double LyricsTime => PlaybackPosition + Offset + S.Latency;

    /// <summary>
    /// The playback position: Spotify's when it reports the same song as the media session (it is exact), else the
    /// media session's. Both are extrapolated between reports with the snap/ease clock.
    /// </summary>
    public double PlaybackPosition =>
        _spotifyTitle is not null && _nowPlaying.Current is { } t &&
        string.Equals(_spotifyTitle, t.Title, StringComparison.OrdinalIgnoreCase)
            ? _spotifyClock.PositionAt(_nowPlaying.Now)
            : _nowPlaying.Position;

    /// <summary>
    /// Feeds Spotify Web API timing (null when not connected or nothing is playing there). <paramref name="position"/>
    /// is the reported progress plus the time since it was fetched.
    /// </summary>
    public void ReportSpotify(string? title, double position, bool isPlaying)
    {
        if (title is null)
        {
            _spotifyTitle = null;
            return;
        }
        var now = _nowPlaying.Now;
        if (!string.Equals(title, _spotifyTitle, StringComparison.Ordinal)) _spotifyClock.Reset(position, isPlaying, now);
        else _spotifyClock.Report(position, isPlaying, now);
        _spotifyTitle = title;
    }

    /// <summary>A short label for the dashboard's status line.</summary>
    public string StatusLabel => Status switch
    {
        LyricsStatus.Searching => "Looking for lyrics…",
        LyricsStatus.Found => Lyrics.Source == LyricsSource.WordSynced ? "Found (word by word)" : "Found (line by line)",
        LyricsStatus.NotFound => "No synced lyrics for this song",
        LyricsStatus.Instrumental => "Instrumental: no lyrics",
        LyricsStatus.Error => StatusDetail ?? "Could not reach lrclib.net",
        _ => "Waiting for a song",
    };

    public void Start() => Apply();

    /// <summary>Adds to this song's offset. Positive values light words earlier. Resets on track change.</summary>
    public void Nudge(double seconds)
    {
        Offset = Math.Round(Offset + seconds, 2);
        Changed?.Invoke(this, EventArgs.Empty);
    }

    /// <summary>The resolved look for the current settings (shared by overlay and preview).</summary>
    public LyricsLook Look => _look ??= BuildLook();

    private LyricsLook BuildLook()
    {
        var accent = Accent.Current;
        var highlight = S.MatchAlbumArt && _albumHighlight is { } album
            ? album
            : string.IsNullOrWhiteSpace(S.HighlightColor) ? accent : ColorPicker.ParseOr(S.HighlightColor, accent);
        return new LyricsLook
        {
            Family = LyricsLook.FamilyFor(S.Font),
            Stretch = LyricsLook.StretchFor(S.Font),
            Mono = LyricsLook.FamilyFor(LyricFont.Mono),
            Scale = S.Size,
            Sung = ColorPicker.ParseOr(S.TextColor, Colors.White),
            Highlight = highlight,
            Dim = ColorPicker.ParseOr(S.DimColor, Color.FromArgb(0x73, 0xFF, 0xFF, 0xFF)),
            Shadow = S.Shadow,
        };
    }

    public double Anchor => S.Placement switch
    {
        Placement.Top => 0,
        Placement.Centre => 0.5,
        _ => 1,
    };

    private LyricsFrame? BuildFrame()
    {
        if (!Lyrics.HasSyncedLyrics) return null;
        return new LyricsFrame
        {
            Document = Lyrics,
            Time = LyricsTime,
            Look = Look,
            Anchor = Anchor,
            WallTime = _wall.Elapsed.TotalSeconds,
        };
    }

    /// <summary>A frame of the built-in demo song, looping, for the settings preview.</summary>
    public LyricsFrame DemoFrame(double anchor = 0.5) => new()
    {
        Document = DemoLyrics.Document,
        Time = _wall.Elapsed.TotalSeconds % DemoLyrics.LoopSeconds,
        Look = Look,
        Anchor = anchor,
        WallTime = _wall.Elapsed.TotalSeconds,
    };

    /// <summary>Re-reads settings: windows, style, look.</summary>
    public void Apply()
    {
        S.Normalize();
        _look = null;
        SyncWindows();
        foreach (var w in _windows.Values) w.Canvas.StyleKind = S.Style;
        UpdateVisibility();
    }

    private void OnTrackChanged()
    {
        Offset = 0;
        _fetch?.Cancel();
        _fetch = null;
        Lyrics = LyricsDocument.Empty;
        StatusDetail = null;

        var track = _nowPlaying.Current;
        if (track is null || string.IsNullOrWhiteSpace(track.Title))
        {
            Status = LyricsStatus.Idle;
            Changed?.Invoke(this, EventArgs.Empty);
            UpdateVisibility();
            return;
        }
        Fetch(track);
    }

    private async void Fetch(TrackSnapshot track)
    {
        var cts = new CancellationTokenSource();
        _fetch = cts;
        Status = LyricsStatus.Searching;
        Changed?.Invoke(this, EventArgs.Empty);
        UpdateVisibility();

        try
        {
            var query = new LyricsQuery(track.Artist, track.Title, track.Album, track.DurationSec);
            var doc = await _client.GetLyricsAsync(query, cts.Token);
            if (cts.IsCancellationRequested || _nowPlaying.Current?.TrackId != track.TrackId) return;
            Lyrics = doc;
            Status = doc.IsInstrumental ? LyricsStatus.Instrumental : doc.HasSyncedLyrics ? LyricsStatus.Found : LyricsStatus.NotFound;
            StatusDetail = null;
        }
        catch (OperationCanceledException) when (cts.IsCancellationRequested)
        {
            return;
        }
        catch (Exception ex)
        {
            if (cts.IsCancellationRequested) return;
            Status = LyricsStatus.Error;
            StatusDetail = ex is System.Net.Http.HttpRequestException or TaskCanceledException ? "Could not reach lrclib.net" : ex.Message;
            _lastFailure = DateTime.UtcNow;
        }
        Changed?.Invoke(this, EventArgs.Empty);
        UpdateVisibility();
    }

    private void OnArtworkChanged()
    {
        _albumHighlight = ArtworkColors.MostVibrant(_nowPlaying.Artwork);
        _look = null;
    }

    private void OnUpdated()
    {
        if (Status == LyricsStatus.Error && DateTime.UtcNow - _lastFailure > RetryAfter && _nowPlaying.Current is { } t)
            Fetch(t);
        UpdateVisibility();
    }

    /// <summary>Shown when lyrics are on, music is playing and synced lyrics exist. Also holds keep-awake.</summary>
    private void UpdateVisibility()
    {
        var playing = _nowPlaying.IsPlaying;
        KeepAwake.Set(S.KeepAwake && playing);
        var show = S.ShowLyrics && playing && Lyrics.HasSyncedLyrics;
        foreach (var w in _windows.Values) w.SetShown(show);
    }

    private void OnDisplaysChanged(object? sender, EventArgs e) =>
        Application.Current?.Dispatcher.BeginInvoke(new Action(Apply));

    private void SyncWindows()
    {
        var wanted = DisplayInfo.All();
        var ids = wanted.Select(d => d.Id).ToHashSet();

        foreach (var id in _windows.Keys.Where(id => !ids.Contains(id)).ToList())
        {
            _windows[id].Close();
            _windows.Remove(id);
        }
        foreach (var display in wanted)
        {
            if (!_windows.TryGetValue(display.Id, out var window))
            {
                window = new LyricsOverlayWindow(display, BuildFrame);
                window.Canvas.StyleKind = S.Style;
                _windows[display.Id] = window;
            }
            window.Place(display, S.Placement, S.Size);
        }
    }

    public void Dispose()
    {
        SystemEvents.DisplaySettingsChanged -= OnDisplaysChanged;
        _fetch?.Cancel();
        foreach (var w in _windows.Values) w.Close();
        _windows.Clear();
        KeepAwake.Set(false);
        _client.Dispose();
    }
}
