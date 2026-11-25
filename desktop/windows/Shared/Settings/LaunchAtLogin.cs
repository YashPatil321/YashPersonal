using Microsoft.Win32;

namespace Shared.Settings;

/// <summary>Launch at login through <c>HKCU\Software\Microsoft\Windows\CurrentVersion\Run</c>.</summary>
public static class LaunchAtLogin
{
    private const string RunKey = @"Software\Microsoft\Windows\CurrentVersion\Run";

    public static bool IsEnabled(string appName)
    {
        using var key = Registry.CurrentUser.OpenSubKey(RunKey, writable: false);
        return key?.GetValue(appName) is string;
    }

    public static void Set(string appName, bool enabled)
    {
        try
        {
            using var key = Registry.CurrentUser.CreateSubKey(RunKey, writable: true);
            if (enabled)
            {
                var exe = Environment.ProcessPath;
                if (string.IsNullOrEmpty(exe)) return;
                key.SetValue(appName, $"\"{exe}\"", RegistryValueKind.String);
            }
            else if (key.GetValue(appName) is not null)
            {
                key.DeleteValue(appName, throwOnMissingValue: false);
            }
        }
        catch (Exception ex) when (ex is UnauthorizedAccessException or System.Security.SecurityException or System.IO.IOException)
        {
        }
    }
}
