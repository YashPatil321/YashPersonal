namespace Shared.NowPlaying;

/// <summary>
/// Extrapolates the playback position between player reports.
/// While playing, <c>position = lastReportedPosition + (now - lastReportTime)</c>. A new report that differs from the
/// extrapolated value by more than <see cref="SnapThreshold"/> snaps; a smaller difference is eased in over
/// <see cref="EaseSeconds"/> so the position never jumps backwards by a tiny amount.
/// Platform-neutral (also compiled into the Linux test project).
/// </summary>
public sealed class PositionClock
{
    public const double SnapThreshold = 0.35;
    public const double EaseSeconds = 0.5;

    private double _anchorPosition;
    private double _anchorTime;
    private double _correction;
    private bool _playing;
    private bool _hasReport;

    public bool IsPlaying => _playing;

    /// <summary>Feeds a reported position (seconds) observed at <paramref name="now"/> (seconds, monotonic).</summary>
    public void Report(double reportedPosition, bool playing, double now)
    {
        if (!_hasReport || !playing || !_playing)
        {
            Snap(reportedPosition, playing, now);
            return;
        }

        var current = PositionAt(now);
        var diff = reportedPosition - current;
        if (Math.Abs(diff) > SnapThreshold)
        {
            Snap(reportedPosition, playing, now);
            return;
        }

        _anchorPosition = current;
        _anchorTime = now;
        _correction = diff;
    }

    /// <summary>Forgets the history, e.g. when the track changes.</summary>
    public void Reset(double position, bool playing, double now) => Snap(position, playing, now);

    public double PositionAt(double now)
    {
        if (!_hasReport) return 0;
        if (!_playing) return _anchorPosition;
        var elapsed = Math.Max(0, now - _anchorTime);
        // The eased correction moves at most |diff| / EaseSeconds = 0.7 s/s, slower than real time, so the
        // displayed position is monotonic while playing.
        return _anchorPosition + elapsed + _correction * (1 - Math.Exp(-elapsed / EaseSeconds));
    }

    private void Snap(double position, bool playing, double now)
    {
        _anchorPosition = position;
        _anchorTime = now;
        _correction = 0;
        _playing = playing;
        _hasReport = true;
    }
}
