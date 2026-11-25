using System.Windows;
using System.Windows.Media;

namespace Lyra.Styles;

/// <summary>
/// The current line, large and centred. Sung words are full colour, upcoming words dim, and the current word fills
/// left to right with a gentle scale-up. The next line shows small underneath.
/// </summary>
public sealed class SpotlightStyle : ILyricsStyle
{
    public const double BaseSize = 44;
    private readonly FlowCache _flows = new();

    public void Render(DrawingContext dc, Size size, LyricsFrame f, TextKit kit)
    {
        var doc = f.Document;
        var look = f.Look;
        var fs = BaseSize * look.Scale;
        var nextFs = fs * 0.5;
        var face = look.Face(FontWeights.SemiBold);
        var nextFace = look.Face(FontWeights.Medium);
        var maxWidth = Math.Max(100, size.Width * 0.86);
        var lineHeight = kit.Height(fs, face) * 1.08;
        var t = f.Time;
        var state = f.State;

        int lineIndex;
        double alpha;
        var preview = false;
        if (state.HasLine)
        {
            lineIndex = state.LineIndex;
            var line = doc.Lines[lineIndex];
            alpha = Ease.Smooth((t - line.Start) / 0.22);
            var until = doc.LineVisibleUntil(lineIndex);
            var nextStart = lineIndex + 1 < doc.Lines.Count ? doc.Lines[lineIndex + 1].Start : double.PositiveInfinity;
            if (until < nextStart - 0.01) alpha *= Ease.Smooth((until - t) / 0.3); // fading into a gap
        }
        else
        {
            // In a gap: fade the upcoming line in, all dim, just before it starts.
            lineIndex = doc.NextLineAfter(t);
            if (lineIndex < 0) return;
            var lead = doc.Lines[lineIndex].Start - t;
            if (lead > 0.6) return;
            alpha = 0.7 * Ease.Smooth(1 - lead / 0.6);
            preview = true;
        }

        var current = doc.Lines[lineIndex];
        var flow = _flows.Get(current, kit, fs, face, maxWidth, center: true);
        var nextIndex = preview ? -1 : doc.NextLineAfter(current.Start);
        var next = nextIndex > lineIndex ? doc.Lines[nextIndex] : null;
        var nextHeight = next is null ? 0 : kit.Height(nextFs, nextFace) * 1.1 + fs * 0.25;
        var blockHeight = flow.Rows * lineHeight + nextHeight;
        var top = f.Anchor * Math.Max(0, size.Height - blockHeight);
        var left = (size.Width - maxWidth) / 2;

        foreach (var box in flow.Boxes)
        {
            var word = current.Words[box.Index];
            var origin = new Point(left + box.X, top + box.Row * lineHeight);
            if (preview || box.Index > state.WordIndex)
            {
                kit.Draw(dc, word.Text, fs, face, look.Dim, origin, alpha);
            }
            else if (box.Index < state.WordIndex)
            {
                kit.Draw(dc, word.Text, fs, face, look.Sung, origin, alpha);
            }
            else
            {
                var p = state.WordProgress;
                var scale = 1 + 0.07 * Math.Sin(Math.PI * Math.Min(1, p * 1.15));
                var cx = origin.X + box.Width / 2;
                var cy = origin.Y + lineHeight * 0.55;
                dc.PushTransform(new ScaleTransform(scale, scale, cx, cy));
                kit.DrawFill(dc, word.Text, fs, face, look.Dim, look.Highlight, origin, p, alpha);
                dc.Pop();
            }
        }

        if (next is not null)
        {
            var nextWidth = kit.Width(next.Text, nextFs, nextFace);
            var y = top + flow.Rows * lineHeight + fs * 0.25;
            var shown = next.Text;
            if (nextWidth > maxWidth)
            {
                // Keep it to one line: trim with an ellipsis.
                while (shown.Length > 4 && kit.Width(shown + "…", nextFs, nextFace) > maxWidth) shown = shown[..^4];
                shown += "…";
                nextWidth = kit.Width(shown, nextFs, nextFace);
            }
            kit.Draw(dc, shown, nextFs, nextFace, look.Dim, new Point((size.Width - nextWidth) / 2, y), alpha * 0.9);
        }
    }
}
