using System.Globalization;
using System.Text.Json.Nodes;
using Shared.Settings;

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

/// <summary>The lyrics-overlay settings, built from Wave's settings dictionary by <see cref="FromWave"/>.</summary>
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

    public bool KeepAwake { get; set; }

    /// <summary>Added to the playback position so words light slightly early (reads as on time).</summary>
    public double Latency { get; set; } = 0.15;

    /// <summary>
    /// Maps the <c>lyrics*</c> keys of Wave's settings dictionary (defaults as in <c>Wave.DEFAULTS</c> in
    /// desktop/visuals/core.js). Upcoming words use the text colour at <c>lyricsDimOpacity</c>. Every display.
    /// </summary>
    public static LyraSettings FromWave(JsonObject? d)
    {
        var text = WaveKeys.String(d, "lyricsText", "#ffffff");
        var dimAlpha = Math.Clamp(WaveKeys.Number(d, "lyricsDimOpacity", 0.38), 0, 1);
        var s = new LyraSettings
        {
            ShowLyrics = WaveKeys.Bool(d, "lyricsEnabled", true),
            Style = WaveKeys.String(d, "lyricsStyle", "spotlight") switch
            {
                "stack" => LyricStyle.Stack,
                "thread" => LyricStyle.Thread,
                "terminal" => LyricStyle.Terminal,
                "drift" => LyricStyle.Drift,
                _ => LyricStyle.Spotlight,
            },
            Font = WaveKeys.String(d, "lyricsFont", "system") switch
            {
                "rounded" => LyricFont.Rounded,
                "serif" => LyricFont.Serif,
                "mono" => LyricFont.Mono,
                "condensed" => LyricFont.Condensed,
                _ => LyricFont.System,
            },
            Size = WaveKeys.Number(d, "lyricsSize", 1),
            TextColor = text,
            HighlightColor = WaveKeys.String(d, "lyricsHighlight", "#ff6b9e"),
            DimColor = WithAlpha(text, dimAlpha),
            MatchAlbumArt = WaveKeys.Bool(d, "lyricsMatchAlbum", false),
            Shadow = WaveKeys.Bool(d, "lyricsShadow", true),
            Placement = WaveKeys.String(d, "lyricsPlacement", "bottom") switch
            {
                "top" => Placement.Top,
                "center" or "centre" => Placement.Centre,
                _ => Placement.Bottom,
            },
            KeepAwake = WaveKeys.Bool(d, "lyricsKeepAwake", false),
            Latency = WaveKeys.Number(d, "lyricsLatency", 0.15),
        };
        s.Normalize();
        return s;
    }

    /// <summary>"#rrggbb" (or "#rgb") plus an opacity → "#AARRGGBB". Unparseable input gives white.</summary>
    public static string WithAlpha(string hex, double alpha)
    {
        var h = hex.Trim().TrimStart('#');
        if (h.Length == 3) h = string.Concat(h.Select(c => new string(c, 2)));
        if (h.Length == 8) h = h[2..];
        if (h.Length != 6 || !int.TryParse(h, NumberStyles.HexNumber, CultureInfo.InvariantCulture, out _)) h = "FFFFFF";
        var a = (int)Math.Round(Math.Clamp(alpha, 0, 1) * 255);
        return $"#{a:X2}{h.ToUpperInvariant()}";
    }

    public void Normalize()
    {
        Size = Math.Clamp(Size, MinSize, MaxSize);
        Latency = Math.Clamp(Latency, MinLatency, MaxLatency);
        if (!Enum.IsDefined(Style)) Style = LyricStyle.Spotlight;
        if (!Enum.IsDefined(Font)) Font = LyricFont.System;
        if (!Enum.IsDefined(Placement)) Placement = Placement.Bottom;
    }
}
