import { callMatch, courtStatus, fillCourts, matchQueue, nextMatchToCall, unassignMatch, waitEstimates } from '../lib/actions';
import { stageLabel, divisionName, MatchRow, TeamLine } from '../components/match';
import { minutesLabel } from '../components/ui';
import { useMatchDialog } from '../components/useMatchDialog';
import { useTournament } from '../state/store';

export function Courts() {
  const { t, resolved, canScore, update } = useTournament();
  const { open, dialog } = useMatchDialog();
  const courts = courtStatus(t, resolved);
  const queue = matchQueue(resolved);
  const next = nextMatchToCall(resolved);
  const waits = waitEstimates(t, resolved);
  const openCourts = courts.filter((c) => !c.match);
  const liveWithoutCourt = resolved.ordered.filter(
    (r) => r.m.status === 'live' && !r.done && (!r.m.court || !t.courts.includes(r.m.court)),
  );

  return (
    <>
      <div className="page-head">
        <div>
          <h1>Courts</h1>
          <div className="muted small">
            {courts.length - openCourts.length} of {courts.length} courts in use · {queue.length} match
            {queue.length === 1 ? '' : 'es'} waiting
          </div>
        </div>
        {canScore && (
          <div className="row">
            <label className="check small" title="When a match finishes, automatically send the next match to that court">
              <input
                type="checkbox"
                checked={t.settings.autoCall}
                onChange={(e) =>
                  update((tt) => ({ ...tt, settings: { ...tt.settings, autoCall: e.target.checked }, updatedAt: Date.now() }))
                }
              />
              Auto-call next match
            </label>
            <button className="btn btn-primary" disabled={!openCourts.length || !next} onClick={() => update(fillCourts)}>
              Fill open courts
            </button>
          </div>
        )}
      </div>

      <div className="grid grid-courts">
        {courts.map(({ court, match }) => {
          const game = match?.m.games[match.m.games.length - 1];
          return (
            <div key={court} className={`court ${match ? '' : 'open'}`}>
              <div className="court-head">
                <span>{court}</span>
                {match ? <span className="badge badge-live">Live</span> : <span className="small">Open</span>}
              </div>
              <div className="court-body">
                {match ? (
                  <>
                    <div className="small muted">
                      M{match.m.number} · {t.divisions.length > 1 ? `${divisionName(t, match.m.divisionId)} · ` : ''}
                      {stageLabel(t, match.m)}
                      {match.m.games.length > 1 ? ` · Game ${match.m.games.length}` : ''}
                    </div>
                    {(['a', 'b'] as const).map((side) => (
                      <div className="court-score" key={side}>
                        <div style={{ minWidth: 0 }}>
                          <TeamLine t={t} r={{ ...match, m: { ...match.m, games: [] } }} side={side} />
                        </div>
                        <span className="big">{game ? (side === 'a' ? game.a : game.b) : 0}</span>
                      </div>
                    ))}
                    {canScore && (
                      <div className="row" style={{ marginTop: 'auto' }}>
                        <a className="btn btn-primary btn-sm" href={`#/score/${match.m.id}`}>
                          Keep score
                        </a>
                        <button className="btn btn-sm" onClick={() => open(match)}>
                          Enter final
                        </button>
                        <button
                          className="btn btn-sm btn-ghost"
                          title="Send this match back to the queue"
                          onClick={() => update((tt) => unassignMatch(tt, match.m.id))}
                        >
                          Unassign
                        </button>
                      </div>
                    )}
                  </>
                ) : (
                  <>
                    {next ? (
                      <div className="small">
                        <div className="muted">Next up:</div>
                        <div className="bold truncate">
                          M{next.m.number}: {t.teams[next.a as string]?.name} vs {t.teams[next.b as string]?.name}
                        </div>
                      </div>
                    ) : (
                      <div className="muted small">No match ready right now.</div>
                    )}
                    {canScore && next && (
                      <button
                        className="btn btn-accent"
                        style={{ marginTop: 'auto' }}
                        onClick={() => update((tt) => callMatch(tt, next.m.id, court))}
                      >
                        Call M{next.m.number} to {court}
                      </button>
                    )}
                  </>
                )}
              </div>
            </div>
          );
        })}
      </div>

      {liveWithoutCourt.length > 0 && (
        <>
          <div className="section-title">
            <h2>In progress (no court)</h2>
          </div>
          <div className="card" style={{ padding: 0 }}>
            {liveWithoutCourt.map((r) => (
              <MatchRow key={r.m.id} t={t} r={r} onOpen={open} />
            ))}
          </div>
        </>
      )}

      <div className="section-title">
        <h2>Queue</h2>
        <span className="muted small">Ready matches in play order. Teams still on court are skipped automatically.</span>
      </div>
      {queue.length === 0 ? (
        <div className="card empty">Nothing waiting — matches appear here once both teams are known.</div>
      ) : (
        <div className="card" style={{ padding: 0 }}>
          {queue.map((q) => (
            <MatchRow
              key={q.r.m.id}
              t={t}
              r={q.r}
              onOpen={open}
              right={
                <>
                  {q.blocked ? (
                    <span className="tiny muted">Team on court</span>
                  ) : (
                    <span className="tiny muted">{minutesLabel(waits.get(q.r.m.id))}</span>
                  )}
                  {canScore && openCourts.length > 0 && (
                    <select
                      className="input"
                      style={{ padding: '3px 6px', fontSize: '0.8rem', width: 'auto' }}
                      value=""
                      onClick={(e) => e.stopPropagation()}
                      onChange={(e) => {
                        const court = e.target.value;
                        if (court) update((tt) => callMatch(tt, q.r.m.id, court));
                      }}
                    >
                      <option value="">Call to…</option>
                      {openCourts.map((c) => (
                        <option key={c.court} value={c.court}>
                          {c.court}
                        </option>
                      ))}
                    </select>
                  )}
                </>
              }
            />
          ))}
        </div>
      )}
      {dialog}
    </>
  );
}
