import { Fragment as _Fragment, jsx as _jsx, jsxs as _jsxs } from "react/jsx-runtime";
import { useState } from 'react';
import { Bracket } from '../components/Bracket';
import { Podium, StandingsTable } from '../components/Standings';
import { Empty, Segmented } from '../components/ui';
import { useMatchDialog } from '../components/useMatchDialog';
import { FORMAT_LABELS } from '../lib/tournament';
import { useRoute } from '../state/router';
import { useTournament } from '../state/store';
function DrawTabs({ current }) {
    const { t } = useTournament();
    if (!t.divisions.some((d) => d.settings.format !== 'round_robin'))
        return null;
    return (_jsxs("div", { className: "segmented", children: [_jsx("a", { href: "#/standings", className: current === 'standings' ? 'on' : '', children: "Standings" }), _jsx("a", { href: "#/brackets", className: current === 'brackets' ? 'on' : '', children: "Brackets" })] }));
}
function DivisionPicker({ value, onChange }) {
    const { t } = useTournament();
    if (t.divisions.length < 2)
        return null;
    return (_jsx("div", { style: { marginBottom: 14, overflowX: 'auto' }, children: _jsx(Segmented, { value: value, onChange: onChange, options: t.divisions.map((d) => ({ value: d.id, label: d.name })) }) }));
}
function useDivisionParam(filter) {
    const { t } = useTournament();
    const route = useRoute();
    const candidates = t.divisions.filter((d) => !filter || filter(d.settings.format));
    const initial = route.query.get('d');
    const [id, setId] = useState(candidates.find((d) => d.id === initial)?.id ?? candidates[0]?.id ?? t.divisions[0]?.id ?? '');
    return [id, setId];
}
export function Standings() {
    const { t, resolved } = useTournament();
    const [divisionId, setDivisionId] = useDivisionParam();
    const rd = resolved.divisions[divisionId];
    if (!rd)
        return _jsx(Empty, { title: "No divisions yet" });
    const { division } = rd;
    const advance = division.settings.advancePerPool;
    return (_jsxs(_Fragment, { children: [_jsxs("div", { className: "page-head", children: [_jsxs("div", { children: [_jsx("div", { className: "eyebrow", children: FORMAT_LABELS[division.settings.format] }), _jsx("h1", { children: "Standings" })] }), _jsx(DrawTabs, { current: "standings" })] }), _jsx(DivisionPicker, { value: divisionId, onChange: setDivisionId }), rd.placements.length > 0 && (_jsxs("div", { className: "card", style: { marginBottom: 14 }, children: [_jsx("h2", { children: rd.complete ? 'Final results' : 'Results so far' }), _jsx(Podium, { t: t, placements: rd.placements, limit: 8 })] })), division.settings.format === 'round_robin' && rd.rrStandings && (_jsx("div", { className: "card", children: _jsx(StandingsTable, { t: t, rows: rd.rrStandings }) })), division.settings.format === 'pools_playoff' && (_jsxs(_Fragment, { children: [_jsxs("p", { className: "muted small", children: ["Top ", advance, " from each pool advance to the playoffs. Ties are broken by head-to-head, then point differential, then points scored.", !rd.poolsComplete && ' Playoff seeding locks in once every pool match is final.'] }), _jsx("div", { className: "grid grid-2", children: division.pools.map((p) => (_jsxs("div", { className: "card", children: [_jsx("h3", { children: p.name }), _jsx(StandingsTable, { t: t, rows: rd.poolStandings[p.id] ?? [], advancing: rd.poolsComplete ? 0 : advance, qualified: rd.poolsComplete ? rd.qualified : undefined })] }, p.id))) })] })), (division.settings.format === 'single_elim' || division.settings.format === 'double_elim') && (_jsx("div", { className: "card", children: _jsxs("p", { className: "muted", style: { margin: 0 }, children: ["This division is a straight ", FORMAT_LABELS[division.settings.format].toLowerCase(), " bracket \u2014", ' ', _jsx("a", { href: `#/brackets?d=${division.id}`, children: "see the bracket" }), "."] }) }))] }));
}
export function Brackets() {
    const { t, resolved } = useTournament();
    const [divisionId, setDivisionId] = useDivisionParam((f) => f !== 'round_robin');
    const { open, dialog } = useMatchDialog();
    const withBrackets = t.divisions.filter((d) => d.settings.format !== 'round_robin');
    if (!withBrackets.length)
        return (_jsx(Empty, { title: "No brackets", children: _jsx("p", { children: "Every division is a round robin \u2014 check the Standings page." }) }));
    const rd = resolved.divisions[divisionId];
    return (_jsxs(_Fragment, { children: [_jsxs("div", { className: "page-head", children: [_jsxs("div", { children: [_jsx("div", { className: "eyebrow", children: "Playoffs" }), _jsx("h1", { children: "Brackets" })] }), _jsx(DrawTabs, { current: "brackets" })] }), withBrackets.length > 1 && (_jsx("div", { style: { marginBottom: 14, overflowX: 'auto' }, children: _jsx(Segmented, { value: divisionId, onChange: setDivisionId, options: withBrackets.map((d) => ({ value: d.id, label: d.name })) }) })), rd && (_jsxs(_Fragment, { children: [rd.division.settings.format === 'pools_playoff' && !rd.poolsComplete && (_jsxs("div", { className: "alert", style: { marginBottom: 14 }, children: ["Playoff spots fill in automatically once pool play finishes (", rd.matches.filter((r) => r.m.stage === 'pool' && r.done).length, "/", rd.matches.filter((r) => r.m.stage === 'pool').length, " pool matches done)."] })), rd.placements.length > 0 && rd.complete && (_jsxs("div", { className: "card", style: { marginBottom: 14 }, children: [_jsx("h2", { children: "Champions" }), _jsx(Podium, { t: t, placements: rd.placements })] })), _jsx(Bracket, { t: t, rd: rd, onOpen: open })] })), dialog] }));
}
