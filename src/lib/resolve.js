import { bracketSeedOrder, nextPow2 } from './generate';
import { rulesForMatch, winnerFromGames } from './scoring';
import { BYE } from './types';
const isTeam = (v) => v !== null && v !== BYE;
/* ------------------------------------------------------------------ */
/* Standings                                                          */
/* ------------------------------------------------------------------ */
/** Compute standings from finished matches among `teamIds`, with pickleball-style tiebreakers. */
export function computeStandings(teamIds, finals) {
    const rows = new Map();
    teamIds.forEach((id) => rows.set(id, {
        teamId: id,
        played: 0,
        wins: 0,
        losses: 0,
        gamesWon: 0,
        gamesLost: 0,
        pointsFor: 0,
        pointsAgainst: 0,
        diff: 0,
        rank: 0,
    }));
    const h2h = new Map(); // "winner|loser" → count
    for (const r of finals) {
        if (!isTeam(r.a) || !isTeam(r.b) || !r.winnerSide)
            continue;
        const ra = rows.get(r.a);
        const rb = rows.get(r.b);
        if (!ra || !rb)
            continue;
        ra.played++;
        rb.played++;
        for (const g of r.m.games) {
            ra.pointsFor += g.a;
            ra.pointsAgainst += g.b;
            rb.pointsFor += g.b;
            rb.pointsAgainst += g.a;
            if (g.a > g.b) {
                ra.gamesWon++;
                rb.gamesLost++;
            }
            else if (g.b > g.a) {
                rb.gamesWon++;
                ra.gamesLost++;
            }
        }
        const [w, l] = r.winnerSide === 'a' ? [ra, rb] : [rb, ra];
        w.wins++;
        l.losses++;
        h2h.set(`${w.teamId}|${l.teamId}`, (h2h.get(`${w.teamId}|${l.teamId}`) ?? 0) + 1);
    }
    rows.forEach((row) => (row.diff = row.pointsFor - row.pointsAgainst));
    const seedIndex = new Map(teamIds.map((id, i) => [id, i]));
    const list = [...rows.values()];
    // Primary: wins, then fewer losses
    list.sort((x, y) => y.wins - x.wins || x.losses - y.losses);
    // Resolve tied groups with head-to-head among the tied teams, then point diff, points for, seed
    const out = [];
    let i = 0;
    while (i < list.length) {
        let j = i + 1;
        while (j < list.length && list[j].wins === list[i].wins && list[j].losses === list[i].losses)
            j++;
        const group = list.slice(i, j);
        if (group.length > 1) {
            const ids = group.map((g) => g.teamId);
            const miniWins = new Map();
            for (const id of ids) {
                let w = 0;
                for (const other of ids)
                    if (other !== id)
                        w += h2h.get(`${id}|${other}`) ?? 0;
                miniWins.set(id, w);
            }
            group.sort((x, y) => miniWins.get(y.teamId) - miniWins.get(x.teamId) ||
                y.diff - x.diff ||
                y.pointsFor - x.pointsFor ||
                x.pointsAgainst - y.pointsAgainst ||
                seedIndex.get(x.teamId) - seedIndex.get(y.teamId));
        }
        out.push(...group);
        i = j;
    }
    out.forEach((row, idx) => (row.rank = idx + 1));
    return out;
}
/* ------------------------------------------------------------------ */
/* Qualifiers                                                         */
/* ------------------------------------------------------------------ */
function perGame(n, d) {
    return d > 0 ? n / d : 0;
}
/**
 * Seed pool-play qualifiers: all pool winners first, then all runners-up, etc.
 * Within a tier, better win %, point diff per match, points per match.
 * Then nudge first-round pairings so teams from the same pool don't meet immediately.
 */
export function seedQualifiers(division, standings, advance) {
    const pools = division.pools;
    const seedIndex = new Map(division.teamIds.map((id, i) => [id, i]));
    const poolOf = new Map();
    pools.forEach((p) => p.teamIds.forEach((id) => poolOf.set(id, p.id)));
    const ordered = [];
    for (let tier = 0; tier < advance; tier++) {
        const tierRows = pools.map((p) => standings[p.id]?.[tier]).filter((r) => !!r);
        tierRows.sort((x, y) => perGame(y.wins, y.played) - perGame(x.wins, x.played) ||
            perGame(y.diff, y.played) - perGame(x.diff, x.played) ||
            perGame(y.pointsFor, y.played) - perGame(x.pointsFor, x.played) ||
            seedIndex.get(x.teamId) - seedIndex.get(y.teamId));
        ordered.push(...tierRows.map((r) => r.teamId));
    }
    if (pools.length < 2)
        return ordered;
    // Avoid same-pool first-round matchups by swapping within a tier.
    const size = nextPow2(ordered.length);
    const order = bracketSeedOrder(size);
    const partner = new Map(); // seed → opponent seed in round 1
    for (let i = 0; i < order.length; i += 2) {
        partner.set(order[i], order[i + 1]);
        partner.set(order[i + 1], order[i]);
    }
    const P = pools.length;
    const tierOf = (seed) => Math.floor((seed - 1) / P);
    const pool = (seed) => (seed <= ordered.length ? poolOf.get(ordered[seed - 1]) : undefined);
    const conflict = (seed) => {
        const opp = partner.get(seed);
        const p1 = pool(seed);
        return p1 !== undefined && p1 === pool(opp);
    };
    for (let s = 1; s <= ordered.length; s++) {
        if (!conflict(s))
            continue;
        const opp = partner.get(s);
        const mover = Math.max(s, opp); // move the lower-seeded team
        if (mover > ordered.length)
            continue;
        for (let c = 1; c <= ordered.length; c++) {
            if (c === mover || tierOf(c) !== tierOf(mover))
                continue;
            const tmp = ordered[mover - 1];
            ordered[mover - 1] = ordered[c - 1];
            ordered[c - 1] = tmp;
            if (!conflict(mover) && !conflict(c))
                break;
            // revert
            ordered[c - 1] = ordered[mover - 1];
            ordered[mover - 1] = tmp;
        }
    }
    return ordered;
}
/* ------------------------------------------------------------------ */
/* Resolution                                                         */
/* ------------------------------------------------------------------ */
export function resolveTournament(t) {
    const matches = {};
    const divisions = {};
    const byDivision = new Map();
    for (const m of Object.values(t.matches)) {
        const list = byDivision.get(m.divisionId) ?? [];
        list.push(m);
        byDivision.set(m.divisionId, list);
    }
    for (const division of t.divisions) {
        const divMatches = (byDivision.get(division.id) ?? []).slice().sort((x, y) => x.number - y.number);
        const local = new Map(divMatches.map((m) => [m.id, m]));
        const memo = new Map();
        let qualifiers = [];
        const slot = (s) => {
            switch (s.kind) {
                case 'team':
                    return s.teamId;
                case 'bye':
                    return BYE;
                case 'qualifier':
                    return qualifiers[s.rank - 1] ?? null;
                case 'winner':
                    return resolve(s.matchId)?.winner ?? null;
                case 'loser':
                    return resolve(s.matchId)?.loser ?? null;
            }
        };
        const finish = (m, a, b, extra = {}) => {
            const rules = rulesForMatch(m, division.settings);
            const base = {
                m,
                a,
                b,
                winner: null,
                loser: null,
                winnerSide: null,
                isBye: false,
                notNeeded: false,
                stale: false,
                ready: false,
                done: false,
                rules,
                ...extra,
            };
            if (base.notNeeded) {
                base.done = true;
                return base;
            }
            if (a === BYE || b === BYE) {
                base.isBye = true;
                base.done = true;
                base.loser = BYE;
                base.winner = a === BYE ? b : a; // may still be null (TBD) or BYE
                base.winnerSide = a === BYE ? 'b' : 'a';
                return base;
            }
            if (!isTeam(a) || !isTeam(b))
                return base;
            if (m.status === 'final') {
                if (m.resultTeams && (m.resultTeams[0] !== a || m.resultTeams[1] !== b)) {
                    base.stale = true;
                    base.ready = true;
                    return base;
                }
                const side = m.forfeit ? (m.forfeit === 'a' ? 'b' : 'a') : winnerFromGames(m.games);
                if (side) {
                    base.winnerSide = side;
                    base.winner = side === 'a' ? a : b;
                    base.loser = side === 'a' ? b : a;
                    base.done = true;
                    return base;
                }
            }
            base.ready = true;
            return base;
        };
        const resolve = (id) => {
            const cached = memo.get(id);
            if (cached)
                return cached;
            const m = local.get(id);
            if (!m)
                return undefined;
            let r;
            if (m.stage === 'reset' && (m.a.kind === 'winner' || m.a.kind === 'loser')) {
                const gf = resolve(m.a.matchId);
                if (!gf || !gf.winnerSide)
                    r = finish(m, null, null);
                else if (gf.winnerSide === 'a')
                    r = finish(m, gf.winner, gf.loser, { notNeeded: true });
                else
                    r = finish(m, gf.winner, gf.loser);
            }
            else {
                r = finish(m, slot(m.a), slot(m.b));
            }
            memo.set(id, r);
            return r;
        };
        // 1) Pool / round-robin matches have fixed teams.
        const groupMatches = divMatches.filter((m) => m.stage === 'pool' || m.stage === 'rr');
        groupMatches.forEach((m) => resolve(m.id));
        const poolStandings = {};
        for (const pool of division.pools) {
            const finals = groupMatches.filter((m) => m.poolId === pool.id).map((m) => memo.get(m.id));
            poolStandings[pool.id] = computeStandings(pool.teamIds, finals.filter((r) => r.done));
        }
        const rrStandings = division.settings.format === 'round_robin'
            ? computeStandings(division.teamIds, groupMatches.map((m) => memo.get(m.id)).filter((r) => r.done))
            : null;
        const poolsComplete = division.settings.format === 'pools_playoff' &&
            groupMatches.length > 0 &&
            groupMatches.every((m) => memo.get(m.id).done);
        const minPool = division.pools.length ? Math.min(...division.pools.map((p) => p.teamIds.length)) : 0;
        const advance = Math.max(1, Math.min(division.settings.advancePerPool, minPool));
        if (poolsComplete)
            qualifiers = seedQualifiers(division, poolStandings, advance);
        // 2) Everything else resolves recursively.
        divMatches.forEach((m) => resolve(m.id));
        const resolvedList = divMatches.map((m) => memo.get(m.id));
        resolvedList.forEach((r) => (matches[r.m.id] = r));
        const playable = resolvedList.filter((r) => !r.isBye && !r.notNeeded);
        const done = playable.filter((r) => r.done).length;
        const complete = resolvedList.length > 0 && resolvedList.every((r) => r.done);
        const resolvedDivision = {
            division,
            matches: resolvedList,
            poolStandings,
            rrStandings,
            poolsComplete,
            qualifiers,
            qualified: new Set(qualifiers),
            placements: [],
            complete,
            progress: { done, total: playable.length },
        };
        resolvedDivision.placements = computePlacements(resolvedDivision, advance);
        divisions[division.id] = resolvedDivision;
    }
    const ordered = Object.values(matches)
        .filter((r) => !r.isBye)
        .sort((x, y) => x.m.number - y.m.number);
    return { matches, divisions, ordered };
}
/* ------------------------------------------------------------------ */
/* Placements                                                         */
/* ------------------------------------------------------------------ */
function computePlacements(rd, advance) {
    const { division } = rd;
    if (division.settings.format === 'round_robin') {
        if (!rd.complete || !rd.rrStandings)
            return [];
        return rd.rrStandings.map((r) => ({ place: r.rank, teamIds: [r.teamId] }));
    }
    const bracket = rd.matches.filter((r) => r.m.stage !== 'pool' && r.m.stage !== 'rr');
    if (!bracket.length)
        return [];
    const isDouble = division.settings.format === 'double_elim' ||
        (division.settings.format === 'pools_playoff' && division.settings.playoffFormat === 'double_elim');
    // Elimination key: later = better. Champion gets Infinity.
    const elimKey = new Map();
    const keyOf = (r) => {
        switch (r.m.stage) {
            case 'winners':
                return r.m.round; // only used for single elimination
            case 'losers':
                return r.m.round;
            case 'third':
                return 1000;
            case 'final':
                return 2000;
            case 'reset':
                return 3000;
            default:
                return 0;
        }
    };
    const finalMatch = bracket.find((r) => r.m.stage === 'final') ??
        bracket.filter((r) => r.m.stage === 'winners').sort((x, y) => y.m.round - x.m.round)[0];
    const reset = bracket.find((r) => r.m.stage === 'reset');
    const decider = reset && !reset.notNeeded ? reset : finalMatch;
    if (!decider?.done || !isTeam(decider.winner))
        return [];
    for (const r of bracket) {
        if (!r.done || !isTeam(r.loser))
            continue;
        if (!isDouble && r.m.stage === 'third')
            continue;
        if (isDouble && r.m.stage === 'winners')
            continue;
        elimKey.set(r.loser, Math.max(elimKey.get(r.loser) ?? -Infinity, keyOf(r)));
    }
    elimKey.set(decider.winner, Infinity);
    if (isTeam(decider.loser))
        elimKey.set(decider.loser, 5000);
    const groups = new Map();
    elimKey.forEach((k, team) => groups.set(k, [...(groups.get(k) ?? []), team]));
    const keys = [...groups.keys()].sort((x, y) => y - x);
    const placements = [];
    let place = 1;
    for (const k of keys) {
        const teams = groups.get(k);
        placements.push({ place, teamIds: teams });
        place += teams.length;
    }
    // Single elimination third-place match splits 3rd/4th.
    const third = bracket.find((r) => r.m.stage === 'third');
    if (!isDouble && third?.done && isTeam(third.winner) && isTeam(third.loser)) {
        const idx = placements.findIndex((p) => p.teamIds.includes(third.winner));
        if (idx >= 0 && placements[idx].teamIds.length === 2) {
            const base = placements[idx].place;
            placements.splice(idx, 1, { place: base, teamIds: [third.winner] }, { place: base + 1, teamIds: [third.loser] });
        }
    }
    // Pool-play teams that didn't qualify.
    if (division.settings.format === 'pools_playoff' && rd.poolsComplete) {
        const placed = new Set(placements.flatMap((p) => p.teamIds));
        const maxPoolSize = Math.max(...division.pools.map((p) => p.teamIds.length));
        for (let tier = advance; tier < maxPoolSize; tier++) {
            const teams = division.pools
                .map((p) => rd.poolStandings[p.id]?.[tier]?.teamId)
                .filter((id) => !!id && !placed.has(id));
            if (teams.length) {
                placements.push({ place, teamIds: teams });
                place += teams.length;
            }
        }
    }
    return placements;
}
/* ------------------------------------------------------------------ */
/* Queries                                                            */
/* ------------------------------------------------------------------ */
export function teamMatches(resolved, teamId) {
    return resolved.ordered.filter((r) => r.a === teamId || r.b === teamId);
}
export function teamRecord(resolved, teamId) {
    let wins = 0;
    let losses = 0;
    for (const r of teamMatches(resolved, teamId)) {
        if (!r.done || !r.winnerSide)
            continue;
        if (r.winner === teamId)
            wins++;
        else if (r.loser === teamId)
            losses++;
    }
    return { wins, losses };
}
