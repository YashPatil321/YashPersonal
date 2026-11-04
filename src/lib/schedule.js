import { rulesForMatch } from './scoring';
/**
 * Expected minutes for a match under the given rules, where `base` is the
 * organizer's "minutes for one game to 11" (including changeover).
 */
export function matchMinutes(rules, base) {
    const expectedGames = rules.bestOf <= 1 ? 1 : rules.bestOf === 3 ? 2.4 : 3.6;
    const length = rules.cap ? Math.min(rules.pointsToWin, rules.cap) : rules.pointsToWin;
    return Math.max(4, base * expectedGames * (length / 11));
}
/**
 * Simulate the day the way the court desk runs it: matches go to the first
 * free court in play order, a team never plays two matches at once, bracket
 * matches wait for the results they depend on.
 *
 * With `fromNow`, finished matches are skipped and live ones are assumed to be
 * half done.
 */
export function projectSchedule(t, opts = {}) {
    const base = t.settings.minutesPerMatch || 20;
    const courts = Math.max(1, t.courts.length);
    const divisions = new Map(t.divisions.map((d) => [d.id, d]));
    const byId = t.matches;
    const duration = (m) => {
        const div = divisions.get(m.divisionId);
        return div ? matchMinutes(rulesForMatch(m, div.settings), base) : base;
    };
    const finish = new Map();
    const courtFree = Array(courts).fill(0);
    const teamFree = new Map();
    const real = Object.values(byId).filter((m) => !m.bye && m.stage !== 'reset');
    let pending = real;
    if (opts.fromNow) {
        for (const m of real)
            if (m.status === 'final')
                finish.set(m.id, 0);
        const live = real.filter((m) => m.status === 'live');
        live.forEach((m, i) => {
            const end = duration(m) / 2;
            finish.set(m.id, end);
            courtFree[i % courts] = Math.max(courtFree[i % courts], end);
            for (const s of [m.a, m.b])
                if (s.kind === 'team')
                    teamFree.set(s.teamId, end);
        });
        pending = real.filter((m) => m.status === 'pending');
    }
    const groupByDivision = new Map();
    for (const m of real) {
        if (m.stage !== 'pool' && m.stage !== 'rr')
            continue;
        groupByDivision.set(m.divisionId, [...(groupByDivision.get(m.divisionId) ?? []), m]);
    }
    // When is a match's input known? undefined = not yet schedulable.
    const sourceReady = (s, divisionId) => {
        switch (s.kind) {
            case 'team':
            case 'bye':
                return 0;
            case 'qualifier': {
                let latest = 0;
                for (const m of groupByDivision.get(divisionId) ?? []) {
                    const f = finish.get(m.id);
                    if (f === undefined)
                        return undefined;
                    latest = Math.max(latest, f);
                }
                return latest;
            }
            case 'winner':
            case 'loser':
                return matchDone(s.matchId);
        }
    };
    const matchDone = (id) => {
        const known = finish.get(id);
        if (known !== undefined)
            return known;
        const m = byId[id];
        if (!m)
            return 0;
        if (m.bye) {
            // A bye "finishes" as soon as its real side is decided.
            const a = sourceReady(m.a, m.divisionId);
            const b = sourceReady(m.b, m.divisionId);
            return a === undefined || b === undefined ? undefined : Math.max(a, b);
        }
        return undefined;
    };
    const order = (x, y) => x.depth - y.depth || x.number - y.number;
    pending = pending.slice().sort(order);
    let guard = pending.length * 2 + 10;
    while (pending.length && guard-- > 0) {
        let court = 0;
        for (let c = 1; c < courts; c++)
            if (courtFree[c] < courtFree[court])
                court = c;
        const free = courtFree[court];
        let best;
        for (const m of pending) {
            const a = sourceReady(m.a, m.divisionId);
            const b = sourceReady(m.b, m.divisionId);
            if (a === undefined || b === undefined)
                continue;
            let start = Math.max(free, a, b);
            for (const s of [m.a, m.b])
                if (s.kind === 'team')
                    start = Math.max(start, teamFree.get(s.teamId) ?? 0);
            if (!best || start < best.start)
                best = { m, start };
            if (start === free)
                break; // can't do better than starting right away
        }
        if (!best)
            break;
        const end = best.start + duration(best.m);
        finish.set(best.m.id, end);
        courtFree[court] = end;
        for (const s of [best.m.a, best.m.b])
            if (s.kind === 'team')
                teamFree.set(s.teamId, end);
        pending = pending.filter((m) => m !== best.m);
    }
    let minutes = 0;
    finish.forEach((v) => (minutes = Math.max(minutes, v)));
    const remaining = opts.fromNow ? real.filter((m) => m.status !== 'final').length : real.length;
    return { minutes: Math.round(minutes), matches: remaining };
}
export function formatDuration(min) {
    const m = Math.max(0, Math.round(min / 5) * 5);
    if (m < 60)
        return `${m} min`;
    const h = Math.floor(m / 60);
    const r = m % 60;
    return `${h}h${r ? ` ${r}m` : ''}`;
}
export function clockAfter(minutes, from = Date.now()) {
    return new Date(from + minutes * 60000).toLocaleTimeString([], { hour: 'numeric', minute: '2-digit' });
}
