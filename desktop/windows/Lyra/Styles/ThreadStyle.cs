using System.Windows;
using System.Windows.Media;
using Lyrics;
using Shared.Ui;

namespace Lyra.Styles;

/// <summary>
/// Chat bubbles, one per line. The newest slides up from the bottom and words appear inside it as they are sung.
/// The previous two bubbles stay above it, faded. Alternate lines sit left (grey) or right (accent).
/// </summary>
public sealed class ThreadStyle : ILyricsStyle
{
    public const double BaseSize = 24;
    private static readonly Color Grey = Color.FromArgb(0xEB, 0x3A, 0x3A, 0x3E);
    private static readonly double[] Fade = { 1.0, 0.62, 0.34 };
    private readonly FlowCache _flows = new();

    private readonly record struct Bubble(LyricLine Line, int Index, WordFlow Flow, int VisibleWords, double Width, double Height);

    public void Render(DrawingContext dc, Size size, LyricsFrame f, TextKit kit)
    {
        var doc = f.Document;
        var look = f.Look;
        var t = f.Time;
        var fs = BaseSize * look.Scale;
        var face = look.Face(FontWeights.Medium);
        var padX = 16 * look.Scale;
        var padY = 9 * look.Scale;
        var gap = 10 * look.Scale;
        var radius = 18 * look.Scale;
        var lineHeight = kit.Height(fs, face) * 1.02;
        var columnWidth = Math.Min(size.Width * 0.8, 980 * look.Scale);
        var maxBubbleText = Math.Min(columnWidth * 0.72, 640 * look.Scale);

        // The newest bubble is the current line, or (in a short gap) the line that just finished.
        var state = f.State;
        int newest;
        double groupAlpha = 1;
        if (state.HasLine)
        {
            newest = state.LineIndex;
        }
        else
        {
            newest = LastStartedLine(doc, t);
            if (newest < 0) return;
            groupAlpha = Ease.Smooth(1 - (t - doc.LineVisibleUntil(newest)) / 0.5);
            if (groupAlpha <= 0) return;
        }

        // Newest plus the two lines with text before it.
        var bubbles = new List<Bubble>(3);
        for (var i = newest; i >= 0 && bubbles.Count < 3; i--)
        {
            var line = doc.Lines[i];
            if (line.IsInstrumental || line.Words.Count == 0) continue;
            var flow = _flows.Get(line, kit, fs, face, maxBubbleText, center: false);
            var visible = i == newest ? CountVisible(line, t) : line.Words.Count;
            var (w, rows) = Extent(flow, visible);
            var height = Math.Max(1, rows) * lineHeight + padY * 2;
            var width = Math.Max(radius * 2, w + padX * 2);
            bubbles.Add(new Bubble(line, i, flow, visible, width, height));
        }
        if (bubbles.Count == 0) return;

        var total = bubbles.Sum(b => b.Height) + gap * (bubbles.Count - 1);
        var bottom = f.Anchor * Math.Max(0, size.Height - total) + total;

        // Slide everything up as the newest bubble arrives.
        var arrive = Ease.OutCubic((t - bubbles[0].Line.Start) / 0.38);
        var slide = (1 - arrive) * (bubbles[0].Height + gap);
        var colLeft = (size.Width - columnWidth) / 2;
        var colRight = colLeft + columnWidth;

        var y = bottom + slide;
        for (var k = 0; k < bubbles.Count; k++)
        {
            var b = bubbles[k];
            y -= b.Height;
            var alpha = Fade[k] * groupAlpha * (k == 0 ? Ease.Smooth(arrive * 1.6) : 1);
            if (k == 0 && b.VisibleWords == 0) alpha *= 0.85;
            var right = b.Index % 2 == 1;
            var fill = right ? look.Highlight : Grey;
            var textColor = right ? (Accent.Luminance(look.Highlight) > 0.62 ? Color.FromRgb(0x10, 0x10, 0x12) : Colors.White) : look.Sung;
            var x = right ? colRight - b.Width : colLeft;
            var rect = new Rect(x, y, b.Width, b.Height);

            if (alpha > 0.005)
            {
                dc.PushOpacity(alpha);
                dc.DrawRoundedRectangle(kit.Brush(fill), null, rect, radius, radius);
                for (var wi = 0; wi < b.VisibleWords; wi++)
                {
                    var box = b.Flow.Boxes[wi];
                    var word = b.Line.Words[box.Index];
                    var wordAlpha = 1.0;
                    if (k == 0 && wi == b.VisibleWords - 1 && state.HasLine && state.WordIndex == wi)
                        wordAlpha = Ease.Smooth(state.WordProgress * 5); // the newest word pops in
                    kit.Draw(dc, word.Text, fs, face, textColor, new Point(x + padX + box.X, y + padY + box.Row * lineHeight), wordAlpha);
                }
                if (k == 0 && b.VisibleWords == 0) DrawTypingDots(dc, kit, rect, textColor, f.WallTime, look.Scale);
                dc.Pop();
            }
            y -= gap;
        }
    }

    private static int CountVisible(LyricLine line, double t)
    {
        var n = 0;
        while (n < line.Words.Count && line.Words[n].Start <= t) n++;
        return n;
    }

    private static (double Width, int Rows) Extent(WordFlow flow, int visible)
    {
        if (visible <= 0) return (36, 1);
        double w = 0;
        var rows = 0;
        for (var i = 0; i < visible; i++)
        {
            var b = flow.Boxes[i];
            w = Math.Max(w, b.X + b.Width);
            rows = Math.Max(rows, b.Row + 1);
        }
        return (w, rows);
    }

    private static int LastStartedLine(LyricsDocument doc, double t)
    {
        for (var i = doc.Lines.Count - 1; i >= 0; i--)
        {
            if (doc.Lines[i].Start <= t && !doc.Lines[i].IsInstrumental) return i;
        }
        return -1;
    }

    private static void DrawTypingDots(DrawingContext dc, TextKit kit, Rect bubble, Color color, double wall, double scale)
    {
        var r = 3.2 * scale;
        var cx = bubble.X + bubble.Width / 2 - r * 3.2;
        var cy = bubble.Y + bubble.Height / 2;
        for (var i = 0; i < 3; i++)
        {
            var a = 0.35 + 0.65 * Math.Max(0, Math.Sin(wall * 6 - i * 0.9));
            dc.PushOpacity(a);
            dc.DrawEllipse(kit.Brush(color), null, new Point(cx + i * r * 3.2, cy), r, r);
            dc.Pop();
        }
    }
}
