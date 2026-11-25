using System.Windows;
using System.Windows.Media;

namespace Halo;

/// <summary>
/// Draws a rectangle stroke hugging the element's edge, coloured with an angular (conic) gradient that can rotate.
/// WPF has no conic brush, so the perimeter is cut into short segments, each filled with the gradient colour at its
/// angle from the centre. Colours come from a cached palette of frozen brushes, so a frame allocates nothing heavy.
/// </summary>
public sealed class GlowSurface : FrameworkElement
{
    private const int PaletteSize = 256;
    private readonly Brush[] _palette = new Brush[PaletteSize];
    private Color[] _colors = { Colors.White, Colors.White };
    private double _split = 0.6;
    private bool _paletteDirty = true;

    public GlowSurface()
    {
        IsHitTestVisible = false;
        SnapsToDevicePixels = false;
    }

    /// <summary>Rotation in turns (0..1).</summary>
    public double Phase { get; set; }

    /// <summary>Stroke width in DIPs.</summary>
    public double StrokeWidth { get; set; } = 10;

    /// <summary>Distance of the stroke's centre line from the edge. Defaults to half the stroke width.</summary>
    public double? CenterInset { get; set; }

    public double CornerRadius { get; set; }

    public void SetColors(IReadOnlyList<Color> colors, double split)
    {
        if (colors.Count == 0) return;
        if (_colors.Length == colors.Count && _split == split && _colors.SequenceEqual(colors)) return;
        _colors = colors.ToArray();
        _split = split;
        _paletteDirty = true;
    }

    /// <summary>The gradient colour at angle fraction <paramref name="f"/> (0 = top centre, clockwise).</summary>
    public static Color ColorAt(IReadOnlyList<Color> colors, double split, double f)
    {
        f -= Math.Floor(f);
        var n = colors.Count;
        if (n == 1) return colors[0];

        // Regions: primary gets `split`; the remaining share is divided evenly between the others.
        Span<double> starts = stackalloc double[4];
        Span<double> widths = stackalloc double[4];
        starts[0] = 0;
        widths[0] = split;
        var rest = (1 - split) / (n - 1);
        for (var i = 1; i < n; i++)
        {
            starts[i] = split + rest * (i - 1);
            widths[i] = rest;
        }

        var region = n - 1;
        for (var i = 0; i < n; i++)
        {
            if (f < starts[i] + widths[i]) { region = i; break; }
        }

        var next = (region + 1) % n;
        var prev = (region + n - 1) % n;
        var toEnd = starts[region] + widths[region] - f;
        var fromStart = f - starts[region];
        var halfNext = 0.35 * Math.Min(widths[region], widths[next]);
        var halfPrev = 0.35 * Math.Min(widths[region], widths[prev]);

        if (toEnd < halfNext) return Mix(colors[region], colors[next], Smooth(0.5 - toEnd / (2 * halfNext)));
        if (fromStart < halfPrev) return Mix(colors[region], colors[prev], Smooth(0.5 - fromStart / (2 * halfPrev)));
        return colors[region];
    }

    private static double Smooth(double t)
    {
        t = Math.Clamp(t, 0, 1);
        return t * t * (3 - 2 * t);
    }

    public static Color Mix(Color a, Color b, double t) => Color.FromArgb(
        (byte)Math.Round(a.A + (b.A - a.A) * t),
        (byte)Math.Round(a.R + (b.R - a.R) * t),
        (byte)Math.Round(a.G + (b.G - a.G) * t),
        (byte)Math.Round(a.B + (b.B - a.B) * t));

    private void RebuildPalette()
    {
        for (var i = 0; i < PaletteSize; i++)
        {
            var b = new SolidColorBrush(ColorAt(_colors, _split, (double)i / PaletteSize));
            b.Freeze();
            _palette[i] = b;
        }
        _paletteDirty = false;
    }

    private Brush BrushAt(double x, double y, double cx, double cy)
    {
        // Angle from the top, clockwise, plus rotation.
        var f = Math.Atan2(x - cx, cy - y) / (2 * Math.PI) + Phase;
        f -= Math.Floor(f);
        return _palette[Math.Min(PaletteSize - 1, (int)(f * PaletteSize))];
    }

    protected override void OnRender(DrawingContext dc)
    {
        var size = RenderSize;
        var w = StrokeWidth;
        if (size.Width < 4 || size.Height < 4 || w <= 0) return;
        if (_paletteDirty) RebuildPalette();

        var inset = CenterInset ?? w / 2;
        var left = inset;
        var top = inset;
        var right = size.Width - inset;
        var bottom = size.Height - inset;
        if (right <= left || bottom <= top) return;
        var cx = size.Width / 2;
        var cy = size.Height / 2;
        var half = w / 2;

        if (CornerRadius > 0) dc.PushClip(new RectangleGeometry(new Rect(size), CornerRadius, CornerRadius));

        var perimeter = 2 * (right - left + bottom - top);
        var step = Math.Max(6, perimeter / 420);
        const double overlap = 0.6; // hides anti-aliasing seams between segments

        // Top edge, left to right.
        for (var x = left; x < right; x += step)
        {
            var x1 = Math.Min(right, x + step);
            dc.DrawRectangle(BrushAt((x + x1) / 2, top, cx, cy), null,
                new Rect(x - overlap, top - half, x1 - x + 2 * overlap, w));
        }
        // Right edge, top to bottom.
        for (var y = top; y < bottom; y += step)
        {
            var y1 = Math.Min(bottom, y + step);
            dc.DrawRectangle(BrushAt(right, (y + y1) / 2, cx, cy), null,
                new Rect(right - half, y - overlap, w, y1 - y + 2 * overlap));
        }
        // Bottom edge, right to left.
        for (var x = right; x > left; x -= step)
        {
            var x0 = Math.Max(left, x - step);
            dc.DrawRectangle(BrushAt((x + x0) / 2, bottom, cx, cy), null,
                new Rect(x0 - overlap, bottom - half, x - x0 + 2 * overlap, w));
        }
        // Left edge, bottom to top.
        for (var y = bottom; y > top; y -= step)
        {
            var y0 = Math.Max(top, y - step);
            dc.DrawRectangle(BrushAt(left, (y + y0) / 2, cx, cy), null,
                new Rect(left - half, y0 - overlap, w, y - y0 + 2 * overlap));
        }
        // Corners.
        dc.DrawRectangle(BrushAt(left, top, cx, cy), null, new Rect(left - half, top - half, w, w));
        dc.DrawRectangle(BrushAt(right, top, cx, cy), null, new Rect(right - half, top - half, w, w));
        dc.DrawRectangle(BrushAt(right, bottom, cx, cy), null, new Rect(right - half, bottom - half, w, w));
        dc.DrawRectangle(BrushAt(left, bottom, cx, cy), null, new Rect(left - half, bottom - half, w, w));

        if (CornerRadius > 0) dc.Pop();
    }
}
