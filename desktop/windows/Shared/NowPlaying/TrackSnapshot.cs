using System.Windows.Media.Imaging;

namespace Shared.NowPlaying;

public enum PlayerKind
{
    Spotify,
    AppleMusic,
    Other,
}

/// <summary>The current track, as in the shared spec.</summary>
public sealed record TrackSnapshot(
    PlayerKind Player,
    string PlayerName,
    string SourceAppId,
    string Title,
    string Artist,
    string Album,
    double DurationSec,
    double PositionSec,
    bool IsPlaying,
    BitmapSource? Artwork,
    string TrackId)
{
    public string Display => string.IsNullOrEmpty(Artist) ? Title : $"{Title} – {Artist}";
}

/// <summary>One media session in the Windows media flyout (for Lyra's Status tab).</summary>
public sealed record PlayerSessionInfo(PlayerKind Player, string PlayerName, string SourceAppId, string Title, string Artist, bool IsPlaying);

public static class PlayerNames
{
    public static PlayerKind KindOf(string appId)
    {
        if (appId.Contains("spotify", StringComparison.OrdinalIgnoreCase)) return PlayerKind.Spotify;
        if (appId.Contains("AppleMusic", StringComparison.OrdinalIgnoreCase) ||
            appId.Contains("iTunes", StringComparison.OrdinalIgnoreCase)) return PlayerKind.AppleMusic;
        return PlayerKind.Other;
    }

    /// <summary>A friendly name for an AppUserModelID such as <c>Spotify.exe</c> or <c>Microsoft.ZuneMusic_8wekyb3d8bbwe!Microsoft.ZuneMusic</c>.</summary>
    public static string NameOf(string appId)
    {
        switch (KindOf(appId))
        {
            case PlayerKind.Spotify: return "Spotify";
            case PlayerKind.AppleMusic: return "Apple Music";
        }
        var id = appId;
        if (id.Contains("ZuneMusic", StringComparison.OrdinalIgnoreCase)) return "Media Player";
        if (id.Contains("chrome", StringComparison.OrdinalIgnoreCase)) return "Chrome";
        if (id.Contains("msedge", StringComparison.OrdinalIgnoreCase) || id.Contains("MicrosoftEdge", StringComparison.OrdinalIgnoreCase)) return "Edge";
        if (id.Contains("firefox", StringComparison.OrdinalIgnoreCase)) return "Firefox";
        var bang = id.LastIndexOf('!');
        if (bang >= 0) id = id[(bang + 1)..];
        var underscore = id.IndexOf('_');
        if (underscore > 0) id = id[..underscore];
        if (id.EndsWith(".exe", StringComparison.OrdinalIgnoreCase)) id = id[..^4];
        var dot = id.LastIndexOf('.');
        if (dot >= 0 && dot < id.Length - 1) id = id[(dot + 1)..];
        return id.Length == 0 ? "Media app" : char.ToUpperInvariant(id[0]) + id[1..];
    }
}
