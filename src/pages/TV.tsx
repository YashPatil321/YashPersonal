import { useEffect, useState } from 'react';
import { courtStatus, matchQueue } from '../lib/actions';
import { teamName } from '../lib/tournament';
import { stageLabel } from '../components/match';
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
        <div className="row" style={{ gap: 14 }}>
          <BallIcon size={44} />
          <div className="tv-title">{t.name}</div>
        </div>
        <div className="row" style={{ gap: 16 }}>
          <span style={{ fontSize: '1.4rem', fontWeight: 700 }} className="num">
            {new Date(now).toLocaleTimeString([], { hour: 'numeric', minute: '2-digit' })}
          </span>
          <a href="#/" className="small" style={{ color: '#8fa398' }}>
            Exit
          </a>
        </div>
      </div>

      {champions.length > 0 && (
        <div className="tv-court" style={{ marginBottom: 20, borderColor: 'var(--accent)' }}>
          <div className="label">Champions</div>
          {champions.map(({ d, rd }) => (
            <div key={d.id} className="team">
              <span>{d.name}</span>
              <span>🏆 {teamName(t, rd.placements[0].teamIds[0])}</span>
            </div>
          ))}
        </div>
      )}

      <div className="tv-grid">
        <div>
          <div className="grid" style={{ gridTemplateColumns: 'repeat(auto-fill, minmax(320px, 1fr))', gap: 16 }}>
            {courts.map(({ court, match }) => {
              const g = match?.m.games[match.m.games.length - 1];
              return (
                <div className="tv-court" key={court}>
                  <div className="label">
                    {court}
                    {match && (
                      <span style={{ color: '#8fa398', fontWeight: 600, textTransform: 'none', letterSpacing: 0 }}>
                        {' '}
                        · M{match.m.number} · {stageLabel(t, match.m)}
                        {match.m.games.length > 1 ? ` · G${match.m.games.length}` : ''}
                      </span>
                    )}
                  </div>
                  {match ? (
                    (['a', 'b'] as const).map((side) => (
                      <div className="team" key={side}>
                        <span style={{ minWidth: 0, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
                          {match.m.serve?.side === side && <span className="serving-dot" />}
                          {teamName(t, side === 'a' ? (match.a as string) : (match.b as string))}
                        </span>
                        <span className="pts">{g ? (side === 'a' ? g.a : g.b) : 0}</span>
                      </div>
                    ))
                  ) : (
                    <div style={{ color: '#8fa398', fontSize: '1.2rem' }}>Open</div>
                  )}
                </div>
              );
            })}
          </div>
        </div>
        <div className="stack" style={{ gap: 20 }}>
          <div>
            <h2 style={{ color: 'var(--accent)' }}>Up next</h2>
            <div className="tv-list">
              {queue.length === 0 && <div className="item" style={{ color: '#8fa398' }}>No matches waiting</div>}
              {queue.map((q, i) => (
                <div className="item" key={q.r.m.id}>
                  <span style={{ color: 'var(--accent)', fontWeight: 800 }}>{i + 1}.</span> {teamName(t, q.r.a as string)}{' '}
                  <span style={{ color: '#8fa398' }}>vs</span> {teamName(t, q.r.b as string)}
                </div>
              ))}
            </div>
          </div>
          {recent.length > 0 && (
            <div>
              <h2 style={{ color: 'var(--accent)' }}>Results</h2>
              <div className="tv-list">
                {recent.map((r) => (
                  <div className="item" key={r.m.id}>
                    <b>{teamName(t, r.winner as string)}</b> <span style={{ color: '#8fa398' }}>def.</span>{' '}
                    {teamName(t, r.loser as string)}{' '}
                    <span style={{ color: '#8fa398' }} className="num">
                      {r.m.forfeit
                        ? 'W/O'
                        : r.m.games.map((g) => (r.winnerSide === 'a' ? `${g.a}-${g.b}` : `${g.b}-${g.a}`)).join(', ')}
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
