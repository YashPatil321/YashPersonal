using System.Windows;
using Shared.NowPlaying;
using Shared.Settings;
using Shared.Tray;
using Shared.Ui;
using Drawing = System.Drawing;
using Forms = System.Windows.Forms;

namespace Lyra;

public partial class App : Application
{
    private SingleInstance? _instance;
    private SettingsStore<LyraSettings>? _store;
    private NowPlayingService? _nowPlaying;
    private LyraController? _lyra;
    private TrayIcon? _tray;
    private SettingsWindow? _settingsWindow;
    private Forms.ToolStripMenuItem? _offsetItem;

    protected override void OnStartup(StartupEventArgs e)
    {
        base.OnStartup(e);

        _instance = SingleInstance.Acquire("Lyra");
        if (!_instance.IsFirst)
        {
            Shutdown();
            return;
        }

        Accent.Install(this);
        _store = new SettingsStore<LyraSettings>("Lyra");
        _store.Value.Normalize();

        _nowPlaying = new NowPlayingService();
        _lyra = new LyraController(_store, _nowPlaying);
        BuildTray();

        _nowPlaying.Start();
        _lyra.Start();

        DispatcherUnhandledException += (_, args) =>
        {
            System.Diagnostics.Debug.WriteLine(args.Exception);
            args.Handled = true;
        };
    }

    private LyraSettings S => _store!.Value;

    private void BuildTray()
    {
        _tray = new TrayIcon("Lyra", DrawIcon());
        _tray.AddCheck("Show lyrics", () => S.ShowLyrics, () => Update(s => s.ShowLyrics = !s.ShowLyrics));
        _tray.AddSeparator();
        foreach (var style in Enum.GetValues<LyricStyle>())
            _tray.AddCheck(style.ToString(), () => S.Style == style, () => Update(s => s.Style = style));
        _tray.AddSeparator();
        _tray.Add("Earlier (−0.25 s)", () => _lyra!.Nudge(-LyraController.NudgeSeconds));
        _tray.Add("Later (+0.25 s)", () => _lyra!.Nudge(+LyraController.NudgeSeconds));
        _offsetItem = _tray.Add("Offset: +0.00 s", () => { });
        _offsetItem.Enabled = false;
        _tray.AddSeparator();
        _tray.AddCheck("Keep screen awake", () => S.KeepAwake, () => Update(s => s.KeepAwake = !s.KeepAwake));
        _tray.Add("Settings…", ShowSettings);
        _tray.AddSeparator();
        _tray.Add("Quit Lyra", Quit);
        _tray.LeftClick += (_, _) => ShowSettings();
        _tray.Opening += (_, _) => RefreshTrayText();
        _lyra!.Changed += (_, _) => RefreshTrayText();
    }

    private void RefreshTrayText()
    {
        if (_offsetItem is not null) _offsetItem.Text = $"Offset: {_lyra!.Offset:+0.00;−0.00;+0.00} s";
        var track = _nowPlaying?.Current;
        if (_tray is not null) _tray.Tooltip = track is null ? "Lyra" : $"Lyra · {track.Display}";
    }

    private void Update(Action<LyraSettings> change)
    {
        change(S);
        _store!.Save();
    }

    private void ShowSettings() =>
        DarkChrome.ShowSingle(ref _settingsWindow, () => new SettingsWindow(_store!, _lyra!));

    private void Quit()
    {
        _settingsWindow?.Close();
        _lyra?.Dispose();
        _nowPlaying?.Dispose();
        _store?.Dispose();
        _tray?.Dispose();
        _instance?.Dispose();
        Shutdown();
    }

    protected override void OnExit(ExitEventArgs e)
    {
        KeepAwake.Set(false);
        _store?.Flush();
        _tray?.Dispose();
        base.OnExit(e);
    }

    /// <summary>A speech-bubble of lyric lines, the top one in the accent colour.</summary>
    private static Drawing.Icon DrawIcon()
    {
        var accent = TrayIconArt.FromWpf(Accent.Current);
        return TrayIconArt.Draw((g, size) =>
        {
            var s = size / 32f;
            using var bubble = new Drawing.SolidBrush(Drawing.Color.FromArgb(235, 245, 245, 250));
            using var path = new Drawing.Drawing2D.GraphicsPath();
            var r = new Drawing.RectangleF(2 * s, 4 * s, 28 * s, 20 * s);
            var d = 8 * s;
            path.AddArc(r.X, r.Y, d, d, 180, 90);
            path.AddArc(r.Right - d, r.Y, d, d, 270, 90);
            path.AddArc(r.Right - d, r.Bottom - d, d, d, 0, 90);
            path.AddLine(r.X + 12 * s, r.Bottom, r.X + 6 * s, r.Bottom + 6 * s);
            path.AddLine(r.X + 6 * s, r.Bottom + 6 * s, r.X + 6 * s, r.Bottom);
            path.AddArc(r.X, r.Bottom - d, d, d, 90, 90);
            path.CloseFigure();
            g.FillPath(bubble, path);

            using var line1 = new Drawing.Pen(accent, 3.2f * s) { StartCap = Drawing.Drawing2D.LineCap.Round, EndCap = Drawing.Drawing2D.LineCap.Round };
            using var line2 = new Drawing.Pen(Drawing.Color.FromArgb(255, 70, 70, 78), 3.2f * s) { StartCap = Drawing.Drawing2D.LineCap.Round, EndCap = Drawing.Drawing2D.LineCap.Round };
            g.DrawLine(line1, 8 * s, 11 * s, 24 * s, 11 * s);
            g.DrawLine(line2, 8 * s, 17.5f * s, 19 * s, 17.5f * s);
        }, TrayIconArt.PreferredSize);
    }
}
