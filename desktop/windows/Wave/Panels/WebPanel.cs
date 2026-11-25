using System.IO;
using System.Text.Json;
using System.Text.Json.Nodes;
using System.Windows;
using Microsoft.Web.WebView2.Core;
using Microsoft.Web.WebView2.Wpf;

namespace Wave.Panels;

public enum PanelKind
{
    Widget,
    Clock,
    Dashboard,
    Fullscreen,
}

/// <summary>The shared WebView2 environment (one browser process group, data in %LOCALAPPDATA%\Wave\WebView2).</summary>
public static class WebViewEnvironment
{
    private static Task<CoreWebView2Environment>? _env;

    public static string UserDataFolder { get; } =
        Path.Combine(Environment.GetFolderPath(Environment.SpecialFolder.LocalApplicationData), "Wave", "WebView2");

    public static Task<CoreWebView2Environment> GetAsync() =>
        _env ??= CoreWebView2Environment.CreateAsync(browserExecutableFolder: null, userDataFolder: UserDataFolder);

    /// <summary>The installed Evergreen runtime's version, or null when WebView2 is missing.</summary>
    public static string? RuntimeVersion()
    {
        try
        {
            return CoreWebView2Environment.GetAvailableBrowserVersionString();
        }
        catch (WebView2RuntimeNotFoundException)
        {
            return null;
        }
        catch (Exception)
        {
            return null;
        }
    }
}

/// <summary>
/// One view of the Wave web engine (desktop/visuals) in a WebView2. The folder is served as https://wave.local/.
/// Page → host messages arrive as JSON through <c>chrome.webview.postMessage</c>; host → page calls are
/// <c>Wave.fn(json)</c>, queued until the page says <c>ready</c> (audio frames are dropped instead of queued).
/// </summary>
public sealed class WebPanel : IDisposable
{
    public const string HostName = "wave.local";

    private readonly List<string> _queue = new();
    private bool _ready;
    private bool _disposed;

    public WebPanel(PanelKind kind, Window window, string visualsDir)
    {
        Kind = kind;
        Window = window;
        WebView = new WebView2();
        if (kind is PanelKind.Widget or PanelKind.Clock)
            WebView.DefaultBackgroundColor = System.Drawing.Color.Transparent;
        else
            WebView.DefaultBackgroundColor = System.Drawing.Color.FromArgb(255, 10, 10, 15);
        window.Content = WebView;
        _ = InitAsync(visualsDir);
    }

    public PanelKind Kind { get; }
    public Window Window { get; }
    public WebView2 WebView { get; }
    public bool IsReady => _ready;

    /// <summary>Raised for every page message (including <c>ready</c>, after the queue is flushed).</summary>
    public event Action<WebPanel, JsonObject>? Message;

    /// <summary>Last value sent with <c>setPaused</c>, so it is only sent on change.</summary>
    public bool? LastPaused { get; set; }

    public string Mode => Kind.ToString().ToLowerInvariant();

    private async Task InitAsync(string visualsDir)
    {
        try
        {
            var env = await WebViewEnvironment.GetAsync();
            await WebView.EnsureCoreWebView2Async(env);
            if (_disposed) return;
            var core = WebView.CoreWebView2;
            core.SetVirtualHostNameToFolderMapping(HostName, visualsDir, CoreWebView2HostResourceAccessKind.Allow);
            var s = core.Settings;
            s.AreDefaultContextMenusEnabled = Kind == PanelKind.Dashboard;
            s.IsStatusBarEnabled = false;
            s.IsZoomControlEnabled = false;
            s.AreBrowserAcceleratorKeysEnabled = Kind == PanelKind.Dashboard;
#if !DEBUG
            s.AreDevToolsEnabled = false;
#endif
            core.WebMessageReceived += OnWebMessage;
            core.NavigationStarting += (_, _) => _ready = false;
            core.NewWindowRequested += (_, e) => e.Handled = true; // the engine never needs pop-ups
            core.Navigate($"https://{HostName}/index.html?mode={Mode}");
        }
        catch (Exception ex)
        {
            System.Diagnostics.Debug.WriteLine($"WebView2 init failed for {Kind}: {ex}");
        }
    }

    private void OnWebMessage(object? sender, CoreWebView2WebMessageReceivedEventArgs e)
    {
        JsonObject? msg;
        try
        {
            msg = JsonNode.Parse(e.WebMessageAsJson) as JsonObject;
        }
        catch (JsonException)
        {
            return;
        }
        if (msg is null) return;

        if (msg["cmd"]?.GetValue<string>() == "ready")
        {
            _ready = true;
            LastPaused = null; // a fresh page starts unpaused
            foreach (var js in _queue) Execute(js);
            _queue.Clear();
        }
        Message?.Invoke(this, msg);
    }

    /// <summary>Calls <c>Wave.{fn}({json})</c> in the page.</summary>
    public void Call(string fn, string json)
    {
        if (_disposed) return;
        var js = $"Wave.{fn}({json})";
        if (_ready && WebView.CoreWebView2 is not null) Execute(js);
        else if (fn != "pushAudio") _queue.Add(js);
    }

    public void Call(string fn, JsonNode? payload) => Call(fn, payload?.ToJsonString() ?? "null");

    public void Reload()
    {
        _ready = false;
        WebView.CoreWebView2?.Reload();
    }

    private void Execute(string js)
    {
        try
        {
            WebView.ExecuteScriptAsync(js).ContinueWith(t => _ = t.Exception, TaskContinuationOptions.OnlyOnFaulted);
        }
        catch (Exception)
        {
            // The view is being torn down.
        }
    }

    public void Dispose()
    {
        if (_disposed) return;
        _disposed = true;
        try
        {
            WebView.Dispose();
        }
        catch (Exception)
        {
        }
    }
}
