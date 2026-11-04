import { Fragment as _Fragment, jsx as _jsx, jsxs as _jsxs } from "react/jsx-runtime";
import { useEffect, useState } from 'react';
import QRCode from 'qrcode';
import { toCSV } from '../lib/csv';
import { download, matchesTable, placementsTable, slug, standingsTable, teamsTable } from '../lib/exporters';
import { addLateTeam, canAddLateTeam, regenerateDivision } from '../lib/generate';
import { uid } from '../lib/ids';
import { autoTeamNames, averageRating, distinctTeamNames, teamDisplayName } from '../lib/registrations';
import { remote } from '../lib/sync';
import { FORMAT_LABELS } from '../lib/tournament';
import { timeAgo } from '../components/ui';
import { navigate } from '../state/router';
import { useStore } from '../state/store';
export function Settings() {
    const { t, isAdmin } = useStore();
    return (_jsxs(_Fragment, { children: [_jsx("div", { className: "page-head", children: _jsx("h1", { children: "Settings" }) }), _jsxs("div", { className: "stack", style: { gap: 14 }, children: [t && _jsx(ShareCard, {}), t && isAdmin && _jsx(EventCard, {}), t && isAdmin && _jsx(DivisionsCard, {}), t && isAdmin && _jsx(PlayersCard, {}), _jsx(DataCard, {})] })] }));
}
/* ------------------------------------------------------------------ */
export function SyncCard() {
    const { sync, syncState, connect, t, refresh } = useStore();
    const [url, setUrl] = useState(sync?.url ?? '');
    const [passcode, setPasscode] = useState(sync?.passcode ?? '');
    const [busy, setBusy] = useState(false);
    const [message, setMessage] = useState(null);
    const doConnect = async (publishLocal = false) => {
        setBusy(true);
        setMessage(null);
        try {
            const text = await connect({ url: url.trim(), passcode: passcode.trim() || undefined, role: 'viewer' }, { publishLocal });
            setMessage({ ok: true, text });
        }
        catch (e) {
            setMessage({ ok: false, text: e.message });
        }
        finally {
            setBusy(false);
        }
    };
    return (_jsxs("div", { className: "card", children: [_jsxs("div", { className: "card-head", children: [_jsx("h2", { children: "Live sync with Google Sheets" }), sync && (_jsxs("span", { className: `badge ${syncState.status === 'synced' ? 'badge-final' : syncState.status === 'error' || syncState.status === 'offline' ? 'badge-warn' : ''}`, children: [syncState.status, " ", syncState.lastSync ? `· ${timeAgo(syncState.lastSync)}` : ''] }))] }), _jsxs("p", { className: "muted small", children: ["Optional. Connect the Apps Script that lives in your form\u2019s Google Sheet and every phone and laptop sees the same live scores. Without it, the tournament is saved on this device only. Setup takes about 3 minutes \u2014 see", ' ', _jsx("b", { children: "apps-script/Code.gs" }), " and the README."] }), sync && (_jsxs("div", { className: "alert alert-ok small", style: { marginBottom: 12 }, children: ["Connected as ", _jsx("b", { children: sync.role }), sync.role === 'viewer' && ' (read-only — enter the passcode to keep score)', ".", syncState.message && _jsx("div", { children: syncState.message })] })), _jsxs("div", { className: "form-grid", children: [_jsxs("label", { className: "field", children: ["Apps Script web-app URL", _jsx("input", { className: "input", placeholder: "https://script.google.com/macros/s/\u2026/exec", value: url, onChange: (e) => setUrl(e.target.value) })] }), _jsxs("label", { className: "field", children: ["Passcode (admin or scorer)", _jsx("input", { className: "input", type: "password", placeholder: "Leave blank to just watch", value: passcode, onChange: (e) => setPasscode(e.target.value) })] })] }), _jsxs("div", { className: "row", style: { marginTop: 12 }, children: [_jsx("button", { className: "btn btn-primary", disabled: !url.trim() || busy, onClick: () => doConnect(false), children: busy ? 'Connecting…' : sync ? 'Reconnect' : 'Connect' }), t && !!passcode && (_jsx("button", { className: "btn", disabled: !url.trim() || busy, onClick: () => {
                            if (window.confirm('Upload this device’s tournament to the sheet, replacing whatever is there?'))
                                void doConnect(true);
                        }, children: "Connect & publish this device\u2019s tournament" })), sync && (_jsxs(_Fragment, { children: [_jsx("button", { className: "btn btn-ghost", onClick: () => void refresh(), children: "Refresh now" }), _jsx("button", { className: "btn btn-ghost btn-danger", onClick: async () => setMessage({ ok: true, text: await connect(null) }), children: "Disconnect" })] }))] }), message && (_jsx("div", { className: `alert ${message.ok ? 'alert-ok' : 'alert-error'} small`, style: { marginTop: 12 }, children: message.text }))] }));
}
/* ------------------------------------------------------------------ */
function ShareCard() {
    const { sync } = useStore();
    const base = `${window.location.origin}${window.location.pathname}`;
    const link = sync ? `${base}?live=${encodeURIComponent(sync.url)}#/` : '';
    const [qr, setQr] = useState('');
    const [copied, setCopied] = useState(false);
    useEffect(() => {
        if (!link)
            return;
        QRCode.toDataURL(link, { margin: 1, width: 360 }).then(setQr).catch(() => setQr(''));
    }, [link]);
    return (_jsxs("div", { className: "card", children: [_jsx("h2", { children: "Share with players" }), !sync ? (_jsx("p", { className: "muted small", style: { margin: 0 }, children: "Connect the Google Sheet above to get a link and QR code players can open on their phones." })) : (_jsxs("div", { className: "row", style: { alignItems: 'flex-start', gap: 16 }, children: [qr && _jsx("img", { className: "qr", src: qr, alt: "QR code for the live tournament page" }), _jsxs("div", { className: "stack", style: { flex: '1 1 240px', minWidth: 0 }, children: [_jsx("div", { className: "small muted", children: "Read-only live page \u2014 print the QR code or text the link:" }), _jsx("input", { className: "input", readOnly: true, value: link, onFocus: (e) => e.target.select() }), _jsx("div", { className: "row", children: _jsx("button", { className: "btn btn-sm", onClick: () => {
                                        void navigator.clipboard?.writeText(link);
                                        setCopied(true);
                                        setTimeout(() => setCopied(false), 1500);
                                    }, children: copied ? 'Copied!' : 'Copy link' }) }), _jsx("div", { className: "tiny muted", children: "Court volunteers: open the same link, then enter the scorer passcode under Settings to keep score." })] })] }))] }));
}
/* ------------------------------------------------------------------ */
export function EventCard() {
    const { t, update } = useStore();
    if (!t)
        return null;
    const set = (p) => update((tt) => ({ ...tt, ...p, updatedAt: Date.now() }));
    const setCourts = (courts) => set({ courts });
    return (_jsxs("div", { className: "card", children: [_jsx("h2", { children: "Courts & time" }), _jsxs("div", { className: "form-grid", children: [_jsxs("label", { className: "field", children: ["Date", _jsx("input", { className: "input", type: "date", defaultValue: t.date, onBlur: (e) => set({ date: e.target.value || undefined }) })] }), _jsxs("label", { className: "field", children: ["Minutes for one game to 11", _jsx("input", { className: "input", type: "number", min: 5, defaultValue: t.settings.minutesPerMatch, onBlur: (e) => set({ settings: { ...t.settings, minutesPerMatch: Math.max(5, Number(e.target.value) || 20) } }) })] }), _jsxs("label", { className: "field", children: ["Hours you have the courts", _jsx("input", { className: "input", type: "number", min: 0.5, step: 0.5, defaultValue: t.settings.hoursAvailable ?? '', placeholder: "e.g. 4", onBlur: (e) => set({ settings: { ...t.settings, hoursAvailable: Number(e.target.value) > 0 ? Number(e.target.value) : undefined } }) })] })] }), _jsxs("label", { className: "field", style: { maxWidth: 220, marginBottom: 10 }, children: ["Number of courts", _jsx("input", { className: "input", type: "number", min: 1, max: 60, defaultValue: t.courts.length, onBlur: (e) => {
                            const want = Math.max(1, Math.min(60, Math.round(Number(e.target.value) || t.courts.length)));
                            if (want === t.courts.length)
                                return;
                            if (want < t.courts.length) {
                                const busy = new Set(Object.values(t.matches).filter((m) => m.status === 'live' && m.court).map((m) => m.court));
                                const keep = t.courts.slice(0, want);
                                const dropped = t.courts.slice(want);
                                if (dropped.some((c) => busy.has(c)) && !window.confirm('A match is in progress on a court you’re removing. Remove it anyway?'))
                                    return;
                                setCourts(keep);
                                return;
                            }
                            const courts = [...t.courts];
                            let n = courts.length + 1;
                            while (courts.length < want) {
                                while (courts.includes(`Court ${n}`))
                                    n++;
                                courts.push(`Court ${n}`);
                            }
                            setCourts(courts);
                        } }, t.courts.length), _jsx("span", { className: "hint", children: "Or add, rename and remove courts one by one below." })] }), _jsxs("div", { className: "row", children: [t.courts.map((c, i) => (_jsxs("div", { className: "row", style: { gap: 2, background: 'var(--surface-2)', borderRadius: 10, padding: '2px 4px 2px 2px' }, children: [_jsx("input", { className: "inline-input", style: { width: 110 }, defaultValue: c, onBlur: (e) => {
                                    const name = e.target.value.trim();
                                    if (!name || name === c || t.courts.includes(name))
                                        return;
                                    update((tt) => ({
                                        ...tt,
                                        courts: tt.courts.map((x) => (x === c ? name : x)),
                                        matches: Object.fromEntries(Object.entries(tt.matches).map(([id, m]) => [id, m.court === c ? { ...m, court: name, updatedAt: Date.now() } : m])),
                                        updatedAt: Date.now(),
                                    }));
                                } }), _jsx("button", { className: "btn btn-ghost btn-sm", "aria-label": `Remove ${c}`, disabled: t.courts.length <= 1, onClick: () => setCourts(t.courts.filter((x) => x !== c)), children: "\u2715" })] }, `${c}-${i}`))), _jsx("button", { className: "btn btn-sm", onClick: () => {
                            let n = t.courts.length + 1;
                            while (t.courts.includes(`Court ${n}`))
                                n++;
                            setCourts([...t.courts, `Court ${n}`]);
                        }, children: "+ Add court" })] })] }));
}
/* ------------------------------------------------------------------ */
export function DivisionsCard() {
    const { t, resolved, update } = useStore();
    const [adding, setAdding] = useState({});
    if (!t || !resolved)
        return null;
    const addTeam = (divisionId) => {
        const entry = adding[divisionId];
        const names = [entry?.p1, entry?.p2].map((s) => s?.trim()).filter((s) => !!s).slice(0, t.settings.doubles ? 2 : 1);
        if (!names.length)
            return;
        update((tt) => {
            const players = { ...tt.players };
            const members = names.map((name) => {
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
            const next = {
                ...tt,
                players,
                teams: distinctTeamNames({ ...tt.teams, [team.id]: team }, players),
                divisions: tt.divisions.map((d) => (d.id === divisionId ? { ...d, teamIds: [...d.teamIds, team.id] } : d)),
                updatedAt: Date.now(),
            };
            // Round robin and pool play: slot the team in without touching any scores.
            return canAddLateTeam(next, divisionId) ? addLateTeam(next, team.id) : next;
        });
        setAdding((s) => ({ ...s, [divisionId]: { p1: '', p2: '' } }));
    };
    return (_jsxs("div", { className: "card", children: [_jsx("h2", { children: "Divisions & schedule" }), _jsx("p", { className: "muted small", children: "Late sign-up? Add the team here. In round robin and pool play it\u2019s slotted straight into the schedule (into the smallest pool) and every score is kept. For brackets, or after removing a team, rebuild that division\u2019s schedule; rebuilding clears that division\u2019s scores, so do it before play starts there." }), _jsx("div", { className: "stack", style: { gap: 16 }, children: t.divisions.map((d) => {
                    const rd = resolved.divisions[d.id];
                    const played = rd.matches.filter((r) => r.m.status !== 'pending').length;
                    const scheduled = new Set(rd.matches.flatMap((r) => [r.m.a, r.m.b]).flatMap((s) => (s.kind === 'team' ? [s.teamId] : [])));
                    const outOfDate = d.settings.format !== 'pools_playoff'
                        ? d.teamIds.some((id) => !scheduled.has(id)) || [...scheduled].some((id) => !d.teamIds.includes(id))
                        : d.teamIds.length !== d.pools.reduce((n, p) => n + p.teamIds.length, 0);
                    return (_jsxs("div", { style: { borderTop: '1px solid var(--line)', paddingTop: 12 }, children: [_jsxs("div", { className: "row-between", style: { flexWrap: 'wrap' }, children: [_jsx("h3", { style: { margin: 0 }, children: d.name }), _jsxs("span", { className: "small muted", children: [d.teamIds.length, " ", t.settings.doubles ? 'teams' : 'players', " \u00B7 ", played, " matches started"] })] }), _jsxs("div", { className: "form-grid", style: { marginTop: 8 }, children: [_jsxs("label", { className: "field", children: ["Format", _jsx("select", { className: "input", value: d.settings.format, onChange: (e) => update((tt) => ({
                                                    ...tt,
                                                    divisions: tt.divisions.map((x) => x.id === d.id ? { ...x, settings: { ...x.settings, format: e.target.value } } : x),
                                                    updatedAt: Date.now(),
                                                })), children: Object.keys(FORMAT_LABELS).map((f) => (_jsx("option", { value: f, children: FORMAT_LABELS[f] }, f))) })] }), _jsxs("label", { className: "field", children: ["Remove a ", t.settings.doubles ? 'team' : 'player', _jsxs("select", { className: "input", value: "", onChange: (e) => {
                                                    const id = e.target.value;
                                                    if (!id || !window.confirm(`Remove ${t.teams[id]?.name} from ${d.name}?`))
                                                        return;
                                                    update((tt) => ({
                                                        ...tt,
                                                        divisions: tt.divisions.map((x) => (x.id === d.id ? { ...x, teamIds: x.teamIds.filter((y) => y !== id) } : x)),
                                                        updatedAt: Date.now(),
                                                    }));
                                                }, children: [_jsx("option", { value: "", children: "Choose\u2026" }), d.teamIds.map((id) => (_jsx("option", { value: id, children: t.teams[id]?.name }, id)))] })] })] }), _jsxs("div", { className: "row", style: { marginTop: 8 }, children: [_jsx("input", { className: "input", style: { flex: '1 1 130px' }, placeholder: t.settings.doubles ? 'Player 1' : 'Player name', value: adding[d.id]?.p1 ?? '', onChange: (e) => setAdding((s) => ({ ...s, [d.id]: { p1: e.target.value, p2: s[d.id]?.p2 ?? '' } })) }), t.settings.doubles && (_jsx("input", { className: "input", style: { flex: '1 1 130px' }, placeholder: "Player 2", value: adding[d.id]?.p2 ?? '', onChange: (e) => setAdding((s) => ({ ...s, [d.id]: { p1: s[d.id]?.p1 ?? '', p2: e.target.value } })) })), _jsx("button", { className: "btn btn-sm", onClick: () => addTeam(d.id), children: "+ Add" })] }), _jsxs("div", { className: "row", style: { marginTop: 8 }, children: [outOfDate && _jsx("span", { className: "badge badge-warn", children: "Teams changed \u2014 rebuild to update the schedule" }), _jsx("button", { className: `btn btn-sm ${outOfDate ? 'btn-primary' : ''}`, onClick: () => {
                                            if (played && !window.confirm(`Rebuild ${d.name}? This clears ${played} started/finished match(es) in this division.`))
                                                return;
                                            update((tt) => regenerateDivision(tt, d.id));
                                        }, children: "Rebuild schedule" })] })] }, d.id));
                }) }), _jsx("div", { className: "row", style: { marginTop: 14 }, children: _jsx("a", { className: "btn btn-sm", href: "#/setup", children: "Start a new tournament from the sign-ups\u2026" }) })] }));
}
/* ------------------------------------------------------------------ */
function DataCard() {
    const { t, resolved, isAdmin, replace, sync } = useStore();
    const [msg, setMsg] = useState(null);
    const name = slug(t?.name ?? 'tournament');
    const exportTables = async () => {
        if (!t || !resolved || !sync?.passcode)
            return;
        setMsg('Writing to Google Sheet…');
        try {
            await remote.writeTables(sync.url, sync.passcode, {
                Matches: matchesTable(t, resolved),
                Standings: standingsTable(t, resolved),
                Results: placementsTable(t, resolved),
                Teams: teamsTable(t),
            });
            setMsg('Done — look for the “TM Matches”, “TM Standings”, “TM Results” and “TM Teams” tabs in your sheet.');
        }
        catch (e) {
            setMsg(`Couldn't write to the sheet: ${e.message}`);
        }
    };
    return (_jsxs("div", { className: "card", children: [_jsx("h2", { children: "Data" }), t && resolved && (_jsxs(_Fragment, { children: [_jsx("div", { className: "small bold muted", style: { marginBottom: 6 }, children: "Download" }), _jsxs("div", { className: "row", children: [_jsx("button", { className: "btn btn-sm", onClick: () => download(`${name}-matches.csv`, toCSV(matchesTable(t, resolved)), 'text/csv'), children: "Matches CSV" }), _jsx("button", { className: "btn btn-sm", onClick: () => download(`${name}-standings.csv`, toCSV(standingsTable(t, resolved)), 'text/csv'), children: "Standings CSV" }), _jsx("button", { className: "btn btn-sm", onClick: () => download(`${name}-results.csv`, toCSV(placementsTable(t, resolved)), 'text/csv'), children: "Final results CSV" }), _jsx("button", { className: "btn btn-sm", onClick: () => download(`${name}-teams.csv`, toCSV(teamsTable(t)), 'text/csv'), children: "Teams CSV" }), _jsx("button", { className: "btn btn-sm", onClick: () => download(`${name}-backup.json`, JSON.stringify(t, null, 1), 'application/json'), children: "Full backup (.json)" })] }), sync?.role === 'admin' && (_jsx("div", { className: "row", style: { marginTop: 10 }, children: _jsx("button", { className: "btn btn-sm btn-primary", onClick: exportTables, children: "Write results into the Google Sheet" }) }))] })), isAdmin && (_jsxs(_Fragment, { children: [_jsx("div", { className: "small bold muted", style: { margin: '14px 0 6px' }, children: "Restore" }), _jsxs("label", { className: "field", children: ["Load a backup (.json)", _jsx("input", { className: "input", type: "file", accept: "application/json,.json", onChange: async (e) => {
                                    const file = e.target.files?.[0];
                                    if (!file)
                                        return;
                                    try {
                                        const data = JSON.parse(await file.text());
                                        if (!data.matches || !data.divisions || !data.teams)
                                            throw new Error('Not a tournament backup');
                                        if (t && !window.confirm('Replace the current tournament with this backup?'))
                                            return;
                                        replace({ ...data, id: data.id ?? uid('tour'), published: false });
                                        setMsg('Backup loaded as a draft. Press “Publish to players” when you’re ready.');
                                        navigate('/');
                                    }
                                    catch (err) {
                                        setMsg(`Couldn't load that file: ${err.message}`);
                                    }
                                } })] })] })), t && isAdmin && (_jsx("div", { className: "row", style: { marginTop: 14 }, children: _jsx("button", { className: "btn btn-sm btn-danger", onClick: () => {
                        if (!window.confirm(`Delete “${t.name}”${sync ? ' for everyone connected' : ''}? Download a backup first if you might need it.`))
                            return;
                        replace(null);
                        navigate('/');
                    }, children: "Delete tournament" }) })), msg && (_jsx("div", { className: "alert small", style: { marginTop: 12 }, children: msg }))] }));
}
/* ------------------------------------------------------------------ */
/** Fix any player's name (or swap in a new partner); team names follow automatically. */
export function PlayersCard() {
    const { t, update } = useStore();
    const [q, setQ] = useState('');
    if (!t)
        return null;
    const needle = q.trim().toLowerCase();
    const teams = Object.values(t.teams).filter((team) => !needle ||
        team.name.toLowerCase().includes(needle) ||
        team.playerIds.some((id) => t.players[id]?.name.toLowerCase().includes(needle)));
    const renamePlayer = (teamId, playerId, name) => update((tt) => {
        const team = tt.teams[teamId];
        if (!team || !tt.players[playerId])
            return tt;
        const players = { ...tt.players, [playerId]: { ...tt.players[playerId], name } };
        const oldName = tt.players[playerId].name;
        const autoName = autoTeamNames(team.playerIds.map((id) => tt.players[id]).filter(Boolean)).includes(team.name);
        const members = team.playerIds.map((id) => players[id]).filter(Boolean);
        const teamName = autoName ? teamDisplayName(members) : team.name.includes(oldName) ? team.name.replace(oldName, name) : team.name;
        return {
            ...tt,
            players,
            teams: distinctTeamNames({ ...tt.teams, [teamId]: { ...team, name: teamName } }, players),
            updatedAt: Date.now(),
        };
    });
    const renameTeam = (teamId, name) => update((tt) => ({ ...tt, teams: { ...tt.teams, [teamId]: { ...tt.teams[teamId], name } }, updatedAt: Date.now() }));
    const addPartner = (teamId, name) => update((tt) => {
        const team = tt.teams[teamId];
        if (!team)
            return tt;
        const p = { id: uid('pl'), name };
        const players = { ...tt.players, [p.id]: p };
        const members = [...team.playerIds, p.id].map((id) => players[id]).filter(Boolean);
        return {
            ...tt,
            players,
            teams: distinctTeamNames({ ...tt.teams, [teamId]: { ...team, playerIds: [...team.playerIds, p.id], name: teamDisplayName(members) } }, players),
            updatedAt: Date.now(),
        };
    });
    return (_jsxs("div", { className: "card", children: [_jsx("h2", { children: "Teams & players" }), _jsx("p", { className: "muted small", children: "Fix a misspelled name or swap in a new partner by typing over their name. Scores and the schedule stay the same." }), _jsx("input", { className: "input", placeholder: "Search names\u2026", value: q, onChange: (e) => setQ(e.target.value), style: { marginBottom: 10 } }), _jsxs("div", { className: "stack", style: { gap: 8, maxHeight: 520, overflowY: 'auto' }, children: [teams.map((team) => (_jsxs("div", { className: "row", style: { gap: 6, borderTop: '1px solid var(--line)', paddingTop: 8 }, children: [_jsx("input", { className: "inline-input bold", style: { flex: '1 1 180px' }, defaultValue: team.name, "aria-label": "Team name", onBlur: (e) => {
                                    const name = e.target.value.trim();
                                    if (name && name !== team.name)
                                        renameTeam(team.id, name);
                                } }, `${team.id}-${team.name}`), team.playerIds.map((pid, i) => (_jsx("input", { className: "input", style: { flex: '1 1 140px' }, defaultValue: t.players[pid]?.name, "aria-label": `Player ${i + 1}`, onBlur: (e) => {
                                    const name = e.target.value.trim();
                                    if (name && name !== t.players[pid]?.name)
                                        renamePlayer(team.id, pid, name);
                                } }, `${pid}-${t.players[pid]?.name}`))), t.settings.doubles && team.playerIds.length < 2 && (_jsx("input", { className: "input", style: { flex: '1 1 140px' }, placeholder: "Add partner", onKeyDown: (e) => e.key === 'Enter' && e.target.blur(), onBlur: (e) => {
                                    const name = e.target.value.trim();
                                    if (name) {
                                        addPartner(team.id, name);
                                        e.target.value = '';
                                    }
                                } }))] }, team.id))), !teams.length && _jsx("div", { className: "muted small", children: "No matches." })] })] }));
}
