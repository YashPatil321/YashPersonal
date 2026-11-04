import { describe, expect, it } from 'vitest';
import { finishMatch, setMatchTeams } from '../actions';
import { parseCSV, toCSV } from '../csv';
import { bracketSeedOrder, roundRobinRounds, snakePools } from '../generate';
import { seededRandom } from '../ids';
import { resolveTournament } from '../resolve';
import { buildTournament, courtNames, defaultDivisionSettings } from '../tournament';
import type { DivisionSettings, FormatType, Player, Team, Tournament } from '../types';

function makeTeams(n: number, divisionId = 'div') {
  const players: Record<string, Player> = {};
  const teams: Record<string, Team> = {};
  const ids: string[] = [];
  for (let i = 0; i < n; i++) {
    const p1 = { id: `p${i}a`, name: `Player ${i}A`, rating: 4 - i * 0.05 };
    const p2 = { id: `p${i}b`, name: `Player ${i}B`, rating: 4 - i * 0.05 };
    players[p1.id] = p1;
    players[p2.id] = p2;
    const id = `t${i}`;
    teams[id] = { id, name: `Team ${i + 1}`, playerIds: [p1.id, p2.id], divisionId, rating: p1.rating };
    ids.push(id);
  }
  return { players, teams, ids };
}

function makeTournament(n: number, overrides: Partial<DivisionSettings>): Tournament {
  const { players, teams, ids } = makeTeams(n);
  const settings = { ...defaultDivisionSettings(n), ...overrides };
  return buildTournament(
    { name: 'Test', courts: courtNames(4), minutesPerMatch: 20, doubles: true },
    players,
    teams,
    [{ name: 'Open', teamIds: ids, settings }],
  );
}

/** Play every ready match with random scores until nothing is left. */
function playOut(t: Tournament, random: () => number, favorSeeds = false): Tournament {
  for (let guard = 0; guard < 2000; guard++) {
    const resolved = resolveTournament(t);
    const ready = resolved.ordered.find((r) => r.ready);
    if (!ready) return t;
    const teamIdx = (id: string) => Number(id.slice(1));
    let aWins = random() < 0.5;
    if (favorSeeds) aWins = teamIdx(ready.a as string) < teamIdx(ready.b as string);
    const loserPts = Math.floor(random() * 10);
    t = finishMatch(t, ready.m.id, [aWins ? { a: 11, b: loserPts } : { a: loserPts, b: 11 }]);
  }
  throw new Error('did not terminate');
}

describe('csv', () => {
  it('parses quoted fields, escaped quotes and embedded newlines', () => {
    const rows = parseCSV('Name,Note\r\n"Smith, Jo","said ""hi""\nthere"\nBob,\n\n');
    expect(rows).toEqual([
      ['Name', 'Note'],
      ['Smith, Jo', 'said "hi"\nthere'],
      ['Bob', ''],
    ]);
  });
  it('round-trips', () => {
    const data = [['a', 'b,c'], ['"q"', 'x\ny']];
    expect(parseCSV(toCSV(data))).toEqual(data);
  });
});

describe('round robin', () => {
  for (let n = 2; n <= 13; n++) {
    it(`${n} teams: every pair once, nobody twice per round`, () => {
      const rounds = roundRobinRounds(n);
      const seen = new Set<string>();
      for (const round of rounds) {
        const inRound = new Set<number>();
        for (const [a, b] of round) {
          expect(inRound.has(a) || inRound.has(b)).toBe(false);
          inRound.add(a);
          inRound.add(b);
          const key = [a, b].sort().join('-');
          expect(seen.has(key)).toBe(false);
          seen.add(key);
        }
      }
      expect(seen.size).toBe((n * (n - 1)) / 2);
    });
  }
});

describe('seeding helpers', () => {
  it('bracket seed order', () => {
    expect(bracketSeedOrder(8)).toEqual([1, 8, 4, 5, 2, 7, 3, 6]);
    expect(bracketSeedOrder(4)).toEqual([1, 4, 2, 3]);
  });
  it('snake pools', () => {
    expect(snakePools(['1', '2', '3', '4', '5', '6'], 2)).toEqual([
      ['1', '4', '5'],
      ['2', '3', '6'],
    ]);
  });
});

const formats: Array<{ format: FormatType; extra?: Partial<DivisionSettings> }> = [
  { format: 'round_robin' },
  { format: 'single_elim' },
  { format: 'single_elim', extra: { thirdPlaceMatch: true } },
  { format: 'double_elim' },
  { format: 'double_elim', extra: { grandFinalReset: true } },
  { format: 'pools_playoff', extra: { poolCount: 2, advancePerPool: 2 } },
  { format: 'pools_playoff', extra: { poolCount: 3, advancePerPool: 2, playoffFormat: 'double_elim' } },
  { format: 'pools_playoff', extra: { poolCount: 4, advancePerPool: 1 } },
];

describe('full tournament simulation', () => {
  for (const { format, extra } of formats) {
    for (const n of [2, 3, 4, 5, 6, 7, 8, 9, 12, 13, 16, 17, 24]) {
      if (format === 'pools_playoff' && n < 6) continue;
      const name = `${format}${extra ? ' ' + JSON.stringify(extra) : ''} with ${n} teams`;
      it(name, () => {
        for (let seed = 1; seed <= 4; seed++) {
          const random = seededRandom(seed * 100 + n);
          let t = makeTournament(n, { format, ...extra });
          t = playOut(t, random);
          const resolved = resolveTournament(t);
          const div = resolved.divisions[t.divisions[0].id];

          expect(div.complete).toBe(true);
          expect(div.progress.done).toBe(div.progress.total);

          // No team plays itself; no stale results
          for (const r of resolved.ordered) {
            expect(r.stale).toBe(false);
            if (r.done && !r.notNeeded) expect(r.a).not.toBe(r.b);
          }

          // Placements cover every team exactly once with a single champion
          const placed = div.placements.flatMap((p) => p.teamIds);
          expect(new Set(placed).size).toBe(placed.length);
          expect(placed.length).toBe(n);
          expect(div.placements[0].place).toBe(1);
          expect(div.placements[0].teamIds.length).toBe(1);

          // Elimination: losses per team
          const losses = new Map<string, number>();
          for (const r of resolved.ordered) {
            if (!r.done || r.notNeeded || r.m.stage === 'pool' || r.m.stage === 'rr') continue;
            if (typeof r.loser === 'string' && r.loser !== 'BYE')
              losses.set(r.loser, (losses.get(r.loser) ?? 0) + 1);
          }
          const isDouble =
            format === 'double_elim' || (format === 'pools_playoff' && extra?.playoffFormat === 'double_elim');
          const champion = div.placements[0].teamIds[0];
          for (const [team, l] of losses) {
            if (format === 'round_robin') continue;
            const max = isDouble ? 2 : 1;
            // third-place match gives SF losers a second loss
            const allowance = extra?.thirdPlaceMatch ? 1 : 0;
            expect(l).toBeLessThanOrEqual(max + allowance);
            if (team === champion) expect(l).toBeLessThanOrEqual(isDouble ? 1 : 0);
          }
        }
      });
    }
  }

  it('favourite seeds win a single-elim bracket', () => {
    let t = makeTournament(8, { format: 'single_elim' });
    t = playOut(t, seededRandom(1), true);
    const div = resolveTournament(t).divisions[t.divisions[0].id];
    expect(div.placements[0].teamIds).toEqual(['t0']);
    expect(div.placements[1].teamIds).toEqual(['t1']);
  });

  it('top seeds get byes', () => {
    const t = makeTournament(5, { format: 'single_elim' });
    const resolved = resolveTournament(t);
    const r1 = resolved.divisions[t.divisions[0].id].matches.filter((r) => r.m.stage === 'winners' && r.m.round === 1);
    const byeTeams = r1.filter((r) => r.isBye).map((r) => r.winner);
    expect(byeTeams.sort()).toEqual(['t0', 't1', 't2']);
  });

  it('grand final reset is only played when the losers-bracket champion wins', () => {
    for (let seed = 1; seed < 20; seed++) {
      let t = makeTournament(4, { format: 'double_elim', grandFinalReset: true });
      t = playOut(t, seededRandom(seed));
      const r = resolveTournament(t);
      const gf = r.ordered.find((x) => x.m.stage === 'final')!;
      const reset = Object.values(r.matches).find((x) => x.m.stage === 'reset')!;
      if (gf.winnerSide === 'a') expect(reset.notNeeded).toBe(true);
      else expect(reset.notNeeded).toBe(false);
    }
  });

  it('flags results that no longer match the bracket', () => {
    let t = makeTournament(4, { format: 'single_elim' });
    let r = resolveTournament(t);
    const [sf1, sf2] = r.ordered.filter((x) => x.m.round === 1);
    t = finishMatch(t, sf1.m.id, [{ a: 11, b: 3 }]);
    t = finishMatch(t, sf2.m.id, [{ a: 11, b: 5 }]);
    r = resolveTournament(t);
    const final = r.ordered.find((x) => x.m.round === 2)!;
    t = finishMatch(t, final.m.id, [{ a: 11, b: 9 }]);
    // Correct semifinal 1 — the final now has a different team
    t = { ...t, matches: { ...t.matches, [sf1.m.id]: { ...t.matches[sf1.m.id], resultTeams: undefined, status: 'pending' } } };
    t = finishMatch(t, sf1.m.id, [{ a: 3, b: 11 }]);
    r = resolveTournament(t);
    expect(r.matches[final.m.id].stale).toBe(true);
  });
});

describe('pools → playoffs', () => {
  it('avoids same-pool first-round rematches when possible', () => {
    for (let seed = 1; seed <= 25; seed++) {
      let t = makeTournament(8, { format: 'pools_playoff', poolCount: 2, advancePerPool: 2 });
      const random = seededRandom(seed);
      // play only pool matches
      for (;;) {
        const r = resolveTournament(t);
        const ready = r.ordered.find((x) => x.ready && x.m.stage === 'pool');
        if (!ready) break;
        const aw = random() < 0.5;
        t = finishMatch(t, ready.m.id, [aw ? { a: 11, b: 4 } : { a: 6, b: 11 }]);
      }
      const r = resolveTournament(t);
      const div = r.divisions[t.divisions[0].id];
      expect(div.poolsComplete).toBe(true);
      const poolOf = new Map<string, string>();
      div.division.pools.forEach((p) => p.teamIds.forEach((id) => poolOf.set(id, p.id)));
      const semis = div.matches.filter((x) => x.m.stage === 'winners' && x.m.round === 1);
      for (const sf of semis) {
        expect(poolOf.get(sf.a as string)).not.toBe(poolOf.get(sf.b as string));
      }
    }
  });
});

describe('organizer edits', () => {
  it('can change who plays in a match before it is finished', () => {
    let t = makeTournament(6, { format: 'round_robin' });
    const first = resolveTournament(t).ordered[0];
    const [a, b] = [first.a as string, first.b as string];
    const other = t.divisions[0].teamIds.find((id) => id !== a && id !== b)!;
    t = setMatchTeams(t, first.m.id, a, other);
    let r = resolveTournament(t).matches[first.m.id];
    expect([r.a, r.b]).toEqual([a, other]);
    expect(setMatchTeams(t, first.m.id, a, a)).toBe(t); // same team twice is ignored
    t = finishMatch(t, first.m.id, [{ a: 11, b: 4 }]);
    expect(setMatchTeams(t, first.m.id, a, b)).toBe(t); // finished matches are locked
    r = resolveTournament(t).matches[first.m.id];
    expect(r.winner).toBe(a);
  });

  it('can fill a bracket slot by hand', () => {
    let t = makeTournament(4, { format: 'single_elim' });
    const final = resolveTournament(t).ordered.find((x) => x.m.round === 2)!;
    expect(final.a).toBeNull();
    t = setMatchTeams(t, final.m.id, 't0', 't3');
    const r = resolveTournament(t).matches[final.m.id];
    expect([r.a, r.b, r.ready]).toEqual(['t0', 't3', true]);
  });
});
