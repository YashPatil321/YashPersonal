import { clampPoolCount, computeStructuralByes, generateAllMatches, generateDivision } from './generate';
import { BRAND } from '../brand';
import { uid } from './ids';
import { DEFAULT_SCORING } from './scoring';
export function defaultDivisionSettings(teamCount) {
    const base = {
        format: 'round_robin',
        scoring: { ...DEFAULT_SCORING },
        finalsScoring: { ...DEFAULT_SCORING },
        poolCount: 2,
        advancePerPool: 2,
        playoffFormat: 'single_elim',
        thirdPlaceMatch: false,
        grandFinalReset: false,
        roundRobinCycles: 1,
    };
    if (teamCount <= 6)
        return base;
    const poolCount = Math.max(2, Math.round(teamCount / 5));
    return { ...base, format: 'pools_playoff', poolCount: clampPoolCount(teamCount, poolCount) };
}
export function courtNames(count) {
    return Array.from({ length: count }, (_, i) => `Court ${i + 1}`);
}
export function buildTournament(info, players, teams, divisions) {
    const now = Date.now();
    const divs = divisions.map((d) => ({
        id: d.id ?? uid('d'),
        name: d.name,
        settings: d.settings,
        teamIds: d.teamIds.slice(),
        pools: [],
    }));
    const teamCopy = {};
    for (const d of divs) {
        for (const id of d.teamIds) {
            const team = teams[id];
            if (team)
                teamCopy[id] = { ...team, divisionId: d.id };
        }
    }
    const usedPlayers = new Set(Object.values(teamCopy).flatMap((t) => t.playerIds));
    const playerCopy = {};
    for (const id of usedPlayers)
        if (players[id])
            playerCopy[id] = players[id];
    const t = {
        id: uid('tour'),
        name: info.name || BRAND.eventName,
        date: info.date,
        location: info.location,
        courts: info.courts.length ? info.courts : courtNames(4),
        players: playerCopy,
        teams: teamCopy,
        divisions: divs,
        matches: {},
        settings: {
            autoCall: true,
            minutesPerMatch: info.minutesPerMatch || 20,
            doubles: info.doubles,
            hoursAvailable: info.hoursAvailable,
        },
        createdAt: now,
        updatedAt: now,
    };
    return generateAllMatches(t);
}
/** Matches a division will need (excluding byes and "if necessary" matches). */
export function estimateDivision(teamIds, settings) {
    const division = { id: 'x', name: 'x', settings, teamIds, pools: [] };
    const gen = generateDivision(division);
    const byes = computeStructuralByes(gen.matches);
    const playable = gen.matches.filter((m) => m.stage !== 'reset' && !byes.has(m.id));
    const rounds = new Set(gen.matches.map((m) => `${m.stage}-${m.round}`)).size;
    return { matches: playable.length, rounds };
}
export const FORMAT_LABELS = {
    round_robin: 'Round robin',
    pools_playoff: 'Pool play → playoffs',
    single_elim: 'Single elimination',
    double_elim: 'Double elimination',
};
export function teamName(t, id) {
    if (!id)
        return 'TBD';
    if (id === 'BYE')
        return 'BYE';
    return t.teams[id]?.name ?? 'Unknown team';
}
