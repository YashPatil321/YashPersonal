using System.Windows;
using System.Windows.Media;
using Lyrics;

namespace Lyra.Styles;

/// <summary>
/// Three words stacked vertically. The current word is big; the previous ones shrink upward and fade. Each new word
/// springs in from below.
/// </summary>
public sealed class StackStyle : ILyricsStyle
{
    public const double BaseSize = 64;

    // Slots: -1 = below (entering), 0 = current, 1 and 2 = previous, 3 = gone.
    private static readonly double[] SlotY = { 1.05, 0, -0.95, -1.62, -2.1 };   // in units of the big size, index slot+1
    private static readonly double[] SlotScale = { 1.0, 1.0, 0.56, 0.4, 0.32 };
    private static readonly double[] SlotAlpha = { 0.0, 1.0, 0.55, 0.25, 0.0 };

    public void Render(DrawingContext dc, Size size, LyricsFrame f, TextKit kit)
    {
        var state = f.State;
        if (!state.HasLine) return;
        var doc = f.Document;
        var look = f.Look;
        var big = BaseSize * look.Scale;
        var face = look.Face(FontWeights.Bold);
        var t = f.Time;

        // Collect the current word and the three before it (across lines).
        var words = new List<(LyricWord Word, bool IsCurrent)>(4);
        var li = state.LineIndex;
        var wi = state.WordIndex;
        if (wi >= 0) words.Add((doc.Lines[li].Words[wi], true));
        var (pl, pw) = (li, wi);
        while (words.Count < 4 && Step(doc, ref pl, ref pw)) words.Add((doc.Lines[pl].Words[pw], false));
        if (words.Count == 0) return;

        // The spring is driven by the time since the newest word began.
        var newest = words[0].Word;
        var p = Ease.Spring(t - newest.Start);
        var lineAlpha = Ease.Smooth((doc.LineVisibleUntil(li) - t) / 0.3);

        var blockHeight = big * 2.9;
        var top = f.Anchor * Math.Max(0, size.Height - blockHeight);
        var centerY = top + big * 1.75; // the current word's centre
        var cx = size.Width / 2;

        // Draw back to front. Arrays are indexed by slot + 1; a word now in slot s came from slot s - 1.
        var entering = words[0].IsCurrent;
        var count = entering ? words.Count : Math.Min(words.Count, 3);
        var pc = Math.Clamp(p, 0, 1);
        for (var k = count - 1; k >= 0; k--)
        {
            var slot = entering ? k : k + 1;
            double y, scale, alpha;
            if (entering)
            {
                y = Ease.Lerp(SlotY[slot], SlotY[slot + 1], p); // the spring may overshoot a little
                scale = Ease.Lerp(SlotScale[slot], SlotScale[slot + 1], pc);
                alpha = Ease.Lerp(SlotAlpha[slot], SlotAlpha[slot + 1], pc);
            }
            else
            {
                // The line has started but its first word has not: everything rests in place.
                y = SlotY[slot + 1];
                scale = SlotScale[slot + 1];
                alpha = SlotAlpha[slot + 1];
            }
            alpha *= lineAlpha;
            if (alpha <= 0.01) continue;

            var (word, isCurrent) = words[k];
            var fs = big * scale;
            var width = kit.Width(word.Text, fs, face);
            var height = kit.Height(fs, face);
            var origin = new Point(cx - width / 2, centerY + y * big - height / 2);
            if (isCurrent)
                kit.DrawFill(dc, word.Text, fs, face, look.Sung, look.Highlight, origin, Math.Min(1, state.WordProgress * 1.4), alpha);
            else
                kit.Draw(dc, word.Text, fs, face, look.Sung, origin, alpha);
        }
    }

    /// <summary>Moves to the previous word, crossing into earlier lines. Returns false at the start.</summary>
    private static bool Step(LyricsDocument doc, ref int line, ref int word)
    {
        word--;
        while (word < 0)
        {
            line--;
            if (line < 0) return false;
            word = doc.Lines[line].Words.Count - 1;
        }
        return true;
    }
}
