import { Fragment as _Fragment, jsx as _jsx, jsxs as _jsxs } from "react/jsx-runtime";
import { useEffect, useMemo, useState } from 'react';
import { parseCSV } from '../lib/csv';
import { clampPoolCount } from '../lib/generate';
import { uid } from '../lib/ids';
import { averageRating, DEFAULT_IMPORT_OPTIONS, detectColumns, FIELD_LABELS, FIELD_ORDER, importRegistrations, seedTeams, distinctTeamNames, teamDisplayName, } from '../lib/registrations';
import { sampleRegistrations } from '../lib/sample';
import { describeRules } from '../lib/scoring';
import { formatDuration, projectSchedule } from '../lib/schedule';
import { classifyGoogleUrl, fetchSheetRows } from '../lib/sheets';
import { buildTournament, courtNames, defaultDivisionSettings, estimateDivision, FORMAT_LABELS, } from '../lib/tournament';
import { Segmented } from '../components/ui';
import { BRAND } from '../brand';
import { navigate } from '../state/router';
import { load, save, useStore } from '../state/store';
const LS_DRAFT = 'pbt.draft.v1';
function emptyDraft() {
    return {
        step: 0,
        info: {
            name: BRAND.eventName,
            date: BRAND.date,
            location: '',
            courtCount: 10,
            minutesPerMatch: 20,
            hours: 4,
            doubles: true,
        },
        sourceTab: 'sheet',
        sheetUrl: '',
        pasted: '',
        rows: null,
        mapping: {},
        options: { ...DEFAULT_IMPORT_OPTIONS },
        importKey: null,
        players: {},
        teams: {},
        divisions: [],
        unmatched: [],
        warnings: [],
    };
}
const STEPS = ['Event', 'Registrations', 'Columns', 'Teams', 'Format', 'Create'];
export function Setup() {
    const { t, replace, sync } = useStore();
    const [draft, setDraft] = useState(() => load(LS_DRAFT) ?? emptyDraft());
    useEffect(() => save(LS_DRAFT, draft), [draft]);
    const patch = (p) => setDraft((d) => ({ ...d, ...p }));
    const go = (step) => {
        setDraft((d) => ({ ...d, step }));
        window.scrollTo({ top: 0 });
    };
    const importKey = useMemo(() => (draft.rows ? JSON.stringify([draft.mapping, draft.options, draft.rows.length, draft.rows[1]]) : null), [draft.rows, draft.mapping, draft.options]);
    /** Run the importer (only if inputs changed, so manual team edits survive back/next). */
    const runImport = () => {
        if (!draft.rows)
            return;
        if (draft.importKey === importKey && draft.divisions.length)
            return go(3);
        const res = importRegistrations(draft.rows, draft.mapping, { ...draft.options, doubles: draft.info.doubles });
        // Exactly two divisions. Anything else (an old sheet, a typo) goes to the closest one.
        const fixedName = (name) => (/kid|teen|youth|junior|child|student/i.test(name) ? 'Kids/Teens' : 'Adults');
        const divisions = BRAND.divisions.map((name) => {
            const teamIds = res.divisions.filter((d) => fixedName(d.name) === name).flatMap((d) => d.teamIds);
            return { id: uid('d'), name, teamIds, settings: defaultDivisionSettings(teamIds.length), seeding: 'rating' };
        });
        const moved = res.divisions.filter((d) => !BRAND.divisions.includes(d.name));
        if (moved.length)
            res.warnings.push(`Put “${moved.map((d) => d.name).join('”, “')}” sign-ups into ${[...new Set(moved.map((d) => fixedName(d.name)))].join(' / ')}. Move any team that’s in the wrong division.`);
        const idOf = (name) => divisions.find((d) => d.name === fixedName(name)).id;
        const nameToId = new Map(res.divisions.map((d) => [d.name, idOf(d.name)]));
        const teams = { ...res.teams };
        for (const d of divisions)
            for (const id of d.teamIds)
                teams[id] = { ...teams[id], divisionId: d.id };
        setDraft((prev) => ({
            ...prev,
            importKey,
            players: res.players,
            teams,
            divisions,
            unmatched: res.unmatched.map((u) => ({ playerId: u.playerId, divisionId: nameToId.get(u.division) ?? '' })),
            warnings: res.warnings,
            step: 3,
        }));
        window.scrollTo({ top: 0 });
    };
    const create = () => {
        const info = draft.info;
        const divisions = draft.divisions
            .filter((d) => d.teamIds.length >= 2)
            .map((d) => ({
            id: d.id,
            name: d.name,
            settings: d.settings,
            teamIds: seedTeams(d.teamIds, draft.teams, d.seeding),
        }));
        const tournament = buildTournament({
            name: info.name.trim() || BRAND.eventName,
            date: info.date || undefined,
            location: info.location.trim() || undefined,
            courts: courtNames(Math.max(1, info.courtCount)),
            minutesPerMatch: info.minutesPerMatch,
            doubles: info.doubles,
            hoursAvailable: info.hours ?? 4,
        }, draft.players, distinctTeamNames(draft.teams, draft.players), divisions);
        replace({ ...tournament, published: false });
        save(LS_DRAFT, null);
        navigate('/admin');
    };
    const step = draft.step;
    return (_jsxs(_Fragment, { children: [_jsxs("div", { className: "page-head", children: [_jsxs("div", { children: [_jsx("div", { className: "eyebrow", children: "Organizer tools" }), _jsx("h1", { children: "Build the draw" }), _jsxs("div", { className: "muted small", children: ["Build the ", BRAND.short, " draw from your sign-up form."] })] }), _jsx("button", { className: "btn btn-sm btn-ghost", onClick: () => {
                            if (window.confirm('Clear this setup and start again?'))
                                setDraft(emptyDraft());
                        }, children: "Reset setup" })] }), _jsx("div", { className: "steps", children: STEPS.map((label, i) => (_jsxs("button", { className: i === step ? 'on' : i < step ? 'done' : '', disabled: i > step, onClick: () => i < step && go(i), children: [_jsx("div", { className: "bar" }), _jsxs("span", { className: "lbl", children: [i + 1, ". ", label] })] }, label))) }), step === 0 && _jsx(EventStep, { draft: draft, patch: patch, next: () => go(1) }), step === 1 && _jsx(SourceStep, { draft: draft, patch: patch, back: () => go(0), next: () => go(2), skip: () => skipImport(setDraft) }), step === 2 && _jsx(ColumnsStep, { draft: draft, patch: patch, back: () => go(1), next: runImport }), step === 3 && _jsx(TeamsStep, { draft: draft, setDraft: setDraft, back: () => go(draft.rows ? 2 : 1), next: () => go(4) }), step === 4 && _jsx(FormatStep, { draft: draft, setDraft: setDraft, back: () => go(3), next: () => go(5) }), step === 5 && (_jsx(ReviewStep, { draft: draft, back: () => go(4), create: create, replacing: !!t, synced: !!sync }))] }));
}
function skipImport(setDraft) {
    setDraft((d) => ({
        ...d,
        rows: null,
        importKey: null,
        players: {},
        teams: {},
        unmatched: [],
        warnings: [],
        divisions: d.divisions.length
            ? d.divisions
            : BRAND.divisions.map((name) => ({ id: uid('d'), name, teamIds: [], settings: defaultDivisionSettings(0), seeding: 'registration' })),
        step: 3,
    }));
}
/* ------------------------------------------------------------------ */
function Foot({ back, next, nextLabel = 'Next', disabled, extra }) {
    return (_jsxs("div", { className: "wizard-foot", children: [back ? (_jsx("button", { className: "btn", onClick: back, children: "\u2190 Back" })) : (_jsx("span", {})), _jsxs("div", { className: "row", children: [extra, _jsx("button", { className: "btn btn-primary", disabled: disabled, onClick: next, children: nextLabel })] })] }));
}
function EventStep({ draft, patch, next }) {
    const info = draft.info;
    const set = (p) => patch({ info: { ...info, ...p } });
    return (_jsxs(_Fragment, { children: [_jsxs("div", { className: "card", children: [_jsx("h2", { children: "Event details" }), _jsxs("div", { className: "form-grid", children: [_jsxs("label", { className: "field", children: ["Tournament name", _jsx("input", { className: "input", placeholder: "Fall Classic 2026", value: info.name, onChange: (e) => set({ name: e.target.value }) })] }), _jsxs("label", { className: "field", children: ["Date", _jsx("input", { className: "input", type: "date", value: info.date, onChange: (e) => set({ date: e.target.value }) })] }), _jsxs("label", { className: "field", children: ["Location", _jsx("input", { className: "input", placeholder: "Community Park Courts", value: info.location, onChange: (e) => set({ location: e.target.value }) })] })] }), _jsxs("div", { className: "form-grid", style: { marginTop: 12 }, children: [_jsxs("label", { className: "field", children: ["Number of courts", _jsx("input", { className: "input", type: "number", min: 1, max: 60, value: info.courtCount, onChange: (e) => set({ courtCount: Math.max(1, Math.min(60, Number(e.target.value) || 1)) }) })] }), _jsxs("label", { className: "field", children: ["Hours you have the courts", _jsx("input", { className: "input", type: "number", min: 0.5, max: 24, step: 0.5, value: info.hours ?? 4, onChange: (e) => set({ hours: Math.max(0.5, Number(e.target.value) || 4) }) }), _jsx("span", { className: "hint", children: "We\u2019ll check the draw fits in this time." })] }), _jsxs("label", { className: "field", children: ["Minutes for one game to 11", _jsx("input", { className: "input", type: "number", min: 5, max: 120, value: info.minutesPerMatch, onChange: (e) => set({ minutesPerMatch: Math.max(5, Number(e.target.value) || 20) }) }), _jsx("span", { className: "hint", children: "Including changeover. Rec play is usually 15\u201320." })] }), _jsxs("div", { className: "field", children: ["Event type", _jsx(Segmented, { value: info.doubles ? 'd' : 's', onChange: (v) => set({ doubles: v === 'd' }), options: [
                                            { value: 'd', label: 'Doubles' },
                                            { value: 's', label: 'Singles' },
                                        ] })] })] })] }), _jsx(Foot, { next: next })] }));
}
/* ------------------------------------------------------------------ */
function PreviewTable({ rows }) {
    const head = rows[0] ?? [];
    return (_jsx("div", { className: "table-wrap", children: _jsxs("table", { className: "table preview-table", children: [_jsx("thead", { children: _jsx("tr", { children: head.map((h, i) => (_jsx("th", { title: h, children: h || `Column ${i + 1}` }, i))) }) }), _jsx("tbody", { children: rows.slice(1, 6).map((r, i) => (_jsx("tr", { children: head.map((_, j) => (_jsx("td", { title: r[j], children: r[j] }, j))) }, i))) })] }) }));
}
function SourceStep({ draft, patch, back, next, skip, }) {
    const { sync } = useStore();
    const [loading, setLoading] = useState(false);
    const [error, setError] = useState(null);
    const isScript = classifyGoogleUrl(draft.sheetUrl).kind === 'appsScript';
    const [scriptPass, setScriptPass] = useState(sync?.role === 'admin' ? sync.passcode ?? '' : '');
    // Connected organizers: default to the connected sign-up sheet.
    useEffect(() => {
        if (sync?.role === 'admin' && !draft.sheetUrl)
            patch({ sheetUrl: sync.url });
    }, []);
    const acceptRows = (rows) => {
        if (rows.length < 2) {
            setError('That data has no registration rows (only a header, or nothing at all).');
            return;
        }
        setError(null);
        patch({ rows, mapping: detectColumns(rows[0]), importKey: null });
    };
    const loadSheet = async () => {
        setLoading(true);
        setError(null);
        try {
            acceptRows(await fetchSheetRows(draft.sheetUrl, scriptPass.trim() || undefined));
        }
        catch (e) {
            setError(e.message);
        }
        finally {
            setLoading(false);
        }
    };
    return (_jsxs(_Fragment, { children: [_jsxs("div", { className: "card", children: [_jsx("h2", { children: "Where are the sign-ups?" }), _jsx("div", { style: { marginBottom: 14 }, children: _jsx(Segmented, { value: draft.sourceTab, onChange: (v) => patch({ sourceTab: v }), options: [
                                { value: 'sheet', label: 'Google Sheet link' },
                                { value: 'upload', label: 'Upload CSV' },
                                { value: 'paste', label: 'Paste' },
                                { value: 'sample', label: 'Sample data' },
                            ] }) }), draft.sourceTab === 'sheet' && (_jsxs("div", { className: "stack", children: [_jsxs("label", { className: "field", children: ["Google Sheet (form responses) link", _jsx("input", { className: "input", placeholder: "https://docs.google.com/spreadsheets/d/\u2026", value: draft.sheetUrl, onChange: (e) => patch({ sheetUrl: e.target.value }), onKeyDown: (e) => e.key === 'Enter' && draft.sheetUrl && loadSheet() }), _jsx("span", { className: "hint", children: "Works with: a sheet shared as \u201CAnyone with the link can view\u201D, a \u201CPublish to web \u2192 CSV\u201D link, or your Apps Script web-app URL (see the README for the private option)." })] }), isScript && (_jsxs("label", { className: "field", children: ["Admin passcode (from Code.gs)", _jsx("input", { className: "input", type: "password", value: scriptPass, onChange: (e) => setScriptPass(e.target.value) })] })), _jsxs("div", { className: "row", children: [_jsx("button", { className: "btn btn-primary", disabled: !draft.sheetUrl || loading, onClick: loadSheet, children: loading ? 'Loading…' : 'Load responses' }), sync?.role === 'admin' && sync.passcode && draft.sheetUrl !== sync.url && (_jsx("button", { className: "btn", onClick: () => {
                                            patch({ sheetUrl: sync.url });
                                            setScriptPass(sync.passcode ?? '');
                                        }, children: "Use the connected Google Sheet" }))] }), _jsxs("details", { className: "small muted", children: [_jsx("summary", { children: "How do I get the link?" }), _jsxs("ol", { style: { paddingLeft: 18, marginTop: 6 }, children: [_jsxs("li", { children: ["In Google Forms open ", _jsx("b", { children: "Responses" }), " \u2192 ", _jsx("b", { children: "Link to Sheets" }), " (creates the response spreadsheet)."] }), _jsxs("li", { children: ["In that sheet click ", _jsx("b", { children: "Share" }), " \u2192 General access: ", _jsx("b", { children: "Anyone with the link" }), " \u2192 Viewer \u2192 Copy link."] }), _jsx("li", { children: "Paste it above. New sign-ups show up whenever you load it again." })] }), "Want to keep the sheet private? Use the Apps Script option in the README \u2014 it also enables live scores on everyone\u2019s phone."] })] })), draft.sourceTab === 'upload' && (_jsxs("label", { className: "field", children: ["CSV file (Google Sheets \u2192 File \u2192 Download \u2192 .csv)", _jsx("input", { className: "input", type: "file", accept: ".csv,text/csv", onChange: (e) => {
                                    const file = e.target.files?.[0];
                                    if (!file)
                                        return;
                                    file.text().then((text) => acceptRows(parseCSV(text)));
                                } })] })), draft.sourceTab === 'paste' && (_jsxs("div", { className: "stack", children: [_jsxs("label", { className: "field", children: ["Paste CSV or rows copied from the spreadsheet (include the header row)", _jsx("textarea", { className: "input", value: draft.pasted, placeholder: 'Name,Partner,Skill,Division\nAlex Kim,Jordan Lee,3.5,Intermediate', onChange: (e) => patch({ pasted: e.target.value }) })] }), _jsx("div", { className: "row", children: _jsx("button", { className: "btn btn-primary", disabled: !draft.pasted.trim(), onClick: () => {
                                        const text = draft.pasted.includes('\t') ? draft.pasted.replace(/\t/g, ',') : draft.pasted;
                                        acceptRows(parseCSV(text));
                                    }, children: "Use this data" }) })] })), draft.sourceTab === 'sample' && (_jsxs("div", { className: "stack", children: [_jsxs("p", { className: "muted", style: { margin: 0 }, children: ["Try everything out with ", sampleRegistrations().length - 1, " made-up sign-ups across two divisions, including partners who didn\u2019t register and players looking for a partner."] }), _jsx("div", { children: _jsx("button", { className: "btn btn-primary", onClick: () => acceptRows(sampleRegistrations()), children: "Load sample sign-ups" }) })] })), error && (_jsx("div", { className: "alert alert-error", style: { marginTop: 12 }, children: error }))] }), draft.rows && (_jsxs("div", { className: "card section", children: [_jsxs("div", { className: "card-head", children: [_jsxs("h3", { children: ["Loaded ", draft.rows.length - 1, " response", draft.rows.length === 2 ? '' : 's'] }), _jsxs("span", { className: "muted small", children: [draft.rows[0].length, " columns"] })] }), _jsx(PreviewTable, { rows: draft.rows })] })), _jsx(Foot, { back: back, next: next, disabled: !draft.rows, extra: _jsx("button", { className: "btn btn-ghost", onClick: skip, children: "Skip \u2014 add teams by hand" }) })] }));
}
/* ------------------------------------------------------------------ */
function ColumnsStep({ draft, patch, back, next }) {
    const rows = draft.rows ?? [];
    const headers = rows[0] ?? [];
    const sample = rows[1] ?? [];
    const opts = draft.options;
    const setOpt = (p) => patch({ options: { ...opts, ...p } });
    const setMap = (key, value) => {
        const mapping = { ...draft.mapping };
        if (value === '')
            delete mapping[key];
        else
            mapping[key] = Number(value);
        patch({ mapping });
    };
    const preview = useMemo(() => (rows.length ? importRegistrations(rows, draft.mapping, { ...opts, doubles: draft.info.doubles }) : null), [rows, draft.mapping, opts, draft.info.doubles]);
    const fields = FIELD_ORDER.filter((f) => draft.info.doubles || !f.startsWith('partner'));
    const divisionValues = draft.mapping.division !== undefined
        ? [...new Set(rows.slice(1).map((r) => r[draft.mapping.division]).filter(Boolean))]
        : [];
    const hasCommaDivisions = divisionValues.some((v) => /,/.test(v));
    return (_jsxs(_Fragment, { children: [_jsxs("div", { className: "grid grid-2", children: [_jsxs("div", { className: "card", children: [_jsx("h2", { children: "Match your form questions" }), _jsx("p", { className: "muted small", children: "We guessed from the column headers \u2014 fix anything that looks off." }), _jsx("div", { className: "stack", children: fields.map((key) => (_jsxs("label", { className: "field", children: [FIELD_LABELS[key], _jsxs("select", { className: "input", value: draft.mapping[key] ?? '', onChange: (e) => setMap(key, e.target.value), children: [_jsx("option", { value: "", children: "\u2014 not in the form \u2014" }), headers.map((h, i) => (_jsx("option", { value: i, children: h || `Column ${i + 1}` }, i)))] }), draft.mapping[key] !== undefined && sample[draft.mapping[key]] && (_jsxs("span", { className: "hint", children: ["e.g. \u201C", sample[draft.mapping[key]], "\u201D"] }))] }, key))) })] }), _jsxs("div", { className: "stack", style: { gap: 14 }, children: [_jsxs("div", { className: "card", children: [_jsx("h2", { children: "Options" }), _jsxs("div", { className: "stack", children: [draft.mapping.division === undefined && (_jsxs("label", { className: "field", children: ["Division name (no division question in the form)", _jsx("input", { className: "input", value: opts.defaultDivision, onChange: (e) => setOpt({ defaultDivision: e.target.value }) })] })), draft.mapping.division !== undefined && (_jsxs("label", { className: "check", children: [_jsx("input", { type: "checkbox", checked: opts.splitDivisions, onChange: (e) => setOpt({ splitDivisions: e.target.checked }) }), _jsxs("span", { children: ["Players can enter several divisions (split \u201CA, B\u201D checkbox answers)", hasCommaDivisions && _jsx("span", { className: "badge badge-warn", style: { marginLeft: 6 }, children: "detected" })] })] })), draft.info.doubles && (_jsxs("label", { className: "field", children: ["Players without a partner", _jsxs("select", { className: "input", value: opts.pairing, onChange: (e) => setOpt({ pairing: e.target.value }), children: [_jsx("option", { value: "balanced", children: "Pair for balanced teams (strongest with weakest)" }), _jsx("option", { value: "similar", children: "Pair players of similar skill" }), _jsx("option", { value: "random", children: "Pair randomly" })] })] })), _jsxs("label", { className: "check", children: [_jsx("input", { type: "checkbox", checked: opts.dedupe, onChange: (e) => setOpt({ dedupe: e.target.checked }) }), "Remove duplicate submissions (keeps the latest)"] })] })] }), preview && (_jsxs("div", { className: "card", children: [_jsx("h2", { children: "Preview" }), _jsxs("div", { className: "grid grid-3", style: { gap: 8 }, children: [_jsx(Stat, { label: "Responses", value: preview.rowCount }), _jsx(Stat, { label: draft.info.doubles ? 'Teams' : 'Players', value: Object.keys(preview.teams).length }), _jsx(Stat, { label: "Divisions", value: preview.divisions.length })] }), _jsx("div", { className: "stack small", style: { marginTop: 10, gap: 4 }, children: preview.divisions.map((d) => (_jsxs("div", { className: "row-between", children: [_jsx("span", { className: "truncate", children: d.name }), _jsxs("span", { className: "muted num", children: [d.teamIds.length, " ", draft.info.doubles ? 'teams' : 'players'] })] }, d.name))) }), preview.warnings.length > 0 && (_jsxs("div", { className: "alert alert-warn small", style: { marginTop: 12 }, children: [_jsx("b", { children: "Heads up" }), _jsxs("ul", { children: [preview.warnings.slice(0, 8).map((w, i) => (_jsx("li", { children: w }, i))), preview.warnings.length > 8 && _jsxs("li", { children: ["\u2026and ", preview.warnings.length - 8, " more"] })] })] })), draft.mapping.name === undefined && (_jsx("div", { className: "alert alert-error small", style: { marginTop: 12 }, children: "Choose which column has the player\u2019s name." }))] }))] })] }), _jsx(Foot, { back: back, next: next, nextLabel: "Build teams", disabled: draft.mapping.name === undefined })] }));
}
function Stat({ label, value }) {
    return (_jsxs("div", { style: { background: 'var(--surface-2)', borderRadius: 10, padding: '8px 10px' }, children: [_jsx("div", { className: "tiny muted bold", children: label }), _jsx("div", { style: { fontSize: '1.3rem', fontWeight: 800 }, className: "num", children: value })] }));
}
/* ------------------------------------------------------------------ */
function TeamsStep({ draft, setDraft, back, next, }) {
    const doubles = draft.info.doubles;
    const [selected, setSelected] = useState([]);
    const [newTeam, setNewTeam] = useState({});
    const updateDivision = (id, fn) => setDraft((d) => ({ ...d, divisions: d.divisions.map((x) => (x.id === id ? fn(x) : x)) }));
    const renameTeam = (id, name) => setDraft((d) => ({ ...d, teams: { ...d.teams, [id]: { ...d.teams[id], name } } }));
    const moveTeam = (teamId, from, to) => setDraft((d) => ({
        ...d,
        teams: { ...d.teams, [teamId]: { ...d.teams[teamId], divisionId: to } },
        divisions: d.divisions.map((x) => x.id === from ? { ...x, teamIds: x.teamIds.filter((t) => t !== teamId) } : x.id === to ? { ...x, teamIds: [...x.teamIds, teamId] } : x),
    }));
    const removeTeam = (teamId, divisionId) => setDraft((d) => ({
        ...d,
        divisions: d.divisions.map((x) => (x.id === divisionId ? { ...x, teamIds: x.teamIds.filter((t) => t !== teamId) } : x)),
    }));
    const shift = (divisionId, index, dir) => updateDivision(divisionId, (x) => {
        const ids = x.teamIds.slice();
        const j = index + dir;
        if (j < 0 || j >= ids.length)
            return x;
        [ids[index], ids[j]] = [ids[j], ids[index]];
        return { ...x, teamIds: ids, seeding: 'registration' };
    });
    const addTeam = (divisionId) => {
        const entry = newTeam[divisionId] ?? { p1: '', p2: '' };
        const names = [entry.p1, entry.p2].map((s) => s.trim()).filter(Boolean);
        if (!names.length)
            return;
        setDraft((d) => {
            const players = { ...d.players };
            const members = names.slice(0, doubles ? 2 : 1).map((name) => {
                const p = { id: uid('pl'), name };
                players[p.id] = p;
                return p;
            });
            const team = {
                id: uid('t'),
                name: teamDisplayName(members),
                playerIds: members.map((m) => m.id),
                divisionId,
                rating: averageRating(members),
            };
            return {
                ...d,
                players,
                teams: { ...d.teams, [team.id]: team },
                divisions: d.divisions.map((x) => (x.id === divisionId ? { ...x, teamIds: [...x.teamIds, team.id] } : x)),
            };
        });
        setNewTeam((s) => ({ ...s, [divisionId]: { p1: '', p2: '' } }));
    };
    const pairSelected = () => {
        if (selected.length !== 2)
            return;
        setDraft((d) => {
            const [a, b] = selected.map((id) => d.unmatched.find((u) => u.playerId === id));
            const members = [d.players[a.playerId], d.players[b.playerId]];
            const team = {
                id: uid('t'),
                name: teamDisplayName(members),
                playerIds: members.map((m) => m.id),
                divisionId: a.divisionId,
                rating: averageRating(members),
            };
            return {
                ...d,
                teams: { ...d.teams, [team.id]: team },
                unmatched: d.unmatched.filter((u) => !selected.includes(u.playerId)),
                divisions: d.divisions.map((x) => (x.id === a.divisionId ? { ...x, teamIds: [...x.teamIds, team.id] } : x)),
            };
        });
        setSelected([]);
    };
    return (_jsxs(_Fragment, { children: [draft.warnings.length > 0 && (_jsxs("details", { className: "alert alert-warn small", style: { marginBottom: 14 }, children: [_jsxs("summary", { className: "bold", children: [draft.warnings.length, " import note", draft.warnings.length === 1 ? '' : 's', " \u2014 tap to review"] }), _jsx("ul", { children: draft.warnings.map((w, i) => (_jsx("li", { children: w }, i))) })] })), draft.unmatched.length > 0 && (_jsxs("div", { className: "card", style: { marginBottom: 14 }, children: [_jsxs("div", { className: "card-head", children: [_jsx("h3", { children: "Still need a partner" }), _jsx("button", { className: "btn btn-sm btn-primary", disabled: selected.length !== 2, onClick: pairSelected, children: "Pair selected" })] }), _jsx("div", { className: "stack", style: { gap: 6 }, children: draft.unmatched.map((u) => {
                            const p = draft.players[u.playerId];
                            const div = draft.divisions.find((d) => d.id === u.divisionId);
                            return (_jsxs("label", { className: "check", children: [_jsx("input", { type: "checkbox", checked: selected.includes(u.playerId), onChange: (e) => setSelected((s) => (e.target.checked ? [...s, u.playerId].slice(-2) : s.filter((x) => x !== u.playerId))) }), _jsxs("span", { children: [_jsx("b", { children: p?.name }), " ", _jsxs("span", { className: "muted small", children: ["\u00B7 ", div?.name, " ", p?.skillLabel ? `· ${p.skillLabel}` : ''] })] })] }, u.playerId));
                        }) }), _jsx("p", { className: "tiny muted", style: { margin: '8px 0 0' }, children: "Tick two players to make them a team, or add their partner below with \u201CAdd team\u201D." })] })), _jsx("p", { className: "muted small", style: { marginTop: 0 }, children: "Rename teams, fix partners, move teams between divisions or add walk-ins. Seeding is chosen on the next step (by skill rating unless you reorder here with \u2191\u2193)." }), _jsx("div", { className: "stack", style: { gap: 14 }, children: draft.divisions.map((div) => (_jsxs("div", { className: "card", children: [_jsxs("div", { className: "card-head", children: [_jsx("h3", { style: { margin: 0 }, children: div.name }), _jsxs("span", { className: "muted small nowrap", children: [div.teamIds.length, " ", doubles ? 'teams' : 'players'] })] }), div.teamIds.length === 0 && _jsx("div", { className: "muted small", children: "No teams yet." }), div.teamIds.map((id, i) => {
                            const team = draft.teams[id];
                            if (!team)
                                return null;
                            return (_jsxs("div", { className: "team-row", children: [_jsx("span", { className: "seed-pill", children: i + 1 }), _jsxs("div", { style: { minWidth: 0 }, children: [_jsx("input", { className: "inline-input", value: team.name, onChange: (e) => renameTeam(id, e.target.value) }), _jsxs("div", { className: "tiny muted", style: { paddingLeft: 7 }, children: [team.rating !== undefined ? `Rating ${team.rating.toFixed(2)}` : 'No rating', team.playerIds.length > 1 &&
                                                        ' · ' +
                                                            team.playerIds
                                                                .map((p) => draft.players[p]?.skillLabel)
                                                                .filter(Boolean)
                                                                .join(' / ')] })] }), _jsxs("div", { className: "row", style: { gap: 2, flexWrap: 'nowrap' }, children: [_jsx("button", { className: "btn btn-ghost btn-sm", onClick: () => shift(div.id, i, -1), "aria-label": "Move up", disabled: i === 0, children: "\u2191" }), _jsx("button", { className: "btn btn-ghost btn-sm", onClick: () => shift(div.id, i, 1), "aria-label": "Move down", disabled: i === div.teamIds.length - 1, children: "\u2193" })] }), _jsxs("div", { className: "row", style: { gap: 2, flexWrap: 'nowrap' }, children: [draft.divisions.length > 1 && (_jsxs("select", { className: "input", style: { width: 90, padding: '3px 4px', fontSize: '0.78rem' }, value: "", onChange: (e) => e.target.value && moveTeam(id, div.id, e.target.value), "aria-label": "Move to division", children: [_jsx("option", { value: "", children: "Move\u2026" }), draft.divisions
                                                        .filter((x) => x.id !== div.id)
                                                        .map((x) => (_jsx("option", { value: x.id, children: x.name }, x.id)))] })), _jsx("button", { className: "btn btn-ghost btn-sm btn-danger", onClick: () => removeTeam(id, div.id), "aria-label": "Remove team", children: "\u2715" })] })] }, id));
                        }), _jsxs("div", { className: "row", style: { marginTop: 10 }, children: [_jsx("input", { className: "input", style: { flex: '1 1 140px' }, placeholder: doubles ? 'Player 1' : 'Player name', value: newTeam[div.id]?.p1 ?? '', onChange: (e) => setNewTeam((s) => ({ ...s, [div.id]: { p1: e.target.value, p2: s[div.id]?.p2 ?? '' } })) }), doubles && (_jsx("input", { className: "input", style: { flex: '1 1 140px' }, placeholder: "Player 2", value: newTeam[div.id]?.p2 ?? '', onChange: (e) => setNewTeam((s) => ({ ...s, [div.id]: { p1: s[div.id]?.p1 ?? '', p2: e.target.value } })), onKeyDown: (e) => e.key === 'Enter' && addTeam(div.id) })), _jsxs("button", { className: "btn btn-sm", onClick: () => addTeam(div.id), children: ["+ Add ", doubles ? 'team' : 'player'] }), div.teamIds.length === 0 && draft.divisions.length > 1 && (_jsx("button", { className: "btn btn-sm btn-ghost btn-danger", onClick: () => setDraft((d) => ({ ...d, divisions: d.divisions.filter((x) => x.id !== div.id) })), children: "Delete division" }))] })] }, div.id))) }), _jsx(Foot, { back: back, next: next, nextLabel: "Choose formats", disabled: !draft.divisions.some((d) => d.teamIds.length >= 2) })] }));
}
/* ------------------------------------------------------------------ */
function ScoringEditor({ value, onChange }) {
    return (_jsxs("div", { className: "form-grid", style: { gridTemplateColumns: 'repeat(auto-fit, minmax(110px, 1fr))' }, children: [_jsxs("label", { className: "field", children: ["Games", _jsxs("select", { className: "input", value: value.bestOf, onChange: (e) => onChange({ ...value, bestOf: Number(e.target.value) }), children: [_jsx("option", { value: 1, children: "1 game" }), _jsx("option", { value: 3, children: "Best of 3" }), _jsx("option", { value: 5, children: "Best of 5" })] })] }), _jsxs("label", { className: "field", children: ["Play to", _jsx("select", { className: "input", value: value.pointsToWin, onChange: (e) => onChange({ ...value, pointsToWin: Number(e.target.value) }), children: [7, 9, 11, 15, 21].map((n) => (_jsx("option", { value: n, children: n }, n))) })] }), _jsxs("label", { className: "field", children: ["Win by", _jsxs("select", { className: "input", value: value.winBy, onChange: (e) => onChange({ ...value, winBy: Number(e.target.value) }), children: [_jsx("option", { value: 2, children: "2" }), _jsx("option", { value: 1, children: "1" })] })] }), _jsxs("label", { className: "field", children: ["Cap", _jsxs("select", { className: "input", value: value.cap ?? '', onChange: (e) => onChange({ ...value, cap: e.target.value ? Number(e.target.value) : undefined }), children: [_jsx("option", { value: "", children: "None" }), [13, 15, 17, 21, 25].filter((n) => n > value.pointsToWin).map((n) => (_jsx("option", { value: n, children: n }, n)))] })] })] }));
}
function DivisionFormat({ div, doubles, onChange, }) {
    const s = div.settings;
    const n = div.teamIds.length;
    const set = (p) => onChange((d) => ({ ...d, settings: { ...d.settings, ...p } }));
    const poolCount = clampPoolCount(n, s.poolCount);
    const minPool = Math.floor(n / poolCount);
    const est = estimateDivision(div.teamIds, s);
    const maxPools = Math.max(1, Math.floor(n / 3));
    const differentFinals = !!s.finalsScoring && JSON.stringify(s.finalsScoring) !== JSON.stringify(s.scoring);
    const hasPlayoffs = s.format !== 'round_robin';
    return (_jsxs("div", { className: "card", children: [_jsxs("div", { className: "card-head", children: [_jsx("h3", { children: div.name }), _jsxs("span", { className: "muted small", children: [n, " ", doubles ? 'teams' : 'players'] })] }), _jsxs("div", { className: "form-grid", children: [_jsxs("label", { className: "field", children: ["Format", _jsx("select", { className: "input", value: s.format, onChange: (e) => set({ format: e.target.value }), children: Object.keys(FORMAT_LABELS).map((f) => (_jsx("option", { value: f, disabled: f === 'pools_playoff' && n < 4, children: FORMAT_LABELS[f] }, f))) })] }), _jsxs("label", { className: "field", children: ["Seeding", _jsxs("select", { className: "input", value: div.seeding, onChange: (e) => onChange((d) => ({ ...d, seeding: e.target.value })), children: [_jsx("option", { value: "rating", children: "By skill rating" }), _jsx("option", { value: "random", children: "Random draw" }), _jsx("option", { value: "registration", children: "As listed on the Teams step" })] })] }), (s.format === 'round_robin' || s.format === 'pools_playoff') && (_jsxs("label", { className: "field", children: [s.format === 'round_robin' ? 'Play each team' : 'In pools, play each team', _jsxs("select", { className: "input", value: s.roundRobinCycles, onChange: (e) => set({ roundRobinCycles: Number(e.target.value) }), children: [_jsx("option", { value: 1, children: "Once" }), _jsx("option", { value: 2, children: "Twice" })] })] }))] }), s.format === 'pools_playoff' && (_jsxs("div", { className: "form-grid", style: { marginTop: 12 }, children: [_jsxs("label", { className: "field", children: ["Pools", _jsx("select", { className: "input", value: poolCount, onChange: (e) => set({ poolCount: Number(e.target.value) }), children: Array.from({ length: maxPools }, (_, i) => i + 1).map((p) => (_jsxs("option", { value: p, children: [p, " pool", p > 1 ? 's' : '', " (", Math.floor(n / p), n % p ? `–${Math.ceil(n / p)}` : '', " each)"] }, p))) })] }), _jsxs("label", { className: "field", children: ["Advance from each pool", _jsx("select", { className: "input", value: Math.min(s.advancePerPool, minPool), onChange: (e) => set({ advancePerPool: Number(e.target.value) }), children: Array.from({ length: Math.max(1, minPool) }, (_, i) => i + 1).map((a) => (_jsxs("option", { value: a, children: ["Top ", a, " (", a * poolCount, " in playoffs)"] }, a))) })] }), _jsxs("label", { className: "field", children: ["Playoff bracket", _jsxs("select", { className: "input", value: s.playoffFormat, onChange: (e) => set({ playoffFormat: e.target.value }), children: [_jsx("option", { value: "single_elim", children: "Single elimination" }), _jsx("option", { value: "double_elim", children: "Double elimination" })] })] })] })), hasPlayoffs && (_jsxs("div", { className: "row", style: { marginTop: 12, gap: 18 }, children: [(s.format === 'single_elim' || (s.format === 'pools_playoff' && s.playoffFormat === 'single_elim')) && (_jsxs("label", { className: "check", children: [_jsx("input", { type: "checkbox", checked: s.thirdPlaceMatch, onChange: (e) => set({ thirdPlaceMatch: e.target.checked }) }), "3rd-place match"] })), (s.format === 'double_elim' || (s.format === 'pools_playoff' && s.playoffFormat === 'double_elim')) && (_jsxs("label", { className: "check", title: "If the losers-bracket team wins the grand final, play one more deciding match", children: [_jsx("input", { type: "checkbox", checked: s.grandFinalReset, onChange: (e) => set({ grandFinalReset: e.target.checked }) }), "Grand-final reset (true double elimination)"] }))] })), _jsxs("div", { style: { marginTop: 14 }, children: [_jsxs("div", { className: "small bold muted", style: { marginBottom: 6 }, children: ["Scoring ", hasPlayoffs ? '(pool play & early rounds)' : ''] }), _jsx(ScoringEditor, { value: s.scoring, onChange: (v) => set({ scoring: v, finalsScoring: differentFinals ? s.finalsScoring : v }) }), hasPlayoffs && (_jsxs(_Fragment, { children: [_jsxs("label", { className: "check", style: { marginTop: 10 }, children: [_jsx("input", { type: "checkbox", checked: differentFinals, onChange: (e) => set({
                                            finalsScoring: e.target.checked ? { ...s.scoring, bestOf: Math.max(3, s.scoring.bestOf) } : { ...s.scoring },
                                        }) }), "Different scoring for semifinals & finals"] }), differentFinals && s.finalsScoring && (_jsx("div", { style: { marginTop: 8 }, children: _jsx(ScoringEditor, { value: s.finalsScoring, onChange: (v) => set({ finalsScoring: v }) }) }))] }))] }), _jsxs("div", { className: "alert small", style: { marginTop: 14 }, children: [_jsx("b", { className: "num", children: est.matches }), " matches \u00B7 ", describeRules(s.scoring), differentFinals && s.finalsScoring ? `; finals ${describeRules(s.finalsScoring).toLowerCase()}` : ''] })] }));
}
function FormatStep({ draft, setDraft, back, next, }) {
    const divisions = draft.divisions.filter((d) => d.teamIds.length >= 2);
    const courts = Math.max(1, draft.info.courtCount);
    const hours = draft.info.hours ?? 4;
    const projection = useMemo(() => {
        if (!divisions.length)
            return null;
        const preview = buildTournament({
            name: 'preview',
            courts: courtNames(courts),
            minutesPerMatch: draft.info.minutesPerMatch,
            doubles: draft.info.doubles,
        }, draft.players, draft.teams, divisions.map((d) => ({ name: d.name, teamIds: d.teamIds, settings: d.settings })));
        return projectSchedule(preview);
    }, [divisions, courts, draft.info.minutesPerMatch, draft.info.doubles, draft.players, draft.teams]);
    const budget = hours * 60;
    const over = projection ? projection.minutes - budget : 0;
    return (_jsxs(_Fragment, { children: [projection && (_jsxs("div", { className: `time-budget ${over > 0 ? 'over' : 'fits'}`, children: [_jsxs("div", { className: "tb-main", children: [_jsx("div", { className: "eyebrow", children: over > 0 ? 'Over your time' : 'Fits your time' }), _jsxs("div", { className: "tb-big", children: [formatDuration(projection.minutes), " ", _jsxs("span", { children: ["of ", formatDuration(budget)] })] }), _jsxs("div", { className: "small", children: [projection.matches, " matches on ", courts, " court", courts === 1 ? '' : 's', " at ~", draft.info.minutesPerMatch, " min per game to 11.", ' ', over > 0
                                        ? `About ${formatDuration(over)} too long.`
                                        : `About ${formatDuration(-over)} to spare for warm-ups, delays and awards.`] })] }), _jsx("div", { className: "tb-bar", "aria-hidden": "true", children: _jsx("div", { style: { width: `${Math.min(100, (projection.minutes / Math.max(1, budget)) * 100)}%` } }) }), over > 0 && (_jsxs("ul", { className: "small tb-tips", children: [_jsx("li", { children: "Play pool games to 9 (or add a cap) instead of 11." }), _jsx("li", { children: "Use one game instead of best of 3, at least until the semifinals." }), _jsx("li", { children: "Send fewer teams from each pool to the playoffs, or use single instead of double elimination." }), _jsx("li", { children: "Use bigger pools, or a single round robin for small divisions." })] }))] })), _jsx("div", { className: "stack", style: { gap: 14 }, children: divisions.map((div) => (_jsx(DivisionFormat, { div: div, doubles: draft.info.doubles, onChange: (fn) => setDraft((d) => ({ ...d, divisions: d.divisions.map((x) => (x.id === div.id ? fn(x) : x)) })) }, div.id))) }), _jsx(Foot, { back: back, next: next, nextLabel: "Review" })] }));
}
function ReviewStep({ draft, back, create, replacing, synced, }) {
    const divisions = draft.divisions.filter((d) => d.teamIds.length >= 2);
    const skipped = draft.divisions.filter((d) => d.teamIds.length < 2);
    return (_jsxs(_Fragment, { children: [_jsxs("div", { className: "card", children: [_jsx("h2", { children: draft.info.name || BRAND.eventName }), _jsx("div", { className: "muted", style: { marginBottom: 12 }, children: [draft.info.date, draft.info.location, `${draft.info.courtCount} courts`, `${draft.info.hours ?? 4} hours`]
                            .filter(Boolean)
                            .join(' · ') }), _jsx("div", { className: "table-wrap", children: _jsxs("table", { className: "table", children: [_jsx("thead", { children: _jsxs("tr", { children: [_jsx("th", { children: "Division" }), _jsx("th", { className: "num", children: draft.info.doubles ? 'Teams' : 'Players' }), _jsx("th", { children: "Format" }), _jsx("th", { children: "Scoring" }), _jsx("th", { className: "num", children: "Matches" })] }) }), _jsx("tbody", { children: divisions.map((d) => (_jsxs("tr", { children: [_jsx("td", { className: "bold", children: d.name }), _jsx("td", { className: "num", children: d.teamIds.length }), _jsxs("td", { children: [FORMAT_LABELS[d.settings.format], d.settings.format === 'pools_playoff' &&
                                                        ` (${clampPoolCount(d.teamIds.length, d.settings.poolCount)} pools, top ${d.settings.advancePerPool})`] }), _jsx("td", { className: "small", children: describeRules(d.settings.scoring) }), _jsx("td", { className: "num", children: estimateDivision(d.teamIds, d.settings).matches })] }, d.id))) })] }) }), skipped.length > 0 && (_jsxs("div", { className: "alert alert-warn small", style: { marginTop: 12 }, children: ["Skipping ", skipped.map((d) => d.name).join(', '), " \u2014 a division needs at least 2 ", draft.info.doubles ? 'teams' : 'players', "."] })), draft.unmatched.length > 0 && (_jsxs("div", { className: "alert alert-warn small", style: { marginTop: 12 }, children: [draft.unmatched.length, " player", draft.unmatched.length === 1 ? ' is' : 's are', " still without a partner and won\u2019t be in the draw."] })), _jsxs("div", { className: "alert alert-ok small", style: { marginTop: 12 }, children: ["This creates a ", _jsx("b", { children: "draft" }), ". Players can\u2019t see it yet: check the courts, matchups and teams, change anything you like, then press ", _jsx("b", { children: "Publish to players" }), " when you\u2019re ready."] }), replacing && (_jsxs("div", { className: "alert alert-warn small", style: { marginTop: 12 }, children: ["This replaces the current tournament", synced ? ' for everyone connected to the Google Sheet' : ' on this device', ". Export it from Settings first if you want a copy."] }))] }), _jsx(Foot, { back: back, next: create, nextLabel: "Create draft", disabled: !divisions.length })] }));
}
