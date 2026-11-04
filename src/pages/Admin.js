import { Fragment as _Fragment, jsx as _jsx, jsxs as _jsxs } from "react/jsx-runtime";
import { useEffect, useState } from 'react';
import { Check, ClipboardList, Copy, Download, ExternalLink, LayoutGrid, LogOut, Settings as SettingsIcon, Wand2 } from 'lucide-react';
import setupScript from '../../apps-script/Code.gs?raw';
import { BRAND } from '../brand';
import { download } from '../lib/exporters';
import { Mandala, Toran } from '../components/ui';
import { quickDraw } from '../lib/quickDraw';
import { remote } from '../lib/sync';
import { FundraiserCard, raisedTotal } from '../components/Fundraiser';
import { SignupTable } from '../components/SignupManager';
import { DivisionsCard, EventCard, PlayersCard } from './Settings';
import { useStore } from '../state/store';
import { useEventInfo } from '../state/useEventInfo';
function useCopy() {
    const [copied, setCopied] = useState(null);
    const copy = async (key, text) => {
        try {
            await navigator.clipboard.writeText(text);
            setCopied(key);
            setTimeout(() => setCopied((c) => (c === key ? null : c)), 1800);
        }
        catch {
            setCopied(null);
        }
    };
    return { copied, copy };
}
function siteBase() {
    return `${window.location.origin}${window.location.pathname}`;
}
function AdminHero({ title, children }) {
    return (_jsxs("section", { className: "hero-banner", style: { marginBottom: 16 }, children: [_jsx(Toran, {}), _jsx(Mandala, {}), _jsxs("div", { className: "eyebrow", children: [BRAND.eventName, " \u00B7 Organizers"] }), _jsx("h1", { children: title }), children && _jsx("div", { style: { color: 'var(--on-night-muted)', maxWidth: 620 }, children: children })] }));
}
function Step({ n, title, children }) {
    return (_jsxs("div", { className: "card admin-step", children: [_jsx("span", { className: "step-num", children: n }), _jsxs("div", { style: { minWidth: 0 }, children: [_jsx("h3", { children: title }), children] })] }));
}
function LinkRow({ label, url, hint }) {
    const { copied, copy } = useCopy();
    return (_jsxs("div", { className: "link-row", children: [_jsx("div", { className: "small bold", children: label }), hint && _jsx("div", { className: "tiny muted", children: hint }), _jsxs("div", { className: "row", style: { flexWrap: 'nowrap', marginTop: 6 }, children: [_jsx("input", { className: "input", readOnly: true, value: url, onFocus: (e) => e.target.select() }), _jsx("button", { className: "btn btn-sm", onClick: () => copy(label, url), "aria-label": `Copy ${label}`, children: copied === label ? _jsx(Check, { size: 15 }) : _jsx(Copy, { size: 15 }) }), _jsx("a", { className: "btn btn-sm", href: url, target: "_blank", rel: "noreferrer", "aria-label": `Open ${label}`, children: _jsx(ExternalLink, { size: 15 }) })] })] }));
}
/** Step-by-step: create the sign-up form + backend, then connect this site. */
function SetupGuide() {
    const { connect } = useStore();
    const { copied, copy } = useCopy();
    const [url, setUrl] = useState('');
    const [passcode, setPasscode] = useState('');
    const [busy, setBusy] = useState(false);
    const [error, setError] = useState(null);
    const submit = async () => {
        setBusy(true);
        setError(null);
        try {
            const clean = url.trim().replace(/\/dev$/, '/exec');
            await connect({ url: clean, passcode: passcode.trim(), role: 'viewer' });
        }
        catch (e) {
            const msg = e.message;
            setError(/^wrong passcode/i.test(msg) ? 'The web app answered, but that passcode isn’t right.' : `Couldn't connect: ${msg}`);
        }
        finally {
            setBusy(false);
        }
    };
    return (_jsxs(_Fragment, { children: [_jsx(AdminHero, { title: "Organizer setup", children: "Open registration on the site and turn on live scores. Takes about 3 minutes in your Google account, no coding. Sign-ups land in a Google Sheet that only you can see." }), _jsxs("div", { className: "stack", style: { gap: 12 }, children: [_jsxs(Step, { n: 1, title: "Copy the setup script", children: [_jsx("p", { className: "muted small", children: "It creates the Google Sheet that collects sign-ups from the site\u2019s Register tab, plus your passcodes." }), _jsxs("div", { className: "row", children: [_jsxs("button", { className: "btn btn-primary", onClick: () => copy('script', setupScript), children: [copied === 'script' ? _jsx(Check, { size: 16 }) : _jsx(Copy, { size: 16 }), " ", copied === 'script' ? 'Copied!' : 'Copy script'] }), _jsxs("button", { className: "btn", onClick: () => download('Code.gs', setupScript), children: [_jsx(Download, { size: 16 }), " Download"] }), _jsxs("a", { className: "btn btn-dark", href: "https://script.new", target: "_blank", rel: "noreferrer", children: ["Open script.new ", _jsx(ExternalLink, { size: 14 })] })] })] }), _jsx(Step, { n: 2, title: "Paste it and run \u201Csetup\u201D", children: _jsxs("ol", { className: "small steps-list", children: [_jsxs("li", { children: ["In the tab that opened (sign in with the account that should own the sheet, e.g. the SACS exec account), select everything in the editor and paste. Press ", _jsx("b", { children: "Save" }), "."] }), _jsxs("li", { children: ["In the toolbar, pick ", _jsx("b", { children: "setup" }), " from the function menu and press ", _jsx("b", { children: "Run" }), ". Allow access when Google asks."] }), _jsxs("li", { children: ["The ", _jsx("b", { children: "Execution log" }), " shows the sign-ups sheet and your ", _jsx("b", { children: "admin" }), " and ", _jsx("b", { children: "scorer" }), " passcodes."] })] }) }), _jsx(Step, { n: 3, title: "Deploy it as a web app", children: _jsxs("ol", { className: "small steps-list", children: [_jsxs("li", { children: [_jsx("b", { children: "Deploy \u2192 New deployment" }), ", then the gear icon \u2192 ", _jsx("b", { children: "Web app" }), "."] }), _jsxs("li", { children: ["Execute as: ", _jsx("b", { children: "Me" }), ". Who has access: ", _jsx("b", { children: "Anyone" }), ". Press ", _jsx("b", { children: "Deploy" }), "."] }), _jsxs("li", { children: ["Copy the ", _jsx("b", { children: "Web app URL" }), " (it ends in ", _jsx("code", { children: "/exec" }), ")."] })] }) }), _jsxs(Step, { n: 4, title: "Connect this site", children: [_jsxs("div", { className: "form-grid", children: [_jsxs("label", { className: "field", children: ["Web app URL", _jsx("input", { className: "input", placeholder: "https://script.google.com/macros/s/\u2026/exec", value: url, onChange: (e) => setUrl(e.target.value) })] }), _jsxs("label", { className: "field", children: ["Admin passcode", _jsx("input", { className: "input", type: "password", placeholder: "sacs-\u2026\u2026", value: passcode, onChange: (e) => setPasscode(e.target.value), onKeyDown: (e) => e.key === 'Enter' && url && passcode && submit() })] })] }), error && (_jsx("div", { className: "alert alert-error small", style: { marginTop: 10 }, children: error })), _jsx("div", { className: "row", style: { marginTop: 12 }, children: _jsx("button", { className: "btn btn-primary", disabled: !url.trim() || !passcode.trim() || busy, onClick: submit, children: busy ? 'Connecting…' : 'Connect' }) })] }), _jsxs("p", { className: "small muted", style: { margin: '4px 4px 0' }, children: ["Just testing? ", _jsx("a", { href: "#/setup", children: "Build a draw on this device only" }), " from a CSV or a shared sheet link. Nobody else will see it."] })] })] }));
}
function LoginCard() {
    const { sync, connect } = useStore();
    const [passcode, setPasscode] = useState('');
    const [error, setError] = useState(null);
    const [busy, setBusy] = useState(false);
    if (!sync)
        return null;
    const submit = async () => {
        setBusy(true);
        setError(null);
        try {
            await connect({ url: sync.url, passcode: passcode.trim(), role: 'viewer' });
        }
        catch (e) {
            const msg = e.message;
            setError(/^wrong passcode/i.test(msg) ? 'That passcode isn’t right.' : msg);
        }
        finally {
            setBusy(false);
        }
    };
    return (_jsxs(_Fragment, { children: [_jsx(AdminHero, { title: "Organizer login", children: "Admins run the tournament. Court volunteers use the scorer passcode." }), _jsx("div", { className: "card", style: { maxWidth: 520 }, children: _jsxs("form", { className: "stack", onSubmit: (e) => {
                        e.preventDefault();
                        void submit();
                    }, children: [_jsxs("label", { className: "field", children: ["Passcode", _jsx("input", { className: "input", type: "password", autoFocus: true, value: passcode, onChange: (e) => setPasscode(e.target.value) })] }), error && _jsx("div", { className: "alert alert-error small", children: error }), _jsx("div", { children: _jsx("button", { className: "btn btn-primary", disabled: !passcode.trim() || busy, type: "submit", children: busy ? 'Checking…' : 'Sign in' }) })] }) })] }));
}
const TABS = [
    { id: 'signups', label: 'Sign-ups' },
    { id: 'draw', label: 'Draw' },
    { id: 'money', label: 'Money' },
    { id: 'share', label: 'Share' },
];
function Dashboard() {
    const { t, sync, connect, resolved } = useStore();
    const { info, refresh } = useEventInfo();
    const [tab, setTab] = useState(() => {
        try {
            return localStorage.getItem('pbt.adminTab') || 'signups';
        }
        catch {
            return 'signups';
        }
    });
    const pick = (next) => {
        setTab(next);
        try {
            localStorage.setItem('pbt.adminTab', next);
        }
        catch {
            /* private mode */
        }
    };
    if (!sync)
        return null;
    const isAdmin = sync.role === 'admin';
    const published = t?.published === true;
    const played = resolved ? resolved.ordered.filter((r) => r.done && !r.notNeeded).length : 0;
    if (!isAdmin) {
        return (_jsxs(_Fragment, { children: [_jsx(AdminHero, { title: "Court volunteer", children: "Thanks for helping! Open the courts to call matches and enter scores." }), _jsxs("div", { className: "row", children: [_jsxs("a", { className: "btn btn-primary btn-lg", href: "#/courts", children: [_jsx(LayoutGrid, { size: 18 }), " Open the courts"] }), _jsxs("button", { className: "btn btn-ghost", onClick: () => void connect({ url: sync.url, role: 'viewer' }), children: [_jsx(LogOut, { size: 16 }), " Sign out"] })] })] }));
    }
    const count = info?.registrations ?? 0;
    const steps = [
        { title: 'Sign-ups', done: count > 0, text: `${count} signed up`, tab: 'signups' },
        { title: 'Create the draw', done: !!t, text: t ? 'Draft ready' : 'When sign-ups close', tab: 'draw' },
        { title: 'Publish', done: published, text: published ? `Published · ${played} played` : 'Players see nothing yet', tab: 'draw' },
    ];
    return (_jsxs(_Fragment, { children: [_jsx("div", { className: "page-head", children: _jsxs("div", { children: [_jsx("div", { className: "eyebrow", children: BRAND.eventName }), _jsx("h1", { children: "Organizer" })] }) }), _jsx("ol", { className: "steps", children: steps.map((s, i) => (_jsx("li", { className: s.done ? 'done' : steps.findIndex((x) => !x.done) === i ? 'now' : '', children: _jsxs("button", { onClick: () => pick(s.tab), children: [_jsx("span", { className: "steps-num", children: s.done ? _jsx(Check, { size: 16 }) : i + 1 }), _jsxs("span", { children: [_jsx("b", { children: s.title }), _jsx("span", { className: "small muted", children: s.text })] })] }) }, s.title))) }), _jsx("div", { className: "admin-tabs", role: "tablist", children: TABS.map((x) => (_jsx("button", { role: "tab", "aria-selected": tab === x.id, className: tab === x.id ? 'on' : '', onClick: () => pick(x.id), children: x.label }, x.id))) }), tab === 'signups' && (_jsx("div", { className: "grid", children: _jsx(RegistrationCard, { open: info?.registrationOpen ?? true, count: count, onChange: refresh }) })), tab === 'draw' && _jsx(DrawTab, { onSignups: () => pick('signups') }), tab === 'money' && _jsx("div", { className: "grid", children: info && _jsx(FundraisingCard, { info: info, onChange: refresh }) }), tab === 'share' && _jsx(ShareTab, {}), _jsxs("div", { className: "row section", children: [_jsxs("button", { className: "btn btn-ghost", onClick: () => void connect({ url: sync.url, role: 'viewer' }), children: [_jsx(LogOut, { size: 16 }), " Sign out on this device"] }), _jsxs("a", { className: "btn btn-ghost", href: "#/settings", children: [_jsx(SettingsIcon, { size: 16 }), " Advanced"] })] })] }));
}
/** Create the draw in one click, then review, edit and publish it. */
function DrawTab({ onSignups }) {
    const { t, sync, replace, update } = useStore();
    const [busy, setBusy] = useState(false);
    const [note, setNote] = useState(null);
    const [error, setError] = useState(null);
    if (!sync?.passcode)
        return null;
    const create = async () => {
        if (t && !window.confirm('Start over? This replaces the current draw (and any scores) with a new one from the sign-ups.'))
            return;
        setBusy(true);
        setError(null);
        setNote(null);
        try {
            const rows = await remote.registrations(sync.url, sync.passcode);
            if (rows.length < 2)
                throw new Error('No sign-ups yet.');
            const d = quickDraw(rows);
            replace(d.t);
            setNote(`Draft created: ${d.teams} teams across ${BRAND.courts} courts.` +
                (d.needPartner.length
                    ? ` ${d.needPartner.join(', ')} still ${d.needPartner.length === 1 ? 'needs' : 'need'} a partner: add one under Teams & players below.`
                    : ''));
        }
        catch (e) {
            setError(e.message);
        }
        finally {
            setBusy(false);
        }
    };
    if (!t) {
        return (_jsxs("div", { className: "card draw-empty", children: [_jsx(Wand2, { size: 34, color: "var(--brand)" }), _jsx("h2", { children: "Create the draw" }), _jsxs("p", { className: "muted", children: ["When sign-ups close, one click turns them into teams and a schedule: partners stay together, solo players get paired, everyone lands in Adults or Kids/Teens, and every team plays at least ", BRAND.minGames, " games. It stays a private draft until you publish."] }), error && _jsx("div", { className: "alert alert-error small", children: error }), _jsxs("div", { className: "row", style: { justifyContent: 'center' }, children: [_jsxs("button", { className: "btn btn-primary btn-lg", disabled: busy, onClick: () => void create(), children: [_jsx(Wand2, { size: 18 }), " ", busy ? 'Creating…' : 'Create the draw'] }), _jsx("button", { className: "btn btn-ghost", onClick: onSignups, children: "Check sign-ups first" })] }), _jsx("a", { className: "small muted", href: "#/setup", style: { marginTop: 10 }, children: "Or customize it step by step" })] }));
    }
    const published = t.published === true;
    return (_jsxs("div", { className: "stack", style: { gap: 14 }, children: [_jsxs("div", { className: `card publish-card ${published ? 'is-live' : ''}`, children: [_jsxs("div", { style: { minWidth: 0 }, children: [_jsx("div", { className: "eyebrow", children: published ? 'Published' : 'Draft' }), _jsx("h2", { style: { margin: '2px 0 4px' }, children: published ? 'Players can see the draw' : 'Only you can see this draw' }), _jsx("div", { className: "small muted", children: published
                                    ? 'Edits below show up for everyone right away.'
                                    : 'Check the courts, teams and matchups below, then publish. Registration closes when you do.' })] }), _jsxs("div", { className: "row", children: [published ? (_jsx("button", { className: "btn btn-ghost btn-sm", onClick: () => window.confirm('Hide the draw from players until you publish again?') && update((tt) => ({ ...tt, published: false, updatedAt: Date.now() })), children: "Hide from players" })) : (_jsx("button", { className: "btn btn-primary btn-lg", onClick: () => window.confirm('Publish the draw? Everyone will see the courts, teams and schedule, and registration closes.') &&
                                    update((tt) => ({ ...tt, published: true, updatedAt: Date.now() })), children: "Publish to players" })), _jsxs("a", { className: "btn", href: "#/courts", children: [_jsx(LayoutGrid, { size: 16 }), " Courts"] })] })] }), note && _jsx("div", { className: "alert alert-ok small", children: note }), error && _jsx("div", { className: "alert alert-error small", children: error }), _jsx(EventCard, {}), _jsx(PlayersCard, {}), _jsx(DivisionsCard, {}), _jsx("div", { className: "row", children: _jsx("button", { className: "btn btn-ghost btn-sm", disabled: busy, onClick: () => void create(), children: "Start over from the sign-ups" }) })] }));
}
function ShareTab() {
    const { sync } = useStore();
    if (!sync)
        return null;
    const base = `${siteBase()}?live=${encodeURIComponent(sync.url)}`;
    return (_jsx("div", { className: "card", children: _jsxs("div", { className: "stack", style: { gap: 14 }, children: [_jsx(LinkRow, { label: "Registration link", url: `${base}#/register`, hint: "Send this to players so they can sign up." }), _jsx(LinkRow, { label: "Players\u2019 link", url: `${base}#/`, hint: "Courts, schedule and standings once you publish. Read-only." }), _jsx(LinkRow, { label: "Your organizer link", url: `${base}#/admin`, hint: "Bookmark it. Opens this page on any device (passcode needed)." })] }) }));
}
export function Admin() {
    const { sync } = useStore();
    if (!sync)
        return _jsx(SetupGuide, {});
    if (sync.role === 'viewer')
        return _jsx(LoginCard, {});
    return _jsx(Dashboard, {});
}
/** Sign-up count, open/close switch, and the list of who has registered. */
function RegistrationCard({ open, count, onChange }) {
    const { t, sync } = useStore();
    const [rows, setRows] = useState(null);
    const [busy, setBusy] = useState(false);
    const [error, setError] = useState(null);
    const [show, setShow] = useState(false);
    const [tick, setTick] = useState(0);
    useEffect(() => {
        if (!show || !sync?.passcode)
            return;
        let alive = true;
        remote
            .registrations(sync.url, sync.passcode)
            .then((r) => alive && setRows(r))
            .catch((e) => alive && setError(e.message));
        return () => {
            alive = false;
        };
    }, [show, sync?.url, sync?.passcode, count, tick]);
    if (!sync?.passcode)
        return null;
    const toggle = async () => {
        setBusy(true);
        setError(null);
        try {
            await remote.setRegistration(sync.url, sync.passcode, !open);
            onChange();
        }
        catch (e) {
            setError(e.message);
        }
        finally {
            setBusy(false);
        }
    };
    const drawOut = !!t && t.published === true;
    const header = rows?.[0] ?? [];
    const col = (title) => header.indexOf(title);
    const body = rows?.slice(1) ?? [];
    const donationTotal = body.reduce((sum, r) => sum + (Number(String(r[col('Extra donation')] ?? '').replace(/[^0-9.]/g, '')) || 0), 0);
    return (_jsxs("div", { className: "card", style: { gridColumn: '1 / -1' }, children: [_jsxs("div", { className: "card-head", children: [_jsxs("h2", { children: [_jsx(ClipboardList, { size: 20, style: { verticalAlign: '-3px', marginRight: 6 } }), "Registration"] }), _jsx("span", { className: `badge ${drawOut ? '' : open ? 'badge-final' : 'badge-warn'}`, children: drawOut ? 'Closed (draw is out)' : open ? 'Open' : 'Closed' })] }), _jsxs("div", { className: "row-between", style: { flexWrap: 'wrap', gap: 10 }, children: [_jsxs("div", { children: [_jsx("div", { className: "display", style: { fontSize: '2.2rem', lineHeight: 1 }, children: count }), _jsx("div", { className: "small muted", children: "sign-ups so far" }), donationTotal > 0 && _jsxs("div", { className: "small bold", children: ["$", donationTotal, " in extra donations"] })] }), _jsxs("div", { className: "row", children: [_jsx("a", { className: "btn btn-sm", href: "#/register", children: "View form" }), !drawOut && (_jsx("button", { className: "btn btn-sm", disabled: busy, onClick: toggle, children: open ? 'Close registration' : 'Reopen registration' })), _jsx("button", { className: "btn btn-sm btn-ghost", onClick: () => setShow((v) => !v), children: show ? 'Hide sign-ups' : 'Manage sign-ups' })] })] }), error && (_jsx("div", { className: "alert alert-error small", style: { marginTop: 10 }, children: error })), show && rows && sync.passcode && (_jsx(SignupTable, { url: sync.url, passcode: sync.passcode, rows: rows, onChanged: () => {
                    setTick((n) => n + 1);
                    onChange();
                } })), show && !rows && !error && _jsx("div", { className: "muted small", style: { marginTop: 12 }, children: "Loading\u2026" })] }));
}
/** Goal and money raised outside the form, shown on the public progress bar. */
function FundraisingCard({ info, onChange }) {
    const { sync } = useStore();
    const [goal, setGoal] = useState(String(info.fundraising.goal || ''));
    const [extra, setExtra] = useState(String(info.fundraising.extra || ''));
    const [busy, setBusy] = useState(false);
    const [msg, setMsg] = useState(null);
    if (!sync?.passcode)
        return null;
    const save = async () => {
        setBusy(true);
        setMsg(null);
        try {
            await remote.setFundraising(sync.url, sync.passcode, Number(goal) || 0, Number(extra) || 0);
            setMsg('Saved. The progress bar updates for everyone.');
            onChange();
        }
        catch (e) {
            setMsg(e.message);
        }
        finally {
            setBusy(false);
        }
    };
    return (_jsxs("div", { className: "card", style: { gridColumn: '1 / -1' }, children: [_jsx("h2", { children: "Fundraising" }), _jsx(FundraiserCard, { info: info }), _jsxs("p", { className: "small muted", style: { margin: '12px 0' }, children: ["Raised = ", info.fundraising.players || info.registrations, " players \u00D7 $", BRAND.payment.feeAmount || 0, " required donation + $", info.fundraising.donations, " in extra donations + money raised elsewhere. Currently $", raisedTotal(info), ".", !BRAND.payment.feeAmount && ' The required donation amount isn’t set yet, so it isn’t counted.'] }), _jsxs("div", { className: "form-grid", children: [_jsxs("label", { className: "field", children: ["Goal ($)", _jsx("input", { className: "input", inputMode: "numeric", value: goal, onChange: (e) => setGoal(e.target.value.replace(/[^0-9]/g, '')) })] }), _jsxs("label", { className: "field", children: ["Raised elsewhere ($)", _jsx("input", { className: "input", inputMode: "numeric", value: extra, onChange: (e) => setExtra(e.target.value.replace(/[^0-9]/g, '')) }), _jsx("span", { className: "hint", children: "Cash at the event, GoFundMe, sponsors\u2026 anything not entered through the form." })] })] }), _jsxs("div", { className: "row", style: { marginTop: 10 }, children: [_jsx("button", { className: "btn btn-primary btn-sm", disabled: busy, onClick: save, children: busy ? 'Saving…' : 'Save' }), msg && _jsx("span", { className: "small muted", children: msg })] })] }));
}
