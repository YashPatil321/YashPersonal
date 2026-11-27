using System.Windows.Threading;
using Wave.Desktop;

namespace Wave.Panels;

/// <summary>
/// Moves or resizes a widget while the mouse button is held. WebView2's input lives in another process, so instead of
/// WM_NCLBUTTONDOWN tricks this polls the cursor (every ~8 ms) and moves the window by the cursor delta, in physical
/// pixels. Resizing keeps the top-left corner fixed.
/// </summary>
internal sealed class WindowDragger
{
    private readonly DispatcherTimer _timer = new(DispatcherPriority.Input) { Interval = TimeSpan.FromMilliseconds(8) };
    private DesktopWidgetWindow? _window;
    private Win32.POINT _startCursor;
    private Win32.RECT _startRect;
    private bool _resize;
    private int _minWidth, _minHeight;
    private Action<DesktopWidgetWindow>? _done;

    public WindowDragger() => _timer.Tick += (_, _) => Step();

    public bool IsActive => _window is not null;

    /// <param name="minWidth">Minimum size in physical pixels (resize only).</param>
    public void Start(DesktopWidgetWindow window, bool resize, int minWidth, int minHeight, Action<DesktopWidgetWindow> done)
    {
        Finish();
        if (!Win32.GetCursorPos(out _startCursor)) return;
        _window = window;
        _startRect = window.ScreenRect;
        _resize = resize;
        _minWidth = minWidth;
        _minHeight = minHeight;
        _done = done;
        _timer.Start();
        Step();
    }

    private void Step()
    {
        if (_window is not { } w) return;
        if (!Win32.PrimaryButtonDown() || !Win32.GetCursorPos(out var p))
        {
            Finish();
            return;
        }
        int dx = p.X - _startCursor.X, dy = p.Y - _startCursor.Y;
        var r = _startRect;
        Win32.RECT next;
        if (_resize)
        {
            var width = Math.Max(_minWidth, r.Width + dx);
            var height = Math.Max(_minHeight, r.Height + dy);
            next = new Win32.RECT { Left = r.Left, Top = r.Top, Right = r.Left + width, Bottom = r.Top + height };
        }
        else
        {
            next = new Win32.RECT { Left = r.Left + dx, Top = r.Top + dy, Right = r.Right + dx, Bottom = r.Bottom + dy };
        }
        var cur = w.ScreenRect;
        if (cur.Left != next.Left || cur.Top != next.Top || cur.Width != next.Width || cur.Height != next.Height) w.MoveTo(next);
    }

    public void Finish()
    {
        _timer.Stop();
        var w = _window;
        var done = _done;
        _window = null;
        _done = null;
        if (w is not null) done?.Invoke(w);
    }
}
