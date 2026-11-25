using System.Diagnostics;

namespace Wave.Desktop;

/// <summary>Decides whether a desktop widget is hidden behind a maximised or full-screen window.</summary>
internal static class Coverage
{
    private static readonly HashSet<string> ShellClasses = new(StringComparer.Ordinal)
    {
        "Progman", "WorkerW", "Shell_TrayWnd", "Shell_SecondaryTrayWnd", "SHELLDLL_DefView",
        "Windows.UI.Core.CoreWindow", "XamlExplorerHostIslandWindow", "NotifyIconOverflowWindow",
    };

    private static readonly uint OwnProcess = (uint)Environment.ProcessId;

    /// <summary>True when the foreground window is maximised or full screen on the widget's monitor.</summary>
    public static bool IsCovered(IntPtr widget)
    {
        var fg = Win32.GetForegroundWindow();
        if (fg == IntPtr.Zero || fg == widget) return false;
        Win32.GetWindowThreadProcessId(fg, out var pid);
        if (pid == OwnProcess) return false;
        if (!Win32.IsWindowVisible(fg) || Win32.IsIconic(fg)) return false;
        if (ShellClasses.Contains(Win32.ClassName(fg))) return false;

        var widgetMonitor = Win32.MonitorRect(widget);
        var fgMonitor = Win32.MonitorRect(fg);
        if (widgetMonitor is not { } wm || fgMonitor is not { } fm || !Same(wm, fm)) return false;
        if (Win32.IsZoomed(fg)) return true;
        // Full screen (games, video players, F11 browsers): the window covers the whole monitor.
        return Win32.GetWindowRect(fg, out var r) &&
               r.Left <= fm.Left && r.Top <= fm.Top && r.Right >= fm.Right && r.Bottom >= fm.Bottom;
    }

    private static bool Same(Win32.RECT a, Win32.RECT b) =>
        a.Left == b.Left && a.Top == b.Top && a.Right == b.Right && a.Bottom == b.Bottom;

    [Conditional("DEBUG")]
    public static void Trace(string s) => Debug.WriteLine(s);
}
