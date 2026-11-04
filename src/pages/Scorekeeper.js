import { Fragment as _Fragment, jsx as _jsx, jsxs as _jsxs } from "react/jsx-runtime";
import { useEffect, useRef, useState } from 'react';
import { finishMatch, saveLiveScore, startMatch } from '../lib/actions';
import { describeRules, isGameComplete, matchDecided, winnerFromGames } from '../lib/scoring';
import { teamName } from '../lib/tournament';
import { slotName, stageLabel } from '../components/match';
import { Empty, Segmented } from '../components/ui';
import { navigate } from '../state/router';
import { load, save, useTournament } from '../state/store';
export function Scorekeeper({ matchId }) {
    const { t, resolved, canScore, update } = useTournament();
    const r = resolved.matches[matchId];
    const m = t.matches[matchId];
    const doubles = t.settings.doubles;
    const [mode, setModeState] = useState(() => load('pbt.scoremode') ?? 'sideout');
    const setMode = (v) => {
        setModeState(v);
        save('pbt.scoremode', v);
    };
    const [games, setGames] = useState(() => (m?.games.length ? m.games : [{ a: 0, b: 0 }]));
    const [serve, setServe] = useState(() => m?.serve ?? { side: 'a', server: doubles ? 2 : 1 });
    const history = useRef([]);
    const [, force] = useState(0);
    // Mark the match live when the scorekeeper opens it.
    useEffect(() => {
        if (canScore && m && m.status === 'pending' && r?.ready)
            update((tt) => startMatch(tt, matchId));
    }, []);
    if (!r || !m)
        return _jsx(Empty, { title: "Match not found" });
    const nameA = slotName(t, r.a, m.a).text;
    const nameB = slotName(t, r.b, m.b).text;
    const rules = r.rules;
    const teamsKnown = r.ready || r.done;
    if (!canScore || m.status === 'final' || !teamsKnown) {
        return (_jsxs("div", { className: "scorer", children: [_jsx("a", { href: "#/courts", className: "small", children: "\u2190 Courts" }), _jsxs("div", { className: "card", style: { marginTop: 10 }, children: [_jsxs("h2", { children: [nameA, " vs ", nameB] }), _jsx("p", { className: "muted", children: m.status === 'final'
                                ? `Final: ${m.games.map((g) => `${g.a}-${g.b}`).join(', ')} — ${teamName(t, r.winner)} won.`
                                : !teamsKnown
                                    ? 'This match is waiting for earlier results.'
                                    : 'You need a scorer or admin passcode to keep score (Settings → Live sync).' })] })] }));
    }
    const idx = games.length - 1;
    const game = games[idx];
    const gameOver = isGameComplete(game, rules);
    const decided = matchDecided(games, rules);
    const commit = (nextGames, nextServe) => {
        history.current.push({ games, serve });
        if (history.current.length > 200)
            history.current.shift();
        setGames(nextGames);
        setServe(nextServe);
        update((tt) => saveLiveScore(tt, matchId, nextGames, mode === 'simple' ? undefined : nextServe));
        force((n) => n + 1);
    };
    const addPoint = (side, delta = 1) => {
        const g = { ...game, [side]: Math.max(0, game[side] + delta) };
        commit([...games.slice(0, idx), g], serve);
    };
    const rallyWon = (side) => {
        if (gameOver)
            return;
        if (mode === 'rally') {
            const g = { ...game, [side]: game[side] + 1 };
            commit([...games.slice(0, idx), g], { side, server: 1 });
            return;
        }
        if (side === serve.side) {
            const g = { ...game, [side]: game[side] + 1 };
            commit([...games.slice(0, idx), g], serve);
        }
        else if (doubles && serve.server === 1) {
            commit(games, { ...serve, server: 2 });
        }
        else {
            commit(games, { side: serve.side === 'a' ? 'b' : 'a', server: 1 });
        }
    };
    const undo = () => {
        const prev = history.current.pop();
        if (!prev)
            return;
        setGames(prev.games);
        setServe(prev.serve);
        update((tt) => saveLiveScore(tt, matchId, prev.games, mode === 'simple' ? undefined : prev.serve));
        force((n) => n + 1);
    };
    const nextGame = () => {
        // The team that received first last game serves first now.
        const first = games.length % 2 === 1 ? 'b' : 'a';
        commit([...games, { a: 0, b: 0 }], { side: first, server: doubles ? 2 : 1 });
    };
    const finish = () => {
        if (!winnerFromGames(games)) {
            window.alert('Nobody is ahead yet — keep playing or enter the final score from the Courts page.');
            return;
        }
        update((tt) => finishMatch(tt, matchId, games));
        navigate('/courts');
    };
    const servingScore = game[serve.side];
    const receivingScore = game[serve.side === 'a' ? 'b' : 'a'];
    const call = mode === 'sideout'
        ? doubles
            ? `${servingScore}-${receivingScore}-${serve.server}`
            : `${servingScore}-${receivingScore}`
        : `${game.a}-${game.b}`;
    const atStart = game.a === 0 && game.b === 0;
    const showServe = mode !== 'simple';
    return (_jsxs("div", { className: "scorer", children: [_jsxs("div", { className: "row-between", style: { marginBottom: 10 }, children: [_jsx("a", { href: "#/courts", className: "small", children: "\u2190 Courts" }), _jsxs("span", { className: "small muted", children: ["M", m.number, " \u00B7 ", stageLabel(t, m), m.court ? ` · ${m.court}` : ''] })] }), _jsxs("div", { className: "scoreboard", children: [_jsxs("div", { className: "row-between", style: { flexWrap: 'wrap', gap: 10 }, children: [_jsx(Segmented, { value: mode, onChange: setMode, options: [
                                    { value: 'sideout', label: 'Side-out' },
                                    { value: 'rally', label: 'Rally' },
                                    { value: 'simple', label: '+/−' },
                                ] }), _jsxs("span", { className: "tiny", style: { color: 'var(--on-night-muted)' }, children: ["Game ", games.length, " \u00B7 ", describeRules(rules)] })] }), showServe && (_jsxs("div", { style: { marginTop: 16 }, children: [_jsx("div", { className: "eyebrow center", style: { color: 'var(--on-night-muted)' }, children: mode === 'sideout' ? 'Score call' : 'Score' }), _jsx("div", { className: "call", children: call }), _jsxs("div", { className: "tiny center", style: { color: 'var(--on-night-muted)', marginTop: 4 }, children: ["Serving: ", _jsx("b", { style: { color: 'var(--on-night)' }, children: serve.side === 'a' ? nameA : nameB }), mode === 'sideout' && doubles ? ` · server ${serve.server}` : ''] })] })), _jsx("div", { className: "scorer-teams", children: ['a', 'b'].map((side) => (_jsxs("div", { className: `scorer-side ${showServe && serve.side === side ? 'serving' : ''}`, children: [_jsx("div", { className: "team", children: side === 'a' ? nameA : nameB }), _jsx("div", { className: "points", children: game[side] }), mode === 'simple' ? (_jsxs(_Fragment, { children: [_jsx("button", { className: "tap", onClick: () => addPoint(side, 1), disabled: gameOver, children: "+1" }), _jsx("button", { className: "tap secondary", onClick: () => addPoint(side, -1), children: "\u22121" })] })) : (_jsx("button", { className: "tap", onClick: () => rallyWon(side), disabled: gameOver, children: "Won rally" }))] }, side))) })] }), gameOver && (_jsxs("div", { className: "cta-strip", children: [_jsxs("div", { className: "bold", children: ["Game ", games.length, " to ", game.a > game.b ? nameA : nameB, " (", Math.max(game.a, game.b), "-", Math.min(game.a, game.b), ")"] }), _jsx("div", { className: "row", style: { marginTop: 8 }, children: decided ? (_jsxs("button", { className: "btn btn-dark btn-lg", onClick: finish, children: ["Finish match: ", decided === 'a' ? nameA : nameB, " wins"] })) : (_jsxs("button", { className: "btn btn-dark btn-lg", onClick: nextGame, children: ["Start game ", games.length + 1] })) })] })), _jsxs("div", { className: "row", style: { marginTop: 14, justifyContent: 'center' }, children: [_jsx("button", { className: "btn", onClick: undo, disabled: !history.current.length, children: "\u21B6 Undo" }), showServe && atStart && (_jsx("button", { className: "btn", onClick: () => commit(games, { side: serve.side === 'a' ? 'b' : 'a', server: doubles ? 2 : 1 }), children: "Switch first server" })), !decided && (_jsx("button", { className: "btn btn-ghost", onClick: () => {
                            if (window.confirm('End the match now with the current scores?'))
                                finish();
                        }, children: "End match early" }))] }), games.length > 1 && (_jsx("div", { className: "center muted small", style: { marginTop: 14 }, children: games.map((g, i) => (_jsxs("span", { style: { marginRight: 12 }, children: ["G", i + 1, ": ", g.a, "-", g.b] }, i))) })), mode === 'sideout' && (_jsxs("p", { className: "tiny muted center", style: { marginTop: 16 }, children: ["Traditional scoring: only the serving team scores. Tap the team that won each rally and the server rotation and side-outs are handled for you. Games start at ", doubles ? '0-0-2' : '0-0', "."] }))] }));
}
