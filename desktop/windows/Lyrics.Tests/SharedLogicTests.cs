using Shared.Audio;
using Shared.Imaging;
using Shared.NowPlaying;
using Xunit;

namespace Lyrics.Tests;

/// <summary>Tests for the platform-neutral parts of the Windows Shared library (linked into this project).</summary>
public class SharedLogicTests
{
    [Fact]
    public void ClockExtrapolatesWhilePlayingAndFreezesWhenPaused()
    {
        var c = new PositionClock();
        c.Report(10, playing: true, now: 100);
        Assert.Equal(12.5, c.PositionAt(102.5), 6);
        c.Report(13, playing: false, now: 103);
        Assert.Equal(13, c.PositionAt(110), 6);
    }

    [Fact]
    public void ClockSnapsOnLargeDifference()
    {
        var c = new PositionClock();
        c.Report(10, true, 100);
        c.Report(30, true, 101); // seek
        Assert.Equal(30, c.PositionAt(101), 6);
    }

    [Fact]
    public void ClockEasesSmallDifferencesWithoutGoingBackwards()
    {
        var c = new PositionClock();
        c.Report(10, true, 100);
        c.Report(10.8, true, 101); // extrapolated 11.0, reported 10.8 (-0.2): ease, do not jump back
        var previous = c.PositionAt(101);
        Assert.Equal(11.0, previous, 6);
        for (var t = 101.01; t < 104; t += 0.01)
        {
            var p = c.PositionAt(t);
            Assert.True(p >= previous, $"went backwards at {t}");
            previous = p;
        }
        Assert.Equal(10.8 + 3, c.PositionAt(104), 1);
    }

    [Fact]
    public void FftFindsASineBin()
    {
        var re = new double[1024];
        var im = new double[1024];
        for (var i = 0; i < re.Length; i++) re[i] = Math.Sin(2 * Math.PI * 32 * i / re.Length);
        SpectrumAnalyzer.Fft(re, im);
        var mags = re.Select((r, i) => Math.Sqrt(r * r + im[i] * im[i])).Take(512).ToArray();
        Assert.Equal(32, Array.IndexOf(mags, mags.Max()));
    }

    [Fact]
    public void AnalyzerDetectsKickDrumBeats()
    {
        const double rate = 44100;
        var a = new SpectrumAnalyzer();
        var block = new float[SpectrumAnalyzer.BlockSize];
        var beats = new List<double>();
        var blockSeconds = SpectrumAnalyzer.BlockSize / rate;
        long sample = 0;

        for (var b = 0; b < 200; b++)
        {
            var t = b * blockSeconds;
            for (var i = 0; i < block.Length; i++, sample++)
            {
                var ts = sample / rate;
                var sinceKick = ts % 0.5; // 120 bpm
                var kick = Math.Exp(-sinceKick * 30) * Math.Sin(2 * Math.PI * 60 * ts);
                var hat = 0.05 * Math.Sin(2 * Math.PI * 5000 * ts);
                block[i] = (float)(0.8 * kick + hat);
            }
            if (a.Process(block, rate, t)) beats.Add(t);
        }

        // ~4.6 s of audio at 120 bpm: about 9 kicks. Allow for warm-up.
        Assert.InRange(beats.Count, 6, 10);
        for (var i = 1; i < beats.Count; i++) Assert.True(beats[i] - beats[i - 1] >= SpectrumAnalyzer.BeatMinInterval);

        var f = a.Features(beats[^1]);
        Assert.Equal(1.0, f.Beat, 6);
        Assert.InRange(f.Bass, 0, 1);
        Assert.Equal(Math.Pow(0.88, 6), a.Features(beats[^1] + 0.1).Beat, 6);
    }

    [Fact]
    public void DominantColorsPicksVibrantDistinctHues()
    {
        // 60% red, 30% blue, 10% grey.
        var pixels = new List<byte>();
        void Add(int n, byte r, byte g, byte b) { for (var i = 0; i < n; i++) pixels.AddRange(new[] { b, g, r, (byte)255 }); }
        Add(600, 220, 30, 40);
        Add(300, 30, 60, 230);
        Add(100, 128, 128, 128);

        var colors = DominantColors.FromBgra(pixels.ToArray());
        Assert.True(colors.Count >= 2);
        colors[0].ToHsv(out var h0, out _, out _);
        colors[1].ToHsv(out var h1, out _, out _);
        Assert.True(h0 < 15 || h0 > 345, $"first hue {h0}");
        Assert.InRange(h1, 210, 240);
    }

    [Fact]
    public void DominantColorsHandlesGreyArtwork()
    {
        var grey = Enumerable.Repeat(new byte[] { 90, 90, 90, 255 }, 50).SelectMany(x => x).ToArray();
        Assert.Equal(2, DominantColors.FromBgra(grey).Count);
        Assert.Empty(DominantColors.FromBgra(Array.Empty<byte>()));
    }
}
