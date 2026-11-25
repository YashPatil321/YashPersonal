using System.Windows.Controls;
using System.Windows.Media.Effects;
using Shared.Overlay;

namespace Halo;

/// <summary>One click-through overlay per display: a blurred, wider copy of the ring under the sharp ring.</summary>
public sealed class GlowWindow : OverlayWindow
{
    /// <summary>Halo draws square corners on Windows (the spec's corner radius is 0 here).</summary>
    public const double CornerRadiusDip = 0;

    private readonly GlowSurface _glow = new();
    private readonly GlowSurface _ring = new();
    private readonly BlurEffect _blur = new() { KernelType = KernelType.Gaussian, RenderingBias = RenderingBias.Performance };
    private GlowFrame? _last;

    public GlowWindow(DisplayInfo display)
    {
        Display = display;
        Title = "Halo glow";
        _glow.Effect = _blur;
        _glow.CornerRadius = _ring.CornerRadius = CornerRadiusDip;
        var root = new Grid { IsHitTestVisible = false };
        root.Children.Add(_glow);
        root.Children.Add(_ring);
        Content = root;
        PhysicalBounds = display.Bounds;
    }

    public DisplayInfo Display { get; private set; }

    public void Move(DisplayInfo display)
    {
        Display = display;
        PhysicalBounds = display.Bounds;
    }

    public void Render(GlowFrame frame)
    {
        if (_last is not null && Same(_last, frame)) return;
        // Brightness alone only changes opacity, which needs no re-render.
        var redraw = _last is null || !SameShape(_last, frame);
        _last = frame;

        _ring.SetColors(frame.Colors, frame.Split);
        _ring.Phase = frame.Phase;
        _ring.StrokeWidth = frame.StrokeWidth;
        _ring.Opacity = Math.Clamp(frame.Brightness, 0, 1);
        if (redraw) _ring.InvalidateVisual();

        var glowVisible = frame.GlowRadius > 0.5;
        _glow.Visibility = glowVisible ? System.Windows.Visibility.Visible : System.Windows.Visibility.Collapsed;
        if (glowVisible)
        {
            _glow.SetColors(frame.Colors, frame.Split);
            _glow.Phase = frame.Phase;
            // The glow copy is wider, sits on the same centre line, and is blurred by the glow radius.
            _glow.StrokeWidth = frame.StrokeWidth * 2.2 + frame.GlowRadius * 0.35;
            _glow.CenterInset = frame.StrokeWidth / 2;
            _glow.Opacity = Math.Clamp(frame.Brightness * 1.1, 0, 1);
            if (Math.Abs(_blur.Radius - frame.GlowRadius) > 0.01) _blur.Radius = frame.GlowRadius;
            if (redraw) _glow.InvalidateVisual();
        }
    }

    private static bool Same(GlowFrame a, GlowFrame b) =>
        Math.Abs(a.Brightness - b.Brightness) < 1e-3 && SameShape(a, b);

    private static bool SameShape(GlowFrame a, GlowFrame b) =>
        Math.Abs(a.Phase - b.Phase) < 1e-5 &&
        Math.Abs(a.StrokeWidth - b.StrokeWidth) < 1e-3 && Math.Abs(a.GlowRadius - b.GlowRadius) < 1e-3 &&
        Math.Abs(a.Split - b.Split) < 1e-6 && a.Colors.SequenceEqual(b.Colors);
}
