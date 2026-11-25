using System.Windows;
using System.Windows.Media;
using Microsoft.Win32;
using Shared.Audio;
using Shared.Imaging;
using Shared.NowPlaying;
using Shared.Overlay;
using Shared.Settings;
using Shared.Ui;

namespace Halo;

/// <summary>
/// Drives the glow: picks colours (album art or custom, cross-faded over 600 ms), applies the animation mode to the
/// audio features each frame (<c>CompositionTarget.Rendering</c>) and keeps one overlay window per selected display.
/// </summary>
public sealed class GlowController : IDisposable
{
    public const double ColorFadeSeconds = 0.6;

    private readonly SettingsStore<HaloSettings> _store;
    private readonly NowPlayingService _nowPlaying;
    private readonly AudioAnalyzer _audio;
    private readonly Dictionary<string, GlowWindow> _windows = new();
    private readonly System.Diagnostics.Stopwatch _clock = System.Diagnostics.Stopwatch.StartNew();

    private Color[] _fromColors = Array.Empty<Color>();
    private Color[] _toColors = Array.Empty<Color>();
    private double _fadeStart = double.NegativeInfinity;
    private IReadOnlyList<Color> _albumColors = Array.Empty<Color>();
    private double _lastTime;
    private double _phase;
    private double _brightness = 0.6;
    private bool _rendering;

    public GlowController(SettingsStore<HaloSettings> store, NowPlayingService nowPlaying, AudioAnalyzer audio)
    {
        _store = store;
        _nowPlaying = nowPlaying;
        _audio = audio;
        _nowPlaying.ArtworkChanged += (_, _) => OnArtworkChanged();
        _store.Changed += (_, _) => Apply();
        SystemEvents.DisplaySettingsChanged += OnDisplaysChanged;
    }

    private HaloSettings S => _store.Value;

    /// <summary>The most recent frame (the settings preview mirrors it).</summary>
    public GlowFrame? LastFrame { get; private set; }

    /// <summary>True while music sync has fallen back to breathing because nothing is playing.</summary>
    public bool IsIdle { get; private set; }

    public AudioFeatures LastFeatures { get; private set; }

    public void Start()
    {
        UpdateTargetColors(immediate: true);
        Apply();
    }

    /// <summary>Re-reads the settings: windows, audio capture and colours.</summary>
    public void Apply()
    {
        S.Normalize();
        UpdateTargetColors(immediate: false);
        SyncWindows();

        var wantAudio = S.Enabled && S.Mode == GlowMode.MusicSync;
        if (wantAudio) _audio.Start();
        else _audio.Stop();

        var wantRender = S.Enabled || AnyPreview;
        if (wantRender && !_rendering)
        {
            _lastTime = _clock.Elapsed.TotalSeconds;
            CompositionTarget.Rendering += OnRendering;
            _rendering = true;
        }
        else if (!wantRender && _rendering)
        {
            CompositionTarget.Rendering -= OnRendering;
            _rendering = false;
        }
    }

    /// <summary>Set by the settings window so frames keep coming for its preview while the glow is off.</summary>
    public bool AnyPreview { get; set; }

    private void OnArtworkChanged()
    {
        _albumColors = ArtworkColors.Extract(_nowPlaying.Current?.Artwork, 3);
        UpdateTargetColors(immediate: false);
    }

    private Color[] DesiredColors()
    {
        if (S.UseAlbumColors && _albumColors.Count >= 2) return _albumColors.Take(3).ToArray();

        var p = ColorPicker.ParseOr(S.PrimaryColor, Color.FromRgb(0x7C, 0x5C, 0xFF));
        var s = ColorPicker.ParseOr(S.SecondaryColor, Color.FromRgb(0x00, 0xD4, 0xFF));
        if (!S.UseTertiary) return new[] { p, s };
        var t = ColorPicker.ParseOr(S.TertiaryColor, Color.FromRgb(0xFF, 0x4F, 0xA3));
        return new[] { p, s, t };
    }

    private void UpdateTargetColors(bool immediate)
    {
        var desired = DesiredColors();
        if (_toColors.SequenceEqual(desired)) return;
        var now = _clock.Elapsed.TotalSeconds;
        _fromColors = _toColors.Length == 0 || immediate ? desired : CurrentColors(now, desired.Length);
        _toColors = desired;
        _fadeStart = immediate ? double.NegativeInfinity : now;
    }

    /// <summary>The cross-faded colours at <paramref name="now"/>, resampled to <paramref name="count"/> stops.</summary>
    private Color[] CurrentColors(double now, int? count = null)
    {
        var n = count ?? _toColors.Length;
        var t = Math.Clamp((now - _fadeStart) / ColorFadeSeconds, 0, 1);
        t = t * t * (3 - 2 * t);
        var result = new Color[n];
        for (var i = 0; i < n; i++)
        {
            var from = Sample(_fromColors, i, n);
            var to = Sample(_toColors, i, n);
            result[i] = GlowSurface.Mix(from, to, t);
        }
        return result;
    }

    private static Color Sample(Color[] colors, int i, int n)
    {
        if (colors.Length == 0) return Colors.White;
        if (colors.Length == n) return colors[i];
        return colors[Math.Min(colors.Length - 1, i * colors.Length / n)];
    }

    private void OnRendering(object? sender, EventArgs e)
    {
        var now = _clock.Elapsed.TotalSeconds;
        var dt = Math.Clamp(now - _lastTime, 0, 0.1);
        _lastTime = now;

        var f = _audio.Features;
        LastFeatures = f;
        var thickness = S.Thickness;
        double brightness, width = thickness, turnsPerSecond;

        var mode = S.Mode;
        IsIdle = mode == GlowMode.MusicSync && !_nowPlaying.IsPlaying && f.Level < 0.02;
        if (IsIdle) mode = GlowMode.Breathe;

        switch (mode)
        {
            case GlowMode.MusicSync:
                brightness = 0.35 + 0.45 * f.Bass + 0.25 * f.Beat;
                width = thickness * (1 + 0.6 * f.Beat);
                turnsPerSecond = 0.04 + 0.25 * f.Mid;
                break;
            case GlowMode.Breathe:
                brightness = 0.55 + 0.25 * Math.Sin(2 * Math.PI * now / 4.0);
                turnsPerSecond = 0.03;
                break;
            default:
                brightness = 0.8;
                turnsPerSecond = 0;
                break;
        }

        // A very short smoothing so switching between modes does not pop, without dulling beats.
        _brightness += (brightness - _brightness) * Math.Min(1, dt * 30);
        _phase = (_phase + turnsPerSecond * dt) % 1.0;

        var frame = new GlowFrame(CurrentColors(now), S.Split, _phase, width, S.Glow, Math.Clamp(_brightness, 0, 1));
        LastFrame = frame;
        if (!S.Enabled) return;
        foreach (var w in _windows.Values) w.Render(frame);
    }

    private void OnDisplaysChanged(object? sender, EventArgs e) =>
        Application.Current?.Dispatcher.BeginInvoke(new Action(SyncWindows));

    private void SyncWindows()
    {
        var wanted = S.Enabled ? DisplayInfo.Resolve(S.Displays, defaultAll: true) : Array.Empty<DisplayInfo>();
        var ids = wanted.Select(d => d.Id).ToHashSet();

        foreach (var id in _windows.Keys.Where(id => !ids.Contains(id)).ToList())
        {
            _windows[id].Close();
            _windows.Remove(id);
        }
        foreach (var display in wanted)
        {
            if (_windows.TryGetValue(display.Id, out var existing))
            {
                if (!existing.Display.Bounds.Equals(display.Bounds)) existing.Move(display);
                continue;
            }
            var window = new GlowWindow(display);
            _windows[display.Id] = window;
            window.Show();
            if (LastFrame is not null) window.Render(LastFrame);
        }
    }

    public void Dispose()
    {
        SystemEvents.DisplaySettingsChanged -= OnDisplaysChanged;
        if (_rendering) CompositionTarget.Rendering -= OnRendering;
        foreach (var w in _windows.Values) w.Close();
        _windows.Clear();
    }
}
