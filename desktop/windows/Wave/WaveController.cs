using System.Globalization;
using System.IO;
using System.Reflection;
using System.Text;
using System.Text.Json.Nodes;
using System.Windows;
using System.Windows.Media;
using System.Windows.Media.Imaging;
using Microsoft.Win32;
using Shared.Audio;
using Shared.Imaging;
using Shared.NowPlaying;
using Shared.Overlay;
using Shared.Settings;
using Shared.Tray;
using Wave.Desktop;
using Wave.Panels;
using Wave.Spotify;
using Forms = System.Windows.Forms;
using Halo;
using Lyra;

namespace Wave;

/// <summary>
/// Wave: a music visualizer and clock on the desktop, a full-screen player, Spotify control, the screen glow (Halo) and
/// the lyrics overlay (Lyra), around the shared web engine in desktop/visuals. Mirrors desktop/macos/Sources/Wave/main.swift.
/// One now-playing service and one WASAPI capture feed everything.
/// </summary>
public sealed class WaveController : IDisposable
{
    private const double CoverCheckSeconds = 0.25;

    private readonly WaveSettings _settings = new();
    private readonly LayoutStore _layout = new();
    private readonly NowPlayingService _nowPlaying = new();
    private readonly AudioAnalyzer _audio = new();
    private readonly SpotifyClient _spotify;
    private readonly MessageWindow _messages = new();
    private readonly ForegroundWatcher _foreground = new();
    private readonly WindowDragger _dragger = new();
    private readonly System.Windows.Threading.DispatcherTimer _tick = new() { Interval = TimeSpan.FromSeconds(1) };
    private readonly string _visualsDir;
    private readonly string _version;
    private readonly float[] _bins = new float[SpectrumAnalyzer.BinCount];
    private readonly float[] _wave = new float[SpectrumAnalyzer.WaveCount];
    private readonly Dictionary<PanelKind, ArrangeOverlay> _overlays = new();

    private WebPanel? _widget, _clock, _dashboard, _fullscreen;
    private GlowController? _glow;
    private LyraController? _lyrics;
    private TrayIcon? _tray;
    private Forms.ToolStripMenuItem? _headerItem, _widgetsItem, _arrangeItem, _likeItem;
    private bool _widgetsHidden;
    private bool _editing;
    private bool _rendering;
    private double _lastFrame;
    private double _lastBeatSent = double.NegativeInfinity;
    private double _lastCoverCheck = double.NegativeInfinity;
    private readonly Dictionary<PanelKind, bool> _covered = new();
    private string _lastTrackKey = string.Empty;
    private (string Id, string Url) _cachedArt = (string.Empty, string.Empty);
    private string[] _colors = Array.Empty<string>();
    private IReadOnlyList<string> _hotKeyFailures = Array.Empty<string>();

    public WaveController()
    {
        _visualsDir = FindVisualsDir();
        _version = Assembly.GetExecutingAssembly().GetCustomAttribute<AssemblyInformationalVersionAttribute>()?.InformationalVersion?.Split('+')[0] ?? "dev";
        _spotify = new SpotifyClient(_settings.String("spotifyClientId", string.Empty));
    }

    public void Start()
    {
        _spotify.StartPolling();
        _spotify.Changed += (_, _) => { ReportSpotifyTiming(); PushTrack(force: false); PushStatus(); };
        _nowPlaying.Updated += (_, _) => PushTrack(force: false);
        _nowPlaying.ArtworkChanged += (_, _) => OnArtworkChanged();
        _nowPlaying.Start();
        _audio.Start();

        _glow = new GlowController(_nowPlaying, _audio);
        _lyrics = new LyraController(_nowPlaying);
        _lyrics.Changed += (_, _) => PushStatus();
        ApplyFeatures(glow: true, lyrics: true);

        BuildTray();
        _messages.HotKey += id =>
        {
            if (id == MessageWindow.HotKeyFullscreen) ToggleFullscreen();
            else if (id == MessageWindow.HotKeyWidgets) ToggleWidgets();
        };
        _messages.ExplorerRestarted += () => Application.Current.Dispatcher.BeginInvoke(new Action(ApplyWidgets),
            System.Windows.Threading.DispatcherPriority.Background);
        _hotKeyFailures = _messages.RegisterHotKeys();
        SystemEvents.DisplaySettingsChanged += OnDisplaysChanged;
        // Show Desktop (Win+D): keep desktop-placed widgets visible above the desktop until another app comes back.
        _foreground.DesktopForegroundChanged += desktop =>
        {
            foreach (var p in new[] { _widget, _clock })
                if (p?.Window is DesktopWidgetWindow w) w.SetDesktopRaised(desktop);
            _lastCoverCheck = double.NegativeInfinity;
        };

        ApplyWidgets();
        StartFrames();
        _tick.Tick += (_, _) => { ReportSpotifyTiming(); PushTrack(force: true); PushStatus(); };
        _tick.Start();

        if (!_layout.Launched)
        {
            _layout.Launched = true;
            ShowDashboard();
        }
    }

    private IEnumerable<WebPanel> Panels => new[] { _widget, _clock, _dashboard, _fullscreen }.OfType<WebPanel>();

    private static string FindVisualsDir()
    {
        var beside = Path.Combine(AppContext.BaseDirectory, "visuals");
        if (File.Exists(Path.Combine(beside, "index.html"))) return beside;
        // Development: walk up to desktop/visuals in the repository.
        for (var dir = new DirectoryInfo(AppContext.BaseDirectory); dir is not null; dir = dir.Parent)
        {
            var candidate = Path.Combine(dir.FullName, "visuals");
            if (File.Exists(Path.Combine(candidate, "index.html")) && File.Exists(Path.Combine(candidate, "core.js"))) return candidate;
        }
        return beside;
    }

    private WebPanel MakePanel(PanelKind kind, Window window)
    {
        var panel = new WebPanel(kind, window, _visualsDir);
        panel.Message += Handle;
        return panel;
    }

    // ------------------------------------------------------------------ desktop widgets

    private Win32.RECT DefaultFrame(PanelKind kind)
    {
        var primary = DisplayInfo.All().FirstOrDefault();
        var wa = primary?.WorkArea ?? new Int32Rect(0, 0, 1920, 1040);
        var s = primary?.Scale ?? 1.0;
        int P(double dip) => (int)Math.Round(dip * s);
        if (kind == PanelKind.Clock)
            return Rect(wa.X + P(40), wa.Y + P(40), P(520), P(220));
        return Rect(wa.X + wa.Width - P(640), wa.Y + P(40), P(600), P(320));
    }

    private static Win32.RECT Rect(int x, int y, int w, int h) => new() { Left = x, Top = y, Right = x + w, Bottom = y + h };

    private Win32.RECT SavedFrame(PanelKind kind)
    {
        if (_layout.Get(KindKey(kind)) is { } r && r.Width > 50 && r.Height > 30)
        {
            var visible = DisplayInfo.All().Any(d =>
                r.Left < d.Bounds.X + d.Bounds.Width && r.Right > d.Bounds.X && r.Top < d.Bounds.Y + d.Bounds.Height && r.Bottom > d.Bounds.Y);
            if (visible) return r;
        }
        return DefaultFrame(kind);
    }

    private static string KindKey(PanelKind kind) => kind == PanelKind.Clock ? "clock" : "widget";

    /// <summary>
    /// The widget's placement: <c>desktop</c> (default: behind all windows, clickable), <c>wallpaper</c> (behind the
    /// icons, click-through) or <c>top</c> (always on top, clickable). The retired <c>normal</c> means desktop.
    /// </summary>
    private string PlacementOf(PanelKind kind) =>
        _settings.String(kind == PanelKind.Clock ? "clockPlacement" : "widgetPlacement", "desktop") switch
        {
            "wallpaper" => "wallpaper",
            "top" => "top",
            _ => "desktop",
        };

    private WebPanel CreateDesktopPanel(PanelKind kind)
    {
        var window = new DesktopWidgetWindow(kind == PanelKind.Clock ? "Wave clock" : "Wave visualizer");
        var panel = MakePanel(kind, window);
        window.Closed += (_, _) =>
        {
            if (!window.ClosedExternally) return;
            // Explorer destroyed the WorkerW we were parented to: forget the panel; it is recreated on re-attach.
            panel.Dispose();
            if (kind == PanelKind.Clock && _clock == panel) _clock = null;
            if (kind == PanelKind.Widget && _widget == panel) _widget = null;
            Application.Current?.Dispatcher.BeginInvoke(new Action(ApplyWidgets), System.Windows.Threading.DispatcherPriority.Background);
        };
        return panel;
    }

    /// <summary>Create, show, hide or re-place the widgets to match the settings.</summary>
    private void ApplyWidgets()
    {
        var wantWidget = _settings.Bool("widgetEnabled", true) && !_widgetsHidden;
        var wantClock = _settings.Bool("clockEnabled", true) && !_widgetsHidden;
        if (wantWidget && _widget is null) { _widget = CreateDesktopPanel(PanelKind.Widget); PushAll(_widget); }
        if (wantClock && _clock is null) { _clock = CreateDesktopPanel(PanelKind.Clock); PushAll(_clock); }

        IntPtr host = IntPtr.Zero;
        foreach (var (panel, want, placement) in new[]
                 {
                     (_widget, wantWidget, PlacementOf(PanelKind.Widget)),
                     (_clock, wantClock, PlacementOf(PanelKind.Clock)),
                 })
        {
            if (panel?.Window is not DesktopWidgetWindow w) continue;
            if (!want)
            {
                w.Hide();
                continue;
            }
            if (!w.IsVisible) w.Show();
            // First placement uses the saved frame; afterwards the window keeps wherever it is (arranging moves it).
            var frame = w.Placed ? CurrentOrSaved(w, panel.Kind) : SavedFrame(panel.Kind);
            w.Placed = true;

            if (_editing)
            {
                w.ClickThrough = false;
                w.PlaceTopLevel(frame, Win32.HWND_TOPMOST);
                continue;
            }
            // Only the wallpaper placement is click-through; desktop and top take clicks (buttons, drag to move).
            w.ClickThrough = placement == "wallpaper";
            switch (placement)
            {
                case "top":
                    w.PlaceTopLevel(frame, Win32.HWND_TOPMOST);
                    break;
                case "wallpaper":
                    if (host == IntPtr.Zero) host = WallpaperHost.Find();
                    if (host != IntPtr.Zero)
                    {
                        WallpaperHost.Attach(w.Handle, host, frame);
                        w.Remember(frame);
                    }
                    else
                    {
                        w.PlaceOnDesktop(frame);
                    }
                    break;
                default:
                    w.PlaceOnDesktop(frame);
                    break;
            }
        }
    }

    private Win32.RECT CurrentOrSaved(DesktopWidgetWindow w, PanelKind kind)
    {
        var r = w.ScreenRect;
        return r.Width > 50 && r.Height > 30 ? r : SavedFrame(kind);
    }

    private void SetEditing(bool on)
    {
        if (on == _editing) return;
        _editing = on;
        ApplyWidgets();
        if (on)
        {
            foreach (var panel in new[] { _widget, _clock })
            {
                if (panel?.Window is not DesktopWidgetWindow { IsVisible: true } w) continue;
                var overlay = new ArrangeOverlay(w.Handle, w.ScreenRect, panel.Kind == PanelKind.Clock ? "Clock" : "Visualizer");
                overlay.Moved += r => w.PlaceTopLevel(r, Win32.HWND_TOPMOST);
                overlay.Done += () => SetEditing(false);
                _overlays[panel.Kind] = overlay;
                overlay.Show();
                overlay.Activate();
            }
        }
        else
        {
            foreach (var panel in new[] { _widget, _clock })
            {
                if (panel?.Window is DesktopWidgetWindow w && w.Handle != IntPtr.Zero && w.IsVisible)
                    _layout.Set(KindKey(panel.Kind), w.ScreenRect);
            }
            foreach (var o in _overlays.Values) o.Close();
            _overlays.Clear();
            ApplyWidgets();
        }
    }

    public void ToggleWidgets()
    {
        _widgetsHidden = !_widgetsHidden;
        if (_widgetsHidden && _editing) SetEditing(false);
        ApplyWidgets();
    }

    private void OnDisplaysChanged(object? sender, EventArgs e) =>
        Application.Current?.Dispatcher.BeginInvoke(new Action(ApplyWidgets), System.Windows.Threading.DispatcherPriority.Background);

    // ------------------------------------------------------------------ dashboard and full screen

    public void ShowDashboard()
    {
        if (_dashboard is null)
        {
            var w = new DashboardWindow();
            if (AppIcon() is { } icon) w.Icon = icon;
            var panel = MakePanel(PanelKind.Dashboard, w);
            w.Closed += (_, _) =>
            {
                panel.Dispose();
                if (_dashboard == panel) _dashboard = null;
            };
            _dashboard = panel;
            PushAll(panel);
            w.Show();
        }
        var win = _dashboard.Window;
        if (win.WindowState == WindowState.Minimized) win.WindowState = WindowState.Normal;
        win.Activate();
    }

    public void ToggleFullscreen()
    {
        if (_fullscreen is { } fs)
        {
            _fullscreen = null;
            fs.Window.Close();
            fs.Dispose();
            return;
        }
        var w = new FullscreenWindow(FullscreenWindow.MonitorUnderCursor());
        var panel = MakePanel(PanelKind.Fullscreen, w);
        w.Closed += (_, _) =>
        {
            panel.Dispose();
            if (_fullscreen == panel) _fullscreen = null;
        };
        _fullscreen = panel;
        PushAll(panel);
        w.Show();
        Win32.SetForegroundWindow(new System.Windows.Interop.WindowInteropHelper(w).Handle);
        w.Activate();
        panel.WebView.Focus();
        panel.WebView.CoreWebView2InitializationCompleted += (_, _) => panel.WebView.Focus();
    }

    private static ImageSource? AppIcon()
    {
        try
        {
            var path = Environment.ProcessPath;
            if (path is null) return null;
            using var icon = System.Drawing.Icon.ExtractAssociatedIcon(path);
            if (icon is null) return null;
            return System.Windows.Interop.Imaging.CreateBitmapSourceFromHIcon(icon.Handle, Int32Rect.Empty, BitmapSizeOptions.FromEmptyOptions());
        }
        catch (Exception)
        {
            return null;
        }
    }

    // ------------------------------------------------------------------ messages from the page

    private void Handle(WebPanel panel, JsonObject msg)
    {
        var cmd = msg["cmd"] is JsonValue c && c.TryGetValue<string>(out var s) ? s : null;
        switch (cmd)
        {
            case "ready":
                PushAll(panel);
                break;
            case "set":
                if (msg["key"] is not JsonValue k || !k.TryGetValue<string>(out var key)) return;
                var value = msg["value"]?.DeepClone();
                _settings[key] = value;
                foreach (var p in Panels.Where(p => p != panel).ToList())
                    p.Call("config", new JsonObject { [key] = value?.DeepClone() });
                ApplySetting(key);
                break;
            case "lyricsNudge":
                var delta = msg["delta"] is JsonValue dv && double.TryParse(dv.ToJsonString(), NumberStyles.Float, CultureInfo.InvariantCulture, out var dd) ? dd : 0;
                if (delta != 0 && double.IsFinite(delta)) _lyrics?.Nudge(Math.Clamp(delta, -5, 5)); // + = earlier
                PushStatus();
                break;
            case "playpause": Media(NowPlayingService.MediaCommand.PlayPause); break;
            case "next": Media(NowPlayingService.MediaCommand.Next); break;
            case "previous": Media(NowPlayingService.MediaCommand.Previous); break;
            case "like": ToggleLike(); break;
            case "openFullscreen": if (_fullscreen is null) ToggleFullscreen(); break;
            case "closeFullscreen": if (_fullscreen is not null) ToggleFullscreen(); break;
            case "editLayout": SetEditing(!_editing); break;
            case "dragStart" or "resizeStart":
                StartDrag(panel, resize: cmd == "resizeStart");
                break;
            case "spotifyConnect":
                _spotify.ClientId = _settings.String("spotifyClientId", string.Empty);
                _spotify.Connect();
                break;
            case "spotifyDisconnect": _spotify.Disconnect(); break;
            case "resetSettings":
                _settings.Clear();
                foreach (var p in Panels.ToList()) p.Reload();
                ApplyWidgets();
                ApplyFeatures(glow: true, lyrics: true);
                break;
            case "quit":
                Application.Current.Dispatcher.BeginInvoke(new Action(Quit));
                break;
        }
    }

    /// <summary>Re-maps the settings dictionary onto the glow and lyrics features.</summary>
    private void ApplyFeatures(bool glow, bool lyrics)
    {
        if (glow) _glow?.Apply(HaloSettings.FromWave(_settings.Values));
        if (lyrics) _lyrics?.Apply(LyraSettings.FromWave(_settings.Values));
    }

    /// <summary>Gives the lyrics clock Spotify's exact position when Spotify is connected and playing something.</summary>
    private void ReportSpotifyTiming()
    {
        if (_lyrics is null) return;
        if (_spotify.IsConnected && _spotify.Playback is { } p)
        {
            var age = Math.Max(0, (DateTime.UtcNow - p.FetchedAtUtc).TotalSeconds);
            _lyrics.ReportSpotify(p.Title, p.Position + (p.IsPlaying ? age : 0), p.IsPlaying);
        }
        else
        {
            _lyrics.ReportSpotify(null, 0, false);
        }
    }

    /// <summary>Changes one setting from native UI (the tray): persist, tell every page, react.</summary>
    private void SetSetting(string key, JsonNode? value)
    {
        _settings[key] = value;
        foreach (var p in Panels.ToList()) p.Call("config", new JsonObject { [key] = value?.DeepClone() });
        ApplySetting(key);
    }

    /// <summary>The page saw a mouse-down on the widget (or its resize grip): move or resize until the button is released.</summary>
    private void StartDrag(WebPanel panel, bool resize)
    {
        if (_editing || panel.Kind is not (PanelKind.Widget or PanelKind.Clock)) return;
        if (panel.Window is not DesktopWidgetWindow w || w.Handle == IntPtr.Zero || !w.IsVisible) return;
        if (PlacementOf(panel.Kind) == "wallpaper" || _settings.Bool("widgetLocked", false)) return;

        var scale = DisplayInfo.ScaleFor(w.ScreenRect.Left + w.ScreenRect.Width / 2, w.ScreenRect.Top + w.ScreenRect.Height / 2);
        var (minW, minH) = panel.Kind == PanelKind.Clock ? (200, 90) : (240, 120);
        _dragger.Start(w, resize, (int)Math.Round(minW * scale), (int)Math.Round(minH * scale),
            done => _layout.Set(KindKey(panel.Kind), done.ScreenRect));
    }

    private void ApplySetting(string key)
    {
        if (key.StartsWith("glow", StringComparison.Ordinal)) ApplyFeatures(glow: true, lyrics: false);
        else if (key.StartsWith("lyrics", StringComparison.Ordinal)) ApplyFeatures(glow: false, lyrics: true);
        switch (key)
        {
            case "widgetEnabled" or "clockEnabled" or "widgetPlacement" or "clockPlacement":
                ApplyWidgets();
                // Re-evaluate coverage now and resend setPaused, so a page paused under the old placement wakes up.
                _covered.Clear();
                _lastCoverCheck = double.NegativeInfinity;
                foreach (var p in new[] { _widget, _clock }) if (p is not null) p.LastPaused = null;
                break;
            case "launchAtLogin":
                LaunchAtLogin.Set("Wave", _settings.Bool("launchAtLogin", false));
                break;
            case "fps":
                StartFrames();
                break;
            case "spotifyClientId":
                _spotify.ClientId = _settings.String("spotifyClientId", string.Empty);
                break;
        }
    }

    // ------------------------------------------------------------------ media control

    private async void Media(NowPlayingService.MediaCommand command)
    {
        if (_spotify.IsConnected && _spotify.Playback is not null)
        {
            switch (command)
            {
                case NowPlayingService.MediaCommand.Next: await _spotify.NextAsync(); break;
                case NowPlayingService.MediaCommand.Previous: await _spotify.PreviousAsync(); break;
                default: await _spotify.PlayPauseAsync(); break;
            }
            PushTrack(force: true);
            return;
        }
        await _nowPlaying.SendAsync(command);
    }

    private async void ToggleLike()
    {
        await _spotify.ToggleLikeAsync();
        PushTrack(force: true);
    }

    // ------------------------------------------------------------------ pushing state to the pages

    private void OnArtworkChanged()
    {
        var art = _nowPlaying.Artwork;
        _colors = ArtworkColors.Extract(art, 3).Select(c => $"#{c.R:x2}{c.G:x2}{c.B:x2}").ToArray();
        // Encode SMTC artwork once per track, not on every push.
        _cachedArt = art is null ? (string.Empty, string.Empty) : (_nowPlaying.Current?.TrackId ?? string.Empty, JpegDataUrl(art, 600));
        PushTrack(force: false);
    }

    private static string JpegDataUrl(BitmapSource source, int maxSide)
    {
        try
        {
            BitmapSource img = source;
            var scale = Math.Min(1.0, (double)maxSide / Math.Max(source.PixelWidth, source.PixelHeight));
            if (scale < 1) img = new TransformedBitmap(source, new ScaleTransform(scale, scale));
            var encoder = new JpegBitmapEncoder { QualityLevel = 85 };
            encoder.Frames.Add(BitmapFrame.Create(img));
            using var ms = new MemoryStream();
            encoder.Save(ms);
            return "data:image/jpeg;base64," + Convert.ToBase64String(ms.ToArray());
        }
        catch (Exception)
        {
            return string.Empty;
        }
    }

    private JsonObject? TrackPayload()
    {
        var current = _nowPlaying.Current;
        if (_spotify.IsConnected && _spotify.Playback is { } p)
        {
            var age = (DateTime.UtcNow - p.FetchedAtUtc).TotalSeconds;
            var t = new JsonObject
            {
                ["title"] = p.Title,
                ["artist"] = p.Artist,
                ["album"] = p.Album,
                ["isPlaying"] = p.IsPlaying,
                ["position"] = Math.Round(p.Position + (p.IsPlaying ? age : 0), 2),
                ["duration"] = p.Duration,
                ["liked"] = p.Liked,
                ["source"] = "spotify",
            };
            if (p.ArtUrl is not null) t["art"] = p.ArtUrl;
            if (current?.Title == p.Title && _colors.Length > 0) t["colors"] = Colors();
            return t;
        }
        if (current is null) return null;
        var track = new JsonObject
        {
            ["title"] = current.Title,
            ["artist"] = current.Artist,
            ["album"] = current.Album,
            ["isPlaying"] = current.IsPlaying,
            ["position"] = Math.Round(_nowPlaying.Position, 2),
            ["duration"] = current.DurationSec,
            ["liked"] = false,
            ["source"] = current.PlayerName,
        };
        if (_cachedArt.Id == current.TrackId && _cachedArt.Url.Length > 0) track["art"] = _cachedArt.Url;
        if (_colors.Length > 0) track["colors"] = Colors();
        return track;
    }

    private JsonArray Colors() => new(_colors.Select(c => (JsonNode?)JsonValue.Create(c)).ToArray());

    private void PushTrack(bool force)
    {
        var payload = TrackPayload();
        // Compare without position so we only resend when something visible changed (or on the 1 s tick).
        var key = "null";
        if (payload is not null)
        {
            var copy = (JsonObject)payload.DeepClone();
            copy.Remove("position");
            copy.Remove("art"); // art is tied to the track id; a hash of the other fields is enough
            key = copy.ToJsonString() + "|" + (payload["art"]?.ToString().Length ?? 0);
        }
        if (!force && key == _lastTrackKey) return;
        _lastTrackKey = key;
        var json = payload?.ToJsonString() ?? "null";
        foreach (var p in Panels.ToList()) p.Call("setTrack", json);
    }

    private JsonObject StatusPayload()
    {
        string audio;
        if (!_audio.IsCapturing) audio = "Not available: " + _audio.Status;
        else audio = _audio.HasRecentAudio ? "Hearing system audio" : "Listening (nothing playing)";
        if (_hotKeyFailures.Count > 0) audio += $" · shortcut taken by another app: {string.Join(", ", _hotKeyFailures)}";
        return new JsonObject
        {
            ["spotify"] = _spotify.StateName,
            ["spotifyUser"] = _spotify.UserName,
            ["spotifyError"] = _spotify.ErrorMessage,
            ["audio"] = audio,
            ["platform"] = "Windows",
            ["version"] = _version,
            ["lyrics"] = _lyrics?.StatusLabel ?? "Waiting for a song",
            ["lyricsOffset"] = _lyrics?.Offset ?? 0,
        };
    }

    private void PushStatus()
    {
        var json = StatusPayload().ToJsonString();
        foreach (var p in Panels.ToList()) p.Call("setStatus", json);
    }

    private void PushAll(WebPanel panel)
    {
        panel.Call("config", _settings.Values.ToJsonString());
        panel.Call("setTrack", TrackPayload()?.ToJsonString() ?? "null");
        PushStatus();
    }

    // ------------------------------------------------------------------ audio frames

    private void StartFrames()
    {
        if (_rendering) return;
        System.Windows.Media.CompositionTarget.Rendering += OnRendering;
        _rendering = true;
    }

    /// <summary>Sends one audio frame to every visible page, at the fps setting (15 to 120).</summary>
    private void OnRendering(object? sender, EventArgs e)
    {
        var now = _audio.Now;
        var fps = Math.Clamp(_settings.Number("fps", 60), 15, 120);
        if (now - _lastFrame < 1.0 / fps - 0.002) return;
        _lastFrame = now;

        if (now - _lastCoverCheck >= CoverCheckSeconds)
        {
            _lastCoverCheck = now;
            UpdateCoverage();
        }

        var panels = Panels.ToList();
        var anyVisible = panels.Any(IsVisible);
        var pauseCovered = _settings.Bool("pauseWhenCovered", true);
        foreach (var p in panels)
        {
            if (p.Kind is PanelKind.Widget or PanelKind.Clock)
            {
                var paused = pauseCovered && !IsVisible(p) && !_editing;
                if (p.LastPaused != paused && p.IsReady)
                {
                    p.LastPaused = paused;
                    p.Call("setPaused", paused ? "true" : "false");
                }
            }
        }
        if (!anyVisible) return;

        var f = _audio.Features;
        _audio.CopySpectrum(_bins, _wave);
        var beatAt = _audio.LastBeatTime;
        var beat = beatAt > _lastBeatSent && now - beatAt < 0.1;
        if (beat) _lastBeatSent = beatAt;

        var sb = new StringBuilder(2048);
        sb.Append("{\"bins\":[");
        AppendArray(sb, _bins);
        sb.Append("],\"wave\":[");
        AppendArray(sb, _wave);
        sb.Append("],\"level\":").Append(R(f.Level))
          .Append(",\"bass\":").Append(R(f.Bass))
          .Append(",\"mid\":").Append(R(f.Mid))
          .Append(",\"treble\":").Append(R(f.Treble))
          .Append(",\"beat\":").Append(beat ? "true" : "false").Append('}');
        var json = sb.ToString();

        foreach (var p in panels)
            if (IsVisible(p)) p.Call("pushAudio", json);
    }

    private static void AppendArray(StringBuilder sb, float[] values)
    {
        for (var i = 0; i < values.Length; i++)
        {
            if (i > 0) sb.Append(',');
            sb.Append(R(values[i]));
        }
    }

    private static string R(double v) =>
        double.IsFinite(v) ? (Math.Round(v * 1000) / 1000).ToString("0.###", CultureInfo.InvariantCulture) : "0";

    private void UpdateCoverage()
    {
        foreach (var p in new[] { _widget, _clock })
        {
            if (p?.Window is not DesktopWidgetWindow w || w.Handle == IntPtr.Zero) continue;
            var placement = PlacementOf(p.Kind);
            // Top is never covered; a desktop widget lifted over the desktop by Show Desktop is not covered either.
            _covered[p.Kind] = !_editing && placement != "top" && !w.DesktopRaised && Coverage.IsCovered(w.Handle);
        }
    }

    /// <summary>Whether a panel can be seen (only visible panels get audio frames).</summary>
    private bool IsVisible(WebPanel p) => p.Kind switch
    {
        PanelKind.Fullscreen => true,
        PanelKind.Dashboard => p.Window.IsVisible && p.Window.WindowState != WindowState.Minimized,
        _ => p.Window.IsVisible && !(_covered.TryGetValue(p.Kind, out var c) && c),
    };

    // ------------------------------------------------------------------ tray

    private void BuildTray()
    {
        var icon = TrayIconFromExe() ?? TrayIconArt.Draw((g, size) =>
        {
            using var pen = new System.Drawing.Pen(System.Drawing.Color.White, size * 0.1f)
            { StartCap = System.Drawing.Drawing2D.LineCap.Round, EndCap = System.Drawing.Drawing2D.LineCap.Round };
            float[] heights = { 0.35f, 0.7f, 0.5f, 0.85f, 0.45f };
            for (var i = 0; i < heights.Length; i++)
            {
                var x = size * (0.18f + i * 0.16f);
                var h = size * heights[i];
                g.DrawLine(pen, x, (size - h) / 2, x, (size + h) / 2);
            }
        }, TrayIconArt.PreferredSize);

        _tray = new TrayIcon("Wave", icon);
        _headerItem = _tray.Add("Nothing playing", () => { });
        _headerItem.Enabled = false;
        _tray.AddSeparator();
        _tray.Add("Open Wave…", ShowDashboard);
        _tray.Add("Full Screen", ToggleFullscreen).ShortcutKeyDisplayString = "Ctrl+Alt+F";
        _widgetsItem = _tray.Add("Hide Widgets", ToggleWidgets);
        _widgetsItem.ShortcutKeyDisplayString = "Ctrl+Alt+M";
        _arrangeItem = _tray.Add("Arrange Widgets", () => SetEditing(!_editing));
        _tray.AddSeparator();
        _tray.Add("Play / Pause", () => Media(NowPlayingService.MediaCommand.PlayPause));
        _tray.Add("Next Track", () => Media(NowPlayingService.MediaCommand.Next));
        _likeItem = _tray.Add("Save to Liked Songs", ToggleLike);
        _tray.AddSeparator();
        _tray.AddCheck("Screen Glow", () => _settings.Bool("glowEnabled", false),
            () => SetSetting("glowEnabled", JsonValue.Create(!_settings.Bool("glowEnabled", false))));
        _tray.AddCheck("Show Lyrics", () => _settings.Bool("lyricsEnabled", true),
            () => SetSetting("lyricsEnabled", JsonValue.Create(!_settings.Bool("lyricsEnabled", true))));
        _tray.Add("Lyrics Earlier", () => { _lyrics?.Nudge(+LyraController.NudgeSeconds); PushStatus(); }).ShortcutKeyDisplayString = "+0.25 s";
        _tray.Add("Lyrics Later", () => { _lyrics?.Nudge(-LyraController.NudgeSeconds); PushStatus(); }).ShortcutKeyDisplayString = "−0.25 s";
        _tray.AddSeparator();
        _tray.Add("Quit Wave", Quit);
        _tray.LeftClick += (_, _) => ShowDashboard();
        _tray.Opening += (_, _) => RefreshTray();
        RefreshTray();
    }

    private void RefreshTray()
    {
        if (_tray is null) return;
        var sp = _spotify.IsConnected ? _spotify.Playback : null;
        var np = _nowPlaying.Current;
        var title = sp is not null ? $"{sp.Title} – {sp.Artist}" : np is not null ? np.Display : "Nothing playing";
        _headerItem!.Text = title.Length > 60 ? title[..59] + "…" : title;
        _widgetsItem!.Text = _widgetsHidden ? "Show Widgets" : "Hide Widgets";
        _arrangeItem!.Text = _editing ? "Done Arranging" : "Arrange Widgets";
        _likeItem!.Visible = sp is not null;
        if (sp is not null) _likeItem.Text = sp.Liked ? "Remove from Liked Songs" : "Save to Liked Songs";
        _tray.Tooltip = sp is not null || np is not null ? "Wave · " + title : "Wave";
    }

    private static System.Drawing.Icon? TrayIconFromExe()
    {
        try
        {
            var path = Environment.ProcessPath;
            if (path is null) return null;
            var size = Forms.SystemInformation.SmallIconSize;
            using var big = System.Drawing.Icon.ExtractAssociatedIcon(path);
            return big is null ? null : new System.Drawing.Icon(big, size);
        }
        catch (Exception)
        {
            return null;
        }
    }

    // ------------------------------------------------------------------ shutdown

    public void Quit()
    {
        Dispose();
        Application.Current.Shutdown();
    }

    private bool _disposed;

    public void Dispose()
    {
        if (_disposed) return;
        _disposed = true;
        if (_editing) SetEditing(false);
        if (_rendering) System.Windows.Media.CompositionTarget.Rendering -= OnRendering;
        SystemEvents.DisplaySettingsChanged -= OnDisplaysChanged;
        _tick.Stop();
        _glow?.Dispose();
        _lyrics?.Dispose();
        foreach (var p in Panels.ToList())
        {
            if (p.Window is DesktopWidgetWindow w)
            {
                if (w.Handle != IntPtr.Zero && w.IsVisible) _layout.Set(KindKey(p.Kind), w.ScreenRect);
                w.ClosingByUs = true;
            }
            p.Dispose();
            p.Window.Close();
        }
        _settings.Flush();
        _dragger.Finish();
        _foreground.Dispose();
        _messages.Dispose();
        _spotify.Dispose();
        _audio.Dispose();
        _nowPlaying.Dispose();
        _tray?.Dispose();
    }
}
