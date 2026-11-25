using System.Text;
using System.Windows;
using System.Windows.Media;
using Lyrics;

namespace Lyra.Styles;

/// <summary>
/// Monospaced text on a dark translucent panel. Each line is typed out as it is sung after a <c>&gt;</c> prompt, with a
/// blinking block cursor. The previous three lines stay above.
/// </summary>
public sealed class TerminalStyle : ILyricsStyle
{
    public const double BaseSize = 20;
    private const int VisibleRows = 5;
    private static readonly Color Panel = Color.FromArgb(0xD0, 0x0C, 0x0D, 0x10);
    private static readonly Color PanelBorder = Color.FromArgb(0x30, 0xFF, 0xFF, 0xFF);
    private static readonly Color Header = Color.FromArgb(0xFF, 0x1A, 0x1B, 0x20);

    public void Render(DrawingContext dc, Size size, LyricsFrame f, TextKit kit)
    {
        var doc = f.Document;
        var look = f.Look;
        var t = f.Time;
        var fs = BaseSize * look.Scale;
        var face = look.MonoFace(FontWeights.Normal);
        var bold = look.MonoFace(FontWeights.SemiBold);
        var charWidth = Math.Max(1, kit.Width("MMMMMMMMMM", fs, face) / 10);
        var lineHeight = fs * 1.45;
        var pad = 16 * look.Scale;
        var headerHeight = 26 * look.Scale;
        var width = Math.Min(size.Width * 0.8, 920 * look.Scale);
        var height = headerHeight + pad * 2 + VisibleRows * lineHeight;
        var left = (size.Width - width) / 2;
        var top = f.Anchor * Math.Max(0, size.Height - height);
        var radius = 10 * look.Scale;
        var maxChars = Math.Max(10, (int)((width - pad * 2) / charWidth) - 2);

        // Panel and title bar.
        var panelRect = new Rect(left, top, width, height);
        dc.DrawRoundedRectangle(kit.Brush(Panel), new Pen(kit.Brush(PanelBorder), 1), panelRect, radius, radius);
        dc.PushClip(new RectangleGeometry(panelRect, radius, radius));
        dc.DrawRectangle(kit.Brush(Header), null, new Rect(left, top, width, headerHeight));
        dc.Pop();
        var dotY = top + headerHeight / 2;
        var dotR = 5.5 * look.Scale;
        Color[] dots = { Color.FromRgb(0xFF, 0x5F, 0x57), Color.FromRgb(0xFE, 0xBC, 0x2E), Color.FromRgb(0x28, 0xC8, 0x40) };
        for (var i = 0; i < 3; i++)
            dc.DrawEllipse(kit.Brush(dots[i]), null, new Point(left + pad + dotR + i * dotR * 3.2, dotY), dotR, dotR);
        var titleSize = fs * 0.62;
        var title = "lyra — lyrics";
        kit.Draw(dc, title, titleSize, face, Color.FromArgb(0x90, 0xFF, 0xFF, 0xFF),
            new Point(left + (width - kit.Width(title, titleSize, face)) / 2, dotY - kit.Height(titleSize, face) / 2));

        // Rows: up to three finished lines, then the line being typed.
        var state = f.State;
        var rows = new List<(string Text, bool Current)>();
        var current = state.HasLine ? state.LineIndex : -1;
        var lastStarted = LastStarted(doc, t);
        var historyEnd = current >= 0 ? current - 1 : lastStarted;
        var history = new List<string>();
        for (var i = historyEnd; i >= 0 && history.Count < 3; i--)
        {
            if (doc.Lines[i].IsInstrumental) continue;
            history.Insert(0, doc.Lines[i].Text);
        }
        foreach (var h in history)
            foreach (var r in Wrap(h, maxChars)) rows.Add((r, false));

        var typed = current >= 0 ? TypedText(doc.Lines[current], state, t) : string.Empty;
        var typedRows = Wrap(typed, maxChars);
        for (var i = 0; i < typedRows.Count; i++) rows.Add((typedRows[i], true));
        if (typedRows.Count == 0) rows.Add((string.Empty, true));

        // Bottom-align the rows in the panel.
        var firstRow = Math.Max(0, rows.Count - VisibleRows);
        var textTop = top + headerHeight + pad;
        var promptWidth = charWidth * 2;
        var promptColor = look.Highlight;
        var firstOfCurrent = rows.FindIndex(r => r.Current);
        for (var i = firstRow; i < rows.Count; i++)
        {
            var (text, isCurrent) = rows[i];
            var y = textTop + (i - firstRow + (VisibleRows - Math.Min(VisibleRows, rows.Count))) * lineHeight;
            var x = left + pad;
            var isFirstOfLine = isCurrent ? i == firstOfCurrent : IsFirstRowOfHistoryLine(rows, i, history, maxChars);
            if (isFirstOfLine)
                kit.Draw(dc, ">", fs, bold, promptColor, new Point(x, y), isCurrent ? 1 : 0.45);
            kit.Draw(dc, text, fs, isCurrent ? bold : face, look.Sung, new Point(x + promptWidth, y), isCurrent ? 1 : 0.5);

            if (isCurrent && i == rows.Count - 1)
            {
                // Block cursor: solid while typing, blinking when idle.
                var typing = state.HasLine && state.WordIndex >= 0 && state.WordProgress < 1;
                var on = typing || (f.WallTime * 1.8 % 1.0) < 0.55;
                if (on)
                {
                    var cx = x + promptWidth + kit.Width(text, fs, bold);
                    dc.DrawRectangle(kit.Brush(look.Highlight), null, new Rect(cx + 1, y + fs * 0.12, charWidth * 0.95, fs * 1.18));
                }
            }
        }
    }

    private static bool IsFirstRowOfHistoryLine(List<(string Text, bool Current)> rows, int index, List<string> history, int maxChars)
    {
        var r = 0;
        foreach (var h in history)
        {
            if (r == index) return true;
            r += Math.Max(1, Wrap(h, maxChars).Count);
            if (r > index) return false;
        }
        return false;
    }

    /// <summary>The characters typed so far: whole words already sung, plus part of the current word.</summary>
    private static string TypedText(LyricLine line, LyricsState state, double t)
    {
        var sb = new StringBuilder();
        for (var i = 0; i < line.Words.Count; i++)
        {
            var w = line.Words[i];
            if (i < state.WordIndex)
            {
                sb.Append(w.Text);
                if (w.SpaceAfter) sb.Append(' ');
            }
            else if (i == state.WordIndex)
            {
                // Typing runs a little ahead of singing so the word is complete before it ends.
                var chars = (int)Math.Ceiling(w.Text.Length * Math.Min(1, state.WordProgress * 1.6 + 0.05));
                sb.Append(w.Text, 0, Math.Clamp(chars, 0, w.Text.Length));
                if (chars >= w.Text.Length && w.SpaceAfter && state.WordProgress >= 0.95) sb.Append(' ');
            }
            else
            {
                break;
            }
        }
        return sb.ToString();
    }

    private static List<string> Wrap(string text, int maxChars)
    {
        var rows = new List<string>();
        if (string.IsNullOrEmpty(text)) return rows;
        var remaining = text;
        while (remaining.Length > maxChars)
        {
            var cut = remaining.LastIndexOf(' ', maxChars);
            if (cut <= 0) cut = maxChars;
            rows.Add(remaining[..cut]);
            remaining = remaining[cut..].TrimStart();
        }
        rows.Add(remaining);
        return rows;
    }

    private static int LastStarted(LyricsDocument doc, double t)
    {
        for (var i = doc.Lines.Count - 1; i >= 0; i--)
            if (doc.Lines[i].Start <= t) return i;
        return -1;
    }
}
