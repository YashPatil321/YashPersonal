import { jsx as _jsx, jsxs as _jsxs } from "react/jsx-runtime";
import { teamName } from '../lib/tournament';
import { TeamAvatars } from './ui';
export function stageLabel(t, m) {
    if (m.stage === 'pool') {
        const pool = t.divisions.find((d) => d.id === m.divisionId)?.pools.find((p) => p.id === m.poolId);
        return `${pool?.name ?? 'Pool'} · Round ${m.round}`;
    }
    if (m.stage === 'rr')
        return `Round ${m.round}`;
    return m.label ?? 'Playoff';
}
export function divisionName(t, id) {
    return t.divisions.find((d) => d.id === id)?.name ?? '';
}
export function describeSource(t, s) {
    switch (s.kind) {
        case 'winner': {
            const src = t.matches[s.matchId];
            return src && src.number ? `Winner of M${src.number}` : 'TBD';
        }
        case 'loser': {
            const src = t.matches[s.matchId];
            return src && src.number ? `Loser of M${src.number}` : 'TBD';
        }
        case 'qualifier':
            return `Playoff seed ${s.rank}`;
        case 'bye':
            return 'BYE';
        default:
            return 'TBD';
    }
}
export function slotName(t, value, source) {
    if (value === null)
        return { text: describeSource(t, source), tbd: true };
    return { text: teamName(t, value), tbd: value === 'BYE' };
}
export function StatusBadge({ r }) {
    if (r.stale)
        return _jsx("span", { className: "badge badge-warn", children: "Check score" });
    if (r.notNeeded)
        return _jsx("span", { className: "badge", children: "Not needed" });
    if (r.m.status === 'final')
        return _jsxs("span", { className: "badge badge-final", children: ["Final", r.m.forfeit ? ' · W/O' : ''] });
    if (r.m.status === 'live')
        return _jsxs("span", { className: "badge badge-live", children: ["Live", r.m.court ? ` · ${r.m.court}` : ''] });
    if (r.ready)
        return _jsx("span", { className: "badge badge-court", children: "Ready" });
    return _jsx("span", { className: "badge", children: "Waiting" });
}
function Scores({ r, side }) {
    if (!r.m.games.length)
        return null;
    return (_jsx("div", { className: "scores", children: r.m.games.map((g, i) => {
            const mine = side === 'a' ? g.a : g.b;
            const theirs = side === 'a' ? g.b : g.a;
            return (_jsx("span", { className: mine > theirs && r.m.status === 'final' ? 'won' : '', children: mine }, i));
        }) }));
}
export function TeamLine({ t, r, side, avatars = true }) {
    const value = side === 'a' ? r.a : r.b;
    const source = side === 'a' ? r.m.a : r.m.b;
    const { text, tbd } = slotName(t, value, source);
    const isWinner = r.done && r.winnerSide === side && !r.isBye;
    const isLoser = r.done && r.winnerSide && r.winnerSide !== side && !r.isBye;
    const serving = r.m.status === 'live' && r.m.serve?.side === side;
    return (_jsxs("div", { className: `match-team ${isWinner ? 'winner' : ''} ${isLoser ? 'loser' : ''}`, style: avatars ? undefined : { gridTemplateColumns: 'minmax(0,1fr) auto' }, children: [avatars && _jsx(TeamAvatars, { t: t, teamId: typeof value === 'string' ? value : null, size: 26 }), _jsxs("div", { className: `name ${tbd ? 'tbd' : ''}`, title: text, children: [serving && _jsx("span", { className: "serving-dot", title: "Serving" }), text, isWinner && _jsx("span", { className: "check-mark", children: "\u2713" })] }), _jsx(Scores, { r: r, side: side })] }));
}
export function MatchCard({ t, r, onOpen, showDivision = true, extra, }) {
    return (_jsxs("div", { className: `match ${onOpen ? 'clickable' : ''} ${r.m.status === 'live' && !r.done ? 'is-live' : ''}`, onClick: onOpen ? () => onOpen(r) : undefined, role: onOpen ? 'button' : undefined, tabIndex: onOpen ? 0 : undefined, onKeyDown: onOpen ? (e) => e.key === 'Enter' && onOpen(r) : undefined, children: [_jsxs("div", { className: "match-meta", children: [_jsxs("span", { className: "match-no", children: ["M", r.m.number] }), _jsxs("span", { className: "truncate", style: { flex: 1 }, children: [showDivision && t.divisions.length > 1 ? `${divisionName(t, r.m.divisionId)} · ` : '', stageLabel(t, r.m)] }), _jsx(StatusBadge, { r: r })] }), _jsx(TeamLine, { t: t, r: r, side: "a" }), _jsx(TeamLine, { t: t, r: r, side: "b" }), extra] }));
}
/** Compact one-line row used in long match lists. */
export function MatchRow({ t, r, onOpen, right, }) {
    return (_jsxs("div", { className: "list-row", onClick: () => onOpen(r), role: "button", tabIndex: 0, onKeyDown: (e) => e.key === 'Enter' && onOpen(r), children: [_jsxs("div", { children: [_jsxs("div", { className: "match-no", children: ["M", r.m.number] }), _jsx("div", { className: "tiny muted truncate", children: r.m.stage === 'pool' || r.m.stage === 'rr' ? `Round ${r.m.round}` : '' })] }), _jsxs("div", { className: "vs", children: [_jsx(TeamLine, { t: t, r: r, side: "a" }), _jsx(TeamLine, { t: t, r: r, side: "b" })] }), _jsxs("div", { className: "stack", style: { alignItems: 'flex-end', gap: 4 }, children: [_jsx(StatusBadge, { r: r }), right] })] }));
}
