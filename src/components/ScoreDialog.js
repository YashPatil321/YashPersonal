import { Fragment as _Fragment, jsx as _jsx, jsxs as _jsxs } from "react/jsx-runtime";
import { Fragment, useMemo, useState } from 'react';
import { callMatch, finishMatch, reopenMatch, resetMatch, saveLiveScore, setMatchTeams, unassignMatch } from '../lib/actions';
import { describeRules, scoreWarnings, winnerFromGames } from '../lib/scoring';
import { teamName } from '../lib/tournament';
import { useTournament } from '../state/store';
import { divisionName, slotName, stageLabel, StatusBadge } from './match';
import { Modal } from './ui';
export function ScoreDialog({ matchId, onClose }) {
    const { t, resolved, canScore, isAdmin, update } = useTournament();
    const r = resolved.matches[matchId];
    const m = t.matches[matchId];
    const rules = r?.rules;
    const columns = Math.max(rules?.bestOf ?? 1, m?.games.length ?? 0, 1);
    const [games, setGames] = useState(() => Array.from({ length: columns }, (_, i) => ({
        a: m?.games[i] ? String(m.games[i].a) : '',
        b: m?.games[i] ? String(m.games[i].b) : '',
    })));
    const [confirmClear, setConfirmClear] = useState(false);
    const parsed = useMemo(() => games
        .map((g) => ({ a: Number(g.a) || 0, b: Number(g.b) || 0 }))
        .filter((g, i) => games[i].a !== '' || games[i].b !== '' || g.a > 0 || g.b > 0), [games]);
    if (!r || !m || !rules)
        return null;
    const nameA = slotName(t, r.a, m.a);
    const nameB = slotName(t, r.b, m.b);
    const teamsKnown = typeof r.a === 'string' && typeof r.b === 'string' && r.a !== 'BYE' && r.b !== 'BYE';
    const winner = winnerFromGames(parsed);
    const warnings = parsed.length ? scoreWarnings(parsed, rules) : [];
    const editable = canScore && teamsKnown && !r.notNeeded;
    const busyCourts = new Set(resolved.ordered.filter((x) => x.m.status === 'live' && !x.done && x.m.id !== m.id).map((x) => x.m.court));
    const setCell = (i, side, v) => {
        const clean = v.replace(/[^0-9]/g, '').slice(0, 2);
        setGames((prev) => prev.map((g, j) => (j === i ? { ...g, [side]: clean } : g)));
    };
    const saveFinal = () => {
        update((tt) => finishMatch(tt, m.id, parsed));
        onClose();
    };
    const saveProgress = () => {
        update((tt) => saveLiveScore(tt, m.id, parsed, tt.matches[m.id].serve));
        onClose();
    };
    const forfeit = (side) => {
        const who = side === 'a' ? nameA.text : nameB.text;
        if (!window.confirm(`Record a forfeit by ${who}?`))
            return;
        update((tt) => finishMatch(tt, m.id, [], { forfeit: side }));
        onClose();
    };
    return (_jsxs(Modal, { title: _jsxs("span", { children: [nameA.text, " ", _jsx("span", { className: "muted", children: "vs" }), " ", nameB.text] }), subtitle: _jsxs(_Fragment, { children: ["M", m.number, " \u00B7 ", t.divisions.length > 1 ? `${divisionName(t, m.divisionId)} · ` : '', stageLabel(t, m), " \u00B7 ", describeRules(rules)] }), onClose: onClose, children: [_jsxs("div", { className: "row", style: { marginBottom: 12 }, children: [_jsx(StatusBadge, { r: r }), m.court && _jsx("span", { className: "badge", children: m.court })] }), r.stale && (_jsx("div", { className: "alert alert-warn", style: { marginBottom: 12 }, children: "An earlier result was changed, so the teams in this match are different from when this score was entered. Please re-enter the score (or clear it)." })), r.notNeeded && (_jsx("div", { className: "alert", style: { marginBottom: 12 }, children: "The winners-bracket champion won the grand final, so this reset match isn't needed." })), !teamsKnown && !r.notNeeded && (_jsxs("div", { className: "alert", style: { marginBottom: 12 }, children: ["Waiting for earlier results: ", _jsx("b", { children: nameA.text }), " vs ", _jsx("b", { children: nameB.text }), "."] })), teamsKnown && (_jsxs("div", { className: "score-grid", style: { ['--games']: columns }, children: [_jsx("div", {}), games.map((_, i) => (_jsxs("div", { className: "head", children: ["Game ", i + 1] }, i))), ['a', 'b'].map((side) => (_jsxs(Fragment, { children: [_jsxs("div", { className: "bold truncate", title: side === 'a' ? nameA.text : nameB.text, children: [winner === side && _jsx("span", { className: "check-mark", children: "\u2713 " }), side === 'a' ? nameA.text : nameB.text] }), games.map((g, i) => (_jsx("input", { className: "score-input", inputMode: "numeric", pattern: "[0-9]*", "aria-label": `${side === 'a' ? nameA.text : nameB.text} game ${i + 1}`, value: g[side], disabled: !editable, onChange: (e) => setCell(i, side, e.target.value), onFocus: (e) => e.target.select() }, i)))] }, side)))] })), editable && warnings.length > 0 && (_jsxs("div", { className: "alert alert-warn small", style: { marginTop: 12 }, children: [warnings.map((w) => (_jsx("div", { children: w }, w))), _jsx("div", { className: "muted tiny", style: { marginTop: 4 }, children: "You can still save it (e.g. for time-capped games)." })] })), editable && (_jsxs(_Fragment, { children: [_jsxs("div", { className: "row", style: { marginTop: 16 }, children: [_jsx("button", { className: "btn btn-primary btn-lg", disabled: !winner, onClick: saveFinal, children: winner ? `Save final — ${teamName(t, winner === 'a' ? r.a : r.b)} wins` : 'Enter scores to finish' }), m.status !== 'final' && parsed.length > 0 && (_jsx("button", { className: "btn", onClick: saveProgress, children: "Save as in-progress" }))] }), _jsx("div", { className: "section", style: { marginTop: 18 }, children: _jsx("div", { className: "form-grid", children: _jsxs("label", { className: "field", children: ["Court", _jsxs("select", { className: "input", value: m.court ?? '', disabled: m.status === 'final', onChange: (e) => {
                                            const court = e.target.value;
                                            update((tt) => (court ? callMatch(tt, m.id, court) : unassignMatch(tt, m.id)));
                                        }, children: [_jsx("option", { value: "", children: "Not on a court" }), t.courts.map((c) => (_jsxs("option", { value: c, children: [c, busyCourts.has(c) ? ' (busy)' : ''] }, c)))] })] }) }) }), _jsxs("div", { className: "row", style: { marginTop: 16 }, children: [_jsx("a", { className: "btn btn-sm", href: `#/score/${m.id}`, onClick: onClose, children: "Open live scorekeeper" }), m.status !== 'final' && (_jsxs(_Fragment, { children: [_jsxs("button", { className: "btn btn-sm btn-ghost", onClick: () => forfeit('a'), children: [nameA.text.split(' / ')[0], "\u2026 forfeits"] }), _jsxs("button", { className: "btn btn-sm btn-ghost", onClick: () => forfeit('b'), children: [nameB.text.split(' / ')[0], "\u2026 forfeits"] })] })), m.status === 'final' && (_jsx("button", { className: "btn btn-sm btn-ghost", onClick: () => {
                                    update((tt) => reopenMatch(tt, m.id));
                                }, children: "Reopen match" })), (m.status === 'final' || m.games.length > 0) &&
                                (confirmClear ? (_jsx("button", { className: "btn btn-sm btn-danger", onClick: () => {
                                        update((tt) => resetMatch(tt, m.id));
                                        onClose();
                                    }, children: "Really clear the result?" })) : (_jsx("button", { className: "btn btn-sm btn-ghost btn-danger", onClick: () => setConfirmClear(true), children: "Clear result" })))] }), m.status === 'final' && (_jsx("p", { className: "muted tiny", style: { marginTop: 10 }, children: "Changing a finished result updates standings and who advances automatically. Later matches that were already played with different teams will be flagged \u201CCheck score\u201D." }))] })), isAdmin && m.status !== 'final' && (_jsx(MatchupEditor, { divisionId: m.divisionId, a: typeof r.a === 'string' && r.a !== 'BYE' ? r.a : '', b: typeof r.b === 'string' && r.b !== 'BYE' ? r.b : '', onSave: (a, b) => update((tt) => setMatchTeams(tt, m.id, a, b)) }, `${String(r.a)}-${String(r.b)}`))] }));
}
/** Organizer-only: swap which teams play in this match. */
function MatchupEditor({ divisionId, a, b, onSave, }) {
    const { t } = useTournament();
    const [open, setOpen] = useState(false);
    const [teamA, setTeamA] = useState(a);
    const [teamB, setTeamB] = useState(b);
    const division = t.divisions.find((d) => d.id === divisionId);
    const ids = division?.teamIds ?? Object.keys(t.teams);
    if (!open) {
        return (_jsx("div", { style: { marginTop: 14 }, children: _jsx("button", { className: "btn btn-sm btn-ghost", onClick: () => setOpen(true), children: "Edit matchup" }) }));
    }
    const select = (value, onChange, label) => (_jsxs("label", { className: "field", children: [label, _jsxs("select", { className: "input", value: value, onChange: (e) => onChange(e.target.value), children: [_jsx("option", { value: "", children: "Choose a team\u2026" }), ids.map((id) => (_jsx("option", { value: id, children: t.teams[id]?.name }, id)))] })] }));
    return (_jsxs("div", { className: "card card-tight", style: { marginTop: 14, background: 'var(--surface-2)' }, children: [_jsx("h3", { style: { marginBottom: 8 }, children: "Edit matchup" }), _jsxs("div", { className: "form-grid", children: [select(teamA, setTeamA, 'Team A'), select(teamB, setTeamB, 'Team B')] }), teamA && teamA === teamB && _jsx("div", { className: "alert alert-warn small", style: { marginTop: 8 }, children: "Pick two different teams." }), _jsx("p", { className: "tiny muted", style: { margin: '8px 0 0' }, children: "This replaces the teams in this match only. Any score already entered for it is cleared." }), _jsxs("div", { className: "row", style: { marginTop: 10 }, children: [_jsx("button", { className: "btn btn-primary btn-sm", disabled: !teamA || !teamB || teamA === teamB || (teamA === a && teamB === b), onClick: () => {
                            onSave(teamA, teamB);
                            setOpen(false);
                        }, children: "Save matchup" }), _jsx("button", { className: "btn btn-sm btn-ghost", onClick: () => setOpen(false), children: "Cancel" })] })] }));
}
