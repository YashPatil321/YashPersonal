using System.Windows;
using System.Windows.Media;
using System.Windows.Media.Effects;
using Lyra.Styles;

namespace Lyra;

/// <summary>
/// Draws lyrics with the chosen style, re-rendering on every <c>CompositionTarget.Rendering</c> while visible.
/// Used both by the overlay and by the settings preview.
/// </summary>
public sealed class LyricsCanvas : FrameworkElement
{
    private readonly TextKit _kit = new();
    private readonly Dictionary<LyricStyle, ILyricsStyle> _styles = new();
    private readonly DropShadowEffect _shadow = new()
    {
        Color = Colors.Black,
        BlurRadius = 10,
        ShadowDepth = 1.5,
        Direction = 270,
        Opacity = 0.75,
        RenderingBias = RenderingBias.Performance,
    };
    private bool _subscribed;

    public LyricsCanvas()
    {
        IsHitTestVisible = false;
        IsVisibleChanged += (_, _) => UpdateSubscription();
        Loaded += (_, _) => UpdateSubscription();
        Unloaded += (_, _) => UpdateSubscription();
    }

    /// <summary>Supplies the frame to draw, or null to draw nothing.</summary>
    public Func<LyricsFrame?>? FrameSource { get; set; }

    public LyricStyle StyleKind { get; set; } = LyricStyle.Spotlight;

    private void UpdateSubscription()
    {
        var want = IsLoaded && IsVisible;
        if (want == _subscribed) return;
        _subscribed = want;
        if (want) CompositionTarget.Rendering += OnRendering;
        else CompositionTarget.Rendering -= OnRendering;
    }

    private LyricsFrame? _frame;

    private void OnRendering(object? sender, EventArgs e)
    {
        _frame = FrameSource?.Invoke();
        // Toggle the shadow here, not in OnRender (changing Effect during a render pass re-dirties the visual).
        var wantShadow = _frame?.Look.Shadow == true;
        if (wantShadow && Effect is null) Effect = _shadow;
        else if (!wantShadow && Effect is not null) Effect = null;
        InvalidateVisual();
    }

    protected override void OnRender(DrawingContext dc)
    {
        var frame = _frame ?? FrameSource?.Invoke();
        _frame = null;
        if (frame is null || frame.Document.Lines.Count == 0) return;

        _kit.PixelsPerDip = VisualTreeHelper.GetDpi(this).PixelsPerDip;
        if (!_styles.TryGetValue(StyleKind, out var style))
        {
            style = StyleKind switch
            {
                LyricStyle.Stack => new StackStyle(),
                LyricStyle.Thread => new ThreadStyle(),
                LyricStyle.Terminal => new TerminalStyle(),
                LyricStyle.Drift => new DriftStyle(),
                _ => new SpotlightStyle(),
            };
            _styles[StyleKind] = style;
        }
        style.Render(dc, RenderSize, frame, _kit);
    }
}
