using System.Diagnostics;
using System.Windows;
using Shared.Settings;
using Shared.Ui;
using Wave.Panels;

namespace Wave;

public partial class App : Application
{
    /// <summary>Microsoft's Evergreen WebView2 runtime download page.</summary>
    public const string WebView2DownloadUrl = "https://go.microsoft.com/fwlink/p/?LinkId=2124703";

    private SingleInstance? _instance;
    private WaveController? _controller;

    protected override void OnStartup(StartupEventArgs e)
    {
        base.OnStartup(e);

        _instance = SingleInstance.Acquire("Wave");
        if (!_instance.IsFirst)
        {
            Shutdown();
            return;
        }

        // WebView2 ships with Windows 10 and 11, but it can be missing (removed, or an LTSC image).
        if (WebViewEnvironment.RuntimeVersion() is null)
        {
            var answer = MessageBox.Show(
                "Wave needs the Microsoft Edge WebView2 Runtime, which is not installed on this PC.\n\n" +
                "Click OK to open the download page (choose the Evergreen Bootstrapper), then start Wave again.",
                "Wave", MessageBoxButton.OKCancel, MessageBoxImage.Warning);
            if (answer == MessageBoxResult.OK)
            {
                try { Process.Start(new ProcessStartInfo(WebView2DownloadUrl) { UseShellExecute = true }); }
                catch (Exception) { }
            }
            _instance.Dispose();
            Shutdown();
            return;
        }

        Accent.Install(this);
        _controller = new WaveController();
        _controller.Start();

        DispatcherUnhandledException += (_, args) =>
        {
            Debug.WriteLine(args.Exception);
            args.Handled = true; // a tray app should not vanish on a stray exception
        };
    }

    protected override void OnExit(ExitEventArgs e)
    {
        _controller?.Dispose();
        _instance?.Dispose();
        base.OnExit(e);
    }
}
