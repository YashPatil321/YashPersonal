using System.Runtime.InteropServices;
using System.Windows;
using System.Windows.Interop;
using System.Windows.Media;
using Wave.Desktop;

namespace Wave.Panels;

/// <summary>
/// A borderless, transparent desktop widget window (visualizer or clock): no taskbar button, not in Alt+Tab, never
/// activated (WS_EX_NOACTIVATE, so clicks do not steal focus). Click-through only in the wallpaper placement. In the
/// desktop placement it is pinned to the bottom of the z-order (forced in WM_WINDOWPOSCHANGING) so it sits behind
/// every app window, except while Show Desktop is active (<see cref="DesktopRaised"/>). Transparency comes from DWM (frame extended over the whole client area,
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

    private Win32.RECT? _intended;

    public IntPtr Handle => _hwnd;

    /// <summary>Desktop placement: keep the window at the bottom of the z-order.</summary>
    public bool PinnedToBottom { get; private set; }

    /// <summary>Show Desktop is active: the window is temporarily raised above the desktop so it stays visible.</summary>
    public bool DesktopRaised { get; private set; }

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

        HwndSource.FromHwnd(_hwnd)?.AddHook(WndProc);
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
        PinnedToBottom = false;
        DesktopRaised = false;
        _intended = r;
        WallpaperHost.Detach(_hwnd);
        Win32.SetWindowPos(_hwnd, insertAfter, r.Left, r.Top, r.Width, r.Height, Win32.SWP_NOACTIVATE | Win32.SWP_FRAMECHANGED);
    }

    /// <summary>The desktop placement: top-level, interactive, behind every other window.</summary>
    public void PlaceOnDesktop(Win32.RECT r)
    {
        if (_hwnd == IntPtr.Zero) return;
        PlaceTopLevel(r, Win32.HWND_BOTTOM);
        PinnedToBottom = true;
    }

    /// <summary>Records where the window should be when it was put there by someone else (the wallpaper host).</summary>
    public void Remember(Win32.RECT r)
    {
        PinnedToBottom = false;
        DesktopRaised = false;
        _intended = r;
    }

    /// <summary>Moves or resizes without touching the z-order (drag and resize loops).</summary>
    public void MoveTo(Win32.RECT r)
    {
        if (_hwnd == IntPtr.Zero) return;
        _intended = r;
        if (Win32.GetParent(_hwnd) is var parent && parent != IntPtr.Zero && (Win32.GetWindowLong(_hwnd, Win32.GWL_STYLE) & Win32.WS_CHILD) != 0)
        {
            var pt = new Win32.POINT { X = r.Left, Y = r.Top };
            Win32.ScreenToClient(parent, ref pt);
            Win32.SetWindowPos(_hwnd, IntPtr.Zero, pt.X, pt.Y, r.Width, r.Height, Win32.SWP_NOACTIVATE | Win32.SWP_NOZORDER);
            return;
        }
        Win32.SetWindowPos(_hwnd, IntPtr.Zero, r.Left, r.Top, r.Width, r.Height, Win32.SWP_NOACTIVATE | Win32.SWP_NOZORDER);
    }

    /// <summary>
    /// Show Desktop / Win+D brought the desktop to the front: re-show the window if it was hidden or minimised and lift
    /// it above the desktop (topmost for now). Called with false when another window takes the foreground again.
    /// </summary>
    public void SetDesktopRaised(bool raised)
    {
        if (_hwnd == IntPtr.Zero || !PinnedToBottom || !IsVisible) return;
        if (raised)
        {
            if (Win32.IsIconic(_hwnd) || !Win32.IsWindowVisible(_hwnd)) Win32.ShowWindow(_hwnd, Win32.SW_SHOWNOACTIVATE);
            DesktopRaised = true;
            Win32.SetWindowPos(_hwnd, Win32.HWND_TOPMOST, 0, 0, 0, 0, Win32.SWP_NOMOVE | Win32.SWP_NOSIZE | Win32.SWP_NOACTIVATE);
        }
        else if (DesktopRaised)
        {
            DesktopRaised = false;
            // Moving a topmost window to HWND_BOTTOM also clears its topmost state.
            Win32.SetWindowPos(_hwnd, Win32.HWND_BOTTOM, 0, 0, 0, 0, Win32.SWP_NOMOVE | Win32.SWP_NOSIZE | Win32.SWP_NOACTIVATE);
        }
    }

    protected override void OnDpiChanged(DpiScale oldDpi, DpiScale newDpi)
    {
        base.OnDpiChanged(oldDpi, newDpi);
        // Windows suggests a DPI-scaled rectangle when the window crosses monitors; keep ours (physical pixels).
        if (_intended is { } r) Dispatcher.BeginInvoke(new Action(() => MoveTo(r)), System.Windows.Threading.DispatcherPriority.Render);
    }

    private IntPtr WndProc(IntPtr hwnd, int msg, IntPtr wParam, IntPtr lParam, ref bool handled)
    {
        if (msg == Win32.WM_WINDOWPOSCHANGING && PinnedToBottom && !DesktopRaised && lParam != IntPtr.Zero)
        {
            var pos = Marshal.PtrToStructure<Win32.WINDOWPOS>(lParam);
            if ((pos.flags & Win32.SWP_NOZORDER) == 0 && pos.hwndInsertAfter != Win32.HWND_BOTTOM)
            {
                pos.hwndInsertAfter = Win32.HWND_BOTTOM;
                Marshal.StructureToPtr(pos, lParam, fDeleteOld: false);
            }
        }
        return IntPtr.Zero;
    }
}
