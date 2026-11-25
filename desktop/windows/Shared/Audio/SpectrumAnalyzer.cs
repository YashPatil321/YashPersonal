namespace Shared.Audio;

/// <summary>Published audio features, each 0..1.</summary>
public readonly record struct AudioFeatures(double Level, double Bass, double Mid, double Treble, double Beat)
{
    public static AudioFeatures Silent { get; } = new(0, 0, 0, 0, 0);
}

/// <summary>
/// The spec's analysis on blocks of 1024 mono samples: Hann window + FFT, bass/mid/treble band energies normalised
/// against a running peak, attack/release smoothing, and spectral-flux beat detection. Platform-neutral.
/// </summary>
public sealed class SpectrumAnalyzer
{
    public const int BlockSize = 1024;
    public const double PeakDecay = 0.995;
    public const double Attack = 0.5;
    public const double Release = 0.08;
    public const int FluxHistory = 43;
    public const double BeatFluxRatio = 1.5;
    public const double BeatMinBass = 0.3;
    public const double BeatMinInterval = 0.25;
    /// <summary>The beat value decays by this factor every 1/60 s.</summary>
    public const double BeatDecayPerFrame = 0.88;

    private static readonly double[] Window = BuildHann(BlockSize);

    private readonly double[] _re = new double[BlockSize];
    private readonly double[] _im = new double[BlockSize];
    private readonly double[] _peaks = new double[4]; // level, bass, mid, treble
    private readonly double[] _smooth = new double[4];
    private readonly Queue<double> _flux = new(FluxHistory + 1);
    private double _fluxSum;
    private double _previousBass;
    private double _lastBeatTime = double.NegativeInfinity;
    private double _beatTime = double.NegativeInfinity;

    public double LastBeatTime => _beatTime;

    /// <summary>Processes one block. <paramref name="time"/> is the block's timestamp in seconds (monotonic).</summary>
    /// <returns>True when this block was a beat.</returns>
    public bool Process(ReadOnlySpan<float> block, double sampleRate, double time)
    {
        if (block.Length < BlockSize) throw new ArgumentException($"Need {BlockSize} samples.", nameof(block));

        double sumSquares = 0;
        for (var i = 0; i < BlockSize; i++)
        {
            double s = block[i];
            sumSquares += s * s;
            _re[i] = s * Window[i];
            _im[i] = 0;
        }
        Fft(_re, _im);

        var binHz = sampleRate / BlockSize;
        var bass = BandEnergy(20, 150, binHz);
        var mid = BandEnergy(150, 2000, binHz);
        var treble = BandEnergy(2000, 8000, binHz);
        var level = Math.Sqrt(sumSquares / BlockSize);

        var raw = new[] { level, bass, mid, treble };
        var norm = new double[4];
        for (var b = 0; b < 4; b++)
        {
            _peaks[b] = Math.Max(raw[b], _peaks[b] * PeakDecay);
            norm[b] = Math.Clamp(raw[b] / Math.Max(_peaks[b], 1e-4), 0, 1);
            var x = norm[b];
            _smooth[b] += (x - _smooth[b]) * (x > _smooth[b] ? Attack : Release);
        }

        // Beat: bass spectral flux against the mean of the recent history.
        var bassNorm = norm[1];
        var flux = Math.Max(0, bassNorm - _previousBass);
        _previousBass = bassNorm;
        var mean = _flux.Count > 0 ? _fluxSum / _flux.Count : 0;
        var isBeat = _flux.Count > 0
                     && flux > BeatFluxRatio * mean
                     && bassNorm > BeatMinBass
                     && time - _lastBeatTime >= BeatMinInterval;
        _flux.Enqueue(flux);
        _fluxSum += flux;
        if (_flux.Count > FluxHistory) _fluxSum -= _flux.Dequeue();

        if (isBeat)
        {
            _lastBeatTime = time;
            _beatTime = time;
        }
        return isBeat;
    }

    /// <summary>Current features at <paramref name="now"/>; the beat decays by 0.88 per 1/60 s since the last beat.</summary>
    public AudioFeatures Features(double now)
    {
        var beat = double.IsNegativeInfinity(_beatTime)
            ? 0
            : Math.Pow(BeatDecayPerFrame, Math.Max(0, now - _beatTime) * 60);
        return new AudioFeatures(_smooth[0], _smooth[1], _smooth[2], _smooth[3], beat < 1e-3 ? 0 : beat);
    }

    public void Reset()
    {
        Array.Clear(_peaks);
        Array.Clear(_smooth);
        _flux.Clear();
        _fluxSum = 0;
        _previousBass = 0;
        _lastBeatTime = _beatTime = double.NegativeInfinity;
    }

    /// <summary>Mean magnitude of the bins in [lo, hi) Hz.</summary>
    private double BandEnergy(double lo, double hi, double binHz)
    {
        var first = Math.Max(1, (int)Math.Ceiling(lo / binHz));
        var last = Math.Min(BlockSize / 2 - 1, (int)Math.Floor(hi / binHz));
        if (last < first) last = first;
        double sum = 0;
        for (var k = first; k <= last; k++) sum += Math.Sqrt(_re[k] * _re[k] + _im[k] * _im[k]);
        return sum / (last - first + 1) / (BlockSize / 4.0);
    }

    private static double[] BuildHann(int n)
    {
        var w = new double[n];
        for (var i = 0; i < n; i++) w[i] = 0.5 * (1 - Math.Cos(2 * Math.PI * i / (n - 1)));
        return w;
    }

    /// <summary>In-place iterative radix-2 FFT.</summary>
    public static void Fft(double[] re, double[] im)
    {
        var n = re.Length;
        for (int i = 1, j = 0; i < n; i++)
        {
            var bit = n >> 1;
            for (; (j & bit) != 0; bit >>= 1) j ^= bit;
            j ^= bit;
            if (i < j)
            {
                (re[i], re[j]) = (re[j], re[i]);
                (im[i], im[j]) = (im[j], im[i]);
            }
        }
        for (var len = 2; len <= n; len <<= 1)
        {
            var angle = -2 * Math.PI / len;
            double wRe = Math.Cos(angle), wIm = Math.Sin(angle);
            for (var i = 0; i < n; i += len)
            {
                double curRe = 1, curIm = 0;
                for (var k = 0; k < len / 2; k++)
                {
                    var aRe = re[i + k + len / 2] * curRe - im[i + k + len / 2] * curIm;
                    var aIm = re[i + k + len / 2] * curIm + im[i + k + len / 2] * curRe;
                    re[i + k + len / 2] = re[i + k] - aRe;
                    im[i + k + len / 2] = im[i + k] - aIm;
                    re[i + k] += aRe;
                    im[i + k] += aIm;
                    var next = curRe * wRe - curIm * wIm;
                    curIm = curRe * wIm + curIm * wRe;
                    curRe = next;
                }
            }
        }
    }
}
