import { courtStatus, fillCourts, matchQueue, waitEstimates } from '../lib/actions';
import { FORMAT_LABELS, teamName } from '../lib/tournament';
import { MatchCard } from '../components/match';
import { Podium } from '../components/Standings';
import { Progress, minutesLabel, timeAgo } from '../components/ui';
import { useMatchDialog } from '../components/useMatchDialog';
import { useTournament } from '../state/store';

export function Overview() {
  const { t, resolved, canScore, update } = useTournament();
  const { open, dialog } = useMatchDialog();

  const total = resolved.ordered.filter((r) => !r.notNeeded).length;
  const done = resolved.ordered.filter((r) => r.done && !r.notNeeded).length;
  const courts = courtStatus(t, resolved);
  const live = courts.filter((c) => c.match);
  const queue = matchQueue(resolved).filter((q) => !q.blocked);
  const waits = waitEstimates(t, resolved);
  const recent = resolved.ordered
    .filter((r) => r.m.status === 'final' && r.m.finishedAt)
    .sort((a, b) => (b.m.finishedAt ?? 0) - (a.m.finishedAt ?? 0))
    .slice(0, 6);
  const started = resolved.ordered.some((r) => r.m.status !== 'pending');
  const finished = total > 0 && done === total;

  return (
    <>
      <div className="page-head">
        <div>
          <h1>{t.name}</h1>
          <div className="muted">
            {[t.date && new Date(t.date + 'T12:00:00').toLocaleDateString(undefined, { weekday: 'long', month: 'long', day: 'numeric' }), t.location]
              .filter(Boolean)
              .join(' · ')}
          </div>
        </div>
        <a className="btn" href="#/teams">
          Find my matches
        </a>
      </div>

      <div className="grid grid-3">
        <div className="card">
          <div className="muted small bold">Matches complete</div>
          <div className="row-between" style={{ margin: '4px 0 8px' }}>
            <span style={{ fontSize: '1.7rem', fontWeight: 800 }} className="num">
              {done}
              <span className="muted" style={{ fontSize: '1rem' }}>
                {' '}
                / {total}
              </span>
            </span>
            {finished && <span className="badge badge-accent">Tournament complete</span>}
          </div>
          <Progress value={done} total={total} />
        </div>
        <div className="card">
          <div className="muted small bold">On court now</div>
          <div style={{ fontSize: '1.7rem', fontWeight: 800 }} className="num">
            {live.length}
            <span className="muted" style={{ fontSize: '1rem' }}>
              {' '}
              / {t.courts.length} courts
            </span>
          </div>
          <div className="muted small">{queue.length} match{queue.length === 1 ? '' : 'es'} ready to play</div>
        </div>
        <div className="card">
          <div className="muted small bold">Field</div>
          <div style={{ fontSize: '1.7rem', fontWeight: 800 }} className="num">
            {Object.keys(t.teams).length}
            <span className="muted" style={{ fontSize: '1rem' }}>
              {' '}
              {t.settings.doubles ? 'teams' : 'players'}
            </span>
          </div>
          <div className="muted small">
            {t.divisions.length} division{t.divisions.length === 1 ? '' : 's'}
          </div>
        </div>
      </div>

      {canScore && !started && (
        <div className="card section" style={{ background: 'var(--brand-soft)', borderColor: 'transparent' }}>
          <div className="row-between" style={{ flexWrap: 'wrap' }}>
            <div>
              <h3 style={{ marginBottom: 2 }}>Ready to play?</h3>
              <div className="muted small">Send the first {Math.min(t.courts.length, queue.length)} matches to the courts.</div>
            </div>
            <button className="btn btn-primary" onClick={() => update(fillCourts)}>
              Start tournament
            </button>
          </div>
        </div>
      )}

      {live.length > 0 && (
        <>
          <div className="section-title">
            <h2>On court now</h2>
            <a className="small" href="#/courts">
              All courts →
            </a>
          </div>
          <div className="grid grid-courts">
            {live.map(({ court, match }) => (
              <MatchCard key={court} t={t} r={match!} onOpen={open} />
            ))}
          </div>
        </>
      )}

      {queue.length > 0 && (
        <>
          <div className="section-title">
            <h2>Up next</h2>
          </div>
          <div className="grid grid-courts">
            {queue.slice(0, 6).map((q, i) => (
              <MatchCard
                key={q.r.m.id}
                t={t}
                r={q.r}
                onOpen={open}
                extra={
                  <div className="match-meta">
                    <span className="badge badge-accent">#{i + 1} in line</span>
                    <span>{minutesLabel(waits.get(q.r.m.id))}</span>
                  </div>
                }
              />
            ))}
          </div>
        </>
      )}

      <div className="section-title">
        <h2>Divisions</h2>
      </div>
      <div className="grid grid-2">
        {t.divisions.map((d) => {
          const rd = resolved.divisions[d.id];
          return (
            <div className="card" key={d.id}>
              <div className="card-head">
                <h3>{d.name}</h3>
                <span className="badge">{FORMAT_LABELS[d.settings.format]}</span>
              </div>
              <div className="row-between small muted" style={{ marginBottom: 6 }}>
                <span>
                  {d.teamIds.length} {t.settings.doubles ? 'teams' : 'players'}
                </span>
                <span className="num">
                  {rd.progress.done}/{rd.progress.total} matches
                </span>
              </div>
              <Progress value={rd.progress.done} total={rd.progress.total} />
              {rd.placements.length > 0 && (
                <div style={{ marginTop: 12 }}>
                  <Podium t={t} placements={rd.placements} />
                </div>
              )}
              <div className="row" style={{ marginTop: 12 }}>
                <a className="btn btn-sm" href={`#/standings?d=${d.id}`}>
                  Standings
                </a>
                {d.settings.format !== 'round_robin' && (
                  <a className="btn btn-sm" href={`#/brackets?d=${d.id}`}>
                    Bracket
                  </a>
                )}
                <a className="btn btn-sm" href={`#/matches?d=${d.id}`}>
                  Matches
                </a>
              </div>
            </div>
          );
        })}
      </div>

      {recent.length > 0 && (
        <>
          <div className="section-title">
            <h2>Latest results</h2>
          </div>
          <div className="card" style={{ padding: 0 }}>
            {recent.map((r) => (
              <div key={r.m.id} className="list-row" onClick={() => open(r)} role="button" tabIndex={0}>
                <span className="bold">M{r.m.number}</span>
                <span className="truncate">
                  <b>{teamName(t, r.winner as string)}</b> <span className="muted">def.</span> {teamName(t, r.loser as string)}
                </span>
                <span className="num small muted nowrap">
                  {r.m.forfeit ? 'W/O' : r.m.games.map((g) => (r.winnerSide === 'a' ? `${g.a}-${g.b}` : `${g.b}-${g.a}`)).join(', ')}
                  <span className="tiny" style={{ display: 'block', textAlign: 'right' }}>
                    {timeAgo(r.m.finishedAt)}
                  </span>
                </span>
              </div>
            ))}
          </div>
        </>
      )}
      {dialog}
    </>
  );
}
