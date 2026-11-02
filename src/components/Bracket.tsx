import type { ResolvedDivision, ResolvedMatch } from '../lib/resolve';
import type { Tournament } from '../lib/types';
import { slotName } from './match';

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
  return (
    <div
      className={`bracket-match ${r.isBye ? 'bye' : ''} ${r.m.status === 'live' && !r.done ? 'is-live' : ''}`}
      onClick={clickable ? () => onOpen(r) : undefined}
      role={clickable ? 'button' : undefined}
      tabIndex={clickable ? 0 : undefined}
      onKeyDown={clickable ? (e) => e.key === 'Enter' && onOpen(r) : undefined}
      title={r.notNeeded ? 'Not needed' : undefined}
    >
      {!r.isBye && (
        <span className="bm-label">
          M{r.m.number}
          {r.m.status === 'live' && !r.done ? ` · LIVE${r.m.court ? ` ${r.m.court}` : ''}` : ''}
          {r.notNeeded ? ' · not needed' : ''}
          {r.m.stage === 'reset' && !r.done ? ' · if necessary' : ''}
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

function Columns({
  title,
  rounds,
  t,
  rd,
  onOpen,
}: {
  title?: string;
  rounds: Array<{ title: string; matches: ResolvedMatch[] }>;
  t: Tournament;
  rd: ResolvedDivision;
  onOpen: (r: ResolvedMatch) => void;
}) {
  if (!rounds.length) return null;
  return (
    <div style={{ marginBottom: 22 }}>
      {title && <h3>{title}</h3>}
      <div className="bracket-scroll">
        <div className="bracket">
          {rounds.map((round, i) => (
            <div className="bracket-round" key={i}>
              <div className="bracket-round-title">{round.title}</div>
              <div className="bracket-col">
                {round.matches.map((r) => (
                  <BracketMatch key={r.m.id} t={t} rd={rd} r={r} onOpen={onOpen} />
                ))}
              </div>
            </div>
          ))}
        </div>
      </div>
    </div>
  );
}

function groupRounds(matches: ResolvedMatch[]): Array<{ title: string; matches: ResolvedMatch[] }> {
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

export function Bracket({ t, rd, onOpen }: { t: Tournament; rd: ResolvedDivision; onOpen: (r: ResolvedMatch) => void }) {
  const winners = rd.matches.filter((r) => r.m.stage === 'winners');
  const losers = rd.matches.filter((r) => r.m.stage === 'losers');
  const finals = rd.matches.filter((r) => r.m.stage === 'final' || r.m.stage === 'reset' || r.m.stage === 'third');
  if (!winners.length) return null;
  const isDouble = losers.length > 0 || rd.matches.some((r) => r.m.stage === 'final');

  const winnerRounds = groupRounds(winners);
  const finalsRounds = finals.length
    ? [
        {
          title: 'Finals',
          matches: finals.sort((a, b) => a.m.depth - b.m.depth),
        },
      ]
    : [];

  if (!isDouble) {
    return (
      <Columns
        t={t}
        rd={rd}
        onOpen={onOpen}
        rounds={[...winnerRounds, ...finalsRounds.map((f) => ({ ...f, title: '3rd place' }))]}
      />
    );
  }
  return (
    <>
      <Columns title="Winners bracket" t={t} rd={rd} onOpen={onOpen} rounds={winnerRounds} />
      <Columns title="Losers bracket" t={t} rd={rd} onOpen={onOpen} rounds={groupRounds(losers)} />
      <Columns title="Finals" t={t} rd={rd} onOpen={onOpen} rounds={finalsRounds} />
    </>
  );
}
