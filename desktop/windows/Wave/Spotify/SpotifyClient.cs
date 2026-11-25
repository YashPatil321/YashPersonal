using System.Diagnostics;
using System.IO;
using System.Net;
using System.Net.Http;
using System.Net.Http.Headers;
using System.Net.Sockets;
using System.Security.Cryptography;
using System.Text;
using System.Windows.Threading;

namespace Wave.Spotify;

public enum SpotifyState
{
    Disconnected,
    Connecting,
    Connected,
    Error,
}

/// <summary>
/// Spotify Web API with Authorization Code + PKCE (no client secret). Sign-in opens the browser; a one-shot listener
/// on 127.0.0.1:8765 catches the redirect. The refresh token is stored DPAPI-protected (current user) in
/// %APPDATA%\Wave\spotify.bin. Mirrors desktop/macos/Sources/SharedKit/Spotify.swift. Use on the UI thread.
/// </summary>
public sealed class SpotifyClient : IDisposable
{
    private static readonly byte[] Entropy = Encoding.UTF8.GetBytes("Wave.Spotify.v1");
    private static readonly TimeSpan ListenTimeout = TimeSpan.FromMinutes(5);

    private readonly HttpClient _http = new() { Timeout = TimeSpan.FromSeconds(8) };
    private readonly DispatcherTimer _poll = new() { Interval = TimeSpan.FromSeconds(1) };
    private readonly Dictionary<string, bool> _likedCache = new();
    private readonly string _tokenPath;
    private string _clientId = SpotifyProtocol.DefaultClientId;
    private string? _accessToken;
    private DateTime _expiryUtc = DateTime.MinValue;
    private string _verifier = string.Empty;
    private string _authState = string.Empty;
    private CancellationTokenSource? _listen;
    private bool _polling;

    public SpotifyClient(string clientId)
    {
        ClientId = clientId;
        _tokenPath = Path.Combine(Environment.GetFolderPath(Environment.SpecialFolder.ApplicationData), "Wave", "spotify.bin");
        _poll.Tick += async (_, _) =>
        {
            if (State != SpotifyState.Connected || _polling) return;
            _polling = true;
            try { await RefreshPlaybackAsync(); }
            finally { _polling = false; }
        };
        if (RefreshToken is not null)
        {
            State = SpotifyState.Connected;
            _ = LoadProfileAsync();
        }
    }

    public SpotifyState State { get; private set; } = SpotifyState.Disconnected;
    public string ErrorMessage { get; private set; } = string.Empty;
    public string UserName { get; private set; } = string.Empty;
    public SpotifyPlayback? Playback { get; private set; }
    public bool IsConnected => State == SpotifyState.Connected;

    /// <summary>State, user name or playback changed.</summary>
    public event EventHandler? Changed;

    public string ClientId
    {
        get => _clientId;
        set => _clientId = string.IsNullOrWhiteSpace(value) ? SpotifyProtocol.DefaultClientId : value.Trim();
    }

    public void StartPolling() => _poll.Start();

    public string StateName => State switch
    {
        SpotifyState.Connected => "connected",
        SpotifyState.Connecting => "connecting",
        SpotifyState.Error => "error",
        _ => "disconnected",
    };

    // ------------------------------------------------------------------ sign in

    public async void Connect()
    {
        _verifier = SpotifyProtocol.RandomString(64);
        _authState = SpotifyProtocol.RandomString(16);
        var url = SpotifyProtocol.AuthorizeUrl(ClientId, SpotifyProtocol.CodeChallenge(_verifier), _authState);

        _listen?.Cancel();
        var cts = new CancellationTokenSource(ListenTimeout);
        _listen = cts;
        Task<string?> callback;
        try
        {
            callback = CallbackListener.StartAsync(SpotifyProtocol.RedirectPort, cts.Token);
        }
        catch (Exception)
        {
            SetError("Port 8765 is busy. Close the app using it and try again.");
            return;
        }

        SetState(SpotifyState.Connecting);
        try
        {
            Process.Start(new ProcessStartInfo(url) { UseShellExecute = true });
        }
        catch (Exception)
        {
            SetError("Could not open the browser.");
            cts.Cancel();
            return;
        }

        string? pathAndQuery;
        try
        {
            pathAndQuery = await callback;
        }
        catch (Exception ex) when (ex is OperationCanceledException or SocketException or HttpListenerException or IOException)
        {
            if (ReferenceEquals(_listen, cts) && State == SpotifyState.Connecting)
                SetError(ex is OperationCanceledException ? "Sign-in timed out" : "Port 8765 is busy. Close the app using it and try again.");
            return;
        }
        if (!ReferenceEquals(_listen, cts)) return;
        _listen = null;

        var (code, state, error) = SpotifyProtocol.ParseCallback(pathAndQuery ?? string.Empty);
        if (code is null || state != _authState)
        {
            SetError(error ?? "Sign-in was cancelled");
            return;
        }

        var ok = await TokenRequestAsync(new Dictionary<string, string>
        {
            ["grant_type"] = "authorization_code",
            ["code"] = code,
            ["redirect_uri"] = SpotifyProtocol.RedirectUri,
            ["client_id"] = ClientId,
            ["code_verifier"] = _verifier,
        });
        if (ok)
        {
            SetState(SpotifyState.Connected);
            await LoadProfileAsync();
        }
        else if (State == SpotifyState.Connecting)
        {
            SetError("Spotify refused the sign-in. Check the app's redirect URI.");
        }
    }

    public void Disconnect()
    {
        _listen?.Cancel();
        _listen = null;
        RefreshToken = null;
        _accessToken = null;
        Playback = null;
        UserName = string.Empty;
        ErrorMessage = string.Empty;
        SetState(SpotifyState.Disconnected);
    }

    private void SetState(SpotifyState s)
    {
        State = s;
        if (s != SpotifyState.Error) ErrorMessage = string.Empty;
        Changed?.Invoke(this, EventArgs.Empty);
    }

    private void SetError(string message)
    {
        ErrorMessage = message;
        State = SpotifyState.Error;
        Changed?.Invoke(this, EventArgs.Empty);
    }

    private async Task<bool> TokenRequestAsync(Dictionary<string, string> form)
    {
        try
        {
            using var content = new StringContent(SpotifyProtocol.FormBody(form), Encoding.UTF8, "application/x-www-form-urlencoded");
            using var resp = await _http.PostAsync(SpotifyProtocol.TokenEndpoint, content);
            if (resp.StatusCode != HttpStatusCode.OK) return false;
            var token = SpotifyProtocol.ParseToken(await resp.Content.ReadAsStringAsync());
            if (token is null) return false;
            _accessToken = token.AccessToken;
            _expiryUtc = DateTime.UtcNow.AddSeconds(token.ExpiresIn - 60);
            if (token.RefreshToken is not null) RefreshToken = token.RefreshToken;
            return true;
        }
        catch (Exception ex) when (ex is HttpRequestException or TaskCanceledException or System.Text.Json.JsonException)
        {
            return false;
        }
    }

    private async Task<string?> ValidTokenAsync()
    {
        if (_accessToken is not null && DateTime.UtcNow < _expiryUtc) return _accessToken;
        var refresh = RefreshToken;
        if (refresh is null) return null;
        var ok = await TokenRequestAsync(new Dictionary<string, string>
        {
            ["grant_type"] = "refresh_token",
            ["refresh_token"] = refresh,
            ["client_id"] = ClientId,
        });
        if (!ok)
        {
            // A revoked token: sign out so the dashboard offers Connect again.
            Disconnect();
            SetError("Spotify signed you out. Connect again.");
            return null;
        }
        return _accessToken;
    }

    // ------------------------------------------------------------------ token storage (DPAPI)

    private string? RefreshToken
    {
        get
        {
            try
            {
                if (!File.Exists(_tokenPath)) return null;
                var plain = ProtectedData.Unprotect(File.ReadAllBytes(_tokenPath), Entropy, DataProtectionScope.CurrentUser);
                return Encoding.UTF8.GetString(plain);
            }
            catch (Exception ex) when (ex is IOException or CryptographicException or UnauthorizedAccessException)
            {
                return null;
            }
        }
        set
        {
            try
            {
                if (value is null)
                {
                    if (File.Exists(_tokenPath)) File.Delete(_tokenPath);
                    return;
                }
                Directory.CreateDirectory(Path.GetDirectoryName(_tokenPath)!);
                File.WriteAllBytes(_tokenPath, ProtectedData.Protect(Encoding.UTF8.GetBytes(value), Entropy, DataProtectionScope.CurrentUser));
            }
            catch (Exception ex) when (ex is IOException or CryptographicException or UnauthorizedAccessException)
            {
            }
        }
    }

    // ------------------------------------------------------------------ API

    private async Task<(int Status, string? Body)> ApiAsync(HttpMethod method, string path, string query = "")
    {
        var token = await ValidTokenAsync();
        if (token is null) return (401, null);
        try
        {
            using var req = new HttpRequestMessage(method, SpotifyProtocol.ApiBase + path + (query.Length > 0 ? "?" + query : string.Empty));
            req.Headers.Authorization = new AuthenticationHeaderValue("Bearer", token);
            if (method != HttpMethod.Get) req.Content = new ByteArrayContent(Array.Empty<byte>());
            using var resp = await _http.SendAsync(req);
            var body = resp.Content is null ? null : await resp.Content.ReadAsStringAsync();
            return ((int)resp.StatusCode, body);
        }
        catch (Exception ex) when (ex is HttpRequestException or TaskCanceledException)
        {
            return (0, null);
        }
    }

    private async Task LoadProfileAsync()
    {
        var (status, body) = await ApiAsync(HttpMethod.Get, "/me");
        if (status != 200 || body is null) return;
        try
        {
            UserName = SpotifyProtocol.ParseDisplayName(body) ?? string.Empty;
            Changed?.Invoke(this, EventArgs.Empty);
        }
        catch (System.Text.Json.JsonException)
        {
        }
    }

    public async Task RefreshPlaybackAsync()
    {
        var (status, body) = await ApiAsync(HttpMethod.Get, "/me/player", "additional_types=track,episode");
        if (status == 204)
        {
            if (Playback is not null)
            {
                Playback = null;
                Changed?.Invoke(this, EventArgs.Empty);
            }
            return;
        }
        if (status != 200 || string.IsNullOrEmpty(body)) return;

        try
        {
            var id = SpotifyProtocol.ItemId(body);
            if (id is null) return;
            if (!_likedCache.TryGetValue(id, out var liked))
            {
                var (s, d) = await ApiAsync(HttpMethod.Get, "/me/tracks/contains", "ids=" + Uri.EscapeDataString(id));
                liked = s == 200 && d is not null && SpotifyProtocol.ParseContains(d) == true;
                _likedCache[id] = liked;
            }
            var next = SpotifyProtocol.ParsePlayer(body, liked, DateTime.UtcNow);
            var changed = next is null != Playback is null ||
                          (next is not null && Playback is not null && (next with { FetchedAtUtc = default, Position = 0 }) != (Playback with { FetchedAtUtc = default, Position = 0 }));
            Playback = next;
            if (changed) Changed?.Invoke(this, EventArgs.Empty);
        }
        catch (System.Text.Json.JsonException)
        {
        }
    }

    public async Task PlayPauseAsync()
    {
        var playing = Playback?.IsPlaying ?? false;
        await ApiAsync(HttpMethod.Put, playing ? "/me/player/pause" : "/me/player/play");
        await RefreshPlaybackAsync();
    }

    public async Task NextAsync()
    {
        await ApiAsync(HttpMethod.Post, "/me/player/next");
        await Task.Delay(300);
        await RefreshPlaybackAsync();
    }

    public async Task PreviousAsync()
    {
        await ApiAsync(HttpMethod.Post, "/me/player/previous");
        await Task.Delay(300);
        await RefreshPlaybackAsync();
    }

    public async Task ToggleLikeAsync()
    {
        if (Playback is not { } p) return;
        var (s, _) = await ApiAsync(p.Liked ? HttpMethod.Delete : HttpMethod.Put, "/me/tracks", "ids=" + Uri.EscapeDataString(p.Id));
        if (s is >= 200 and < 300)
        {
            _likedCache[p.Id] = !p.Liked;
            if (Playback?.Id == p.Id) Playback = Playback with { Liked = !p.Liked };
            Changed?.Invoke(this, EventArgs.Empty);
        }
    }

    public void Dispose()
    {
        _poll.Stop();
        _listen?.Cancel();
        _http.Dispose();
    }
}

/// <summary>
/// A one-shot HTTP listener for the OAuth redirect. Uses <see cref="HttpListener"/> on http://127.0.0.1:8765/ and falls
/// back to a raw <see cref="TcpListener"/> when HTTP.sys refuses the prefix (no URL ACL for a standard user).
/// Returns the path and query of the /callback request.
/// </summary>
internal static class CallbackListener
{
    private const string Page = """
        <!doctype html><meta charset="utf-8"><title>Spotify</title>
        <body style="font-family:'Segoe UI',system-ui;background:#0a0a0f;color:#fff;display:grid;place-items:center;height:100vh;margin:0">
        <div style="text-align:center"><h1>{0}</h1><p style="opacity:.6">{1}</p></div>
        """;

    public static Task<string?> StartAsync(int port, CancellationToken ct)
    {
        HttpListener? http = null;
        try
        {
            http = new HttpListener();
            http.Prefixes.Add($"http://127.0.0.1:{port}/");
            http.Start();
            return RunHttpListenerAsync(http, ct);
        }
        catch (HttpListenerException)
        {
            try { http?.Close(); }
            catch (Exception) { }
        }
        var tcp = new TcpListener(IPAddress.Loopback, port);
        tcp.Start(); // throws SocketException when the port is busy
        return RunTcpAsync(tcp, ct);
    }

    private static string Body(bool ok) => string.Format(Page,
        ok ? "Connected" : "Didn’t connect",
        ok ? "You can close this tab and go back to Wave." : "You can close this tab and try again.");

    private static async Task<string?> RunHttpListenerAsync(HttpListener http, CancellationToken ct)
    {
        using var reg = ct.Register(() => { try { http.Stop(); } catch (Exception) { } });
        try
        {
            while (true)
            {
                HttpListenerContext ctx;
                try
                {
                    ctx = await http.GetContextAsync();
                }
                catch (Exception) when (ct.IsCancellationRequested)
                {
                    throw new OperationCanceledException(ct);
                }
                var path = ctx.Request.RawUrl ?? "/";
                var ok = path.Contains("code=", StringComparison.Ordinal);
                var bytes = Encoding.UTF8.GetBytes(Body(ok));
                ctx.Response.ContentType = "text/html; charset=utf-8";
                ctx.Response.ContentLength64 = bytes.Length;
                await ctx.Response.OutputStream.WriteAsync(bytes, ct);
                ctx.Response.Close();
                if (path.StartsWith("/callback", StringComparison.Ordinal)) return path;
            }
        }
        finally
        {
            try { http.Close(); }
            catch (Exception) { }
        }
    }

    private static async Task<string?> RunTcpAsync(TcpListener tcp, CancellationToken ct)
    {
        try
        {
            while (true)
            {
                using var client = await tcp.AcceptTcpClientAsync(ct);
                using var stream = client.GetStream();
                var buffer = new byte[16384];
                var read = await stream.ReadAsync(buffer, ct);
                var request = Encoding.UTF8.GetString(buffer, 0, read);
                var firstLine = request.Split("\r\n", 2)[0];
                var parts = firstLine.Split(' ');
                var path = parts.Length > 1 ? parts[1] : "/";
                var body = Encoding.UTF8.GetBytes(Body(path.Contains("code=", StringComparison.Ordinal)));
                var head = Encoding.ASCII.GetBytes(
                    $"HTTP/1.1 200 OK\r\nContent-Type: text/html; charset=utf-8\r\nContent-Length: {body.Length}\r\nConnection: close\r\n\r\n");
                await stream.WriteAsync(head, ct);
                await stream.WriteAsync(body, ct);
                if (path.StartsWith("/callback", StringComparison.Ordinal)) return path;
            }
        }
        finally
        {
            tcp.Stop();
        }
    }
}
