using System.Windows;
using System.Windows.Media;
using Microsoft.Win32;
using Windows.UI.ViewManagement;

namespace Shared.Ui;

/// <summary>The Windows accent colour, exposed to XAML as the <c>AccentColor</c>/<c>AccentBrush</c> resources.</summary>
public static class Accent
{
    private static readonly Color Fallback = Color.FromRgb(0x4C, 0x8D, 0xFF);
    private static UISettings? _ui;

    public static Color Current { get; private set; } = Fallback;

    public static event EventHandler? Changed;

    /// <summary>Reads the accent colour, publishes the resources and follows later changes.</summary>
    public static void Install(Application app)
    {
        Publish(app, Read());
        try
        {
            _ui ??= new UISettings();
            _ui.ColorValuesChanged += (_, _) => app.Dispatcher.BeginInvoke(() => Publish(app, Read()));
        }
        catch (Exception)
        {
            SystemEvents.UserPreferenceChanged += (_, _) => Publish(app, Read());
        }
    }

    public static Color Read()
    {
        try
        {
            _ui ??= new UISettings();
            // AccentLight1 reads better than the raw accent on a dark UI.
            var c = _ui.GetColorValue(UIColorType.AccentLight1);
            return Color.FromRgb(c.R, c.G, c.B);
        }
        catch (Exception)
        {
        }
        try
        {
            using var key = Registry.CurrentUser.OpenSubKey(@"Software\Microsoft\Windows\DWM");
            if (key?.GetValue("AccentColor") is int abgr)
                return Color.FromRgb((byte)(abgr & 0xFF), (byte)((abgr >> 8) & 0xFF), (byte)((abgr >> 16) & 0xFF));
        }
        catch (Exception)
        {
        }
        return Fallback;
    }

    private static void Publish(Application app, Color c)
    {
        Current = c;
        app.Resources["AccentColor"] = c;
        app.Resources["AccentBrush"] = Freeze(new SolidColorBrush(c));
        app.Resources["AccentSoftBrush"] = Freeze(new SolidColorBrush(Color.FromArgb(0x40, c.R, c.G, c.B)));
        app.Resources["AccentForegroundBrush"] = Freeze(new SolidColorBrush(Luminance(c) > 0.6 ? Colors.Black : Colors.White));
        Changed?.Invoke(null, EventArgs.Empty);
    }

    public static double Luminance(Color c) => (0.2126 * c.R + 0.7152 * c.G + 0.0722 * c.B) / 255.0;

    private static T Freeze<T>(T f) where T : Freezable
    {
        f.Freeze();
        return f;
    }
}
