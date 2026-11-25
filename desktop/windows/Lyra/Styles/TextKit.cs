using System.Globalization;
using System.Windows;
using System.Windows.Media;
using Lyrics;

namespace Lyra.Styles;

/// <summary>Cached <see cref="FormattedText"/> and brushes, so drawing a frame stays cheap.</summary>
public sealed class TextKit
{
    private readonly Dictionary<(string, double, Typeface, uint), FormattedText> _texts = new();
    private readonly Dictionary<uint, SolidColorBrush> _brushes = new();
    private double _pixelsPerDip = 1;

    public double PixelsPerDip
    {
        get => _pixelsPerDip;
        set
        {
            if (Math.Abs(value - _pixelsPerDip) < 1e-6) return;
            _pixelsPerDip = value;
            _texts.Clear();
        }
    }

    public Brush Brush(Color c)
    {
        var key = Key(c);
        if (!_brushes.TryGetValue(key, out var b))
        {
            b = new SolidColorBrush(c);
            b.Freeze();
            _brushes[key] = b;
        }
        return b;
    }

    public FormattedText Text(string text, double size, Typeface face, Color color)
    {
        size = Math.Round(size * 4) / 4; // bucket sizes so animated scales do not explode the cache
        var key = (text, size, face, Key(color));
        if (_texts.TryGetValue(key, out var ft)) return ft;
        if (_texts.Count > 3000) _texts.Clear();
        ft = new FormattedText(text, CultureInfo.CurrentUICulture, FlowDirection.LeftToRight, face, size, Brush(color), PixelsPerDip)
        {
            Trimming = TextTrimming.None,
        };
        _texts[key] = ft;
        return ft;
    }

    public double Width(string text, double size, Typeface face) => Text(text, size, face, Colors.White).WidthIncludingTrailingWhitespace;

    public double Height(double size, Typeface face) => Text("Ag", size, face, Colors.White).Height;

    /// <summary>Draws text with its top-left at <paramref name="origin"/>, optionally at an opacity.</summary>
    public void Draw(DrawingContext dc, string text, double size, Typeface face, Color color, Point origin, double opacity = 1)
    {
        if (opacity <= 0.003 || string.IsNullOrEmpty(text)) return;
        var ft = Text(text, size, face, color);
        if (opacity < 0.997) dc.PushOpacity(opacity);
        dc.DrawText(ft, origin);
        if (opacity < 0.997) dc.Pop();
    }

    /// <summary>
    /// Draws a word dim, then the highlight colour clipped to <paramref name="progress"/> of its width (left to right).
    /// </summary>
    public void DrawFill(DrawingContext dc, string text, double size, Typeface face, Color dim, Color fill, Point origin, double progress, double opacity = 1)
    {
        var ft = Text(text, size, face, dim);
        if (opacity < 0.997) dc.PushOpacity(opacity);
        dc.DrawText(ft, origin);
        if (progress > 0)
        {
            var w = ft.WidthIncludingTrailingWhitespace;
            // A soft edge: clip at the progress point plus a short gradient-free overlap.
            dc.PushClip(new RectangleGeometry(new Rect(origin.X - 4, origin.Y - size, (w + 8) * Math.Clamp(progress, 0, 1) + 0.5, ft.Height + size * 2)));
            dc.DrawText(Text(text, size, face, fill), origin);
            dc.Pop();
        }
        if (opacity < 0.997) dc.Pop();
    }

    private static uint Key(Color c) => ((uint)c.A << 24) | ((uint)c.R << 16) | ((uint)c.G << 8) | c.B;
}

/// <summary>A word placed by <see cref="WordFlow"/>.</summary>
public readonly record struct WordBox(int Index, double X, int Row, double Width);

/// <summary>Greedy word wrapping for lyric lines.</summary>
public sealed class WordFlow
{
    public required IReadOnlyList<WordBox> Boxes { get; init; }
    public required int Rows { get; init; }
    public required double[] RowWidths { get; init; }
    public double MaxRowWidth => RowWidths.Length == 0 ? 0 : RowWidths.Max();

    /// <param name="center">Centre each row within <paramref name="maxWidth"/>; otherwise left-align.</param>
    public static WordFlow Layout(IReadOnlyList<LyricWord> words, TextKit kit, double size, Typeface face, double maxWidth, bool center)
    {
        var space = kit.Width(" ", size, face);
        if (space <= 0) space = size * 0.28;
        var boxes = new List<WordBox>(words.Count);
        var rowWidths = new List<double>();
        double x = 0;
        var row = 0;
        var rowStart = 0;

        for (var i = 0; i < words.Count; i++)
        {
            var w = kit.Width(words[i].Text, size, face);
            if (x > 0 && x + w > maxWidth)
            {
                rowWidths.Add(TrimmedRowWidth(boxes, rowStart));
                row++;
                x = 0;
                rowStart = boxes.Count;
            }
            boxes.Add(new WordBox(i, x, row, w));
            x += w + (words[i].SpaceAfter ? space : 0);
        }
        rowWidths.Add(TrimmedRowWidth(boxes, rowStart));

        if (center)
        {
            for (var i = 0; i < boxes.Count; i++)
            {
                var b = boxes[i];
                boxes[i] = b with { X = b.X + (maxWidth - rowWidths[b.Row]) / 2 };
            }
        }
        return new WordFlow { Boxes = boxes, Rows = row + 1, RowWidths = rowWidths.ToArray() };
    }

    private static double TrimmedRowWidth(List<WordBox> boxes, int rowStart)
    {
        if (boxes.Count == rowStart) return 0;
        var last = boxes[^1];
        return last.X + last.Width - boxes[rowStart].X;
    }
}

/// <summary>Caches line layouts per style (layout depends only on the line, the font and the width).</summary>
public sealed class FlowCache
{
    private readonly Dictionary<(LyricLine, double, Typeface, double, bool), WordFlow> _cache = new();

    public WordFlow Get(LyricLine line, TextKit kit, double size, Typeface face, double maxWidth, bool center)
    {
        var key = (line, Math.Round(size, 2), face, Math.Round(maxWidth), center);
        if (_cache.TryGetValue(key, out var flow)) return flow;
        if (_cache.Count > 256) _cache.Clear();
        flow = WordFlow.Layout(line.Words, kit, size, face, maxWidth, center);
        _cache[key] = flow;
        return flow;
    }
}
