import { uid } from './ids';
import type { Division, Match, MatchStage, Pool, SlotSource, Tournament } from './types';

/* ------------------------------------------------------------------ */
/* Helpers                                                            */
/* ------------------------------------------------------------------ */

export function nextPow2(n: number): number {
  let p = 1;
  while (p < n) p *= 2;
  return Math.max(p, 2);
}

/** Standard bracket seed order, e.g. 8 → [1,8,4,5,2,7,3,6]. */
export function bracketSeedOrder(size: number): number[] {
  let order = [1, 2];
  while (order.length < size) {
    const n = order.length * 2;
    order = order.flatMap((s) => [s, n + 1 - s]);
  }
  return order;
}

/**
 * Circle-method round robin. Returns rounds of index pairs.
 * Odd counts get a phantom team (-1) meaning "bye this round".
 */
export function roundRobinRounds(n: number): Array<Array<[number, number]>> {
  if (n < 2) return [];
  const list = Array.from({ length: n }, (_, i) => i);
  if (n % 2 === 1) list.push(-1);
  const m = list.length;
  const rounds: Array<Array<[number, number]>> = [];
  for (let r = 0; r < m - 1; r++) {
    const pairs: Array<[number, number]> = [];
    for (let i = 0; i < m / 2; i++) {
      const x = list[i];
      const y = list[m - 1 - i];
      if (x === -1 || y === -1) continue;
      // Alternate sides so nobody is always "Team A"
      pairs.push(r % 2 === 0 ? [x, y] : [y, x]);
    }
    rounds.push(pairs);
    // rotate everything except the first element
    list.splice(1, 0, list.pop()!);
  }
  return rounds;
}

/** Snake-seed teams into pools: 1→A, 2→B, 3→B, 4→A ... */
export function snakePools(teamIds: string[], poolCount: number): string[][] {
  const pools: string[][] = Array.from({ length: poolCount }, () => []);
  teamIds.forEach((id, i) => {
    const row = Math.floor(i / poolCount);
    const col = i % poolCount;
    const idx = row % 2 === 0 ? col : poolCount - 1 - col;
    pools[idx].push(id);
  });
  return pools;
}

export const poolName = (i: number) => `Pool ${String.fromCharCode(65 + i)}`;

/* ------------------------------------------------------------------ */
/* Match builders                                                     */
/* ------------------------------------------------------------------ */

type Draft = Omit<Match, 'number' | 'depth' | 'status' | 'games' | 'updatedAt'>;

function draft(
  divisionId: string,
  stage: MatchStage,
  round: number,
  slot: number,
  a: SlotSource,
  b: SlotSource,
  extra: Partial<Draft> = {},
): Draft {
  return { id: uid('m'), divisionId, stage, round, slot, a, b, ...extra };
}

function roundRobinMatches(
  divisionId: string,
  teamIds: string[],
  stage: 'rr' | 'pool',
  cycles: number,
  poolId?: string,
): Draft[] {
  const out: Draft[] = [];
  const base = roundRobinRounds(teamIds.length);
  for (let c = 0; c < Math.max(1, cycles); c++) {
    base.forEach((pairs, r) => {
      pairs.forEach(([x, y], slot) => {
        const [i, j] = c % 2 === 0 ? [x, y] : [y, x];
        out.push(
          draft(
            divisionId,
            stage,
            c * base.length + r + 1,
            slot,
            { kind: 'team', teamId: teamIds[i] },
            { kind: 'team', teamId: teamIds[j] },
            { poolId },
          ),
        );
      });
    });
  }
  return out;
}

function roundLabel(roundsFromEnd: number, round: number): string {
  if (roundsFromEnd === 0) return 'Final';
  if (roundsFromEnd === 1) return 'Semifinal';
  if (roundsFromEnd === 2) return 'Quarterfinal';
  return `Round ${round}`;
}

/**
 * Build an elimination bracket from an ordered list of entrants
 * (index 0 = seed 1). Entrants are slot sources so the same builder
 * works for direct seeding and for pool-play qualifiers.
 */
export function eliminationMatches(
  divisionId: string,
  entrants: SlotSource[],
  type: 'single_elim' | 'double_elim',
  opts: { thirdPlace?: boolean; grandFinalReset?: boolean } = {},
): Draft[] {
  const size = nextPow2(entrants.length);
  const k = Math.log2(size);
  const order = bracketSeedOrder(size);
  const seedSource = (seed: number): SlotSource =>
    seed <= entrants.length ? entrants[seed - 1] : { kind: 'bye' };

  const out: Draft[] = [];
  const W: Draft[][] = [];

  // Winners bracket (= the whole bracket for single elimination)
  for (let r = 1; r <= k; r++) {
    const count = size / 2 ** r;
    const round: Draft[] = [];
    for (let i = 0; i < count; i++) {
      let a: SlotSource;
      let b: SlotSource;
      if (r === 1) {
        a = seedSource(order[2 * i]);
        b = seedSource(order[2 * i + 1]);
      } else {
        a = { kind: 'winner', matchId: W[r - 2][2 * i].id };
        b = { kind: 'winner', matchId: W[r - 2][2 * i + 1].id };
      }
      const fromEnd = k - r;
      let label: string;
      if (type === 'single_elim') label = roundLabel(fromEnd, r);
      else label = fromEnd === 0 ? 'Winners Final' : fromEnd === 1 ? 'Winners Semifinal' : `Winners R${r}`;
      round.push(
        draft(divisionId, 'winners', r, i, a, b, {
          label,
          finals: type === 'single_elim' ? fromEnd <= 1 : false,
        }),
      );
    }
    W.push(round);
    out.push(...round);
  }

  if (type === 'single_elim') {
    if (opts.thirdPlace && k >= 2) {
      const semis = W[k - 2];
      out.push(
        draft(
          divisionId,
          'third',
          1,
          0,
          { kind: 'loser', matchId: semis[0].id },
          { kind: 'loser', matchId: semis[1].id },
          { label: '3rd Place', finals: true },
        ),
      );
    }
    return out;
  }

  // Losers bracket
  const L: Draft[][] = [];
  const lbRounds = 2 * (k - 1);
  for (let lr = 1; lr <= lbRounds; lr++) {
    const round: Draft[] = [];
    if (lr === 1) {
      const count = size / 4;
      for (let i = 0; i < count; i++) {
        round.push(
          draft(
            divisionId,
            'losers',
            lr,
            i,
            { kind: 'loser', matchId: W[0][2 * i].id },
            { kind: 'loser', matchId: W[0][2 * i + 1].id },
          ),
        );
      }
    } else if (lr % 2 === 0) {
      // Drop-in round: LB survivors vs losers from winners round j+1
      const j = lr / 2;
      const prev = L[lr - 2];
      const drops = W[j];
      const count = prev.length;
      for (let i = 0; i < count; i++) {
        const dropIdx = j % 2 === 1 ? count - 1 - i : i; // alternate to avoid quick rematches
        round.push(
          draft(
            divisionId,
            'losers',
            lr,
            i,
            { kind: 'winner', matchId: prev[i].id },
            { kind: 'loser', matchId: drops[dropIdx].id },
          ),
        );
      }
    } else {
      const prev = L[lr - 2];
      for (let i = 0; i < prev.length / 2; i++) {
        round.push(
          draft(
            divisionId,
            'losers',
            lr,
            i,
            { kind: 'winner', matchId: prev[2 * i].id },
            { kind: 'winner', matchId: prev[2 * i + 1].id },
          ),
        );
      }
    }
    const fromEnd = lbRounds - lr;
    round.forEach((m) => {
      m.label = fromEnd === 0 ? 'Losers Final' : fromEnd === 1 ? 'Losers Semifinal' : `Losers R${lr}`;
      m.finals = fromEnd === 0;
    });
    L.push(round);
    out.push(...round);
  }

  const wbChamp: SlotSource = { kind: 'winner', matchId: W[k - 1][0].id };
  const lbChamp: SlotSource =
    lbRounds > 0 ? { kind: 'winner', matchId: L[lbRounds - 1][0].id } : { kind: 'loser', matchId: W[0][0].id };
  const gf = draft(divisionId, 'final', 1, 0, wbChamp, lbChamp, { label: 'Grand Final', finals: true });
  out.push(gf);
  if (opts.grandFinalReset) {
    // Teams are copied from the grand final; only played if the LB champion wins it.
    out.push(
      draft(
        divisionId,
        'reset',
        1,
        0,
        { kind: 'winner', matchId: gf.id },
        { kind: 'loser', matchId: gf.id },
        { label: 'Grand Final (Reset)', finals: true },
      ),
    );
  }
  return out;
}

/* ------------------------------------------------------------------ */
/* Division generation                                                */
/* ------------------------------------------------------------------ */

export interface GeneratedDivision {
  pools: Pool[];
  matches: Draft[];
}

export function generateDivision(division: Division): GeneratedDivision {
  const { settings, teamIds, id } = division;
  const n = teamIds.length;
  if (n < 2) return { pools: [], matches: [] };

  switch (settings.format) {
    case 'round_robin':
      return { pools: [], matches: roundRobinMatches(id, teamIds, 'rr', settings.roundRobinCycles) };

    case 'single_elim':
    case 'double_elim':
      return {
        pools: [],
        matches: eliminationMatches(
          id,
          teamIds.map((teamId) => ({ kind: 'team', teamId })),
          settings.format,
          { thirdPlace: settings.thirdPlaceMatch, grandFinalReset: settings.grandFinalReset },
        ),
      };

    case 'pools_playoff': {
      const poolCount = clampPoolCount(n, settings.poolCount);
      const grouped = snakePools(teamIds, poolCount);
      const pools: Pool[] = grouped.map((ids, i) => ({ id: uid('p'), name: poolName(i), teamIds: ids }));
      const matches: Draft[] = [];
      for (const pool of pools) {
        matches.push(...roundRobinMatches(id, pool.teamIds, 'pool', settings.roundRobinCycles, pool.id));
      }
      const minPool = Math.min(...pools.map((p) => p.teamIds.length));
      const advance = Math.max(1, Math.min(settings.advancePerPool, minPool));
      const qualifiers = advance * pools.length;
      if (qualifiers >= 2) {
        const entrants: SlotSource[] = Array.from({ length: qualifiers }, (_, i) => ({
          kind: 'qualifier',
          rank: i + 1,
        }));
        matches.push(
          ...eliminationMatches(id, entrants, settings.playoffFormat, {
            thirdPlace: settings.thirdPlaceMatch,
            grandFinalReset: settings.grandFinalReset,
          }),
        );
      }
      return { pools, matches };
    }
  }
}

export function clampPoolCount(teamCount: number, requested: number): number {
  const maxPools = Math.max(1, Math.floor(teamCount / 3));
  return Math.max(1, Math.min(requested || 1, maxPools));
}

/** Number of qualifiers a pools+playoff division will produce. */
export function qualifierCount(division: Division): number {
  const n = division.teamIds.length;
  const pools = clampPoolCount(n, division.settings.poolCount);
  const minPool = Math.floor(n / pools);
  return Math.max(1, Math.min(division.settings.advancePerPool, minPool)) * pools;
}

/* ------------------------------------------------------------------ */
/* Depth / numbering                                                  */
/* ------------------------------------------------------------------ */

/** Compute play-order depth for every match (pool rounds first, then bracket rounds). */
export function computeDepths(drafts: Draft[]): Map<string, number> {
  const byId = new Map(drafts.map((d) => [d.id, d]));
  const depth = new Map<string, number>();
  const maxPoolRound = Math.max(0, ...drafts.filter((d) => d.stage === 'pool').map((d) => d.round));

  const srcDepth = (s: SlotSource): number => {
    if (s.kind === 'winner' || s.kind === 'loser') return visit(s.matchId);
    if (s.kind === 'qualifier') return maxPoolRound;
    return 0;
  };
  const visit = (id: string): number => {
    const cached = depth.get(id);
    if (cached !== undefined) return cached;
    const d = byId.get(id)!;
    let value: number;
    if (d.stage === 'rr' || d.stage === 'pool') value = d.round;
    else value = Math.max(srcDepth(d.a), srcDepth(d.b)) + 1;
    depth.set(id, value);
    return value;
  };
  drafts.forEach((d) => visit(d.id));
  return depth;
}

/** Mark matches that are structurally byes (one side can only ever be a BYE). */
export function computeStructuralByes(drafts: Draft[]): Set<string> {
  const byId = new Map(drafts.map((d) => [d.id, d]));
  // memo: 'BYE' if slot is always a bye, 'X' otherwise
  const winnerIsBye = new Map<string, boolean>();
  const isByeMatch = new Map<string, boolean>();

  const slotBye = (s: SlotSource): boolean => {
    if (s.kind === 'bye') return true;
    if (s.kind === 'winner') return winnerBye(s.matchId);
    if (s.kind === 'loser') return matchIsBye(s.matchId); // loser of a bye match is a BYE
    return false;
  };
  const matchIsBye = (id: string): boolean => {
    if (isByeMatch.has(id)) return isByeMatch.get(id)!;
    const d = byId.get(id)!;
    const v = d.stage === 'reset' ? false : slotBye(d.a) || slotBye(d.b);
    isByeMatch.set(id, v);
    return v;
  };
  const winnerBye = (id: string): boolean => {
    if (winnerIsBye.has(id)) return winnerIsBye.get(id)!;
    const d = byId.get(id)!;
    const v = slotBye(d.a) && slotBye(d.b);
    winnerIsBye.set(id, v);
    return v;
  };
  const out = new Set<string>();
  drafts.forEach((d) => {
    if (matchIsBye(d.id)) out.add(d.id);
  });
  return out;
}

const STAGE_ORDER: Record<MatchStage, number> = {
  rr: 0,
  pool: 0,
  winners: 1,
  losers: 2,
  third: 3,
  final: 4,
  reset: 5,
};

/**
 * Turn per-division drafts into numbered matches. Numbers interleave
 * divisions by play depth so a shared court queue alternates fairly.
 */
export function finalizeMatches(
  divisions: Array<{ index: number; drafts: Draft[] }>,
  now = Date.now(),
): Record<string, Match> {
  const all: Array<{ d: Draft; depth: number; div: number; bye: boolean }> = [];
  for (const { index, drafts } of divisions) {
    const depths = computeDepths(drafts);
    const byes = computeStructuralByes(drafts);
    drafts.forEach((d) => all.push({ d, depth: depths.get(d.id)!, div: index, bye: byes.has(d.id) }));
  }
  all.sort(
    (x, y) =>
      x.depth - y.depth ||
      x.div - y.div ||
      STAGE_ORDER[x.d.stage] - STAGE_ORDER[y.d.stage] ||
      (x.d.poolId ?? '').localeCompare(y.d.poolId ?? '') ||
      x.d.round - y.d.round ||
      x.d.slot - y.d.slot,
  );
  const matches: Record<string, Match> = {};
  let n = 0;
  for (const { d, depth, bye } of all) {
    matches[d.id] = {
      ...d,
      depth,
      bye: bye || undefined,
      number: bye ? 0 : ++n,
      status: 'pending',
      games: [],
      updatedAt: now,
    };
  }
  return matches;
}

/** (Re)generate the schedule for every division of a tournament. */
export function generateAllMatches(t: Tournament): Tournament {
  const divisions: Division[] = [];
  const perDivision: Array<{ index: number; drafts: Draft[] }> = [];
  t.divisions.forEach((div, index) => {
    const gen = generateDivision(div);
    divisions.push({ ...div, pools: gen.pools });
    perDivision.push({ index, drafts: gen.matches });
  });
  return { ...t, divisions, matches: finalizeMatches(perDivision), updatedAt: Date.now() };
}

/** Regenerate one division, keeping other divisions' matches and renumbering everything. */
export function regenerateDivision(t: Tournament, divisionId: string): Tournament {
  const perDivision: Array<{ index: number; drafts: Draft[] }> = [];
  const newDivisions: Division[] = [];
  t.divisions.forEach((div, index) => {
    if (div.id === divisionId) {
      const gen = generateDivision(div);
      newDivisions.push({ ...div, pools: gen.pools });
      perDivision.push({ index, drafts: gen.matches });
    } else {
      newDivisions.push(div);
    }
  });
  const regenerated = finalizeMatches(perDivision);
  // Keep existing matches for other divisions; renumber all non-bye matches by depth/division.
  const kept = Object.values(t.matches).filter((m) => m.divisionId !== divisionId);
  const merged = [...kept, ...Object.values(regenerated)];
  const divIndex = new Map(newDivisions.map((d, i) => [d.id, i]));
  merged.sort(
    (x, y) =>
      x.depth - y.depth ||
      divIndex.get(x.divisionId)! - divIndex.get(y.divisionId)! ||
      STAGE_ORDER[x.stage] - STAGE_ORDER[y.stage] ||
      (x.poolId ?? '').localeCompare(y.poolId ?? '') ||
      x.round - y.round ||
      x.slot - y.slot,
  );
  const matches: Record<string, Match> = {};
  let n = 0;
  for (const m of merged) matches[m.id] = { ...m, number: m.bye ? 0 : ++n };
  return { ...t, divisions: newDivisions, matches, updatedAt: Date.now() };
}

/**
 * Can `teamId` (already in its division's teamIds) join the schedule without
 * rebuilding? Yes for round robin, and for pool play until the playoffs start.
 */
export function canAddLateTeam(t: Tournament, divisionId: string): boolean {
  const div = t.divisions.find((d) => d.id === divisionId);
  if (!div) return false;
  if (div.settings.format === 'round_robin') return true;
  if (div.settings.format !== 'pools_playoff' || !div.pools.length) return false;
  return !Object.values(t.matches).some(
    (m) => m.divisionId === divisionId && m.stage !== 'pool' && m.status !== 'pending',
  );
}

/**
 * Add a late team to the schedule, keeping every existing match and score.
 * Round robin: it plays everyone. Pool play: it joins the smallest pool and plays
 * everyone there. New matches are spread across the early rounds so the team
 * gets called in soon, and are numbered after the existing ones.
 */
export function addLateTeam(t: Tournament, teamId: string): Tournament {
  const div = t.divisions.find((d) => d.teamIds.includes(teamId));
  if (!div || !canAddLateTeam(t, div.id)) return t;
  const inSchedule = Object.values(t.matches).some(
    (m) => m.divisionId === div.id && [m.a, m.b].some((s) => s.kind === 'team' && s.teamId === teamId),
  );
  if (inSchedule) return t;

  let pools = div.pools;
  let opponents: string[];
  let poolId: string | undefined;
  if (div.settings.format === 'pools_playoff') {
    const pool = pools.reduce((best, p) => (p.teamIds.length < best.teamIds.length ? p : best), pools[0]);
    poolId = pool.id;
    opponents = pool.teamIds.filter((id) => id !== teamId);
    pools = pools.map((p) => (p.id === pool.id ? { ...p, teamIds: [...p.teamIds, teamId] } : p));
  } else {
    opponents = div.teamIds.filter((id) => id !== teamId);
  }

  const stage: MatchStage = poolId ? 'pool' : 'rr';
  const now = Date.now();
  let number = Math.max(0, ...Object.values(t.matches).map((m) => m.number));
  const matches = { ...t.matches };
  const cycles = Math.max(1, div.settings.roundRobinCycles);
  let k = 0;
  for (let c = 0; c < cycles; c++) {
    opponents.forEach((opp) => {
      k++;
      const d = draft(
        div.id,
        stage,
        k,
        100 + k, // after the slots already used in that round
        { kind: 'team', teamId: c % 2 === 0 ? teamId : opp },
        { kind: 'team', teamId: c % 2 === 0 ? opp : teamId },
        { poolId },
      );
      matches[d.id] = { ...d, depth: k, number: ++number, status: 'pending', games: [], updatedAt: now };
    });
  }
  return {
    ...t,
    divisions: t.divisions.map((d) => (d.id === div.id ? { ...d, pools } : d)),
    matches,
    updatedAt: now,
  };
}
