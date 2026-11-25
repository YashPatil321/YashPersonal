using System.IO;
using System.Text.Json;
using System.Text.Json.Serialization;

namespace Shared.Settings;

/// <summary>
/// Persists a settings object as JSON at <c>%APPDATA%\{app}\settings.json</c>. <see cref="Save"/> is debounced by
/// 500 ms; <see cref="Flush"/> writes immediately (call it on exit).
/// </summary>
public sealed class SettingsStore<T> : IDisposable where T : class, new()
{
    public const int DebounceMs = 500;

    public static readonly JsonSerializerOptions JsonOptions = new()
    {
        WriteIndented = true,
        PropertyNamingPolicy = JsonNamingPolicy.CamelCase,
        DefaultIgnoreCondition = JsonIgnoreCondition.Never,
        Converters = { new JsonStringEnumConverter(JsonNamingPolicy.CamelCase) },
        ReadCommentHandling = JsonCommentHandling.Skip,
        AllowTrailingCommas = true,
    };

    private readonly object _gate = new();
    private readonly Timer _timer;
    private bool _dirty;

    public SettingsStore(string appName)
    {
        var dir = Path.Combine(Environment.GetFolderPath(Environment.SpecialFolder.ApplicationData), appName);
        FilePath = Path.Combine(dir, "settings.json");
        Value = Load(FilePath);
        _timer = new Timer(_ => Flush(), null, Timeout.Infinite, Timeout.Infinite);
    }

    public string FilePath { get; }

    /// <summary>The live settings object. Mutate it, then call <see cref="Save"/>.</summary>
    public T Value { get; }

    /// <summary>Raised on the calling thread whenever <see cref="Save"/> is called.</summary>
    public event EventHandler? Changed;

    /// <summary>Marks the settings dirty and schedules a write in 500 ms (restarting the wait).</summary>
    public void Save()
    {
        lock (_gate)
        {
            _dirty = true;
            _timer.Change(DebounceMs, Timeout.Infinite);
        }
        Changed?.Invoke(this, EventArgs.Empty);
    }

    public void Flush()
    {
        string json;
        lock (_gate)
        {
            if (!_dirty) return;
            _dirty = false;
            json = JsonSerializer.Serialize(Value, JsonOptions);
        }
        try
        {
            Directory.CreateDirectory(Path.GetDirectoryName(FilePath)!);
            var tmp = FilePath + ".tmp";
            File.WriteAllText(tmp, json);
            File.Move(tmp, FilePath, overwrite: true);
        }
        catch (IOException)
        {
        }
        catch (UnauthorizedAccessException)
        {
        }
    }

    private static T Load(string path)
    {
        try
        {
            if (File.Exists(path))
                return JsonSerializer.Deserialize<T>(File.ReadAllText(path), JsonOptions) ?? new T();
        }
        catch (Exception ex) when (ex is IOException or JsonException or UnauthorizedAccessException or NotSupportedException)
        {
        }
        return new T();
    }

    public void Dispose()
    {
        _timer.Dispose();
        Flush();
    }
}
