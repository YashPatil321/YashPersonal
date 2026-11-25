using System.Windows;
using System.Windows.Media;
using Lyrics;

namespace Lyra.Styles;

/// <summary>Resolved appearance for drawing.</summary>
public sealed class LyricsLook
{
    public required FontFamily Family { get; init; }
    public FontStretch Stretch { get; init; } = FontStretches.Normal;
    public required FontFamily Mono { get; init; }
    public double Scale { get; init; } = 1.0;
    public Color Sung { get; init; } = Colors.White;
    public Color Highlight { get; init; } = Colors.DeepSkyBlue;
    public Color Dim { get; init; } = Color.FromArgb(0x73, 0xFF, 0xFF, 0xFF);
    public bool Shadow { get; init; } = true;

    public Typeface Face(FontWeight weight) => new(Family, FontStyles.Normal, weight, Stretch);
    public Typeface MonoFace(FontWeight weight) => new(Mono, FontStyles.Normal, weight, FontStretches.Normal);

    public static FontFamily FamilyFor(LyricFont font) => font switch
    {
        LyricFont.Rounded => new FontFamily("Segoe UI Variable Display, Arial Rounded MT Bold, Segoe UI"),
        LyricFont.Serif => new FontFamily("Georgia, Cambria, Times New Roman"),
        LyricFont.Mono => new FontFamily("Cascadia Mono, Consolas, Courier New"),
        LyricFont.Condensed => new FontFamily("Bahnschrift Condensed, Bahnschrift, Arial Narrow, Segoe UI"),
        _ => new FontFamily("Segoe UI"),
    };

    public static FontStretch StretchFor(LyricFont font) =>
        font == LyricFont.Condensed ? FontStretches.Condensed : FontStretches.Normal;
}

/// <summary>Everything a style needs for one frame.</summary>
public sealed class LyricsFrame
{
    public required LyricsDocument Document { get; init; }

    /// <summary>Lyrics time in seconds (position + offset + latency).</summary>
    public required double Time { get; init; }

    public required LyricsLook Look { get; init; }

    /// <summary>Vertical anchor of the content in the band: 0 top, 0.5 centre, 1 bottom.</summary>
    public double Anchor { get; init; } = 1;

    /// <summary>Wall-clock seconds, for effects that run when time stands still (cursor blink).</summary>
    public double WallTime { get; init; }

    private LyricsState? _state;
    public LyricsState State => _state ??= Document.StateAt(Time);
}

/// <summary>A lyric style: draws one frame.</summary>
public interface ILyricsStyle
{
    void Render(DrawingContext dc, Size size, LyricsFrame frame, TextKit text);
}

public static class Ease
{
    public static double Clamp01(double t) => Math.Clamp(t, 0, 1);
    public static double OutCubic(double t) { t = Clamp01(t); return 1 - Math.Pow(1 - t, 3); }
    public static double Smooth(double t) { t = Clamp01(t); return t * t * (3 - 2 * t); }

    /// <summary>A damped spring from 0 to 1 with a little overshoot.</summary>
    public static double Spring(double seconds)
    {
        if (seconds <= 0) return 0;
        return 1 - Math.Exp(-7.5 * seconds) * Math.Cos(10.5 * seconds);
    }

    public static double Lerp(double a, double b, double t) => a + (b - a) * t;
}
