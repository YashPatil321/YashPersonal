import { Play, Zap } from 'lucide-react';
import { callMatch, courtStatus, fillCourts, matchQueue, nextMatchToCall, unassignMatch, waitEstimates } from '../lib/actions';
import { teamName } from '../lib/tournament';
import { divisionName, MatchRow, stageLabel } from '../components/match';
import { MiniCourt } from '../components/MiniCourt';
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
          <div className="eyebrow">Court desk</div>
          <h1>Courts</h1>
          <div className="muted small">
            {courts.length - openCourts.length} of {courts.length} in play · {queue.length} match{queue.length === 1 ? '' : 'es'} waiting
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
              <Zap size={16} /> Fill open courts
            </button>
          </div>
        )}
      </div>

      <div className="grid grid-courts">
        {courts.map(({ court, match }) => (
          <MiniCourt
            key={court}
            t={t}
            court={court}
            match={match}
            meta={
              match ? (
                <>
                  <span className="match-no">M{match.m.number}</span>
                  <span className="truncate">
                    {t.divisions.length > 1 ? `${divisionName(t, match.m.divisionId)} · ` : ''}
                    {stageLabel(t, match.m)}
                    {match.m.games.length > 1 ? ` · Game ${match.m.games.length}` : ''}
                  </span>
                </>
              ) : next ? (
                <span className="truncate">
                  Next up: <b>M{next.m.number}</b> {teamName(t, next.a as string)} vs {teamName(t, next.b as string)}
                </span>
              ) : (
                <span>No match ready right now</span>
              )
            }
          >
            {canScore && match && (
              <div className="row">
                <a className="btn btn-dark btn-sm" href={`#/score/${match.m.id}`}>
                  <Play size={14} /> Keep score
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
            {canScore && !match && next && (
              <button className="btn btn-primary btn-block" onClick={() => update((tt) => callMatch(tt, next.m.id, court))}>
                Call M{next.m.number} to {court}
              </button>
            )}
            {!canScore && match && (
              <button className="btn btn-sm" onClick={() => open(match)}>
                Match details
              </button>
            )}
          </MiniCourt>
        ))}
      </div>

      {liveWithoutCourt.length > 0 && (
        <>
          <div className="section-title">
            <h2>In progress, no court</h2>
          </div>
          <div className="card list-card">
            {liveWithoutCourt.map((r) => (
              <MatchRow key={r.m.id} t={t} r={r} onOpen={open} />
            ))}
          </div>
        </>
      )}

      <div className="section-title">
        <h2>Up next</h2>
        <span className="muted small">In play order. Teams still on court are skipped automatically.</span>
      </div>
      {queue.length === 0 ? (
        <div className="card empty">Nothing waiting. Matches show up here once both teams are known.</div>
      ) : (
        <div className="card list-card">
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
                    <span className="tiny bold">{minutesLabel(waits.get(q.r.m.id))}</span>
                  )}
                  {canScore && openCourts.length > 0 && (
                    <select
                      className="input"
                      style={{ padding: '4px 8px', fontSize: '0.8rem', width: 'auto', borderRadius: 9 }}
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
