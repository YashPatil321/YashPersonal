using System.Windows;
using Shared.Audio;
using Shared.NowPlaying;
using Shared.Settings;
using Shared.Tray;
using Shared.Ui;
using Drawing = System.Drawing;

namespace Halo;

public partial class App : Application
{
    private SingleInstance? _instance;
    private SettingsStore<HaloSettings>? _store;
    private NowPlayingService? _nowPlaying;
    private AudioAnalyzer? _audio;
    private GlowController? _glow;
    private TrayIcon? _tray;
    private SettingsWindow? _settingsWindow;

    protected override void OnStartup(StartupEventArgs e)
    {
        base.OnStartup(e);

        _instance = SingleInstance.Acquire("Halo");
        if (!_instance.IsFirst)
        {
            Shutdown();
            return;
        }

        Accent.Install(this);
        _store = new SettingsStore<HaloSettings>("Halo");
        _store.Value.Normalize();
        _store.Value.LaunchAtLogin = LaunchAtLogin.IsEnabled("Halo");

        _nowPlaying = new NowPlayingService();
        _audio = new AudioAnalyzer();
        _glow = new GlowController(_store, _nowPlaying, _audio);

        BuildTray();
        _nowPlaying.Start();
        _glow.Start();

        DispatcherUnhandledException += (_, args) =>
        {
            System.Diagnostics.Debug.WriteLine(args.Exception);
            args.Handled = true; // a tray app should not vanish on a stray exception
        };
    }

    private HaloSettings S => _store!.Value;

    private void BuildTray()
    {
        _tray = new TrayIcon("Halo", DrawIcon(true));
        _tray.AddCheck("Enabled", () => S.Enabled, () => Update(s => s.Enabled = !s.Enabled));

        var mode = _tray.AddSubmenu("Mode");
        foreach (var (label, value) in new[] { ("Music Sync", GlowMode.MusicSync), ("Breathe", GlowMode.Breathe), ("Static", GlowMode.Static) })
            _tray.AddCheck(label, () => S.Mode == value, () => Update(s => s.Mode = value), mode.DropDownItems);

        _tray.AddCheck("Use album colours", () => S.UseAlbumColors, () => Update(s => s.UseAlbumColors = !s.UseAlbumColors));
        _tray.AddSeparator();
        _tray.Add("Settings…", ShowSettings);
        _tray.AddSeparator();
        _tray.Add("Quit Halo", Quit);
        _tray.LeftClick += (_, _) => ShowSettings();
        var iconEnabled = S.Enabled;
        _store!.Changed += (_, _) =>
        {
            if (iconEnabled == S.Enabled) return;
            iconEnabled = S.Enabled;
            _tray?.SetIcon(DrawIcon(iconEnabled));
        };
    }

    private void Update(Action<HaloSettings> change)
    {
        change(S);
        _store!.Save();
    }

    private void ShowSettings() =>
        DarkChrome.ShowSingle(ref _settingsWindow, () => new SettingsWindow(_store!, _glow!));

    private void Quit()
    {
        _settingsWindow?.Close();
        _glow?.Dispose();
        _audio?.Dispose();
        _nowPlaying?.Dispose();
        _store?.Dispose(); // flushes pending settings
        _tray?.Dispose();
        _instance?.Dispose();
        Shutdown();
    }

    protected override void OnExit(ExitEventArgs e)
    {
        _store?.Flush();
        _tray?.Dispose();
        base.OnExit(e);
    }

    /// <summary>A ring with a conic gradient; dimmed when the glow is off.</summary>
    private static Drawing.Icon DrawIcon(bool enabled)
    {
        var accent = TrayIconArt.FromWpf(Accent.Current);
        return TrayIconArt.Draw((g, size) =>
        {
            var pad = size * 0.14f;
            var rect = new Drawing.RectangleF(pad, pad, size - 2 * pad, size - 2 * pad);
            var thickness = size * 0.13f;
            if (!enabled)
            {
                using var off = new Drawing.Pen(Drawing.Color.FromArgb(200, 160, 160, 168), thickness);
                g.DrawEllipse(off, rect);
                return;
            }
            Drawing.Color[] colors =
            {
                Drawing.Color.FromArgb(255, 124, 92, 255),
                Drawing.Color.FromArgb(255, 0, 212, 255),
                Drawing.Color.FromArgb(255, 255, 79, 163),
                accent,
            };
            const int segments = 48;
            for (var i = 0; i < segments; i++)
            {
                var t = (float)i / segments;
                var pos = t * colors.Length;
                var a = colors[(int)pos % colors.Length];
                var b = colors[((int)pos + 1) % colors.Length];
                var k = pos - (int)pos;
                var c = Drawing.Color.FromArgb(255,
                    (int)(a.R + (b.R - a.R) * k), (int)(a.G + (b.G - a.G) * k), (int)(a.B + (b.B - a.B) * k));
                using var pen = new Drawing.Pen(c, thickness);
                g.DrawArc(pen, rect, -90 + 360f * i / segments, 360f / segments + 1.5f);
            }
            using var glow = new Drawing.Pen(Drawing.Color.FromArgb(70, 255, 255, 255), size * 0.04f);
            g.DrawEllipse(glow, rect.X + thickness * 0.9f, rect.Y + thickness * 0.9f, rect.Width - thickness * 1.8f, rect.Height - thickness * 1.8f);
        }, TrayIconArt.PreferredSize);
    }
}
