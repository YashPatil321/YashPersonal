import type { ReactNode } from 'react';
import type { ResolvedMatch } from '../lib/resolve';
import { teamName } from '../lib/tournament';
import type { Match, SlotSource, SlotValue, Tournament } from '../lib/types';
import { TeamAvatars } from './ui';

export function stageLabel(t: Tournament, m: Match): string {
  if (m.stage === 'pool') {
    const pool = t.divisions.find((d) => d.id === m.divisionId)?.pools.find((p) => p.id === m.poolId);
    return `${pool?.name ?? 'Pool'} · Round ${m.round}`;
  }
  if (m.stage === 'rr') return `Round ${m.round}`;
  return m.label ?? 'Playoff';
}

export function divisionName(t: Tournament, id: string): string {
  return t.divisions.find((d) => d.id === id)?.name ?? '';
}

export function describeSource(t: Tournament, s: SlotSource): string {
  switch (s.kind) {
    case 'winner': {
      const src = t.matches[s.matchId];
      return src && src.number ? `Winner of M${src.number}` : 'TBD';
    }
    case 'loser': {
      const src = t.matches[s.matchId];
      return src && src.number ? `Loser of M${src.number}` : 'TBD';
    }
    case 'qualifier':
      return `Playoff seed ${s.rank}`;
    case 'bye':
      return 'BYE';
    default:
      return 'TBD';
  }
}

export function slotName(t: Tournament, value: SlotValue, source: SlotSource): { text: string; tbd: boolean } {
  if (value === null) return { text: describeSource(t, source), tbd: true };
  return { text: teamName(t, value), tbd: value === 'BYE' };
}

export function StatusBadge({ r }: { r: ResolvedMatch }) {
  if (r.stale) return <span className="badge badge-warn">Check score</span>;
  if (r.notNeeded) return <span className="badge">Not needed</span>;
  if (r.m.status === 'final') return <span className="badge badge-final">Final{r.m.forfeit ? ' · W/O' : ''}</span>;
  if (r.m.status === 'live') return <span className="badge badge-live">Live{r.m.court ? ` · ${r.m.court}` : ''}</span>;
  if (r.ready) return <span className="badge badge-court">Ready</span>;
  return <span className="badge">Waiting</span>;
}

function Scores({ r, side }: { r: ResolvedMatch; side: 'a' | 'b' }) {
  if (!r.m.games.length) return null;
  return (
    <div className="scores">
      {r.m.games.map((g, i) => {
        const mine = side === 'a' ? g.a : g.b;
        const theirs = side === 'a' ? g.b : g.a;
        return (
          <span key={i} className={mine > theirs && r.m.status === 'final' ? 'won' : ''}>
            {mine}
          </span>
        );
      })}
    </div>
  );
}

export function TeamLine({ t, r, side, avatars = true }: { t: Tournament; r: ResolvedMatch; side: 'a' | 'b'; avatars?: boolean }) {
  const value = side === 'a' ? r.a : r.b;
  const source = side === 'a' ? r.m.a : r.m.b;
  const { text, tbd } = slotName(t, value, source);
  const isWinner = r.done && r.winnerSide === side && !r.isBye;
  const isLoser = r.done && r.winnerSide && r.winnerSide !== side && !r.isBye;
  const serving = r.m.status === 'live' && r.m.serve?.side === side;
  return (
    <div
      className={`match-team ${isWinner ? 'winner' : ''} ${isLoser ? 'loser' : ''}`}
      style={avatars ? undefined : { gridTemplateColumns: 'minmax(0,1fr) auto' }}
    >
      {avatars && <TeamAvatars t={t} teamId={typeof value === 'string' ? value : null} size={26} />}
      <div className={`name ${tbd ? 'tbd' : ''}`} title={text}>
        {serving && <span className="serving-dot" title="Serving" />}
        {text}
        {isWinner && <span className="check-mark">✓</span>}
      </div>
      <Scores r={r} side={side} />
    </div>
  );
}

export function MatchCard({
  t,
  r,
  onOpen,
  showDivision = true,
  extra,
}: {
  t: Tournament;
  r: ResolvedMatch;
  onOpen?: (r: ResolvedMatch) => void;
  showDivision?: boolean;
  extra?: ReactNode;
}) {
  return (
    <div
      className={`match ${onOpen ? 'clickable' : ''} ${r.m.status === 'live' && !r.done ? 'is-live' : ''}`}
      onClick={onOpen ? () => onOpen(r) : undefined}
      role={onOpen ? 'button' : undefined}
      tabIndex={onOpen ? 0 : undefined}
      onKeyDown={onOpen ? (e) => e.key === 'Enter' && onOpen(r) : undefined}
    >
      <div className="match-meta">
        <span className="match-no">M{r.m.number}</span>
        <span className="truncate" style={{ flex: 1 }}>
          {showDivision && t.divisions.length > 1 ? `${divisionName(t, r.m.divisionId)} · ` : ''}
          {stageLabel(t, r.m)}
        </span>
        <StatusBadge r={r} />
      </div>
      <TeamLine t={t} r={r} side="a" />
      <TeamLine t={t} r={r} side="b" />
      {extra}
    </div>
  );
}

/** Compact one-line row used in long match lists. */
export function MatchRow({
  t,
  r,
  onOpen,
  right,
}: {
  t: Tournament;
  r: ResolvedMatch;
  onOpen: (r: ResolvedMatch) => void;
  right?: ReactNode;
}) {
  return (
    <div className="list-row" onClick={() => onOpen(r)} role="button" tabIndex={0} onKeyDown={(e) => e.key === 'Enter' && onOpen(r)}>
      <div>
        <div className="match-no">M{r.m.number}</div>
        <div className="tiny muted truncate">{r.m.stage === 'pool' || r.m.stage === 'rr' ? `Round ${r.m.round}` : ''}</div>
      </div>
      <div className="vs">
        <TeamLine t={t} r={r} side="a" />
        <TeamLine t={t} r={r} side="b" />
      </div>
      <div className="stack" style={{ alignItems: 'flex-end', gap: 4 }}>
        <StatusBadge r={r} />
        {right}
      </div>
    </div>
  );
}
