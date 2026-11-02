import { useEffect, useState } from 'react';
import { Trophy } from 'lucide-react';
import { courtStatus, matchQueue } from '../lib/actions';
import { teamName } from '../lib/tournament';
import { divisionName, stageLabel } from '../components/match';
import { MiniCourt } from '../components/MiniCourt';
import { BallIcon } from '../components/ui';
import { useTournament } from '../state/store';

/** Big-screen display for a TV at the venue. */
export function TV() {
  const { t, resolved } = useTournament();
  const [now, setNow] = useState(Date.now());
  useEffect(() => {
    const id = setInterval(() => setNow(Date.now()), 30000);
    return () => clearInterval(id);
  }, []);

  const courts = courtStatus(t, resolved);
  const queue = matchQueue(resolved).filter((q) => !q.blocked).slice(0, 8);
  const recent = resolved.ordered
    .filter((r) => r.m.status === 'final' && r.m.finishedAt)
    .sort((a, b) => (b.m.finishedAt ?? 0) - (a.m.finishedAt ?? 0))
    .slice(0, 6);
  const champions = t.divisions
    .map((d) => ({ d, rd: resolved.divisions[d.id] }))
    .filter(({ rd }) => rd.complete && rd.placements.length);

  return (
    <div className="tv">
      <div className="tv-head">
        <div className="row" style={{ gap: 16, flexWrap: 'nowrap', minWidth: 0 }}>
          <BallIcon size={56} className="ball-spin" />
          <div style={{ minWidth: 0 }}>
            <div className="eyebrow" style={{ color: 'var(--ball)' }}>
              Live courts
            </div>
            <div className="tv-title truncate">{t.name}</div>
          </div>
        </div>
        <div className="row" style={{ gap: 18 }}>
          <span className="tv-clock">{new Date(now).toLocaleTimeString([], { hour: 'numeric', minute: '2-digit' })}</span>
          <a href="#/" className="btn btn-glass btn-sm">
            Exit
          </a>
        </div>
      </div>

      {champions.length > 0 && (
        <div className="champion-card" style={{ marginBottom: 22, textAlign: 'left', display: 'grid', gap: 6 }}>
          <div className="row" style={{ gap: 10 }}>
            <Trophy size={22} color="var(--ball)" />
            <span className="eyebrow">Champions</span>
          </div>
          {champions.map(({ d, rd }) => (
            <div key={d.id} className="row-between" style={{ fontSize: '1.3rem' }}>
              <span style={{ color: 'var(--on-night-muted)', fontWeight: 700 }}>{d.name}</span>
              <span className="who" style={{ margin: 0 }}>
                {teamName(t, rd.placements[0].teamIds[0])}
              </span>
            </div>
          ))}
        </div>
      )}

      <div className="tv-grid">
        <div className="grid" style={{ gridTemplateColumns: 'repeat(auto-fill, minmax(340px, 1fr))', alignContent: 'start' }}>
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
                ) : (
                  <span>Waiting for the next match</span>
                )
              }
            />
          ))}
        </div>
        <div className="stack" style={{ gap: 22 }}>
          <div>
            <h2>Up next</h2>
            <div className="tv-list">
              {queue.length === 0 && (
                <div className="item" style={{ color: 'var(--muted)' }}>
                  No matches waiting
                </div>
              )}
              {queue.map((q, i) => (
                <div className="item" key={q.r.m.id}>
                  <span className="n">{i + 1}</span>
                  <span>
                    {teamName(t, q.r.a as string)} <span style={{ color: 'var(--muted)' }}>vs</span> {teamName(t, q.r.b as string)}
                  </span>
                </div>
              ))}
            </div>
          </div>
          {recent.length > 0 && (
            <div>
              <h2>Results</h2>
              <div className="tv-list">
                {recent.map((r) => (
                  <div className="item" key={r.m.id}>
                    <span>
                      <b>{teamName(t, r.winner as string)}</b> <span style={{ color: 'var(--muted)' }}>def.</span>{' '}
                      {teamName(t, r.loser as string)}{' '}
                      <span style={{ color: 'var(--ball)', fontWeight: 800 }} className="num nowrap">
                        {r.m.forfeit
                          ? 'W/O'
                          : r.m.games.map((g) => (r.winnerSide === 'a' ? `${g.a}-${g.b}` : `${g.b}-${g.a}`)).join(', ')}
                      </span>
                    </span>
                  </div>
                ))}
              </div>
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
