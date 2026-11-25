using System.Windows;
using System.Windows.Controls;
using System.Windows.Media;
using System.Windows.Media.Effects;
using Shared.Overlay;
using Shared.Settings;
using Shared.Ui;

namespace Halo;

public partial class SettingsWindow : Window
{
    private readonly SettingsStore<HaloSettings> _store;
    private readonly GlowController _glow;
    private readonly ColorPicker _primary = new();
    private readonly ColorPicker _secondary = new();
    private readonly ColorPicker _tertiary = new();
    private bool _loading;

    public SettingsWindow(SettingsStore<HaloSettings> store, GlowController glow)
    {
        _store = store;
        _glow = glow;
        InitializeComponent();

        PrimaryHost.Content = _primary;
        SecondaryHost.Content = _secondary;
        TertiaryHost.Content = _tertiary;
        _primary.ColorChanged += (_, c) => Change(s => s.PrimaryColor = ColorPicker.ToHex(c));
        _secondary.ColorChanged += (_, c) => Change(s => s.SecondaryColor = ColorPicker.ToHex(c));
        _tertiary.ColorChanged += (_, c) => Change(s => s.TertiaryColor = ColorPicker.ToHex(c));

        PreviewGlow.Effect = new BlurEffect { Radius = 10, KernelType = KernelType.Gaussian };
        Load();

        _glow.AnyPreview = true;
        _glow.Apply();
        CompositionTarget.Rendering += OnRendering;
        Closed += (_, _) =>
        {
            CompositionTarget.Rendering -= OnRendering;
            _glow.AnyPreview = false;
            _glow.Apply();
        };
    }

    private HaloSettings S => _store.Value;

    private void Load()
    {
        _loading = true;
        try
        {
            EnabledBox.IsChecked = S.Enabled;
            ModeMusic.IsChecked = S.Mode == GlowMode.MusicSync;
            ModeBreathe.IsChecked = S.Mode == GlowMode.Breathe;
            ModeStatic.IsChecked = S.Mode == GlowMode.Static;
            LoginBox.IsChecked = S.LaunchAtLogin;
            AlbumBox.IsChecked = S.UseAlbumColors;
            TertiaryBox.IsChecked = S.UseTertiary;
            _primary.Color = ColorPicker.ParseOr(S.PrimaryColor, Colors.MediumPurple);
            _secondary.Color = ColorPicker.ParseOr(S.SecondaryColor, Colors.DeepSkyBlue);
            _tertiary.Color = ColorPicker.ParseOr(S.TertiaryColor, Colors.HotPink);
            _tertiary.IsEnabled = S.UseTertiary;
            SplitSlider.Value = S.Split;
            ThicknessSlider.Value = S.Thickness;
            GlowSlider.Value = S.Glow;
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
        var displays = DisplayInfo.All();
        foreach (var d in displays)
        {
            var box = new CheckBox
            {
                Content = d.Name,
                Tag = d.Id,
                IsChecked = S.Displays is null || S.Displays.Contains(d.Id),
                Style = (Style)FindResource("BoxCheck"),
            };
            box.Click += (_, _) => OnDisplaysChanged();
            DisplayList.Children.Add(box);
        }
        if (displays.Count == 0)
            DisplayList.Children.Add(new TextBlock { Text = "No displays found.", Style = (Style)FindResource("SubtleText") });
    }

    private void OnDisplaysChanged()
    {
        var boxes = DisplayList.Children.OfType<CheckBox>().ToList();
        var selected = boxes.Where(b => b.IsChecked == true).Select(b => (string)b.Tag).ToList();
        // All checked is stored as null, so newly connected displays get the glow too.
        Change(s => s.Displays = selected.Count == boxes.Count ? null : selected);
    }

    private void OnChanged(object sender, RoutedEventArgs e)
    {
        if (_loading) return;
        Change(s =>
        {
            s.Enabled = EnabledBox.IsChecked == true;
            s.Mode = ModeBreathe.IsChecked == true ? GlowMode.Breathe : ModeStatic.IsChecked == true ? GlowMode.Static : GlowMode.MusicSync;
            s.UseAlbumColors = AlbumBox.IsChecked == true;
            s.UseTertiary = TertiaryBox.IsChecked == true;
            var login = LoginBox.IsChecked == true;
            if (login != s.LaunchAtLogin)
            {
                s.LaunchAtLogin = login;
                LaunchAtLogin.Set("Halo", login);
            }
        });
        _tertiary.IsEnabled = S.UseTertiary;
    }

    private void OnSliderChanged(object sender, RoutedPropertyChangedEventArgs<double> e)
    {
        if (_loading || !IsInitialized) return;
        Change(s =>
        {
            s.Split = Math.Round(SplitSlider.Value, 2);
            s.Thickness = Math.Round(ThicknessSlider.Value);
            s.Glow = Math.Round(GlowSlider.Value);
        });
        UpdateLabels();
    }

    private void UpdateLabels()
    {
        if (SplitLabel is null) return;
        var p = (int)Math.Round(SplitSlider.Value * 100);
        SplitLabel.Text = $"{p} / {100 - p}";
        ThicknessLabel.Text = $"{ThicknessSlider.Value:0} px";
        GlowLabel.Text = $"{GlowSlider.Value:0} px";
    }

    private void Change(Action<HaloSettings> change)
    {
        if (_loading) return;
        change(S);
        _store.Save();
    }

    /// <summary>Mirrors the live glow in the little preview screen.</summary>
    private void OnRendering(object? sender, EventArgs e)
    {
        var frame = _glow.LastFrame;
        if (frame is null) return;
        // Scale the stroke to the preview: a 200 px wide "screen" stands for a ~1600 DIP display.
        const double k = 0.125;
        var width = Math.Max(1.5, frame.StrokeWidth * k * 2);
        PreviewRing.SetColors(frame.Colors, frame.Split);
        PreviewRing.Phase = frame.Phase;
        PreviewRing.StrokeWidth = width;
        PreviewRing.Opacity = frame.Brightness;
        PreviewRing.InvalidateVisual();

        PreviewGlow.SetColors(frame.Colors, frame.Split);
        PreviewGlow.Phase = frame.Phase;
        PreviewGlow.StrokeWidth = width * 2.4;
        PreviewGlow.CenterInset = width / 2;
        PreviewGlow.Opacity = frame.GlowRadius > 0.5 ? frame.Brightness : 0;
        if (PreviewGlow.Effect is BlurEffect blur) blur.Radius = Math.Max(0.1, frame.GlowRadius * k * 2.5);
        PreviewGlow.InvalidateVisual();

        StatusText.Text = !S.Enabled ? "The glow is off"
            : _glow.IsIdle ? "Nothing playing · breathing"
            : S.Mode switch { GlowMode.MusicSync => "Following the music", GlowMode.Breathe => "Breathing", _ => "Static" };
        var f = _glow.LastFeatures;
        AudioStatus.Text = S.Mode == GlowMode.MusicSync && S.Enabled
            ? $"System audio · bass {f.Bass:0.00} · mid {f.Mid:0.00} · treble {f.Treble:0.00}"
            : string.Empty;
    }
}
