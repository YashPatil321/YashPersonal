using System.Diagnostics;
using NAudio.CoreAudioApi;
using NAudio.CoreAudioApi.Interfaces;
using NAudio.Wave;

namespace Shared.Audio;

/// <summary>
/// Captures system audio with WASAPI loopback (no microphone), mixes to mono and feeds 1024-sample blocks to a
/// <see cref="SpectrumAnalyzer"/>. The capture is recreated when the default render device changes or the device
/// disappears. <see cref="Features"/> is safe to read from any thread.
/// </summary>
public sealed class AudioAnalyzer : IDisposable
{
    private readonly object _gate = new();
    private readonly SpectrumAnalyzer _analyzer = new();
    private readonly float[] _block = new float[SpectrumAnalyzer.BlockSize];
    private readonly Stopwatch _clock = Stopwatch.StartNew();
    private readonly MMDeviceEnumerator? _enumerator;
    private readonly DeviceNotifications? _notifications;
    private WasapiLoopbackCapture? _capture;
    private int _blockFill;
    private double _lastDataTime = double.NegativeInfinity;
    private bool _running;
    private bool _disposed;
    private Timer? _restartTimer;

    public AudioAnalyzer()
    {
        try
        {
            _enumerator = new MMDeviceEnumerator();
            _notifications = new DeviceNotifications(this);
            _enumerator.RegisterEndpointNotificationCallback(_notifications);
        }
        catch (Exception ex)
        {
            Debug.WriteLine($"Audio device notifications unavailable: {ex.Message}");
        }
    }

    /// <summary>A short description of the capture state, for diagnostics.</summary>
    public string Status { get; private set; } = "Stopped";

    public bool IsCapturing => _capture is not null;

    public void Start()
    {
        lock (_gate)
        {
            _running = true;
            StartCaptureLocked();
        }
    }

    public void Stop()
    {
        lock (_gate)
        {
            _running = false;
            StopCaptureLocked();
            Status = "Stopped";
        }
    }

    /// <summary>The published features now. Bands fade out when the loopback stream goes silent (no packets).</summary>
    public AudioFeatures Features
    {
        get
        {
            lock (_gate)
            {
                var now = _clock.Elapsed.TotalSeconds;
                var f = _analyzer.Features(now);
                var stale = now - _lastDataTime;
                if (stale > 0.15)
                {
                    // WASAPI loopback sends nothing during silence: decay with the analyser's release rate.
                    var k = Math.Pow(1 - SpectrumAnalyzer.Release, Math.Min(600, (stale - 0.15) * 60));
                    f = new AudioFeatures(f.Level * k, f.Bass * k, f.Mid * k, f.Treble * k, f.Beat);
                }
                return f;
            }
        }
    }

    /// <summary>The time base used by <see cref="SpectrumAnalyzer.LastBeatTime"/> (seconds).</summary>
    public double Now => _clock.Elapsed.TotalSeconds;

    /// <summary>Time of the most recent beat on the <see cref="Now"/> clock (negative infinity when none yet).</summary>
    public double LastBeatTime
    {
        get { lock (_gate) return _analyzer.LastBeatTime; }
    }

    /// <summary>True when non-silent audio arrived in the last two seconds.</summary>
    public bool HasRecentAudio
    {
        get { lock (_gate) return Now - _analyzer.LastAudioTime < 2; }
    }

    /// <summary>
    /// Copies the 64-bin spectrum and 128-sample waveform. Both read as silence when no audio arrived for a second.
    /// </summary>
    public void CopySpectrum(Span<float> bins, Span<float> wave)
    {
        lock (_gate)
        {
            if (Now - _analyzer.LastAudioTime > 1.0)
            {
                bins.Clear();
                wave.Clear();
                return;
            }
            _analyzer.CopySpectrum(bins, wave);
        }
    }

    private void StartCaptureLocked()
    {
        if (_disposed || !_running || _capture is not null) return;
        try
        {
            var capture = new WasapiLoopbackCapture();
            capture.DataAvailable += OnData;
            capture.RecordingStopped += OnStopped;
            capture.StartRecording();
            _capture = capture;
            _blockFill = 0;
            Status = $"Capturing {capture.WaveFormat.SampleRate} Hz, {capture.WaveFormat.Channels} ch";
        }
        catch (Exception ex)
        {
            Status = $"No audio device ({ex.Message})";
            ScheduleRestart(TimeSpan.FromSeconds(3));
        }
    }

    private void StopCaptureLocked()
    {
        var capture = _capture;
        _capture = null;
        if (capture is null) return;
        capture.DataAvailable -= OnData;
        capture.RecordingStopped -= OnStopped;
        try
        {
            capture.StopRecording();
        }
        catch (Exception)
        {
        }
        // Dispose off the capture thread.
        ThreadPool.QueueUserWorkItem(_ =>
        {
            try { capture.Dispose(); }
            catch (Exception) { }
        });
    }

    /// <summary>Recreates the capture after a short delay (device changes arrive in bursts).</summary>
    internal void ScheduleRestart(TimeSpan delay)
    {
        lock (_gate)
        {
            if (_disposed) return;
            _restartTimer?.Dispose();
            _restartTimer = new Timer(_ =>
            {
                lock (_gate)
                {
                    StopCaptureLocked();
                    StartCaptureLocked();
                }
            }, null, delay, Timeout.InfiniteTimeSpan);
        }
    }

    private void OnStopped(object? sender, StoppedEventArgs e)
    {
        if (e.Exception is not null)
        {
            Status = $"Capture stopped ({e.Exception.Message})";
            ScheduleRestart(TimeSpan.FromSeconds(1));
        }
    }

    private void OnData(object? sender, WaveInEventArgs e)
    {
        if (sender is not WasapiLoopbackCapture capture || e.BytesRecorded <= 0) return;
        var format = capture.WaveFormat;
        var channels = Math.Max(1, format.Channels);
        var isFloat = format.Encoding == WaveFormatEncoding.IeeeFloat ||
                      (format.Encoding == WaveFormatEncoding.Extensible && format.BitsPerSample == 32);
        var bytesPerSample = format.BitsPerSample / 8;
        if (bytesPerSample is not (2 or 3 or 4)) return;
        var frameBytes = bytesPerSample * channels;
        var frames = e.BytesRecorded / frameBytes;
        var buffer = e.Buffer;

        lock (_gate)
        {
            if (!ReferenceEquals(capture, _capture)) return;
            _lastDataTime = _clock.Elapsed.TotalSeconds;
            for (var f = 0; f < frames; f++)
            {
                double sum = 0;
                var offset = f * frameBytes;
                for (var c = 0; c < channels; c++)
                {
                    var o = offset + c * bytesPerSample;
                    sum += bytesPerSample switch
                    {
                        4 when isFloat => BitConverter.ToSingle(buffer, o),
                        4 => BitConverter.ToInt32(buffer, o) / 2147483648.0,
                        3 => ((buffer[o] | (buffer[o + 1] << 8) | (buffer[o + 2] << 16)) << 8 >> 8) / 8388608.0,
                        _ => BitConverter.ToInt16(buffer, o) / 32768.0,
                    };
                }
                _block[_blockFill++] = (float)(sum / channels);
                if (_blockFill == _block.Length)
                {
                    _blockFill = 0;
                    _analyzer.Process(_block, format.SampleRate, _clock.Elapsed.TotalSeconds);
                }
            }
        }
    }

    public void Dispose()
    {
        lock (_gate)
        {
            _disposed = true;
            _running = false;
            _restartTimer?.Dispose();
            StopCaptureLocked();
        }
        try
        {
            if (_notifications is not null) _enumerator?.UnregisterEndpointNotificationCallback(_notifications);
            _enumerator?.Dispose();
        }
        catch (Exception)
        {
        }
    }

    /// <summary>COM callback for device changes. Never touches the capture inline (COM re-entrancy); it schedules.</summary>
    private sealed class DeviceNotifications : IMMNotificationClient
    {
        private readonly AudioAnalyzer _owner;

        public DeviceNotifications(AudioAnalyzer owner) => _owner = owner;

        public void OnDefaultDeviceChanged(DataFlow flow, Role role, string defaultDeviceId)
        {
            if (flow == DataFlow.Render && role == Role.Multimedia)
                _owner.ScheduleRestart(TimeSpan.FromMilliseconds(400));
        }

        public void OnDeviceStateChanged(string deviceId, DeviceState newState) { }
        public void OnDeviceAdded(string pwstrDeviceId) { }
        public void OnDeviceRemoved(string deviceId) { }
        public void OnPropertyValueChanged(string pwstrDeviceId, PropertyKey key) { }
    }
}
