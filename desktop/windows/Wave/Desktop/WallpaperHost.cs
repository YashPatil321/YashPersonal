namespace Wave.Desktop;

/// <summary>
/// Puts windows on the wallpaper, behind the desktop icons, by re-parenting them into the desktop's WorkerW.
/// <list type="bullet">
/// <item>Classic (Windows 10, Windows 11 before 24H2): message 0x052C makes Progman spawn a WorkerW behind the
/// SHELLDLL_DefView; it is the top-level WorkerW that follows the window holding SHELLDLL_DefView.</item>
/// <item>Windows 11 24H2: SHELLDLL_DefView stays in Progman and the wallpaper WorkerW is a child of Progman.</item>
/// </list>
/// The host changes when Explorer restarts (the <c>TaskbarCreated</c> message), so callers look it up again then.
/// </summary>
internal static class WallpaperHost
{
    private const uint SpawnWorkerW = 0x052C;

    /// <summary>The window to parent wallpaper widgets into, or zero when the desktop shell is not available.</summary>
    public static IntPtr Find()
    {
        var progman = Win32.FindWindow("Progman", null);
        if (progman == IntPtr.Zero) return IntPtr.Zero;

        Win32.SendMessageTimeout(progman, SpawnWorkerW, new IntPtr(0xD), new IntPtr(0x1), Win32.SMTO_NORMAL, 1000, out _);
        Win32.SendMessageTimeout(progman, SpawnWorkerW, IntPtr.Zero, IntPtr.Zero, Win32.SMTO_NORMAL, 1000, out _);

        var defViewOwner = IntPtr.Zero;
        Win32.EnumWindows((top, _) =>
        {
            if (Win32.FindWindowEx(top, IntPtr.Zero, "SHELLDLL_DefView", null) != IntPtr.Zero)
            {
                defViewOwner = top;
                return false;
            }
            return true;
        }, IntPtr.Zero);

        if (defViewOwner == progman || defViewOwner == IntPtr.Zero)
        {
            // Windows 11 24H2 and later: the WorkerW lives inside Progman, below SHELLDLL_DefView.
            var child = Win32.FindWindowEx(progman, IntPtr.Zero, "WorkerW", null);
            if (child != IntPtr.Zero) return child;
        }

        if (defViewOwner != IntPtr.Zero)
        {
            var worker = Win32.FindWindowEx(IntPtr.Zero, defViewOwner, "WorkerW", null);
            if (worker != IntPtr.Zero) return worker;
        }
        return progman; // last resort: behind the icons on Progman itself
    }

    /// <summary>Re-parents <paramref name="hwnd"/> into <paramref name="host"/> at a rectangle in screen pixels.</summary>
    public static void Attach(IntPtr hwnd, IntPtr host, Win32.RECT screen)
    {
        if (Win32.GetParent(hwnd) != host)
        {
            var style = Win32.GetWindowLong(hwnd, Win32.GWL_STYLE);
            Win32.SetWindowLong(hwnd, Win32.GWL_STYLE, (style | Win32.WS_CHILD) & ~Win32.WS_POPUP);
            Win32.SetParent(hwnd, host);
        }
        var pt = new Win32.POINT { X = screen.Left, Y = screen.Top };
        Win32.ScreenToClient(host, ref pt);
        Win32.SetWindowPos(hwnd, Win32.HWND_TOP, pt.X, pt.Y, screen.Width, screen.Height,
            Win32.SWP_NOACTIVATE | Win32.SWP_FRAMECHANGED);
    }

    /// <summary>Makes <paramref name="hwnd"/> top-level again (no-op when it is not parented).</summary>
    public static void Detach(IntPtr hwnd)
    {
        if (Win32.GetParent(hwnd) == IntPtr.Zero && (Win32.GetWindowLong(hwnd, Win32.GWL_STYLE) & Win32.WS_CHILD) == 0) return;
        Win32.SetParent(hwnd, IntPtr.Zero);
        var style = Win32.GetWindowLong(hwnd, Win32.GWL_STYLE);
        Win32.SetWindowLong(hwnd, Win32.GWL_STYLE, (style & ~Win32.WS_CHILD) | Win32.WS_POPUP);
    }
}
