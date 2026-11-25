using System.IO;
using System.Text.Json;
using System.Text.Json.Nodes;

namespace Wave.Desktop;

/// <summary>Widget frames (screen pixels) and the first-launch flag, in %APPDATA%\Wave\layout.json.</summary>
internal sealed class LayoutStore
{
    private readonly string _path;
    private JsonObject _root;

    public LayoutStore()
    {
        _path = Path.Combine(Environment.GetFolderPath(Environment.SpecialFolder.ApplicationData), "Wave", "layout.json");
        _root = Load(_path);
    }

    public bool Launched
    {
        get => _root["launched"]?.GetValue<bool>() == true;
        set { _root["launched"] = value; Save(); }
    }

    public Win32.RECT? Get(string kind)
    {
        if (_root[kind] is not JsonObject o) return null;
        try
        {
            int x = o["x"]!.GetValue<int>(), y = o["y"]!.GetValue<int>(), w = o["w"]!.GetValue<int>(), h = o["h"]!.GetValue<int>();
            return new Win32.RECT { Left = x, Top = y, Right = x + w, Bottom = y + h };
        }
        catch (Exception)
        {
            return null;
        }
    }

    public void Set(string kind, Win32.RECT r)
    {
        _root[kind] = new JsonObject { ["x"] = r.Left, ["y"] = r.Top, ["w"] = r.Width, ["h"] = r.Height };
        Save();
    }

    private void Save()
    {
        try
        {
            Directory.CreateDirectory(Path.GetDirectoryName(_path)!);
            File.WriteAllText(_path, _root.ToJsonString(new JsonSerializerOptions { WriteIndented = true }));
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
