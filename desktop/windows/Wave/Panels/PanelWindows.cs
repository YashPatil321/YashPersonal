using System.Windows;
using System.Windows.Interop;
using System.Windows.Media;
using Wave.Desktop;

namespace Wave.Panels;

/// <summary>The dashboard: a normal, resizable dark window.</summary>
internal sealed class DashboardWindow : Window
{
    public DashboardWindow()
    {
        Title = "Wave";
        Width = 1060;
        Height = 760;
        MinWidth = 720;
        MinHeight = 520;
        Background = new SolidColorBrush(Color.FromRgb(0x0A, 0x0A, 0x0F));
        WindowStartupLocation = WindowStartupLocation.CenterScreen;
        Shared.Ui.DarkChrome.Apply(this);
    }
}

/// <summary>The full-screen player: borderless and topmost on one monitor, with keyboard focus.</summary>
internal sealed class FullscreenWindow : Window
{
    private readonly Win32.RECT _bounds;

    public FullscreenWindow(Win32.RECT bounds)
    {
        _bounds = bounds;
        Title = "Wave";
        WindowStyle = WindowStyle.None;
        ResizeMode = ResizeMode.NoResize;
        Background = Brushes.Black;
        ShowInTaskbar = false;
        Topmost = true;
        WindowStartupLocation = WindowStartupLocation.Manual;
    }

    protected override void OnSourceInitialized(EventArgs e)
    {
        base.OnSourceInitialized(e);
        var hwnd = new WindowInteropHelper(this).Handle;
        Win32.SetWindowPos(hwnd, Win32.HWND_TOPMOST, _bounds.Left, _bounds.Top, _bounds.Width, _bounds.Height, Win32.SWP_SHOWWINDOW);
    }

    protected override void OnDpiChanged(DpiScale oldDpi, DpiScale newDpi)
    {
        base.OnDpiChanged(oldDpi, newDpi);
        var hwnd = new WindowInteropHelper(this).Handle;
        Dispatcher.BeginInvoke(new Action(() =>
            Win32.SetWindowPos(hwnd, Win32.HWND_TOPMOST, _bounds.Left, _bounds.Top, _bounds.Width, _bounds.Height, Win32.SWP_NOACTIVATE)));
    }

    /// <summary>The monitor under the mouse pointer, in screen pixels.</summary>
    public static Win32.RECT MonitorUnderCursor()
    {
        Win32.GetCursorPos(out var p);
        var s = System.Windows.Forms.Screen.FromPoint(new System.Drawing.Point(p.X, p.Y)).Bounds;
        return new Win32.RECT { Left = s.Left, Top = s.Top, Right = s.Right, Bottom = s.Bottom };
    }
}
