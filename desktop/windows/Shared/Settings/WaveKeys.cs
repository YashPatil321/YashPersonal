using System.Globalization;
using System.Text.Json.Nodes;

namespace Shared.Settings;

/// <summary>Typed, forgiving reads from Wave's JSON settings dictionary (a wrong type falls back to the default).</summary>
public static class WaveKeys
{
    public static bool Bool(JsonObject? d, string key, bool fallback) =>
        d?[key] is JsonValue v && v.TryGetValue<bool>(out var b) ? b : fallback;

    public static string String(JsonObject? d, string key, string fallback) =>
        d?[key] is JsonValue v && v.TryGetValue<string>(out var s) && !string.IsNullOrWhiteSpace(s) ? s : fallback;

    public static double Number(JsonObject? d, string key, double fallback)
    {
        if (d?[key] is not JsonValue v) return fallback;
        if (v.TryGetValue<double>(out var x) && double.IsFinite(x)) return x;
        if (v.TryGetValue<string>(out var str) &&
            double.TryParse(str, NumberStyles.Float, CultureInfo.InvariantCulture, out x) && double.IsFinite(x)) return x;
        return fallback;
    }
}
