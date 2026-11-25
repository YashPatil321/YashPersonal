using System.Windows;
using System.Windows.Interop;
using System.Windows.Media;
using System.Windows.Threading;

namespace Shared.Overlay;

/// <summary>
/// A transparent, borderless, click-through, topmost window that never takes focus and is hidden from Alt+Tab.
/// It is placed in physical pixels with <c>SetWindowPos</c>, so it covers exactly the requested rectangle on any
/// monitor whatever its DPI.
/// </summary>
public class OverlayWindow : Window
{
    private readonly DispatcherTimer _topmostTimer;
    private Int32Rect _physicalBounds;
    private IntPtr _hwnd;

    public OverlayWindow()
    {
        WindowStyle = WindowStyle.None;
        AllowsTransparency = true; // WPF makes this a WS_EX_LAYERED window with per-pixel alpha
        Background = Brushes.Transparent;
        ResizeMode = ResizeMode.NoResize;
        ShowInTaskbar = false;
        ShowActivated = false;
        Topmost = true;
        Focusable = false;
        IsHitTestVisible = false;
        WindowStartupLocation = WindowStartupLocation.Manual;
        SnapsToDevicePixels = true;
        UseLayoutRounding = true;

        // Full-screen apps and the taskbar can push us down; re-assert topmost every couple of seconds.
        _topmostTimer = new DispatcherTimer(DispatcherPriority.Background) { Interval = TimeSpan.FromSeconds(2) };
        _topmostTimer.Tick += (_, _) => ApplyPlacement();
    }

    public IntPtr Handle => _hwnd;

    /// <summary>The rectangle (physical pixels) this window covers.</summary>
    public Int32Rect PhysicalBounds
    {
        get => _physicalBounds;
        set
        {
            _physicalBounds = value;
            if (_hwnd != IntPtr.Zero) ApplyPlacement();
            else
            {
                // A first guess in DIPs so the window opens near the right place before SetWindowPos runs.
                var scale = DisplayInfo.ScaleFor(value.X + value.Width / 2, value.Y + value.Height / 2);
                Left = value.X / scale;
                Top = value.Y / scale;
                Width = Math.Max(1, value.Width / scale);
                Height = Math.Max(1, value.Height / scale);
            }
        }
    }

    protected override void OnSourceInitialized(EventArgs e)
    {
        base.OnSourceInitialized(e);
        _hwnd = new WindowInteropHelper(this).Handle;
        MakeClickThrough(_hwnd);
        ApplyPlacement();
        _topmostTimer.Start();
    }

    protected override void OnDpiChanged(DpiScale oldDpi, DpiScale newDpi)
    {
        base.OnDpiChanged(oldDpi, newDpi);
        // Windows suggests a scaled rectangle on a DPI change; put the window back where we want it.
        Dispatcher.BeginInvoke(new Action(ApplyPlacement), DispatcherPriority.Render);
    }

    protected override void OnClosed(EventArgs e)
    {
        _topmostTimer.Stop();
        base.OnClosed(e);
    }

    /// <summary>Adds the click-through extended styles.</summary>
    public static void MakeClickThrough(IntPtr hwnd)
    {
        var ex = Native.GetWindowLong(hwnd, Native.GWL_EXSTYLE);
        ex |= Native.WS_EX_TRANSPARENT | Native.WS_EX_LAYERED | Native.WS_EX_TOOLWINDOW | Native.WS_EX_NOACTIVATE;
        ex &= ~Native.WS_EX_APPWINDOW;
        Native.SetWindowLong(hwnd, Native.GWL_EXSTYLE, ex);
    }

    private void ApplyPlacement()
    {
        if (_hwnd == IntPtr.Zero || _physicalBounds.Width <= 0 || _physicalBounds.Height <= 0) return;
        Native.SetWindowPos(_hwnd, Native.HWND_TOPMOST,
            _physicalBounds.X, _physicalBounds.Y, _physicalBounds.Width, _physicalBounds.Height,
            Native.SWP_NOACTIVATE | Native.SWP_NOOWNERZORDER);
    }
}
