import { Fragment as _Fragment, jsx as _jsx, jsxs as _jsxs } from "react/jsx-runtime";
import { useMemo, useState } from 'react';
import { teamName } from '../lib/tournament';
import { MatchRow, stageLabel } from '../components/match';
import { Segmented } from '../components/ui';
import { useMatchDialog } from '../components/useMatchDialog';
import { useRoute } from '../state/router';
import { useTournament } from '../state/store';
export function Matches() {
    const { t, resolved } = useTournament();
    const route = useRoute();
    const { open, dialog } = useMatchDialog();
    const [division, setDivision] = useState(route.query.get('d') ?? 'all');
    const [status, setStatus] = useState('all');
    const [q, setQ] = useState('');
    const filtered = useMemo(() => {
        const needle = q.trim().toLowerCase();
        return resolved.ordered.filter((r) => {
            if (division !== 'all' && r.m.divisionId !== division)
                return false;
            if (status === 'live' && !(r.m.status === 'live' && !r.done))
                return false;
            if (status === 'final' && !(r.m.status === 'final'))
                return false;
            if (status === 'upcoming' && (r.done || r.m.status === 'live'))
                return false;
            if (needle) {
                const names = [r.a, r.b].map((x) => (typeof x === 'string' ? teamName(t, x).toLowerCase() : '')).join(' ');
                const players = [r.a, r.b]
                    .flatMap((x) => (typeof x === 'string' ? t.teams[x]?.playerIds ?? [] : []))
                    .map((id) => t.players[id]?.name.toLowerCase() ?? '')
                    .join(' ');
                if (!names.includes(needle) && !players.includes(needle) && `m${r.m.number}` !== needle)
                    return false;
            }
            return true;
        });
    }, [resolved, division, status, q, t]);
    // Group by division → stage heading
    const groups = useMemo(() => {
        const out = [];
        const index = new Map();
        for (const r of filtered) {
            const div = t.divisions.find((d) => d.id === r.m.divisionId);
            const sub = r.m.stage === 'pool' || r.m.stage === 'rr'
                ? r.m.stage === 'pool'
                    ? stageLabel(t, r.m).split(' · ')[0]
                    : 'Round robin'
                : r.m.stage === 'losers'
                    ? 'Losers bracket'
                    : 'Playoffs';
            const key = `${div.id}|${sub}`;
            if (!index.has(key)) {
                index.set(key, out.length);
                out.push({ key, title: t.divisions.length > 1 ? `${div.name} — ${sub}` : sub, matches: [] });
            }
            out[index.get(key)].matches.push(r);
        }
        return out;
    }, [filtered, t]);
    return (_jsxs(_Fragment, { children: [_jsxs("div", { className: "page-head", children: [_jsx("h1", { children: "Matches" }), _jsx("button", { className: "btn btn-sm no-print", onClick: () => window.print(), children: "Print" })] }), _jsxs("div", { className: "card no-print", style: { marginBottom: 14 }, children: [_jsxs("div", { className: "form-grid", children: [_jsxs("label", { className: "field", children: ["Search team or player", _jsx("input", { className: "input", placeholder: "e.g. Kim, or M12", value: q, onChange: (e) => setQ(e.target.value) })] }), t.divisions.length > 1 && (_jsxs("label", { className: "field", children: ["Division", _jsxs("select", { className: "input", value: division, onChange: (e) => setDivision(e.target.value), children: [_jsx("option", { value: "all", children: "All divisions" }), t.divisions.map((d) => (_jsx("option", { value: d.id, children: d.name }, d.id)))] })] }))] }), _jsx("div", { style: { marginTop: 10 }, children: _jsx(Segmented, { value: status, onChange: setStatus, options: [
                                { value: 'all', label: 'All' },
                                { value: 'upcoming', label: 'Upcoming' },
                                { value: 'live', label: 'Live' },
                                { value: 'final', label: 'Final' },
                            ] }) })] }), groups.length === 0 && _jsx("div", { className: "card empty", children: "No matches match those filters." }), groups.map((g) => (_jsxs("div", { style: { marginBottom: 18 }, children: [_jsx("h3", { className: "muted", style: { fontSize: '0.85rem', textTransform: 'uppercase', letterSpacing: '0.05em' }, children: g.title }), _jsx("div", { className: "card", style: { padding: 0 }, children: g.matches.map((r) => (_jsx(MatchRow, { t: t, r: r, onOpen: open, right: _jsx("span", { className: "tiny muted nowrap", children: r.m.stage === 'pool' || r.m.stage === 'rr' ? '' : r.m.label }) }, r.m.id))) })] }, g.key))), dialog] }));
}
