namespace Lyra;

public enum LyricStyle
{
    Spotlight,
    Stack,
    Thread,
    Terminal,
    Drift,
}

public enum LyricFont
{
    System,
    Rounded,
    Serif,
    Mono,
    Condensed,
}

public enum Placement
{
    Bottom,
    Centre,
    Top,
}

/// <summary>Persisted to %APPDATA%\Lyra\settings.json.</summary>
public sealed class LyraSettings
{
    public const double MinSize = 0.6, MaxSize = 2.0;
    public const double MinLatency = -1.0, MaxLatency = 1.5;

    public bool ShowLyrics { get; set; } = true;
    public LyricStyle Style { get; set; } = LyricStyle.Spotlight;
    public LyricFont Font { get; set; } = LyricFont.System;
    public double Size { get; set; } = 1.0;

    /// <summary>Sung words.</summary>
    public string TextColor { get; set; } = "#FFFFFF";

    /// <summary>The current word. Empty means the Windows accent colour.</summary>
    public string HighlightColor { get; set; } = string.Empty;

    /// <summary>Upcoming words (with alpha).</summary>
    public string DimColor { get; set; } = "#73FFFFFF";

    /// <summary>Sets the highlight to the most vibrant artwork colour.</summary>
    public bool MatchAlbumArt { get; set; }

    public bool Shadow { get; set; } = true;
    public Placement Placement { get; set; } = Placement.Bottom;

    /// <summary>Selected display device names; null means the main display.</summary>
    public List<string>? Displays { get; set; }

    public bool KeepAwake { get; set; }

    /// <summary>Added to the playback position so words light slightly early (reads as on time).</summary>
    public double Latency { get; set; } = 0.15;

    public void Normalize()
    {
        Size = Math.Clamp(Size, MinSize, MaxSize);
        Latency = Math.Clamp(Latency, MinLatency, MaxLatency);
        if (!Enum.IsDefined(Style)) Style = LyricStyle.Spotlight;
        if (!Enum.IsDefined(Font)) Font = LyricFont.System;
        if (!Enum.IsDefined(Placement)) Placement = Placement.Bottom;
    }
}
