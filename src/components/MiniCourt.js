import { jsx as _jsx, jsxs as _jsxs } from "react/jsx-runtime";
import { teamName } from '../lib/tournament';
/** A court drawn from above, with each team on its side of the net and the live game score. */
export function MiniCourt({ t, court, match, meta, children, }) {
    const game = match?.m.games[match.m.games.length - 1];
    const serving = match?.m.serve?.side;
    return (_jsxs("div", { className: `court-card ${match ? 'live' : 'open'}`, children: [_jsxs("div", { className: "court-card-head", children: [_jsx("span", { className: "court-name", children: court }), match ? _jsx("span", { className: "badge badge-live", children: "Live" }) : _jsx("span", { className: "badge", children: "Open" })] }), _jsx("div", { className: "court-viz", children: _jsx("div", { className: "court-surface", children: match ? (['a', 'b'].map((side) => (_jsxs("div", { className: `court-side ${side === 'b' ? 'right' : ''} ${serving === side ? 'serving' : ''}`, children: [_jsx("div", { className: "team", title: teamName(t, side === 'a' ? match.a : match.b), children: teamName(t, side === 'a' ? match.a : match.b)
                                    .split(' / ')
                                    .slice(0, 2)
                                    .map((line, i) => (_jsx("span", { children: line }, i))) }), _jsxs("div", { className: "pts", children: [side === 'b' && serving === 'b' && _jsx("span", { className: "serve-ball", title: "Serving" }), game ? (side === 'a' ? game.a : game.b) : 0, side === 'a' && serving === 'a' && _jsx("span", { className: "serve-ball", title: "Serving" })] })] }, side)))) : (_jsx("div", { className: "court-open-label", children: "OPEN" })) }) }), _jsxs("div", { className: "court-card-foot", children: [meta && _jsx("div", { className: "match-meta", children: meta }), children] })] }));
}
