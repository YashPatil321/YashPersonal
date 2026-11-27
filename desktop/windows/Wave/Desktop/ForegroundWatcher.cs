namespace Wave.Desktop;

/// <summary>
/// Watches the foreground window (EVENT_SYSTEM_FOREGROUND) to notice Show Desktop / Win+D: the foreground becomes the
/// desktop itself (Progman or WorkerW). Out-of-context hook, delivered on the creating (UI) thread's message loop.
/// </summary>
internal sealed class ForegroundWatcher : IDisposable
{
    private readonly Win32.WinEventProc _proc; // kept alive: the hook holds a pointer to it
    private readonly IntPtr _hook;
    private bool? _lastDesktop;

    public ForegroundWatcher()
    {
        _proc = OnEvent;
        _hook = Win32.SetWinEventHook(Win32.EVENT_SYSTEM_FOREGROUND, Win32.EVENT_SYSTEM_FOREGROUND, IntPtr.Zero, _proc, 0, 0,
            Win32.WINEVENT_OUTOFCONTEXT);
    }

    /// <summary>Raised with true when the desktop became the foreground, false when another app did.</summary>
    public event Action<bool>? DesktopForegroundChanged;

    public static bool IsDesktop(IntPtr hwnd) => Win32.ClassName(hwnd) is "Progman" or "WorkerW";

    private void OnEvent(IntPtr hook, uint eventType, IntPtr hwnd, int idObject, int idChild, uint thread, uint time)
    {
        if (hwnd == IntPtr.Zero) return;
        var desktop = IsDesktop(hwnd);
        // The taskbar taking focus (clicking the Show Desktop corner, the Start menu) changes nothing.
        if (!desktop && Win32.ClassName(hwnd) is "Shell_TrayWnd" or "Shell_SecondaryTrayWnd") return;
        if (desktop == _lastDesktop && !desktop) return;
        _lastDesktop = desktop;
        DesktopForegroundChanged?.Invoke(desktop);
    }

    public void Dispose()
    {
        if (_hook != IntPtr.Zero) Win32.UnhookWinEvent(_hook);
    }
}
