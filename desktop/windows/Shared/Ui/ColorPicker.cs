using System.Globalization;
using System.Windows;
using System.Windows.Controls;
using System.Windows.Controls.Primitives;
using System.Windows.Input;
using System.Windows.Media;
using Shared.Imaging;

namespace Shared.Ui;

/// <summary>
/// A compact colour picker: a swatch button that opens a popup with a saturation/brightness square, a hue bar,
/// preset swatches and a hex box. Optional alpha slider (for dim text colours).
/// </summary>
public sealed class ColorPicker : ContentControl
{
    public static readonly string[] Presets =
    {
        "#FF375F", "#FF453A", "#FF9F0A", "#FFD60A", "#30D158", "#66D4CF", "#40C8E0", "#64D2FF",
        "#0A84FF", "#5E5CE6", "#BF5AF2", "#FF6FD8", "#FFFFFF", "#D1D1D6", "#8E8E93", "#3A3A3C",
    };

    private readonly Border _swatch;
    private readonly Popup _popup;
    private readonly SvSquare _sv;
    private readonly HueBar _hue;
    private readonly TextBox _hex;
    private readonly Slider? _alpha;
    private Color _color = Colors.White;
    private double _h, _s, _v;
    private bool _updating;

    public ColorPicker() : this(false)
    {
    }

    public ColorPicker(bool withAlpha)
    {
        Focusable = false;
        _swatch = new Border
        {
            Width = 46,
            Height = 26,
            CornerRadius = new CornerRadius(7),
            BorderThickness = new Thickness(1),
            BorderBrush = new SolidColorBrush(Color.FromArgb(0x55, 0xFF, 0xFF, 0xFF)),
        };
        var button = new Button
        {
            Content = _swatch,
            Padding = new Thickness(3),
            HorizontalAlignment = HorizontalAlignment.Right,
            ToolTip = "Choose colour",
        };
        button.Click += (_, _) => _popup!.IsOpen = !_popup.IsOpen;

        _sv = new SvSquare { Width = 220, Height = 150, Margin = new Thickness(0, 0, 0, 10) };
        _sv.Changed += (s, v) => { _s = s; _v = v; FromHsv(); };
        _hue = new HueBar { Width = 220, Height = 14, Margin = new Thickness(0, 0, 0, 10) };
        _hue.Changed += h => { _h = h; _sv.Hue = h; FromHsv(); };

        var presets = new UniformGrid { Columns = 8, Margin = new Thickness(0, 0, 0, 10) };
        foreach (var hex in Presets)
        {
            var c = (Color)ColorConverter.ConvertFromString(hex);
            var chip = new Border
            {
                Width = 22,
                Height = 22,
                Margin = new Thickness(2),
                CornerRadius = new CornerRadius(11),
                Background = new SolidColorBrush(c),
                BorderBrush = new SolidColorBrush(Color.FromArgb(0x40, 0xFF, 0xFF, 0xFF)),
                BorderThickness = new Thickness(1),
                Cursor = Cursors.Hand,
                ToolTip = hex,
            };
            chip.MouseLeftButtonUp += (_, _) => SetColor(Color.FromArgb(_color.A, c.R, c.G, c.B), raise: true);
            presets.Children.Add(chip);
        }

        _hex = new TextBox { Width = 100, FontFamily = new FontFamily("Cascadia Mono, Consolas") };
        _hex.KeyDown += (_, e) =>
        {
            if (e.Key == Key.Enter) ApplyHex();
        };
        _hex.LostKeyboardFocus += (_, _) => ApplyHex();
        var hexRow = new DockPanel();
        hexRow.Children.Add(new TextBlock
        {
            Text = "Hex",
            VerticalAlignment = VerticalAlignment.Center,
            Margin = new Thickness(0, 0, 8, 0),
            Foreground = (Brush)FindResourceOrDefault("SubtleTextBrush", Brushes.Gray),
        });
        hexRow.Children.Add(_hex);

        var panel = new StackPanel { Width = 220 };
        panel.Children.Add(_sv);
        panel.Children.Add(_hue);
        if (withAlpha)
        {
            _alpha = new Slider { Minimum = 0.1, Maximum = 1, Margin = new Thickness(0, 0, 0, 10) };
            _alpha.ValueChanged += (_, _) =>
            {
                if (_updating) return;
                SetColor(Color.FromArgb((byte)Math.Round(_alpha.Value * 255), _color.R, _color.G, _color.B), raise: true, keepHsv: true);
            };
            var alphaRow = new DockPanel();
            alphaRow.Children.Add(new TextBlock
            {
                Text = "Opacity",
                VerticalAlignment = VerticalAlignment.Center,
                Margin = new Thickness(0, 0, 8, 10),
                Foreground = (Brush)FindResourceOrDefault("SubtleTextBrush", Brushes.Gray),
            });
            alphaRow.Children.Add(_alpha);
            panel.Children.Add(alphaRow);
        }
        panel.Children.Add(presets);
        panel.Children.Add(hexRow);

        var surface = new Border { Child = panel };
        surface.SetResourceReference(StyleProperty, "PopupSurface");
        _popup = new Popup
        {
            Child = surface,
            PlacementTarget = button,
            Placement = PlacementMode.Bottom,
            StaysOpen = false,
            AllowsTransparency = true,
            PopupAnimation = PopupAnimation.Fade,
            VerticalOffset = 6,
        };

        var root = new Grid();
        root.Children.Add(button);
        root.Children.Add(_popup);
        Content = root;
        SetColor(Colors.White, raise: false);
    }

    public event EventHandler<Color>? ColorChanged;

    public Color Color
    {
        get => _color;
        set => SetColor(value, raise: false);
    }

    public string Hex => _alpha is not null && _color.A != 255
        ? $"#{_color.A:X2}{_color.R:X2}{_color.G:X2}{_color.B:X2}"
        : $"#{_color.R:X2}{_color.G:X2}{_color.B:X2}";

    private void ApplyHex()
    {
        if (TryParse(_hex.Text, out var c))
        {
            if (_alpha is null) c.A = 255;
            SetColor(c, raise: true);
        }
        else
        {
            _hex.Text = Hex;
        }
    }

    private void FromHsv()
    {
        if (_updating) return;
        var rgb = Rgb.FromHsv(_h, _s, _v);
        SetColor(Color.FromArgb(_color.A, rgb.R, rgb.G, rgb.B), raise: true, keepHsv: true);
    }

    private void SetColor(Color c, bool raise, bool keepHsv = false)
    {
        _updating = true;
        try
        {
            _color = c;
            _swatch.Background = new SolidColorBrush(c);
            if (!keepHsv)
            {
                new Rgb(c.R, c.G, c.B).ToHsv(out var h, out var s, out var v);
                if (s > 0.01) _h = h; // keep the hue for greys
                _s = s;
                _v = v;
            }
            _sv.Hue = _h;
            _sv.Set(_s, _v);
            _hue.Hue = _h;
            if (_alpha is not null) _alpha.Value = c.A / 255.0;
            if (!_hex.IsKeyboardFocused) _hex.Text = Hex;
        }
        finally
        {
            _updating = false;
        }
        if (raise) ColorChanged?.Invoke(this, c);
    }

    private object FindResourceOrDefault(string key, object fallback) => TryFindResource(key) ?? fallback;

    /// <summary>Parses #RGB, #RRGGBB or #AARRGGBB (the # is optional).</summary>
    public static bool TryParse(string? text, out Color color)
    {
        color = Colors.White;
        if (string.IsNullOrWhiteSpace(text)) return false;
        var s = text.Trim().TrimStart('#');
        if (s.Length == 3) s = string.Concat(s.Select(ch => new string(ch, 2)));
        if (s.Length == 6) s = "FF" + s;
        if (s.Length != 8 || !uint.TryParse(s, NumberStyles.HexNumber, CultureInfo.InvariantCulture, out var v)) return false;
        color = Color.FromArgb((byte)(v >> 24), (byte)(v >> 16), (byte)(v >> 8), (byte)v);
        return true;
    }

    public static Color ParseOr(string? text, Color fallback) => TryParse(text, out var c) ? c : fallback;

    public static string ToHex(Color c, bool withAlpha = false) => withAlpha && c.A != 255
        ? $"#{c.A:X2}{c.R:X2}{c.G:X2}{c.B:X2}"
        : $"#{c.R:X2}{c.G:X2}{c.B:X2}";

    /// <summary>Saturation (x) / value (y) square for the current hue.</summary>
    private sealed class SvSquare : FrameworkElement
    {
        private double _hue;
        private double _s = 1, _v = 1;

        public event Action<double, double>? Changed;

        public double Hue
        {
            get => _hue;
            set { _hue = value; InvalidateVisual(); }
        }

        public void Set(double s, double v)
        {
            _s = s;
            _v = v;
            InvalidateVisual();
        }

        protected override void OnRender(DrawingContext dc)
        {
            var r = new Rect(RenderSize);
            var geometry = new RectangleGeometry(r, 8, 8);
            dc.PushClip(geometry);
            var pure = Rgb.FromHsv(_hue, 1, 1);
            dc.DrawRectangle(new LinearGradientBrush(Colors.White, Color.FromRgb(pure.R, pure.G, pure.B), 0), null, r);
            dc.DrawRectangle(new LinearGradientBrush(Colors.Transparent, Colors.Black, 90), null, r);
            dc.Pop();
            var p = new Point(_s * r.Width, (1 - _v) * r.Height);
            dc.DrawEllipse(null, new Pen(Brushes.Black, 3) { }, p, 7, 7);
            dc.DrawEllipse(null, new Pen(Brushes.White, 2), p, 7, 7);
        }

        protected override void OnMouseLeftButtonDown(MouseButtonEventArgs e)
        {
            CaptureMouse();
            Update(e.GetPosition(this));
            e.Handled = true;
        }

        protected override void OnMouseMove(MouseEventArgs e)
        {
            if (IsMouseCaptured) Update(e.GetPosition(this));
        }

        protected override void OnMouseLeftButtonUp(MouseButtonEventArgs e) => ReleaseMouseCapture();

        private void Update(Point p)
        {
            _s = Math.Clamp(p.X / Math.Max(1, ActualWidth), 0, 1);
            _v = Math.Clamp(1 - p.Y / Math.Max(1, ActualHeight), 0, 1);
            InvalidateVisual();
            Changed?.Invoke(_s, _v);
        }
    }

    /// <summary>A horizontal rainbow bar for picking the hue.</summary>
    private sealed class HueBar : FrameworkElement
    {
        private static readonly Brush Rainbow = BuildRainbow();
        private double _hue;

        public event Action<double>? Changed;

        public double Hue
        {
            get => _hue;
            set { _hue = value; InvalidateVisual(); }
        }

        private static Brush BuildRainbow()
        {
            var stops = new GradientStopCollection();
            for (var i = 0; i <= 6; i++)
            {
                var c = Rgb.FromHsv(i * 60, 1, 1);
                stops.Add(new GradientStop(Color.FromRgb(c.R, c.G, c.B), i / 6.0));
            }
            var b = new LinearGradientBrush(stops, 0);
            b.Freeze();
            return b;
        }

        protected override void OnRender(DrawingContext dc)
        {
            var r = new Rect(RenderSize);
            dc.DrawRoundedRectangle(Rainbow, null, r, r.Height / 2, r.Height / 2);
            var x = _hue / 360 * r.Width;
            var marker = new Rect(Math.Clamp(x - 4, 0, r.Width - 8), -2, 8, r.Height + 4);
            dc.DrawRoundedRectangle(Brushes.White, new Pen(Brushes.Black, 1), marker, 3, 3);
        }

        protected override void OnMouseLeftButtonDown(MouseButtonEventArgs e)
        {
            CaptureMouse();
            Update(e.GetPosition(this));
            e.Handled = true;
        }

        protected override void OnMouseMove(MouseEventArgs e)
        {
            if (IsMouseCaptured) Update(e.GetPosition(this));
        }

        protected override void OnMouseLeftButtonUp(MouseButtonEventArgs e) => ReleaseMouseCapture();

        private void Update(Point p)
        {
            _hue = Math.Clamp(p.X / Math.Max(1, ActualWidth), 0, 1) * 359.9;
            InvalidateVisual();
            Changed?.Invoke(_hue);
        }
    }
}
