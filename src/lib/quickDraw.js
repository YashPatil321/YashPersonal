import { BRAND } from '../brand';
import { uid } from './ids';
import { DEFAULT_IMPORT_OPTIONS, detectColumns, distinctTeamNames, importRegistrations } from './registrations';
import { buildTournament, courtNames, defaultDivisionSettings } from './tournament';
/** Which of the two divisions a sign-up's answer belongs to. */
export function fixedDivision(name) {
    return /kid|teen|youth|junior|child|student/i.test(name) ? 'Kids/Teens' : 'Adults';
}
/**
 * One click from sign-ups to a draft draw: read the sheet rows, keep pairs who
 * signed up together, pair up solo players, put everyone in Adults or Kids/Teens,
 * and schedule it so every team plays at least 3 games. Saved as a draft.
 */
export function quickDraw(rows) {
    const res = importRegistrations(rows, detectColumns(rows[0] ?? []), { ...DEFAULT_IMPORT_OPTIONS, doubles: true });
    const teams = { ...res.teams };
    const players = { ...res.players };
    // Anyone left without a partner still gets a spot (as a one-player team) so the
    // organizer can see them and add a partner in one tap.
    const needPartner = [];
    const leftovers = new Map();
    for (const u of res.unmatched) {
        const p = players[u.playerId];
        if (!p)
            continue;
        const team = { id: uid('t'), name: p.name, playerIds: [p.id], divisionId: '' };
        teams[team.id] = team;
        needPartner.push(p.name);
        const key = fixedDivision(u.division);
        leftovers.set(key, [...(leftovers.get(key) ?? []), team.id]);
    }
    const divisions = BRAND.divisions.map((name) => {
        const teamIds = [
            ...res.divisions.filter((d) => fixedDivision(d.name) === name).flatMap((d) => d.teamIds),
            ...(leftovers.get(name) ?? []),
        ];
        return { name, teamIds, settings: defaultDivisionSettings(teamIds.length) };
    });
    const t = buildTournament({
        name: BRAND.eventName,
        date: BRAND.date,
        courts: courtNames(BRAND.courts),
        minutesPerMatch: 20,
        doubles: true,
        hoursAvailable: BRAND.hours,
    }, players, distinctTeamNames(teams, players), divisions);
    // "My partner will sign up on their own" — but did they?
    const header = rows[0] ?? [];
    const col = (title) => header.indexOf(title);
    const norm = (v) => v.trim().toLowerCase().replace(/\s+/g, ' ');
    const signedUp = new Set(rows.slice(1).map((r) => norm(r[col('Full name')] ?? '')));
    const notSignedUp = rows
        .slice(1)
        .filter((r) => col('Partner pays separately') >= 0 && /^yes/i.test(r[col('Partner pays separately')] ?? ''))
        .filter((r) => !signedUp.has(norm(r[col("Partner's full name")] ?? '')))
        .map((r) => `${(r[col("Partner's full name")] ?? '').trim()} (with ${(r[col('Full name')] ?? '').trim()})`);
    return {
        notSignedUp,
        t: { ...t, published: false },
        teams: divisions.reduce((n, d) => n + d.teamIds.length, 0),
        needPartner,
        warnings: res.warnings,
    };
}
