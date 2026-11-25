using System.Windows;
using System.Windows.Media.Animation;
using Shared.Overlay;

namespace Lyra;

/// <summary>A click-through band across one display that shows the lyrics. Fades in and out over 300 ms.</summary>
public sealed class LyricsOverlayWindow : OverlayWindow
{
    public static readonly Duration FadeDuration = new(TimeSpan.FromMilliseconds(300));

    private bool _wantShown;

    public LyricsOverlayWindow(DisplayInfo display, Func<Styles.LyricsFrame?> frameSource)
    {
        Title = "Lyra lyrics";
        Canvas = new LyricsCanvas { FrameSource = frameSource };
        Content = Canvas;
        Opacity = 0;
        Display = display;
    }

    public LyricsCanvas Canvas { get; }

    public DisplayInfo Display { get; private set; }

    /// <summary>Places the band (physical pixels) for a placement and text scale.</summary>
    public void Place(DisplayInfo display, Placement placement, double scale)
    {
        Display = display;
        var b = display.Bounds;
        var dpi = display.Scale;
        var heightDip = Math.Min(b.Height / dpi * 0.6, 300 * scale + 60);
        var height = (int)Math.Round(heightDip * dpi);
        var margin = (int)Math.Round(b.Height * 0.07);
        var y = placement switch
        {
            Placement.Top => b.Y + margin,
            Placement.Centre => b.Y + (b.Height - height) / 2,
            _ => b.Y + b.Height - height - margin,
        };
        PhysicalBounds = new Int32Rect(b.X, y, b.Width, height);
    }

    /// <summary>Fades the window in or out (and hides it when fully faded out, so it stops rendering).</summary>
    public void SetShown(bool shown)
    {
        if (shown == _wantShown) return;
        _wantShown = shown;
        if (shown && !IsVisible) Show();

        var anim = new DoubleAnimation(shown ? 1 : 0, FadeDuration)
        {
            EasingFunction = new QuadraticEase { EasingMode = EasingMode.EaseInOut },
        };
        anim.Completed += (_, _) =>
        {
            if (!_wantShown) Hide();
        };
        BeginAnimation(OpacityProperty, anim);
    }
}
