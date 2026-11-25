using Shared.Overlay;

namespace Shared.Settings;

/// <summary>
/// Keeps the display on with <c>SetThreadExecutionState</c>. The request belongs to the calling thread, so always call
/// <see cref="Set"/> from the same (UI) thread.
/// </summary>
public static class KeepAwake
{
    private static bool _active;

    public static bool IsActive => _active;

    public static void Set(bool active)
    {
        if (active == _active) return;
        _active = active;
        Native.SetThreadExecutionState(active
            ? Native.ExecutionState.Continuous | Native.ExecutionState.DisplayRequired | Native.ExecutionState.SystemRequired
            : Native.ExecutionState.Continuous);
    }
}
