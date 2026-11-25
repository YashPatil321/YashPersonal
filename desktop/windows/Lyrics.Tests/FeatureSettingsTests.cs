using System.Text.Json.Nodes;
using Halo;
using Lyra;
using Xunit;

namespace Lyrics.Tests;

/// <summary>Wave's settings dictionary → the glow and lyrics feature settings.</summary>
public class FeatureSettingsTests
{
    [Fact]
    public void EmptyDictionaryUsesWebDefaults()
    {
        var h = HaloSettings.FromWave(new JsonObject());
        Assert.False(h.Enabled);
        Assert.Equal(GlowMode.MusicSync, h.Mode);
        Assert.True(h.UseAlbumColors);
        Assert.False(h.UseTertiary);
        Assert.Equal(("#ff2e6b", "#3873ff", "#9e4dff"), (h.PrimaryColor, h.SecondaryColor, h.TertiaryColor));
        Assert.Equal((0.6, 10.0, 36.0), (h.Split, h.Thickness, h.Glow));

        var l = LyraSettings.FromWave(null);
        Assert.True(l.ShowLyrics);
        Assert.Equal(LyricStyle.Spotlight, l.Style);
        Assert.Equal(LyricFont.System, l.Font);
        Assert.Equal(1.0, l.Size);
        Assert.Equal("#ffffff", l.TextColor);
        Assert.Equal("#ff6b9e", l.HighlightColor);
        Assert.Equal("#61FFFFFF", l.DimColor); // 0.38 × 255 = 97 = 0x61
        Assert.Equal(Placement.Bottom, l.Placement);
        Assert.True(l.Shadow);
        Assert.False(l.KeepAwake);
        Assert.Equal(0.15, l.Latency);
    }

    [Fact]
    public void MapsGlowKeys()
    {
        var d = JsonNode.Parse("""
            {"glowEnabled":true,"glowMode":"still","glowAlbumColors":false,"glowColorCount":3,
             "glowPrimary":"#112233","glowSecondary":"#445566","glowTertiary":"#778899",
             "glowSplit":0.7,"glowThickness":24,"glowSize":50,"glowNotch":false}
            """)!.AsObject();
        var h = HaloSettings.FromWave(d);
        Assert.True(h.Enabled);
        Assert.Equal(GlowMode.Static, h.Mode);
        Assert.False(h.UseAlbumColors);
        Assert.True(h.UseTertiary);
        Assert.Equal(("#112233", "#445566", "#778899"), (h.PrimaryColor, h.SecondaryColor, h.TertiaryColor));
        Assert.Equal((0.7, 24.0, 50.0), (h.Split, h.Thickness, h.Glow));
        Assert.Equal(GlowMode.Breathe, HaloSettings.FromWave(new JsonObject { ["glowMode"] = "breathe" }).Mode);
    }

    [Fact]
    public void ClampsAndToleratesBadValues()
    {
        var h = HaloSettings.FromWave(new JsonObject { ["glowThickness"] = 500, ["glowSize"] = "12", ["glowEnabled"] = "yes", ["glowSplit"] = 0 });
        Assert.Equal(HaloSettings.MaxThickness, h.Thickness);
        Assert.Equal(12, h.Glow);      // numeric strings are accepted
        Assert.False(h.Enabled);       // a wrong type falls back to the default
        Assert.Equal(0.1, h.Split);

        var l = LyraSettings.FromWave(new JsonObject { ["lyricsSize"] = 9, ["lyricsLatency"] = -5, ["lyricsStyle"] = 3 });
        Assert.Equal(LyraSettings.MaxSize, l.Size);
        Assert.Equal(LyraSettings.MinLatency, l.Latency);
        Assert.Equal(LyricStyle.Spotlight, l.Style);
    }

    [Fact]
    public void MapsLyricsKeys()
    {
        var d = JsonNode.Parse("""
            {"lyricsEnabled":false,"lyricsStyle":"terminal","lyricsFont":"condensed","lyricsSize":1.4,
             "lyricsText":"#80c0ff","lyricsHighlight":"#00ff00","lyricsDimOpacity":0.5,"lyricsMatchAlbum":true,
             "lyricsShadow":false,"lyricsPlacement":"center","lyricsKeepAwake":true,"lyricsLatency":0.3}
            """)!.AsObject();
        var l = LyraSettings.FromWave(d);
        Assert.False(l.ShowLyrics);
        Assert.Equal(LyricStyle.Terminal, l.Style);
        Assert.Equal(LyricFont.Condensed, l.Font);
        Assert.Equal(1.4, l.Size);
        Assert.Equal("#80c0ff", l.TextColor);
        Assert.Equal("#00ff00", l.HighlightColor);
        Assert.Equal("#8080C0FF", l.DimColor);
        Assert.True(l.MatchAlbumArt);
        Assert.False(l.Shadow);
        Assert.Equal(Placement.Centre, l.Placement);
        Assert.True(l.KeepAwake);
        Assert.Equal(0.3, l.Latency);
        Assert.Equal(Placement.Top, LyraSettings.FromWave(new JsonObject { ["lyricsPlacement"] = "top" }).Placement);
        Assert.Equal(LyricStyle.Drift, LyraSettings.FromWave(new JsonObject { ["lyricsStyle"] = "drift" }).Style);
    }

    [Theory]
    [InlineData("#abc", 1.0, "#FFAABBCC")]
    [InlineData("#112233", 0, "#00112233")]
    [InlineData("#FF112233", 0.5, "#80112233")]
    [InlineData("nonsense", 0.38, "#61FFFFFF")]
    public void WithAlpha(string hex, double alpha, string expected) => Assert.Equal(expected, LyraSettings.WithAlpha(hex, alpha));
}
