using System.Windows;
using System.Windows.Interop;
using Shared.Overlay;

namespace Shared.Ui;

/// <summary>Dark title bar and rounded corners for ordinary (settings) windows.</summary>
public static class DarkChrome
{
    public static void Apply(Window window)
    {
        if (new WindowInteropHelper(window).Handle != IntPtr.Zero) ApplyNow(window);
        else window.SourceInitialized += (_, _) => ApplyNow(window);
    }

    private static void ApplyNow(Window window)
    {
        var hwnd = new WindowInteropHelper(window).Handle;
        try
        {
            var on = 1;
            if (Native.DwmSetWindowAttribute(hwnd, Native.DWMWA_USE_IMMERSIVE_DARK_MODE, ref on, sizeof(int)) != 0)
                Native.DwmSetWindowAttribute(hwnd, Native.DWMWA_USE_IMMERSIVE_DARK_MODE_OLD, ref on, sizeof(int));
            var round = Native.DWMWCP_ROUND;
            Native.DwmSetWindowAttribute(hwnd, Native.DWMWA_WINDOW_CORNER_PREFERENCE, ref round, sizeof(int));
        }
        catch (DllNotFoundException)
        {
        }
        catch (EntryPointNotFoundException)
        {
        }
    }

    /// <summary>Shows a settings window, or brings the existing one to the front.</summary>
    public static T ShowSingle<T>(ref T? current, Func<T> create) where T : Window
    {
        if (current is { IsLoaded: true })
        {
            if (current.WindowState == WindowState.Minimized) current.WindowState = WindowState.Normal;
            current.Activate();
            return current;
        }
        var w = create();
        Apply(w);
        current = w;
        w.Show();
        w.Activate();
        return w;
    }
}
