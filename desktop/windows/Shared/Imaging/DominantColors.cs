namespace Shared.Imaging;

/// <summary>An sRGB colour with 0..255 channels. Platform-neutral.</summary>
public readonly record struct Rgb(byte R, byte G, byte B)
{
    public string ToHex() => $"#{R:X2}{G:X2}{B:X2}";

    public void ToHsv(out double h, out double s, out double v)
    {
        double r = R / 255.0, g = G / 255.0, b = B / 255.0;
        double max = Math.Max(r, Math.Max(g, b)), min = Math.Min(r, Math.Min(g, b));
        var d = max - min;
        v = max;
        s = max <= 0 ? 0 : d / max;
        if (d <= 1e-9) h = 0;
        else if (max == r) h = 60 * (((g - b) / d % 6 + 6) % 6);
        else if (max == g) h = 60 * ((b - r) / d + 2);
        else h = 60 * ((r - g) / d + 4);
    }

    public static Rgb FromHsv(double h, double s, double v)
    {
        h = ((h % 360) + 360) % 360;
        s = Math.Clamp(s, 0, 1);
        v = Math.Clamp(v, 0, 1);
        var c = v * s;
        var x = c * (1 - Math.Abs(h / 60 % 2 - 1));
        var m = v - c;
        (double r, double g, double b) = h switch
        {
            < 60 => (c, x, 0.0),
            < 120 => (x, c, 0.0),
            < 180 => (0.0, c, x),
            < 240 => (0.0, x, c),
            < 300 => (x, 0.0, c),
            _ => (c, 0.0, x),
        };
        return new Rgb(ToByte(r + m), ToByte(g + m), ToByte(b + m));
    }

    private static byte ToByte(double d) => (byte)Math.Clamp(Math.Round(d * 255), 0, 255);
}

/// <summary>
/// Picks the most vibrant dominant colours of an image. Pixels are bucketed by hue (24 buckets of 15°); each bucket is
/// scored by <c>pixelCount × vibrancy</c> where vibrancy favours saturated, bright pixels. The best buckets that are at
/// least 30° apart in hue win, and each result is the average colour of its bucket's most vibrant pixels.
/// </summary>
public static class DominantColors
{
    private const int HueBuckets = 24;

    /// <param name="bgra">Pixels in BGRA order (4 bytes each), any size; sample a downscaled copy for speed.</param>
    public static IReadOnlyList<Rgb> FromBgra(ReadOnlySpan<byte> bgra, int maxColors = 3)
    {
        var count = new double[HueBuckets];
        var sumR = new double[HueBuckets];
        var sumG = new double[HueBuckets];
        var sumB = new double[HueBuckets];
        var hueX = new double[HueBuckets];
        var hueY = new double[HueBuckets];
        double greyR = 0, greyG = 0, greyB = 0, greyN = 0;

        for (var i = 0; i + 3 < bgra.Length; i += 4)
        {
            if (bgra[i + 3] < 128) continue;
            var px = new Rgb(bgra[i + 2], bgra[i + 1], bgra[i]);
            px.ToHsv(out var h, out var s, out var v);
            if (s < 0.2 || v < 0.18)
            {
                greyR += px.R; greyG += px.G; greyB += px.B; greyN++;
                continue;
            }
            var weight = s * s * (0.35 + 0.65 * v);
            var bucket = (int)(h / (360.0 / HueBuckets)) % HueBuckets;
            count[bucket] += weight;
            sumR[bucket] += px.R * weight;
            sumG[bucket] += px.G * weight;
            sumB[bucket] += px.B * weight;
            hueX[bucket] += Math.Cos(h * Math.PI / 180) * weight;
            hueY[bucket] += Math.Sin(h * Math.PI / 180) * weight;
        }

        // Smooth buckets with their neighbours so a hue straddling a boundary is not split.
        var score = new double[HueBuckets];
        for (var b = 0; b < HueBuckets; b++)
            score[b] = count[b] + 0.5 * (count[(b + 1) % HueBuckets] + count[(b + HueBuckets - 1) % HueBuckets]);

        var picked = new List<(Rgb Color, double Hue)>();
        var order = Enumerable.Range(0, HueBuckets).Where(b => count[b] > 0).OrderByDescending(b => score[b]).ToList();
        var total = count.Sum();
        foreach (var b in order)
        {
            if (picked.Count >= maxColors) break;
            if (count[b] < total * 0.02 && picked.Count >= 1) continue; // ignore specks once we have a main colour
            var hue = (Math.Atan2(hueY[b], hueX[b]) * 180 / Math.PI + 360) % 360;
            if (picked.Any(p => HueDistance(p.Hue, hue) < 30)) continue;
            var c = new Rgb(
                (byte)Math.Clamp(sumR[b] / count[b], 0, 255),
                (byte)Math.Clamp(sumG[b] / count[b], 0, 255),
                (byte)Math.Clamp(sumB[b] / count[b], 0, 255));
            picked.Add((Vivid(c), hue));
        }

        var result = picked.Select(p => p.Color).ToList();
        if (result.Count == 0)
        {
            if (greyN == 0) return result;
            // Monochrome artwork: use its average tone, lifted so it still glows.
            var g = new Rgb((byte)(greyR / greyN), (byte)(greyG / greyN), (byte)(greyB / greyN));
            g.ToHsv(out var gh, out var gs, out var gv);
            result.Add(Rgb.FromHsv(gh, gs, Math.Max(gv, 0.75)));
        }

        // Always return at least two colours: derive a companion from the main colour.
        if (result.Count == 1 && maxColors >= 2)
        {
            result[0].ToHsv(out var h, out var s, out var v);
            result.Add(Rgb.FromHsv(h + 40, s, Math.Max(v, 0.7)));
        }
        return result;
    }

    /// <summary>The single most vibrant colour, or null for an empty image.</summary>
    public static Rgb? MostVibrant(ReadOnlySpan<byte> bgra)
    {
        var colors = FromBgra(bgra, 1);
        return colors.Count > 0 ? colors[0] : null;
    }

    /// <summary>Lifts value and saturation a little so glows stay bright on dark album art.</summary>
    private static Rgb Vivid(Rgb c)
    {
        c.ToHsv(out var h, out var s, out var v);
        return Rgb.FromHsv(h, Math.Min(1, s * 1.1), Math.Max(v, 0.72));
    }

    private static double HueDistance(double a, double b)
    {
        var d = Math.Abs(a - b) % 360;
        return d > 180 ? 360 - d : d;
    }
}
