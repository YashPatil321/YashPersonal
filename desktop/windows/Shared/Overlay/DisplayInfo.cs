using System.Windows;
using Forms = System.Windows.Forms;

namespace Shared.Overlay;

/// <summary>A connected display. Bounds are in physical pixels (the process is per-monitor-v2 DPI aware).</summary>
public sealed record DisplayInfo(string Id, string Name, Int32Rect Bounds, Int32Rect WorkArea, bool IsPrimary, double Scale)
{
    /// <summary>All displays, primary first.</summary>
    public static IReadOnlyList<DisplayInfo> All()
    {
        var screens = Forms.Screen.AllScreens;
        var list = new List<DisplayInfo>(screens.Length);
        for (var i = 0; i < screens.Length; i++)
        {
            var s = screens[i];
            var b = s.Bounds;
            var w = s.WorkingArea;
            var scale = ScaleFor(b.X + b.Width / 2, b.Y + b.Height / 2);
            var name = $"Display {i + 1} · {b.Width}×{b.Height}" + (s.Primary ? " · Main" : string.Empty);
            list.Add(new DisplayInfo(
                s.DeviceName,
                name,
                new Int32Rect(b.X, b.Y, b.Width, b.Height),
                new Int32Rect(w.X, w.Y, w.Width, w.Height),
                s.Primary,
                scale));
        }
        return list.OrderByDescending(d => d.IsPrimary).ToList();
    }

    /// <summary>The DPI scale (1.0 = 96 DPI) of the monitor containing a physical point.</summary>
    public static double ScaleFor(int x, int y)
    {
        try
        {
            var monitor = Native.MonitorFromPoint(new Native.POINT { X = x, Y = y }, Native.MONITOR_DEFAULTTONEAREST);
            if (monitor != IntPtr.Zero && Native.GetDpiForMonitor(monitor, Native.MDT_EFFECTIVE_DPI, out var dpiX, out _) == 0)
                return dpiX / 96.0;
        }
        catch (DllNotFoundException)
        {
        }
        catch (EntryPointNotFoundException)
        {
        }
        return 1.0;
    }

    /// <summary>
    /// Resolves the selected display ids. <paramref name="selected"/> null means the default:
    /// all displays when <paramref name="defaultAll"/>, otherwise the main display.
    /// </summary>
    public static IReadOnlyList<DisplayInfo> Resolve(IReadOnlyCollection<string>? selected, bool defaultAll)
    {
        var all = All();
        if (selected is null) return defaultAll ? all : all.Where(d => d.IsPrimary).Take(1).ToList();
        return all.Where(d => selected.Contains(d.Id)).ToList();
    }
}
