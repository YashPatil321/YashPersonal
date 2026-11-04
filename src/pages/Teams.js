import { Fragment as _Fragment, jsx as _jsx, jsxs as _jsxs } from "react/jsx-runtime";
import { useMemo, useState } from 'react';
import { matchQueue, waitEstimates } from '../lib/actions';
import { teamMatches, teamRecord } from '../lib/resolve';
import { MatchCard } from '../components/match';
import { Search } from 'lucide-react';
import { Empty, TeamAvatars, minutesLabel } from '../components/ui';
import { useMatchDialog } from '../components/useMatchDialog';
import { navigate } from '../state/router';
import { useTournament } from '../state/store';
export function Teams() {
    const { t, resolved } = useTournament();
    const [q, setQ] = useState('');
    const needle = q.trim().toLowerCase();
    const matches = useMemo(() => {
        return Object.values(t.teams).filter((team) => {
            if (!needle)
                return true;
            if (team.name.toLowerCase().includes(needle))
                return true;
            return team.playerIds.some((id) => t.players[id]?.name.toLowerCase().includes(needle));
        });
    }, [t, needle]);
    return (_jsxs(_Fragment, { children: [_jsx("div", { className: "page-head", children: _jsxs("div", { children: [_jsxs("div", { className: "eyebrow", children: [Object.keys(t.teams).length, " ", t.settings.doubles ? 'teams' : 'players'] }), _jsxs("h1", { children: ["Find your ", t.settings.doubles ? 'team' : 'name'] })] }) }), _jsxs("div", { className: "search-box", style: { marginBottom: 18 }, children: [_jsx(Search, { size: 20 }), _jsx("input", { className: "input", autoFocus: true, placeholder: "Type your name\u2026", value: q, onChange: (e) => setQ(e.target.value), onKeyDown: (e) => {
                            if (e.key === 'Enter' && matches.length === 1)
                                navigate(`/teams/${matches[0].id}`);
                        }, "aria-label": `Find your ${t.settings.doubles ? 'team' : 'name'}` })] }), t.divisions.map((d) => {
                const list = d.teamIds.filter((id) => matches.some((m) => m.id === id));
                if (!list.length)
                    return null;
                return (_jsxs("div", { style: { marginBottom: 18 }, children: [t.divisions.length > 1 && _jsx("div", { className: "eyebrow", style: { margin: '0 0 8px 4px' }, children: d.name }), _jsx("div", { className: "card list-card", children: list.map((id) => {
                                const team = t.teams[id];
                                const rec = teamRecord(resolved, id);
                                const live = teamMatches(resolved, id).find((r) => r.m.status === 'live' && !r.done);
                                return (_jsxs("a", { className: "list-row auto-first", href: `#/teams/${id}`, style: { color: 'inherit', textDecoration: 'none' }, children: [_jsx(TeamAvatars, { t: t, teamId: id, size: 30 }), _jsxs("span", { className: "truncate", children: [_jsx("span", { className: "bold", children: team.name }), _jsxs("span", { className: "muted small", style: { display: 'block' }, children: ["Seed ", d.teamIds.indexOf(id) + 1, team.rating !== undefined ? ` · ${team.rating.toFixed(2)}` : ''] })] }), _jsxs("span", { className: "row", style: { gap: 6 }, children: [live && _jsx("span", { className: "badge badge-live", children: live.m.court ?? 'Live' }), _jsxs("span", { className: "wl num", children: [rec.wins, "-", rec.losses] })] })] }, id));
                            }) })] }, d.id));
            }), !matches.length && _jsx(Empty, { title: "No one by that name", children: "Check the spelling, or ask the tournament desk." })] }));
}
export function TeamDetail({ teamId }) {
    const { t, resolved, isAdmin, update } = useTournament();
    const { open, dialog } = useMatchDialog();
    const team = t.teams[teamId];
    if (!team)
        return _jsx(Empty, { title: "Team not found" });
    const division = t.divisions.find((d) => d.id === team.divisionId);
    const all = teamMatches(resolved, teamId);
    const rec = teamRecord(resolved, teamId);
    const queue = matchQueue(resolved);
    const waits = waitEstimates(t, resolved);
    const upcoming = all.filter((r) => !r.done);
    const played = all.filter((r) => r.done);
    const rd = division ? resolved.divisions[division.id] : undefined;
    const place = rd?.placements.find((p) => p.teamIds.includes(teamId))?.place;
    const rename = (name) => update((tt) => ({ ...tt, teams: { ...tt.teams, [teamId]: { ...tt.teams[teamId], name } }, updatedAt: Date.now() }));
    const renamePlayer = (id, name) => update((tt) => ({ ...tt, players: { ...tt.players, [id]: { ...tt.players[id], name } }, updatedAt: Date.now() }));
    return (_jsxs(_Fragment, { children: [_jsxs("div", { className: "page-head", children: [_jsxs("div", { style: { minWidth: 0 }, children: [_jsxs("a", { className: "small bold", href: "#/teams", children: ["\u2190 All ", t.settings.doubles ? 'teams' : 'players'] }), _jsxs("div", { className: "row", style: { gap: 12, marginTop: 8, flexWrap: 'nowrap' }, children: [_jsx(TeamAvatars, { t: t, teamId: teamId, size: 44 }), _jsx("h1", { style: { margin: 0 }, children: team.name })] }), _jsxs("div", { className: "muted", children: [division?.name, " \u00B7 Record ", _jsxs("b", { className: "num", children: [rec.wins, "-", rec.losses] }), place && ` · Finished #${place}`] })] }), isAdmin && (_jsxs("label", { className: "check", children: [_jsx("input", { type: "checkbox", checked: !!team.checkedIn, onChange: (e) => update((tt) => ({
                                    ...tt,
                                    teams: { ...tt.teams, [teamId]: { ...tt.teams[teamId], checkedIn: e.target.checked } },
                                    updatedAt: Date.now(),
                                })) }), "Checked in"] }))] }), _jsxs("div", { className: "grid grid-2", children: [_jsxs("div", { className: "card", children: [_jsx("h3", { children: t.settings.doubles ? 'Players' : 'Player' }), _jsx("div", { className: "stack", children: team.playerIds.map((id) => {
                                    const p = t.players[id];
                                    if (!p)
                                        return null;
                                    return (_jsxs("div", { children: [isAdmin ? (_jsx("input", { className: "inline-input", defaultValue: p.name, onBlur: (e) => e.target.value.trim() && e.target.value !== p.name && renamePlayer(id, e.target.value.trim()) })) : (_jsx("div", { className: "bold", children: p.name })), _jsx("div", { className: "muted small", style: { paddingLeft: isAdmin ? 7 : 0 }, children: [p.skillLabel && `Skill: ${p.skillLabel}`, isAdmin && p.email, isAdmin && p.phone].filter(Boolean).join(' · ') })] }, id));
                                }) }), isAdmin && (_jsxs("label", { className: "field", style: { marginTop: 12 }, children: ["Team display name", _jsx("input", { className: "input", defaultValue: team.name, onBlur: (e) => e.target.value.trim() && e.target.value !== team.name && rename(e.target.value.trim()) })] }))] }), _jsxs("div", { className: "card", children: [_jsx("h3", { children: "Next up" }), upcoming.length === 0 ? (_jsx("div", { className: "muted", children: played.length ? 'No more scheduled matches.' : 'No matches scheduled.' })) : (_jsx("div", { className: "stack", children: upcoming.slice(0, 3).map((r) => {
                                    const pos = queue.findIndex((q) => q.r.m.id === r.m.id);
                                    return (_jsx(MatchCard, { t: t, r: r, onOpen: open, extra: r.m.status === 'live' ? (_jsx("div", { className: "match-meta", children: _jsxs("span", { className: "badge badge-live", children: ["Playing now", r.m.court ? ` on ${r.m.court}` : ''] }) })) : pos >= 0 ? (_jsxs("div", { className: "match-meta", children: [_jsxs("span", { className: "badge badge-accent", children: ["#", pos + 1, " in the queue"] }), _jsx("span", { children: queue[pos].blocked ? 'after your current match' : minutesLabel(waits.get(r.m.id)) })] })) : (_jsx("div", { className: "match-meta", children: "Waiting on earlier results" })) }, r.m.id));
                                }) }))] })] }), played.length > 0 && (_jsxs(_Fragment, { children: [_jsx("div", { className: "section-title", children: _jsx("h2", { children: "Results" }) }), _jsx("div", { className: "grid grid-courts", children: played
                            .slice()
                            .reverse()
                            .map((r) => (_jsx(MatchCard, { t: t, r: r, onOpen: open }, r.m.id))) })] })), dialog] }));
}
