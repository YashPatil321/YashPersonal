using System.IO;
using System.Text.Json;
using System.Text.Json.Nodes;
using System.Windows.Threading;
using Shared.Settings;

namespace Wave;

/// <summary>
/// The settings dictionary shared with the web engine (keys as in <c>Wave.DEFAULTS</c> in core.js), persisted as JSON
/// in %APPDATA%\Wave\settings.json with a 500 ms debounce. Used on the UI thread only.
/// </summary>
public sealed class WaveSettings
{
    private readonly DispatcherTimer _debounce = new() { Interval = TimeSpan.FromMilliseconds(500) };

    public WaveSettings()
    {
        FilePath = Path.Combine(Environment.GetFolderPath(Environment.SpecialFolder.ApplicationData), "Wave", "settings.json");
        ExistedAtStartup = File.Exists(FilePath);
        Values = Load(FilePath);
        _debounce.Tick += (_, _) => Flush();
    }

    public string FilePath { get; }
    public bool ExistedAtStartup { get; }
    public JsonObject Values { get; private set; }

    public JsonNode? this[string key]
    {
        get => Values[key];
        set
        {
            Values[key] = value;
            Save();
        }
    }

    public bool Bool(string key, bool fallback) => WaveKeys.Bool(Values, key, fallback);

    public double Number(string key, double fallback) => WaveKeys.Number(Values, key, fallback);

    public string String(string key, string fallback) =>
        Values[key] is JsonValue v && v.TryGetValue<string>(out var s) ? s : fallback;

    public void Clear()
    {
        Values = new JsonObject();
        Save();
    }

    public void Save()
    {
        _debounce.Stop();
        _debounce.Start();
    }

    public void Flush()
    {
        _debounce.Stop();
        try
        {
            Directory.CreateDirectory(Path.GetDirectoryName(FilePath)!);
            var tmp = FilePath + ".tmp";
            File.WriteAllText(tmp, Values.ToJsonString(new JsonSerializerOptions { WriteIndented = true }));
            File.Move(tmp, FilePath, overwrite: true);
        }
        catch (Exception ex) when (ex is IOException or UnauthorizedAccessException)
        {
        }
    }

    private static JsonObject Load(string path)
    {
        try
        {
            if (File.Exists(path) && JsonNode.Parse(File.ReadAllText(path)) is JsonObject o) return o;
        }
        catch (Exception ex) when (ex is IOException or JsonException or UnauthorizedAccessException)
        {
        }
        return new JsonObject();
    }
}
