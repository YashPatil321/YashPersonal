using System.Windows;
using System.Windows.Interop;
using System.Windows.Media;
using Wave.Desktop;

namespace Wave.Panels;

/// <summary>
/// A borderless, transparent desktop widget window (visualizer or clock): no taskbar button, not in Alt+Tab, never
/// activated, click-through unless arranging. Transparency comes from DWM (frame extended over the whole client area,
/// transparent composition background), which unlike WPF's layered AllowsTransparency mode can host WebView2.
/// </summary>
internal sealed class DesktopWidgetWindow : Window
{
    private IntPtr _hwnd;
    private bool _clickThrough = true;

    public DesktopWidgetWindow(string title)
    {
        Title = title;
        WindowStyle = WindowStyle.None;
        ResizeMode = ResizeMode.NoResize;
        AllowsTransparency = false;
        Background = Brushes.Transparent;
        ShowInTaskbar = false;
        ShowActivated = false;
        WindowStartupLocation = WindowStartupLocation.Manual;
        // Start off-screen; the controller moves the window into place (in physical pixels) right after it opens.
        Left = -32000;
        Top = -32000;
        Width = 400;
        Height = 200;
    }

    /// <summary>Set once the controller has positioned the window.</summary>
    public bool Placed { get; set; }

    public IntPtr Handle => _hwnd;

    /// <summary>True when Explorer or the user closed the window (not us).</summary>
    public bool ClosedExternally { get; private set; }
    public bool ClosingByUs { get; set; }

    protected override void OnSourceInitialized(EventArgs e)
    {
        base.OnSourceInitialized(e);
        _hwnd = new WindowInteropHelper(this).Handle;
        if (HwndSource.FromHwnd(_hwnd) is { CompositionTarget: { } target }) target.BackgroundColor = Colors.Transparent;
        var margins = new Win32.MARGINS { Left = -1, Right = -1, Top = -1, Bottom = -1 };
        try { Win32.DwmExtendFrameIntoClientArea(_hwnd, ref margins); }
        catch (DllNotFoundException) { }

        var ex = Win32.GetWindowLong(_hwnd, Win32.GWL_EXSTYLE);
        ex = (ex | Win32.WS_EX_TOOLWINDOW | Win32.WS_EX_NOACTIVATE) & ~Win32.WS_EX_APPWINDOW;
        Win32.SetWindowLong(_hwnd, Win32.GWL_EXSTYLE, ex);
        ApplyClickThrough();
    }

    protected override void OnClosed(EventArgs e)
    {
        ClosedExternally = !ClosingByUs;
        base.OnClosed(e);
    }

    public bool ClickThrough
    {
        get => _clickThrough;
        set
        {
            if (_clickThrough == value) return;
            _clickThrough = value;
            ApplyClickThrough();
        }
    }

    private void ApplyClickThrough()
    {
        if (_hwnd == IntPtr.Zero) return;
        var ex = Win32.GetWindowLong(_hwnd, Win32.GWL_EXSTYLE);
        if (_clickThrough)
        {
            Win32.SetWindowLong(_hwnd, Win32.GWL_EXSTYLE, ex | Win32.WS_EX_LAYERED | Win32.WS_EX_TRANSPARENT);
            Win32.SetLayeredWindowAttributes(_hwnd, 0, 255, Win32.LWA_ALPHA);
        }
        else
        {
            Win32.SetWindowLong(_hwnd, Win32.GWL_EXSTYLE, ex & ~(Win32.WS_EX_LAYERED | Win32.WS_EX_TRANSPARENT));
        }
    }

    /// <summary>The window's rectangle in screen pixels.</summary>
    public Win32.RECT ScreenRect
    {
        get
        {
            Win32.GetWindowRect(_hwnd, out var r);
            return r;
        }
    }

    /// <summary>Places the window as a top-level window at a screen rectangle with the given z-order.</summary>
    public void PlaceTopLevel(Win32.RECT r, IntPtr insertAfter)
    {
        if (_hwnd == IntPtr.Zero) return;
        WallpaperHost.Detach(_hwnd);
        Win32.SetWindowPos(_hwnd, insertAfter, r.Left, r.Top, r.Width, r.Height, Win32.SWP_NOACTIVATE | Win32.SWP_FRAMECHANGED);
    }
}
