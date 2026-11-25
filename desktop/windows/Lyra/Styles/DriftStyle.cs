using System.Windows;
using System.Windows.Media;

namespace Lyra.Styles;

/// <summary>
/// Each word appears where the previous one left off, then floats upward and fades out over about two seconds,
/// so a line leaves a trail.
/// </summary>
public sealed class DriftStyle : ILyricsStyle
{
    public const double BaseSize = 40;
    public const double LifeSeconds = 2.1;
    private readonly FlowCache _flows = new();

    public void Render(DrawingContext dc, Size size, LyricsFrame f, TextKit kit)
    {
        var doc = f.Document;
        if (doc.Lines.Count == 0) return;
        var look = f.Look;
        var t = f.Time;
        var fs = BaseSize * look.Scale;
        var face = look.Face(FontWeights.SemiBold);
        var lineHeight = kit.Height(fs, face) * 1.05;
        var rise = 74 * look.Scale;
        var maxWidth = Math.Max(100, size.Width * 0.86);
        var left = (size.Width - maxWidth) / 2;
        var state = f.State;

        // Lines whose words may still be visible: the latest started line and the one before it.
        var last = -1;
        for (var i = doc.Lines.Count - 1; i >= 0; i--)
        {
            if (doc.Lines[i].Start <= t) { last = i; break; }
        }
        if (last < 0) return;

        for (var li = Math.Max(0, last - 1); li <= last; li++)
        {
            var line = doc.Lines[li];
            if (line.IsInstrumental || line.Words.Count == 0) continue;
            var flow = _flows.Get(line, kit, fs, face, maxWidth, center: true);
            var blockHeight = flow.Rows * lineHeight + rise;
            var top = f.Anchor * Math.Max(0, size.Height - blockHeight) + rise;

            foreach (var box in flow.Boxes)
            {
                var word = line.Words[box.Index];
                var age = t - word.Start;
                if (age < 0 || age > LifeSeconds) continue;

                var appear = Ease.Smooth(age / 0.14);
                var fade = 1 - Ease.Smooth((age - 0.35) / (LifeSeconds - 0.35));
                var alpha = appear * fade;
                if (alpha <= 0.01) continue;
                var lift = rise * Ease.OutCubic(age / LifeSeconds) * 0.9 + rise * 0.1 * (1 - appear);
                var origin = new Point(left + box.X, top + box.Row * lineHeight - lift);
                var isCurrent = state.HasLine && li == state.LineIndex && box.Index == state.WordIndex;
                var color = isCurrent ? look.Highlight : look.Sung;
                if (isCurrent)
                {
                    var s = 1 + 0.05 * (1 - Ease.Smooth(age / 0.4));
                    dc.PushTransform(new ScaleTransform(s, s, origin.X + box.Width / 2, origin.Y + lineHeight / 2));
                    kit.Draw(dc, word.Text, fs, face, color, origin, alpha);
                    dc.Pop();
                }
                else
                {
                    kit.Draw(dc, word.Text, fs, face, color, origin, alpha);
                }
            }
        }
    }
}
