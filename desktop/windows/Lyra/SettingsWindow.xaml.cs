using System.Diagnostics;
using System.Windows;
using System.Windows.Controls;
using System.Windows.Media;
using System.Windows.Threading;
using Lyrics;
using Shared.NowPlaying;
using Shared.Overlay;
using Shared.Settings;
using Shared.Ui;

namespace Lyra;

public partial class SettingsWindow : Window
{
    private static readonly (LyricStyle Style, string Blurb)[] StyleInfo =
    {
        (LyricStyle.Spotlight, "The current line, large and centred. The sung word fills in."),
        (LyricStyle.Stack, "Three words stacked. Each new word springs in from below."),
        (LyricStyle.Thread, "Chat bubbles, one per line, alternating left and right."),
        (LyricStyle.Terminal, "Typed out after a > prompt with a blinking cursor."),
        (LyricStyle.Drift, "Words float upward and fade, leaving a trail."),
    };

    private readonly SettingsStore<LyraSettings> _store;
    private readonly LyraController _lyra;
    private readonly ColorPicker _textColor = new();
    private readonly ColorPicker _highlight = new();
    private readonly ColorPicker _dim = new(withAlpha: true);
    private readonly DispatcherTimer _statusTimer = new() { Interval = TimeSpan.FromSeconds(1) };
    private readonly Dictionary<LyricStyle, RadioButton> _styleCards = new();
    private readonly Dictionary<LyricFont, RadioButton> _fontSegments = new();
    private bool _loading;

    public SettingsWindow(SettingsStore<LyraSettings> store, LyraController lyra)
    {
        _store = store;
        _lyra = lyra;
        InitializeComponent();

        StylePreview.FrameSource = () => _lyra.DemoFrame(0.5);
        AppearancePreview.FrameSource = () => _lyra.DemoFrame(0.5);

        foreach (var (style, blurb) in StyleInfo)
        {
            var content = new StackPanel();
            content.Children.Add(new TextBlock { Text = style.ToString(), FontWeight = FontWeights.SemiBold, FontSize = 14 });
            content.Children.Add(new TextBlock { Text = blurb, Style = (Style)FindResource("SubtleText"), Margin = new Thickness(0, 3, 0, 0) });
            var card = new RadioButton { Content = content, GroupName = "LyricStyle", Style = (Style)FindResource("ChoiceCard") };
            card.Click += (_, _) => Change(s => s.Style = style);
            _styleCards[style] = card;
            StyleCards.Children.Add(card);
        }

        foreach (var font in Enum.GetValues<LyricFont>())
        {
            var seg = new RadioButton
            {
                Content = font.ToString(),
                GroupName = "Font",
                Style = (Style)FindResource("Segment"),
                FontFamily = Styles.LyricsLook.FamilyFor(font),
                FontStretch = Styles.LyricsLook.StretchFor(font),
            };
            seg.Click += (_, _) => Change(s => s.Font = font);
            _fontSegments[font] = seg;
            FontSegments.Children.Add(seg);
        }

        TextColorHost.Content = _textColor;
        HighlightHost.Content = _highlight;
        DimColorHost.Content = _dim;
        _textColor.ColorChanged += (_, c) => Change(s => s.TextColor = ColorPicker.ToHex(c));
        _highlight.ColorChanged += (_, c) => Change(s => s.HighlightColor = ColorPicker.ToHex(c));
        _dim.ColorChanged += (_, c) => Change(s => s.DimColor = ColorPicker.ToHex(c, withAlpha: true));

        Load();

        _lyra.Changed += OnLyraChanged;
        Accent.Changed += OnAccentChanged;
        _statusTimer.Tick += (_, _) => RefreshStatus();
        _statusTimer.Start();
        RefreshStatus();
        Closed += (_, _) =>
        {
            _statusTimer.Stop();
            _lyra.Changed -= OnLyraChanged;
            Accent.Changed -= OnAccentChanged;
        };
    }

    private LyraSettings S => _store.Value;

    private void OnLyraChanged(object? sender, EventArgs e) => RefreshStatus();

    private void OnAccentChanged(object? sender, EventArgs e) => Dispatcher.BeginInvoke(new Action(Load));

    private void Load()
    {
        _loading = true;
        try
        {
            foreach (var (style, card) in _styleCards) card.IsChecked = style == S.Style;
            foreach (var (font, seg) in _fontSegments) seg.IsChecked = font == S.Font;
            StylePreview.StyleKind = AppearancePreview.StyleKind = S.Style;
            SizeSlider.Value = S.Size;
            ShadowBox.IsChecked = S.Shadow;
            AlbumBox.IsChecked = S.MatchAlbumArt;
            _textColor.Color = ColorPicker.ParseOr(S.TextColor, Colors.White);
            _highlight.Color = string.IsNullOrWhiteSpace(S.HighlightColor) ? Accent.Current : ColorPicker.ParseOr(S.HighlightColor, Accent.Current);
            _dim.Color = ColorPicker.ParseOr(S.DimColor, Color.FromArgb(0x73, 0xFF, 0xFF, 0xFF));
            AccentButton.IsEnabled = !string.IsNullOrWhiteSpace(S.HighlightColor);
            _highlight.IsEnabled = !S.MatchAlbumArt;
            PlaceBottom.IsChecked = S.Placement == Placement.Bottom;
            PlaceCentre.IsChecked = S.Placement == Placement.Centre;
            PlaceTop.IsChecked = S.Placement == Placement.Top;
            ShowBox.IsChecked = S.ShowLyrics;
            AwakeBox.IsChecked = S.KeepAwake;
            LatencySlider.Value = S.Latency;
            UpdateLabels();
            BuildDisplayList();
        }
        finally
        {
            _loading = false;
        }
    }

    private void BuildDisplayList()
    {
        DisplayList.Children.Clear();
        foreach (var d in DisplayInfo.All())
        {
            var box = new CheckBox
            {
                Content = d.Name,
                Tag = d.Id,
                IsChecked = S.Displays is null ? d.IsPrimary : S.Displays.Contains(d.Id),
                Style = (Style)FindResource("BoxCheck"),
            };
            box.Click += (_, _) =>
            {
                var selected = DisplayList.Children.OfType<CheckBox>().Where(b => b.IsChecked == true).Select(b => (string)b.Tag).ToList();
                Change(s => s.Displays = selected);
            };
            DisplayList.Children.Add(box);
        }
    }

    private void Change(Action<LyraSettings> change)
    {
        if (_loading) return;
        change(S);
        _store.Save();
        StylePreview.StyleKind = AppearancePreview.StyleKind = S.Style;
        AccentButton.IsEnabled = !string.IsNullOrWhiteSpace(S.HighlightColor);
        _highlight.IsEnabled = !S.MatchAlbumArt;
    }

    private void OnToggle(object sender, RoutedEventArgs e) => Change(s =>
    {
        s.Shadow = ShadowBox.IsChecked == true;
        s.MatchAlbumArt = AlbumBox.IsChecked == true;
        s.ShowLyrics = ShowBox.IsChecked == true;
        s.KeepAwake = AwakeBox.IsChecked == true;
        s.Placement = PlaceTop.IsChecked == true ? Placement.Top : PlaceCentre.IsChecked == true ? Placement.Centre : Placement.Bottom;
    });

    private void OnUseAccent(object sender, RoutedEventArgs e)
    {
        Change(s => s.HighlightColor = string.Empty);
        _loading = true;
        _highlight.Color = Accent.Current;
        _loading = false;
    }

    private void OnSizeChanged(object sender, RoutedPropertyChangedEventArgs<double> e)
    {
        if (!IsInitialized) return;
        UpdateLabels();
        Change(s => s.Size = Math.Round(SizeSlider.Value, 2));
    }

    private void OnLatencyChanged(object sender, RoutedPropertyChangedEventArgs<double> e)
    {
        if (!IsInitialized) return;
        UpdateLabels();
        Change(s => s.Latency = Math.Round(LatencySlider.Value / 0.05) * 0.05);
    }

    private void OnEarlier(object sender, RoutedEventArgs e) => _lyra.Nudge(-LyraController.NudgeSeconds);

    private void OnLater(object sender, RoutedEventArgs e) => _lyra.Nudge(+LyraController.NudgeSeconds);

    private void UpdateLabels()
    {
        if (SizeLabel is null || LatencyLabel is null) return;
        SizeLabel.Text = $"{SizeSlider.Value:0.00}×";
        LatencyLabel.Text = $"{Math.Round(LatencySlider.Value / 0.05) * 0.05:+0.00;−0.00;0.00} s";
        OffsetLabel.Text = $"This song: {_lyra.Offset:+0.00;−0.00;+0.00} s";
    }

    // ------------------------------------------------------------------ status

    private void RefreshStatus()
    {
        UpdateLabels();
        var np = _lyra.NowPlaying;
        var track = np.Current;
        HeaderStatus.Text = track is null
            ? "Nothing playing"
            : $"{(track.IsPlaying ? "Playing" : "Paused")} · {track.Display} · {LyricsSummary()}";

        PlayerList.Children.Clear();
        var sessions = np.Sessions;
        AddPlayerCard("Spotify", IsRunning("Spotify"), sessions.FirstOrDefault(s => s.Player == PlayerKind.Spotify), np.IsAvailable, track);
        AddPlayerCard("Apple Music", IsRunning("AppleMusic") || IsRunning("iTunes"), sessions.FirstOrDefault(s => s.Player == PlayerKind.AppleMusic), np.IsAvailable, track);
        foreach (var other in sessions.Where(s => s.Player == PlayerKind.Other))
            AddPlayerCard(other.PlayerName, true, other, np.IsAvailable, track);

        LyricsStatusPanel.Children.Clear();
        LyricsStatusPanel.Children.Add(StatusLine(_lyra.Status switch
        {
            LyricsStatus.Found => true,
            LyricsStatus.Searching or LyricsStatus.Idle => null,
            _ => false,
        }, "Lyrics", LyricsSummary()));
        if (_lyra.Status == LyricsStatus.NotFound || _lyra.Status == LyricsStatus.Instrumental)
            LyricsStatusPanel.Children.Add(new TextBlock
            {
                Text = _lyra.Status == LyricsStatus.Instrumental ? "This track is marked instrumental." : "No synced lyrics for this song",
                Style = (Style)FindResource("SubtleText"),
                Margin = new Thickness(26, 2, 0, 0),
            });
    }

    private string LyricsSummary() => _lyra.Status switch
    {
        LyricsStatus.Searching => "searching lrclib.net…",
        LyricsStatus.Found => _lyra.Lyrics.Source == LyricsSource.WordSynced ? "word-synced lyrics" : "line-synced lyrics",
        LyricsStatus.NotFound => "no synced lyrics",
        LyricsStatus.Instrumental => "instrumental",
        LyricsStatus.Error => _lyra.StatusDetail ?? "lookup failed",
        _ => "no track",
    };

    private void AddPlayerCard(string name, bool running, PlayerSessionInfo? session, bool apiAvailable, TrackSnapshot? track)
    {
        var card = new Border { Style = (Style)FindResource("Card"), Padding = new Thickness(16, 12, 16, 12), Margin = new Thickness(0, 0, 0, 10) };
        var panel = new StackPanel();
        panel.Children.Add(new TextBlock { Text = name, FontWeight = FontWeights.SemiBold, FontSize = 14, Margin = new Thickness(0, 0, 0, 6) });
        panel.Children.Add(StatusLine(running, "Running", running ? "yes" : "not running"));
        panel.Children.Add(StatusLine(session is not null && apiAvailable, "Lyra can read it",
            !apiAvailable ? "media sessions unavailable" : session is not null ? "via Windows media controls" : running ? "no media session yet (start playback)" : "—"));
        var playing = session is null || string.IsNullOrEmpty(session.Title)
            ? "nothing"
            : string.IsNullOrEmpty(session.Artist) ? session.Title : $"{session.Title} – {session.Artist}";
        panel.Children.Add(StatusLine(session?.IsPlaying == true ? true : null, "Playing", playing + (session is { IsPlaying: false } && session.Title.Length > 0 ? " (paused)" : string.Empty)));
        var isCurrent = session is not null && track is not null && track.SourceAppId == session.SourceAppId;
        panel.Children.Add(StatusLine(isCurrent ? _lyra.Status == LyricsStatus.Found : null, "Lyrics", isCurrent ? LyricsSummary() : "—"));
        card.Child = panel;
        PlayerList.Children.Add(card);
    }

    /// <summary>A checklist row: a coloured mark (true ✓ / false ✕ / null •), a label and a detail.</summary>
    private FrameworkElement StatusLine(bool? ok, string label, string detail)
    {
        var row = new DockPanel { Margin = new Thickness(0, 3, 0, 3) };
        var mark = new TextBlock
        {
            Text = ok switch { true => "✓", false => "✕", _ => "•" },
            Width = 26,
            FontWeight = FontWeights.Bold,
            Foreground = (Brush)FindResource(ok switch { true => "GoodBrush", false => "BadBrush", _ => "SubtleTextBrush" }),
        };
        row.Children.Add(mark);
        var labelText = new TextBlock { Text = label, Width = 130, Foreground = (Brush)FindResource("TextBrush") };
        row.Children.Add(labelText);
        row.Children.Add(new TextBlock { Text = detail, Foreground = (Brush)FindResource("SubtleTextBrush"), TextTrimming = TextTrimming.CharacterEllipsis });
        return row;
    }

    private static bool IsRunning(string processName)
    {
        try
        {
            var procs = Process.GetProcessesByName(processName);
            var any = procs.Length > 0;
            foreach (var p in procs) p.Dispose();
            return any;
        }
        catch (Exception)
        {
            return false;
        }
    }
}
