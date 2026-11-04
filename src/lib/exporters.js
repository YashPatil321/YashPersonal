import { teamName } from './tournament';
function stageText(t, stage, round, poolId, label, divisionId) {
    if (stage === 'pool') {
        const pool = t.divisions.find((d) => d.id === divisionId)?.pools.find((p) => p.id === poolId);
        return `${pool?.name ?? 'Pool'} R${round}`;
    }
    if (stage === 'rr')
        return `Round ${round}`;
    return label ?? stage;
}
export function matchesTable(t, resolved) {
    const rows = [['Match', 'Division', 'Stage', 'Team A', 'Team B', 'Score', 'Winner', 'Status', 'Court']];
    for (const r of resolved.ordered) {
        if (r.notNeeded)
            continue;
        const div = t.divisions.find((d) => d.id === r.m.divisionId);
        rows.push([
            `M${r.m.number}`,
            div?.name ?? '',
            stageText(t, r.m.stage, r.m.round, r.m.poolId, r.m.label, r.m.divisionId),
            typeof r.a === 'string' ? teamName(t, r.a) : 'TBD',
            typeof r.b === 'string' ? teamName(t, r.b) : 'TBD',
            r.m.forfeit ? 'Forfeit' : r.m.games.map((g) => `${g.a}-${g.b}`).join(', '),
            r.done && typeof r.winner === 'string' ? teamName(t, r.winner) : '',
            r.m.status,
            r.m.court ?? '',
        ]);
    }
    return rows;
}
export function standingsTable(t, resolved) {
    const rows = [['Division', 'Group', 'Rank', 'Team', 'W', 'L', 'Games W', 'Games L', 'PF', 'PA', '+/-']];
    for (const d of t.divisions) {
        const rd = resolved.divisions[d.id];
        const groups = rd.rrStandings
            ? [['Round robin', rd.rrStandings]]
            : d.pools.map((p) => [p.name, rd.poolStandings[p.id]]);
        for (const [group, list] of groups) {
            for (const s of list ?? []) {
                rows.push([
                    d.name,
                    group,
                    String(s.rank),
                    teamName(t, s.teamId),
                    String(s.wins),
                    String(s.losses),
                    String(s.gamesWon),
                    String(s.gamesLost),
                    String(s.pointsFor),
                    String(s.pointsAgainst),
                    String(s.diff),
                ]);
            }
        }
    }
    return rows;
}
export function placementsTable(t, resolved) {
    const rows = [['Division', 'Place', 'Team', 'Players']];
    for (const d of t.divisions) {
        for (const p of resolved.divisions[d.id].placements) {
            for (const id of p.teamIds) {
                const team = t.teams[id];
                rows.push([d.name, String(p.place), team?.name ?? '', (team?.playerIds ?? []).map((pid) => t.players[pid]?.name).join(', ')]);
            }
        }
    }
    return rows;
}
export function teamsTable(t) {
    const rows = [['Division', 'Seed', 'Team', 'Players', 'Rating', 'Emails', 'Checked in']];
    for (const d of t.divisions) {
        d.teamIds.forEach((id, i) => {
            const team = t.teams[id];
            const players = team.playerIds.map((pid) => t.players[pid]).filter(Boolean);
            rows.push([
                d.name,
                String(i + 1),
                team.name,
                players.map((p) => p.name).join(', '),
                team.rating !== undefined ? String(team.rating) : '',
                players.map((p) => p.email ?? '').filter(Boolean).join(', '),
                team.checkedIn ? 'yes' : '',
            ]);
        });
    }
    return rows;
}
export function download(filename, content, type = 'text/plain') {
    const blob = new Blob([content], { type });
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = filename;
    document.body.appendChild(a);
    a.click();
    a.remove();
    setTimeout(() => URL.revokeObjectURL(url), 1000);
}
export function slug(s) {
    return s.toLowerCase().replace(/[^a-z0-9]+/g, '-').replace(/^-|-$/g, '') || 'tournament';
}
