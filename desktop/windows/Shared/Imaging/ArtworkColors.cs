using System.Windows;
using System.Windows.Media;
using System.Windows.Media.Imaging;

namespace Shared.Imaging;

/// <summary>Dominant-colour extraction from WPF artwork.</summary>
public static class ArtworkColors
{
    private const int SampleSize = 48;

    /// <summary>The 2 or 3 most vibrant dominant colours, or an empty list when there is no artwork.</summary>
    public static IReadOnlyList<Color> Extract(BitmapSource? artwork, int maxColors = 3)
    {
        var pixels = Sample(artwork);
        if (pixels is null) return Array.Empty<Color>();
        return DominantColors.FromBgra(pixels, maxColors).Select(ToColor).ToList();
    }

    public static Color? MostVibrant(BitmapSource? artwork)
    {
        var colors = Extract(artwork, 1);
        return colors.Count > 0 ? colors[0] : null;
    }

    public static Color ToColor(Rgb c) => Color.FromRgb(c.R, c.G, c.B);

    /// <summary>Downscales to 48×48 BGRA bytes.</summary>
    private static byte[]? Sample(BitmapSource? source)
    {
        if (source is null || source.PixelWidth <= 0 || source.PixelHeight <= 0) return null;
        try
        {
            BitmapSource scaled = new TransformedBitmap(source,
                new ScaleTransform((double)SampleSize / source.PixelWidth, (double)SampleSize / source.PixelHeight));
            if (scaled.Format != PixelFormats.Bgra32)
                scaled = new FormatConvertedBitmap(scaled, PixelFormats.Bgra32, null, 0);
            var w = scaled.PixelWidth;
            var h = scaled.PixelHeight;
            var stride = w * 4;
            var buffer = new byte[stride * h];
            scaled.CopyPixels(new Int32Rect(0, 0, w, h), buffer, stride, 0);
            return buffer;
        }
        catch (Exception)
        {
            return null;
        }
    }
}
