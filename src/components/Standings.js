import { jsx as _jsx, jsxs as _jsxs } from "react/jsx-runtime";
import { Crown } from 'lucide-react';
import { teamName } from '../lib/tournament';
import { TeamAvatars } from './ui';
export function StandingsTable({ t, rows, advancing = 0, qualified, }) {
    return (_jsx("div", { className: "table-wrap", children: _jsxs("table", { className: "table", children: [_jsx("thead", { children: _jsxs("tr", { children: [_jsx("th", { children: "#" }), _jsx("th", { children: "Team" }), _jsx("th", { className: "num", title: "Wins-Losses", children: "W-L" }), _jsx("th", { className: "num", title: "Games won-lost", children: "Games" }), _jsx("th", { className: "num", title: "Points for", children: "PF" }), _jsx("th", { className: "num", title: "Points against", children: "PA" }), _jsx("th", { className: "num", title: "Point differential", children: "+/-" })] }) }), _jsx("tbody", { children: rows.map((r) => {
                        const adv = qualified ? qualified.has(r.teamId) : r.played > 0 && r.rank <= advancing;
                        return (_jsxs("tr", { className: adv ? 'advancing' : '', children: [_jsx("td", { children: _jsx("span", { className: "rank", children: r.rank }) }), _jsx("td", { className: "team-cell", children: _jsxs("a", { href: `#/teams/${r.teamId}`, className: "row", style: { gap: 9, flexWrap: 'nowrap' }, children: [_jsx(TeamAvatars, { t: t, teamId: r.teamId, size: 26 }), _jsx("span", { className: "truncate", children: teamName(t, r.teamId) }), qualified?.has(r.teamId) && _jsx("span", { className: "badge badge-accent", children: "In" })] }) }), _jsxs("td", { className: "num wl", children: [r.wins, "-", r.losses] }), _jsxs("td", { className: "num", children: [r.gamesWon, "-", r.gamesLost] }), _jsx("td", { className: "num", children: r.pointsFor }), _jsx("td", { className: "num", children: r.pointsAgainst }), _jsx("td", { className: `num bold ${r.diff > 0 ? 'diff-pos' : r.diff < 0 ? 'diff-neg' : ''}`, children: r.diff > 0 ? `+${r.diff}` : r.diff })] }, r.teamId));
                    }) })] }) }));
}
/** 1-2-3 podium plus a list of the remaining places. */
export function Podium({ t, placements, limit = 3, }) {
    const flat = placements.flatMap((p) => p.teamIds.map((id) => ({ place: p.place, id })));
    if (!flat.length)
        return null;
    const first = flat.find((x) => x.place === 1);
    const second = flat.find((x) => x.place === 2);
    const thirds = flat.filter((x) => x.place === 3);
    const rest = flat.filter((x) => x.place > 3 && x.place <= limit);
    const Step = ({ x, cls }) => x ? (_jsxs("div", { className: `podium-step ${cls}`, children: [cls === 'p1' && _jsx(Crown, { size: 22, className: "crown" }), _jsx(TeamAvatars, { t: t, teamId: x.id, size: cls === 'p1' ? 36 : 30 }), _jsx("a", { className: "who", href: `#/teams/${x.id}`, children: teamName(t, x.id) }), _jsx("div", { className: "block", children: x.place })] })) : (_jsx("div", {}));
    return (_jsxs("div", { children: [_jsxs("div", { className: "podium3", children: [_jsx(Step, { x: second, cls: "p2" }), _jsx(Step, { x: first, cls: "p1" }), _jsx(Step, { x: thirds[0], cls: "p3" })] }), (thirds.length > 1 || rest.length > 0) && (_jsx("div", { className: "podium-rest", children: [...thirds.slice(1), ...rest].map((x) => (_jsxs("div", { className: "podium-row", children: [_jsx("span", { className: "medal", children: x.place }), _jsx(TeamAvatars, { t: t, teamId: x.id, size: 24 }), _jsx("a", { className: "bold truncate", href: `#/teams/${x.id}`, style: { color: 'inherit' }, children: teamName(t, x.id) })] }, x.id))) }))] }));
}
