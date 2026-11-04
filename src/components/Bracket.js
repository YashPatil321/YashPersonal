import { Fragment as _Fragment, jsx as _jsx, jsxs as _jsxs } from "react/jsx-runtime";
import { Trophy } from 'lucide-react';
import { teamName } from '../lib/tournament';
import { slotName } from './match';
import { TeamAvatars } from './ui';
function seedFor(rd, teamId) {
    if (!teamId || teamId === 'BYE')
        return undefined;
    if (rd.division.settings.format === 'pools_playoff') {
        const i = rd.qualifiers.indexOf(teamId);
        return i >= 0 ? i + 1 : undefined;
    }
    const i = rd.division.teamIds.indexOf(teamId);
    return i >= 0 ? i + 1 : undefined;
}
function BracketMatch({ t, rd, r, onOpen, }) {
    const sides = ['a', 'b'].map((side) => {
        const value = side === 'a' ? r.a : r.b;
        const src = side === 'a' ? r.m.a : r.m.b;
        const { text, tbd } = slotName(t, value, src);
        const won = r.done && !r.isBye && r.winnerSide === side;
        const lost = r.done && !r.isBye && r.winnerSide && r.winnerSide !== side;
        const score = r.m.games.map((g) => (side === 'a' ? g.a : g.b)).join(' ');
        return { side, text, tbd, won, lost, score, seed: seedFor(rd, value) };
    });
    const clickable = !r.isBye;
    const live = r.m.status === 'live' && !r.done;
    return (_jsxs("div", { className: `bracket-match ${r.isBye ? 'bye' : ''} ${live ? 'is-live' : ''}`, onClick: clickable ? () => onOpen(r) : undefined, role: clickable ? 'button' : undefined, tabIndex: clickable ? 0 : undefined, onKeyDown: clickable ? (e) => e.key === 'Enter' && onOpen(r) : undefined, title: r.notNeeded ? 'Not needed' : undefined, children: [!r.isBye && (_jsxs("span", { className: "bm-label", children: ["M", r.m.number, live ? ` · LIVE${r.m.court ? ` ${r.m.court}` : ''}` : '', r.notNeeded ? ' · not needed' : '', r.m.stage === 'reset' && !r.done ? ' · if needed' : ''] })), sides.map((s) => (_jsxs("div", { className: `bm-team ${s.won ? 'win' : ''} ${s.lost ? 'lose' : ''} ${s.tbd ? 'tbd' : ''}`, children: [_jsx("span", { className: "seed", children: s.seed ?? '' }), _jsx("span", { className: "nm", title: s.text, children: s.text }), _jsx("span", { className: "sc", children: s.score })] }, s.side)))] }));
}
function chunk(items, size) {
    const out = [];
    for (let i = 0; i < items.length; i += size)
        out.push(items.slice(i, i + size));
    return out;
}
function Columns({ title, rounds, t, rd, onOpen, }) {
    if (!rounds.length)
        return null;
    const size = (r) => (r ? (r.matches ? r.matches.length : 1) : 0);
    return (_jsxs("div", { style: { marginBottom: 26 }, children: [title && _jsx("h2", { style: { fontSize: '1.2rem' }, children: title }), _jsx("div", { className: "bracket-scroll", children: _jsx("div", { className: "bracket", children: rounds.map((round, i) => {
                        const next = rounds[i + 1];
                        const pair = !!next && size(next) * 2 === size(round);
                        const straight = !!next && size(next) === size(round);
                        const cls = `bracket-round ${pair || straight ? 'has-next' : ''} ${straight ? 'straight' : ''}`;
                        const slot = (r) => (_jsx("div", { className: "bm-slot", children: _jsx(BracketMatch, { t: t, rd: rd, r: r, onOpen: onOpen }) }, r.m.id));
                        return (_jsxs("div", { className: cls, children: [_jsx("div", { className: "bracket-round-title", children: round.title }), _jsx("div", { className: "bracket-col", children: round.node ? (_jsx("div", { className: "bm-single", children: _jsx("div", { className: "bm-slot", children: round.node }) })) : pair ? (chunk(round.matches, 2).map((p, j) => (_jsx("div", { className: "bm-pair", children: p.map(slot) }, j)))) : (round.matches.map((r) => (_jsx("div", { className: "bm-single", children: slot(r) }, r.m.id)))) })] }, i));
                    }) }) })] }));
}
function groupRounds(matches) {
    const byRound = new Map();
    for (const r of matches)
        byRound.set(r.m.round, [...(byRound.get(r.m.round) ?? []), r]);
    return [...byRound.entries()]
        .sort((a, b) => a[0] - b[0])
        .map(([, list]) => {
        const sorted = list.sort((a, b) => a.m.slot - b.m.slot);
        const label = sorted[0].m.label ?? '';
        return { title: label.replace(/^(Winners|Losers) /, ''), matches: sorted };
    });
}
function ChampionCard({ t, teamId }) {
    return (_jsxs("div", { className: "champion-card", children: [_jsx(Trophy, { size: 26, color: "var(--ball)" }), _jsx("div", { className: "eyebrow", style: { marginTop: 6 }, children: "Champion" }), teamId ? (_jsxs(_Fragment, { children: [_jsx("div", { style: { marginTop: 8 }, children: _jsx(TeamAvatars, { t: t, teamId: teamId, size: 32 }) }), _jsx("div", { className: "who", children: teamName(t, teamId) })] })) : (_jsx("div", { className: "who", style: { color: 'var(--on-night-muted)' }, children: "TBD" }))] }));
}
export function Bracket({ t, rd, onOpen }) {
    const winners = rd.matches.filter((r) => r.m.stage === 'winners');
    const losers = rd.matches.filter((r) => r.m.stage === 'losers');
    const grandFinal = rd.matches.find((r) => r.m.stage === 'final');
    const reset = rd.matches.find((r) => r.m.stage === 'reset');
    const third = rd.matches.find((r) => r.m.stage === 'third');
    if (!winners.length)
        return null;
    const champion = rd.placements.find((p) => p.place === 1)?.teamIds[0];
    const championRound = { title: 'Champion', node: _jsx(ChampionCard, { t: t, teamId: champion }) };
    if (!grandFinal) {
        // Single elimination
        return (_jsxs(_Fragment, { children: [_jsx(Columns, { t: t, rd: rd, onOpen: onOpen, rounds: [...groupRounds(winners), championRound] }), third && _jsx(Columns, { title: "3rd place", t: t, rd: rd, onOpen: onOpen, rounds: [{ title: '3rd place', matches: [third] }] })] }));
    }
    const finals = [{ title: 'Grand final', matches: [grandFinal] }];
    if (reset)
        finals.push({ title: 'Reset', matches: [reset] });
    finals.push(championRound);
    return (_jsxs(_Fragment, { children: [_jsx(Columns, { title: "Winners bracket", t: t, rd: rd, onOpen: onOpen, rounds: groupRounds(winners) }), losers.length > 0 && _jsx(Columns, { title: "Losers bracket", t: t, rd: rd, onOpen: onOpen, rounds: groupRounds(losers) }), _jsx(Columns, { title: "Finals", t: t, rd: rd, onOpen: onOpen, rounds: finals })] }));
}
