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

    private readonly SettingsStore<LyraSettings> _store;
    private readonly NowPlayingService _nowPlaying;
    private readonly LrclibClient _client = new();
    private readonly Dictionary<string, LyricsOverlayWindow> _windows = new();
    private readonly Stopwatch _wall = Stopwatch.StartNew();
    private CancellationTokenSource? _fetch;
    private DateTime _lastFailure;
    private Color? _albumHighlight;
    private LyricsLook? _look;

    public LyraController(SettingsStore<LyraSettings> store, NowPlayingService nowPlaying)
    {
        _store = store;
        _nowPlaying = nowPlaying;
        _nowPlaying.TrackChanged += (_, _) => OnTrackChanged();
        _nowPlaying.ArtworkChanged += (_, _) => OnArtworkChanged();
        _nowPlaying.Updated += (_, _) => OnUpdated();
        _store.Changed += (_, _) => Apply();
        Accent.Changed += (_, _) => _look = null;
        SystemEvents.DisplaySettingsChanged += OnDisplaysChanged;
    }

    private LyraSettings S => _store.Value;

    public LyricsDocument Lyrics { get; private set; } = LyricsDocument.Empty;
    public LyricsStatus Status { get; private set; } = LyricsStatus.Idle;
    public string? StatusDetail { get; private set; }

    /// <summary>The user's nudge for this track (resets on track change).</summary>
    public double Offset { get; private set; }

    public NowPlayingService NowPlaying => _nowPlaying;

    /// <summary>Raised when lyrics, status or offset change.</summary>
    public event EventHandler? Changed;

    /// <summary>Lyrics time: extrapolated position + nudge offset + global latency.</summary>
    public double LyricsTime => _nowPlaying.Position + Offset + S.Latency;

    public void Start() => Apply();

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
        _albumHighlight = ArtworkColors.MostVibrant(_nowPlaying.Current?.Artwork);
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
        var wanted = DisplayInfo.Resolve(S.Displays, defaultAll: false);
        if (wanted.Count == 0 && S.Displays is not null && S.Displays.Count > 0)
            wanted = DisplayInfo.Resolve(null, defaultAll: false); // the chosen display was unplugged
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
