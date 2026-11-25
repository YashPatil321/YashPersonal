using System.Windows.Media;

namespace Halo;

/// <summary>Everything needed to draw one frame of the glow.</summary>
public sealed record GlowFrame(
    IReadOnlyList<Color> Colors,
    double Split,
    double Phase,
    double StrokeWidth,
    double GlowRadius,
    double Brightness);
