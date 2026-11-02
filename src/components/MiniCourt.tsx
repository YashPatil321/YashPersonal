import type { ReactNode } from 'react';
import type { ResolvedMatch } from '../lib/resolve';
import { teamName } from '../lib/tournament';
import type { Tournament } from '../lib/types';

/** A court drawn from above, with each team on its side of the net and the live game score. */
export function MiniCourt({
  t,
  court,
  match,
  meta,
  children,
}: {
  t: Tournament;
  court: string;
  match?: ResolvedMatch;
  meta?: ReactNode;
  children?: ReactNode;
}) {
  const game = match?.m.games[match.m.games.length - 1];
  const serving = match?.m.serve?.side;
  return (
    <div className={`court-card ${match ? 'live' : 'open'}`}>
      <div className="court-card-head">
        <span className="court-name">{court}</span>
        {match ? <span className="badge badge-live">Live</span> : <span className="badge">Open</span>}
      </div>
      <div className="court-viz">
        <div className="court-surface">
          {match ? (
            (['a', 'b'] as const).map((side) => (
              <div key={side} className={`court-side ${side === 'b' ? 'right' : ''} ${serving === side ? 'serving' : ''}`}>
                <div className="team" title={teamName(t, side === 'a' ? (match.a as string) : (match.b as string))}>
                  {teamName(t, side === 'a' ? (match.a as string) : (match.b as string))
                    .split(' / ')
                    .slice(0, 2)
                    .map((line, i) => (
                      <span key={i}>{line}</span>
                    ))}
                </div>
                <div className="pts">
                  {side === 'b' && serving === 'b' && <span className="serve-ball" title="Serving" />}
                  {game ? (side === 'a' ? game.a : game.b) : 0}
                  {side === 'a' && serving === 'a' && <span className="serve-ball" title="Serving" />}
                </div>
              </div>
            ))
          ) : (
            <div className="court-open-label">OPEN</div>
          )}
        </div>
      </div>
      <div className="court-card-foot">
        {meta && <div className="match-meta">{meta}</div>}
        {children}
      </div>
    </div>
  );
}
