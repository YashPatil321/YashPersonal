namespace Shared.Settings;

/// <summary>Prevents two copies of an app running in the same session.</summary>
public sealed class SingleInstance : IDisposable
{
    private readonly Mutex _mutex;

    private SingleInstance(Mutex mutex, bool owned)
    {
        _mutex = mutex;
        IsFirst = owned;
    }

    public bool IsFirst { get; }

    public static SingleInstance Acquire(string appName)
    {
        var mutex = new Mutex(initiallyOwned: true, $@"Local\{appName}.SingleInstance", out var created);
        return new SingleInstance(mutex, created);
    }

    public void Dispose()
    {
        if (IsFirst)
        {
            try { _mutex.ReleaseMutex(); }
            catch (ApplicationException) { }
        }
        _mutex.Dispose();
    }
}
