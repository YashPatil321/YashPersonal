using System.Text.Json.Nodes;
using Shared.Settings;

namespace Halo;

public enum GlowMode
{
    MusicSync,
    Breathe,
    Static,
}

/// <summary>The screen-glow settings, built from Wave's settings dictionary by <see cref="FromWave"/>.</summary>
public sealed class HaloSettings
{
    public const double MinThickness = 2, MaxThickness = 60;
    public const double MinGlow = 0, MaxGlow = 80;

    public bool Enabled { get; set; } = true;
    public GlowMode Mode { get; set; } = GlowMode.MusicSync;
    public bool UseAlbumColors { get; set; } = true;
    public string PrimaryColor { get; set; } = "#7C5CFF";
    public string SecondaryColor { get; set; } = "#00D4FF";
    public string TertiaryColor { get; set; } = "#FF4FA3";
    public bool UseTertiary { get; set; } = true;

    /// <summary>Share of the ring given to the primary colour (default 60/40).</summary>
    public double Split { get; set; } = 0.6;

    public double Thickness { get; set; } = 10;
    public double Glow { get; set; } = 36;

    /// <summary>
    /// Maps the <c>glow*</c> keys of Wave's settings dictionary (defaults as in <c>Wave.DEFAULTS</c> in
    /// desktop/visuals/core.js). <c>glowNotch</c> is macOS only and ignored. The glow covers every display.
    /// </summary>
    public static HaloSettings FromWave(JsonObject? d)
    {
        var s = new HaloSettings
        {
            Enabled = WaveKeys.Bool(d, "glowEnabled", false),
            Mode = WaveKeys.String(d, "glowMode", "music") switch
            {
                "breathe" => GlowMode.Breathe,
                "still" => GlowMode.Static,
                _ => GlowMode.MusicSync,
            },
            UseAlbumColors = WaveKeys.Bool(d, "glowAlbumColors", true),
            UseTertiary = WaveKeys.Number(d, "glowColorCount", 2) >= 3,
            PrimaryColor = WaveKeys.String(d, "glowPrimary", "#ff2e6b"),
            SecondaryColor = WaveKeys.String(d, "glowSecondary", "#3873ff"),
            TertiaryColor = WaveKeys.String(d, "glowTertiary", "#9e4dff"),
            Split = WaveKeys.Number(d, "glowSplit", 0.6),
            Thickness = WaveKeys.Number(d, "glowThickness", 10),
            Glow = WaveKeys.Number(d, "glowSize", 36),
        };
        s.Normalize();
        return s;
    }

    public void Normalize()
    {
        Thickness = Math.Clamp(Thickness, MinThickness, MaxThickness);
        Glow = Math.Clamp(Glow, MinGlow, MaxGlow);
        Split = Math.Clamp(Split, 0.1, 0.9);
        if (!Enum.IsDefined(Mode)) Mode = GlowMode.MusicSync;
    }
}

