namespace Halo;

public enum GlowMode
{
    MusicSync,
    Breathe,
    Static,
}

/// <summary>Persisted to %APPDATA%\Halo\settings.json.</summary>
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

    /// <summary>Selected display device names; null means every display.</summary>
    public List<string>? Displays { get; set; }

    public bool LaunchAtLogin { get; set; }

    public void Normalize()
    {
        Thickness = Math.Clamp(Thickness, MinThickness, MaxThickness);
        Glow = Math.Clamp(Glow, MinGlow, MaxGlow);
        Split = Math.Clamp(Split, 0.1, 0.9);
        if (!Enum.IsDefined(Mode)) Mode = GlowMode.MusicSync;
    }
}
