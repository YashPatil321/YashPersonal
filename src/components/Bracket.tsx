import { Trophy } from 'lucide-react';
import type { ReactNode } from 'react';
import type { ResolvedDivision, ResolvedMatch } from '../lib/resolve';
import { teamName } from '../lib/tournament';
import type { Tournament } from '../lib/types';
import { slotName } from './match';
import { TeamAvatars } from './ui';

function seedFor(rd: ResolvedDivision, teamId: string | null): number | undefined {
  if (!teamId || teamId === 'BYE') return undefined;
  if (rd.division.settings.format === 'pools_playoff') {
    const i = rd.qualifiers.indexOf(teamId);
    return i >= 0 ? i + 1 : undefined;
  }
  const i = rd.division.teamIds.indexOf(teamId);
  return i >= 0 ? i + 1 : undefined;
}

function BracketMatch({
  t,
  rd,
  r,
  onOpen,
}: {
  t: Tournament;
  rd: ResolvedDivision;
  r: ResolvedMatch;
  onOpen: (r: ResolvedMatch) => void;
}) {
  const sides = (['a', 'b'] as const).map((side) => {
    const value = side === 'a' ? r.a : r.b;
    const src = side === 'a' ? r.m.a : r.m.b;
    const { text, tbd } = slotName(t, value, src);
    const won = r.done && !r.isBye && r.winnerSide === side;
    const lost = r.done && !r.isBye && r.winnerSide && r.winnerSide !== side;
    const score = r.m.games.map((g) => (side === 'a' ? g.a : g.b)).join(' ');
    return { side, text, tbd, won, lost, score, seed: seedFor(rd, value) };
  });
  const clickable = !r.isBye;
  const live = r.m.status === 'live' && !r.done;
  return (
    <div
      className={`bracket-match ${r.isBye ? 'bye' : ''} ${live ? 'is-live' : ''}`}
      onClick={clickable ? () => onOpen(r) : undefined}
      role={clickable ? 'button' : undefined}
      tabIndex={clickable ? 0 : undefined}
      onKeyDown={clickable ? (e) => e.key === 'Enter' && onOpen(r) : undefined}
      title={r.notNeeded ? 'Not needed' : undefined}
    >
      {!r.isBye && (
        <span className="bm-label">
          M{r.m.number}
          {live ? ` · LIVE${r.m.court ? ` ${r.m.court}` : ''}` : ''}
          {r.notNeeded ? ' · not needed' : ''}
          {r.m.stage === 'reset' && !r.done ? ' · if needed' : ''}
        </span>
      )}
      {sides.map((s) => (
        <div key={s.side} className={`bm-team ${s.won ? 'win' : ''} ${s.lost ? 'lose' : ''} ${s.tbd ? 'tbd' : ''}`}>
          <span className="seed">{s.seed ?? ''}</span>
          <span className="nm" title={s.text}>
            {s.text}
          </span>
          <span className="sc">{s.score}</span>
        </div>
      ))}
    </div>
  );
}

interface Round {
  title: string;
  matches?: ResolvedMatch[];
  node?: ReactNode;
}

function chunk<T>(items: T[], size: number): T[][] {
  const out: T[][] = [];
  for (let i = 0; i < items.length; i += size) out.push(items.slice(i, i + size));
  return out;
}

function Columns({
  title,
  rounds,
  t,
  rd,
  onOpen,
}: {
  title?: string;
  rounds: Round[];
  t: Tournament;
  rd: ResolvedDivision;
  onOpen: (r: ResolvedMatch) => void;
}) {
  if (!rounds.length) return null;
  const size = (r?: Round) => (r ? (r.matches ? r.matches.length : 1) : 0);
  return (
    <div style={{ marginBottom: 26 }}>
      {title && <h2 style={{ fontSize: '1.2rem' }}>{title}</h2>}
      <div className="bracket-scroll">
        <div className="bracket">
          {rounds.map((round, i) => {
            const next = rounds[i + 1];
            const pair = !!next && size(next) * 2 === size(round);
            const straight = !!next && size(next) === size(round);
            const cls = `bracket-round ${pair || straight ? 'has-next' : ''} ${straight ? 'straight' : ''}`;
            const slot = (r: ResolvedMatch) => (
              <div className="bm-slot" key={r.m.id}>
                <BracketMatch t={t} rd={rd} r={r} onOpen={onOpen} />
              </div>
            );
            return (
              <div className={cls} key={i}>
                <div className="bracket-round-title">{round.title}</div>
                <div className="bracket-col">
                  {round.node ? (
                    <div className="bm-single">
                      <div className="bm-slot">{round.node}</div>
                    </div>
                  ) : pair ? (
                    chunk(round.matches!, 2).map((p, j) => (
                      <div className="bm-pair" key={j}>
                        {p.map(slot)}
                      </div>
                    ))
                  ) : (
                    round.matches!.map((r) => (
                      <div className="bm-single" key={r.m.id}>
                        {slot(r)}
                      </div>
                    ))
                  )}
                </div>
              </div>
            );
          })}
        </div>
      </div>
    </div>
  );
}

function groupRounds(matches: ResolvedMatch[]): Round[] {
  const byRound = new Map<number, ResolvedMatch[]>();
  for (const r of matches) byRound.set(r.m.round, [...(byRound.get(r.m.round) ?? []), r]);
  return [...byRound.entries()]
    .sort((a, b) => a[0] - b[0])
    .map(([, list]) => {
      const sorted = list.sort((a, b) => a.m.slot - b.m.slot);
      const label = sorted[0].m.label ?? '';
      return { title: label.replace(/^(Winners|Losers) /, ''), matches: sorted };
    });
}

function ChampionCard({ t, teamId }: { t: Tournament; teamId?: string }) {
  return (
    <div className="champion-card">
      <Trophy size={26} color="var(--ball)" />
      <div className="eyebrow" style={{ marginTop: 6 }}>
        Champion
      </div>
      {teamId ? (
        <>
          <div style={{ marginTop: 8 }}>
            <TeamAvatars t={t} teamId={teamId} size={32} />
          </div>
          <div className="who">{teamName(t, teamId)}</div>
        </>
      ) : (
        <div className="who" style={{ color: 'var(--on-night-muted)' }}>
          TBD
        </div>
      )}
    </div>
  );
}

export function Bracket({ t, rd, onOpen }: { t: Tournament; rd: ResolvedDivision; onOpen: (r: ResolvedMatch) => void }) {
  const winners = rd.matches.filter((r) => r.m.stage === 'winners');
  const losers = rd.matches.filter((r) => r.m.stage === 'losers');
  const grandFinal = rd.matches.find((r) => r.m.stage === 'final');
  const reset = rd.matches.find((r) => r.m.stage === 'reset');
  const third = rd.matches.find((r) => r.m.stage === 'third');
  if (!winners.length) return null;
  const champion = rd.placements.find((p) => p.place === 1)?.teamIds[0];
  const championRound: Round = { title: 'Champion', node: <ChampionCard t={t} teamId={champion} /> };

  if (!grandFinal) {
    // Single elimination
    return (
      <>
        <Columns t={t} rd={rd} onOpen={onOpen} rounds={[...groupRounds(winners), championRound]} />
        {third && <Columns title="3rd place" t={t} rd={rd} onOpen={onOpen} rounds={[{ title: '3rd place', matches: [third] }]} />}
      </>
    );
  }

  const finals: Round[] = [{ title: 'Grand final', matches: [grandFinal] }];
  if (reset) finals.push({ title: 'Reset', matches: [reset] });
  finals.push(championRound);
  return (
    <>
      <Columns title="Winners bracket" t={t} rd={rd} onOpen={onOpen} rounds={groupRounds(winners)} />
      {losers.length > 0 && <Columns title="Losers bracket" t={t} rd={rd} onOpen={onOpen} rounds={groupRounds(losers)} />}
      <Columns title="Finals" t={t} rd={rd} onOpen={onOpen} rounds={finals} />
    </>
  );
}
