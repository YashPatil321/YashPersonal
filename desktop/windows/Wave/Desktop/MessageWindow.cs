using System.Windows.Interop;

namespace Wave.Desktop;

/// <summary>
/// A hidden top-level window (not message-only, so it receives the <c>TaskbarCreated</c> broadcast) that owns the
/// global hotkeys: Ctrl+Alt+F (full screen) and Ctrl+Alt+M (show or hide the widgets).
/// </summary>
internal sealed class MessageWindow : IDisposable
{
    public const int HotKeyFullscreen = 1;
    public const int HotKeyWidgets = 2;

    private readonly HwndSource _source;
    private readonly uint _taskbarCreated;
    private readonly List<int> _registered = new();

    public MessageWindow()
    {
        _taskbarCreated = Win32.RegisterWindowMessage("TaskbarCreated");
        var p = new HwndSourceParameters("Wave.MessageWindow")
        {
            Width = 0,
            Height = 0,
            WindowStyle = 0, // WS_OVERLAPPED without WS_VISIBLE: hidden, but still top-level
            ExtendedWindowStyle = (int)Win32.WS_EX_TOOLWINDOW,
        };
        _source = new HwndSource(p);
        _source.AddHook(WndProc);
    }

    public event Action<int>? HotKey;

    /// <summary>Explorer restarted: the taskbar and the desktop's WorkerW were recreated.</summary>
    public event Action? ExplorerRestarted;

    /// <summary>Registers the two hotkeys. Returns the names of any that another app already owns.</summary>
    public IReadOnlyList<string> RegisterHotKeys()
    {
        var failed = new List<string>();
        Register(HotKeyFullscreen, Win32.VK_F, "Ctrl+Alt+F", failed);
        Register(HotKeyWidgets, Win32.VK_M, "Ctrl+Alt+M", failed);
        return failed;
    }

    private void Register(int id, uint vk, string name, List<string> failed)
    {
        if (Win32.RegisterHotKey(_source.Handle, id, Win32.MOD_CONTROL | Win32.MOD_ALT | Win32.MOD_NOREPEAT, vk)) _registered.Add(id);
        else failed.Add(name);
    }

    private IntPtr WndProc(IntPtr hwnd, int msg, IntPtr wParam, IntPtr lParam, ref bool handled)
    {
        if (msg == Win32.WM_HOTKEY)
        {
            HotKey?.Invoke(wParam.ToInt32());
            handled = true;
        }
        else if (_taskbarCreated != 0 && (uint)msg == _taskbarCreated)
        {
            ExplorerRestarted?.Invoke();
        }
        return IntPtr.Zero;
    }

    public void Dispose()
    {
        foreach (var id in _registered) Win32.UnregisterHotKey(_source.Handle, id);
        _registered.Clear();
        _source.RemoveHook(WndProc);
        _source.Dispose();
    }
}
