using System.Diagnostics;
using System.IO;
using System.Windows.Media.Imaging;
using System.Windows.Threading;
using Windows.Media.Control;
using Windows.Storage.Streams;

namespace Shared.NowPlaying;

/// <summary>
/// Watches the Windows media sessions (<c>GlobalSystemMediaTransportControlsSessionManager</c>) every 500 ms.
/// Must be created on the UI thread; events are raised there.
/// </summary>
public sealed class NowPlayingService : IDisposable
{
    public static readonly TimeSpan PollInterval = TimeSpan.FromMilliseconds(500);
    private const int ArtworkRetries = 12;

    private readonly DispatcherTimer _timer;
    private readonly Stopwatch _clockSource = Stopwatch.StartNew();
    private readonly PositionClock _clock = new();
    private GlobalSystemMediaTransportControlsSessionManager? _manager;
    private bool _polling;
    private bool _managerFailed;
    private int _artworkAttempts;
    private BitmapSource? _artwork;
    private string? _artworkTrackId;

    public NowPlayingService()
    {
        _timer = new DispatcherTimer(DispatcherPriority.Background) { Interval = PollInterval };
        _timer.Tick += async (_, _) => await PollAsync();
    }

    /// <summary>The latest snapshot, or null when nothing is in the media flyout.</summary>
    public TrackSnapshot? Current { get; private set; }

    /// <summary>All sessions seen on the last poll.</summary>
    public IReadOnlyList<PlayerSessionInfo> Sessions { get; private set; } = Array.Empty<PlayerSessionInfo>();

    /// <summary>False when the media session API is unavailable (it should exist on Windows 10 1809+).</summary>
    public bool IsAvailable => !_managerFailed;

    /// <summary>Raised after every poll.</summary>
    public event EventHandler? Updated;

    /// <summary>Raised when <see cref="TrackSnapshot.TrackId"/> changes (including to/from nothing).</summary>
    public event EventHandler? TrackChanged;

    /// <summary>Raised when the artwork of the current track arrives or changes.</summary>
    public event EventHandler? ArtworkChanged;

    public void Start()
    {
        _timer.Start();
        _ = PollAsync();
    }

    /// <summary>Seconds on a monotonic clock.</summary>
    public double Now => _clockSource.Elapsed.TotalSeconds;

    /// <summary>The extrapolated playback position (seconds) right now.</summary>
    public double Position => Current is null ? 0 : _clock.PositionAt(Now);

    public bool IsPlaying => Current?.IsPlaying == true;

    /// <summary>
    /// The artwork of the newest track. Read this in <see cref="ArtworkChanged"/> handlers: the event fires before
    /// <see cref="Current"/> is replaced with the new snapshot.
    /// </summary>
    public BitmapSource? Artwork => _artwork;

    private async Task PollAsync()
    {
        if (_polling) return;
        _polling = true;
        try
        {
            await PollCoreAsync();
        }
        catch (Exception ex)
        {
            Debug.WriteLine($"NowPlaying poll failed: {ex.Message}");
        }
        finally
        {
            _polling = false;
        }
    }

    private async Task PollCoreAsync()
    {
        if (_manager is null && !_managerFailed)
        {
            try
            {
                _manager = await GlobalSystemMediaTransportControlsSessionManager.RequestAsync();
            }
            catch (Exception)
            {
                _managerFailed = true;
            }
        }
        if (_manager is null)
        {
            SetSnapshot(null);
            return;
        }

        var sessions = _manager.GetSessions();
        var infos = new List<PlayerSessionInfo>(sessions.Count);
        GlobalSystemMediaTransportControlsSession? chosen = null;
        GlobalSystemMediaTransportControlsSessionMediaProperties? chosenProps = null;
        var chosenPlaying = false;
        var current = _manager.GetCurrentSession();

        foreach (var session in sessions)
        {
            GlobalSystemMediaTransportControlsSessionMediaProperties? props = null;
            try
            {
                props = await session.TryGetMediaPropertiesAsync();
            }
            catch (Exception)
            {
            }
            var playing = session.GetPlaybackInfo()?.PlaybackStatus == GlobalSystemMediaTransportControlsSessionPlaybackStatus.Playing;
            var appId = session.SourceAppUserModelId ?? string.Empty;
            infos.Add(new PlayerSessionInfo(PlayerNames.KindOf(appId), PlayerNames.NameOf(appId), appId,
                props?.Title ?? string.Empty, props?.Artist ?? string.Empty, playing));

            // Prefer a playing session; among equals prefer the one Windows calls current.
            var isCurrent = current is not null && current.SourceAppUserModelId == session.SourceAppUserModelId;
            var better = chosen is null
                         || (playing && !chosenPlaying)
                         || (playing == chosenPlaying && isCurrent);
            if (better && props is not null && !string.IsNullOrWhiteSpace(props.Title))
            {
                chosen = session;
                chosenProps = props;
                chosenPlaying = playing;
            }
        }
        Sessions = infos;

        if (chosen is null || chosenProps is null)
        {
            SetSnapshot(null);
            return;
        }

        var timeline = chosen.GetTimelineProperties();
        var duration = Math.Max(0, (timeline.EndTime - timeline.StartTime).TotalSeconds);
        var reported = Math.Max(0, (timeline.Position - timeline.StartTime).TotalSeconds);

        // Players only update the timeline now and then; LastUpdatedTime says when this position was true.
        if (chosenPlaying)
        {
            var age = (DateTimeOffset.Now - timeline.LastUpdatedTime).TotalSeconds;
            if (age > 0 && age < 600 && (duration <= 0 || reported + age <= duration + 1)) reported += age;
        }

        var appId2 = chosen.SourceAppUserModelId ?? string.Empty;
        var title = chosenProps.Title ?? string.Empty;
        var artist = chosenProps.Artist ?? chosenProps.AlbumArtist ?? string.Empty;
        var album = chosenProps.AlbumTitle ?? string.Empty;
        if (album.Length == 0 && artist.Contains(" — ", StringComparison.Ordinal))
        {
            // Apple Music for Windows reports "Artist — Album" in the artist field.
            var parts = artist.Split(" — ", 2, StringSplitOptions.TrimEntries);
            artist = parts[0];
            album = parts[1];
        }
        var trackId = $"{appId2}|{title}|{artist}|{album}";

        if (_artworkTrackId != trackId)
        {
            _artworkTrackId = trackId;
            _artwork = null;
            _artworkAttempts = 0;
            ArtworkChanged?.Invoke(this, EventArgs.Empty);
        }
        if (_artwork is null && _artworkAttempts < ArtworkRetries && chosenProps.Thumbnail is not null)
        {
            // The thumbnail often arrives a moment after the title, so retry for a few seconds.
            _artworkAttempts++;
            var art = await LoadThumbnailAsync(chosenProps.Thumbnail);
            if (art is not null && _artworkTrackId == trackId)
            {
                _artwork = art;
                ArtworkChanged?.Invoke(this, EventArgs.Empty);
            }
        }

        var snapshot = new TrackSnapshot(
            PlayerNames.KindOf(appId2), PlayerNames.NameOf(appId2), appId2,
            title, artist, album, duration, reported, chosenPlaying, _artwork, trackId);

        var trackChanged = Current?.TrackId != snapshot.TrackId;
        if (trackChanged) _clock.Reset(reported, chosenPlaying, Now);
        else _clock.Report(reported, chosenPlaying, Now);

        Current = snapshot;
        if (trackChanged) TrackChanged?.Invoke(this, EventArgs.Empty);
        Updated?.Invoke(this, EventArgs.Empty);
    }

    private void SetSnapshot(TrackSnapshot? snapshot)
    {
        var changed = Current?.TrackId != snapshot?.TrackId;
        Current = snapshot;
        if (snapshot is null && changed)
        {
            _artwork = null;
            _artworkTrackId = null;
            ArtworkChanged?.Invoke(this, EventArgs.Empty);
        }
        if (changed) TrackChanged?.Invoke(this, EventArgs.Empty);
        Updated?.Invoke(this, EventArgs.Empty);
    }

    private static async Task<BitmapSource?> LoadThumbnailAsync(IRandomAccessStreamReference reference)
    {
        try
        {
            using var stream = await reference.OpenReadAsync();
            if (stream.Size == 0 || stream.Size > 32 * 1024 * 1024) return null;
            var size = (uint)stream.Size;
            using var reader = new DataReader(stream.GetInputStreamAt(0));
            await reader.LoadAsync(size);
            var bytes = new byte[size];
            reader.ReadBytes(bytes);

            using var ms = new MemoryStream(bytes);
            var image = new BitmapImage();
            image.BeginInit();
            image.CacheOption = BitmapCacheOption.OnLoad;
            image.CreateOptions = BitmapCreateOptions.IgnoreColorProfile;
            image.DecodePixelWidth = 300;
            image.StreamSource = ms;
            image.EndInit();
            image.Freeze();
            return image;
        }
        catch (Exception)
        {
            return null;
        }
    }

    public void Dispose() => _timer.Stop();
}
