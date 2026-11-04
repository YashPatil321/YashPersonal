import { Fragment as _Fragment, jsx as _jsx, jsxs as _jsxs } from "react/jsx-runtime";
import { useEffect, useState } from 'react';
import { Trophy } from 'lucide-react';
import { courtStatus, matchQueue } from '../lib/actions';
import { teamName } from '../lib/tournament';
import { divisionName, stageLabel } from '../components/match';
import { MiniCourt } from '../components/MiniCourt';
import { HandHeart } from 'lucide-react';
import { BRAND } from '../brand';
import { BallIcon, BrandName } from '../components/ui';
import { useTournament } from '../state/store';
/** Big-screen display for a TV at the venue. */
export function TV() {
    const { t, resolved } = useTournament();
    const [now, setNow] = useState(Date.now());
    useEffect(() => {
        const id = setInterval(() => setNow(Date.now()), 30000);
        return () => clearInterval(id);
    }, []);
    const courts = courtStatus(t, resolved);
    const queue = matchQueue(resolved).filter((q) => !q.blocked).slice(0, 8);
    const recent = resolved.ordered
        .filter((r) => r.m.status === 'final' && r.m.finishedAt)
        .sort((a, b) => (b.m.finishedAt ?? 0) - (a.m.finishedAt ?? 0))
        .slice(0, 6);
    const champions = t.divisions
        .map((d) => ({ d, rd: resolved.divisions[d.id] }))
        .filter(({ rd }) => rd.complete && rd.placements.length);
    return (_jsxs("div", { className: "tv", children: [_jsxs("div", { className: "tv-head", children: [_jsxs("div", { className: "row", style: { gap: 16, flexWrap: 'nowrap', minWidth: 0 }, children: [_jsx(BallIcon, { size: 56, className: "ball-spin" }), _jsxs("div", { style: { minWidth: 0 }, children: [_jsxs("div", { className: "eyebrow", style: { color: 'var(--ball)' }, children: [BRAND.organizer, " \u00B7 Live courts"] }), _jsx("div", { className: "tv-title truncate", children: _jsx(BrandName, { name: t.name }) })] })] }), _jsxs("div", { className: "row", style: { gap: 18 }, children: [_jsx("span", { className: "tv-clock", children: new Date(now).toLocaleTimeString([], { hour: 'numeric', minute: '2-digit' }) }), _jsx("a", { href: "#/", className: "btn btn-glass btn-sm", children: "Exit" })] })] }), champions.length > 0 && (_jsxs("div", { className: "champion-card", style: { marginBottom: 22, textAlign: 'left', display: 'grid', gap: 6 }, children: [_jsxs("div", { className: "row", style: { gap: 10 }, children: [_jsx(Trophy, { size: 22, color: "var(--ball)" }), _jsx("span", { className: "eyebrow", children: "Champions" })] }), champions.map(({ d, rd }) => (_jsxs("div", { className: "row-between", style: { fontSize: '1.3rem' }, children: [_jsx("span", { style: { color: 'var(--on-night-muted)', fontWeight: 700 }, children: d.name }), _jsx("span", { className: "who", style: { margin: 0 }, children: teamName(t, rd.placements[0].teamIds[0]) })] }, d.id)))] })), _jsxs("div", { className: "tv-grid", children: [_jsx("div", { className: `tv-courts ${courts.length > 6 ? 'compact' : ''}`, children: courts.map(({ court, match }) => (_jsx(MiniCourt, { t: t, court: court, match: match, meta: match ? (_jsxs(_Fragment, { children: [_jsxs("span", { className: "match-no", children: ["M", match.m.number] }), _jsxs("span", { className: "truncate", children: [t.divisions.length > 1 ? `${divisionName(t, match.m.divisionId)} · ` : '', stageLabel(t, match.m), match.m.games.length > 1 ? ` · Game ${match.m.games.length}` : ''] })] })) : (_jsx("span", { children: "Waiting for the next match" })) }, court))) }), _jsxs("div", { className: "stack", style: { gap: 22 }, children: [_jsxs("div", { children: [_jsx("h2", { children: "Up next" }), _jsxs("div", { className: "tv-list", children: [queue.length === 0 && (_jsx("div", { className: "item", style: { color: 'var(--muted)' }, children: "No matches waiting" })), queue.map((q, i) => (_jsxs("div", { className: "item", children: [_jsx("span", { className: "n", children: i + 1 }), _jsxs("span", { children: [teamName(t, q.r.a), " ", _jsx("span", { style: { color: 'var(--muted)' }, children: "vs" }), " ", teamName(t, q.r.b)] })] }, q.r.m.id)))] })] }), recent.length > 0 && (_jsxs("div", { children: [_jsx("h2", { children: "Results" }), _jsx("div", { className: "tv-list", children: recent.map((r) => (_jsx("div", { className: "item", children: _jsxs("span", { children: [_jsx("b", { children: teamName(t, r.winner) }), " ", _jsx("span", { style: { color: 'var(--muted)' }, children: "def." }), ' ', teamName(t, r.loser), ' ', _jsx("span", { style: { color: 'var(--ball)', fontWeight: 800 }, className: "num nowrap", children: r.m.forfeit
                                                            ? 'W/O'
                                                            : r.m.games.map((g) => (r.winnerSide === 'a' ? `${g.a}-${g.b}` : `${g.b}-${g.a}`)).join(', ') })] }) }, r.m.id))) })] }))] })] }), _jsxs("div", { className: "tv-cause", children: [_jsx(HandHeart, { size: 22, color: "var(--ball)" }), _jsxs("span", { children: [_jsxs("b", { children: ["Playing for the ", BRAND.charity.name, "."] }), " ", BRAND.charity.pledge.replace(`${BRAND.charity.name}`, 'cause')] })] })] }));
}
