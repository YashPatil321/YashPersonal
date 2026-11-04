import { Fragment as _Fragment, jsx as _jsx, jsxs as _jsxs } from "react/jsx-runtime";
import { useEffect, useState } from 'react';
import { Check, ClipboardList, Copy, Download, ExternalLink, LayoutGrid, LogOut, Settings as SettingsIcon, Wand2 } from 'lucide-react';
import setupScript from '../../apps-script/Code.gs?raw';
import { BRAND } from '../brand';
import { download } from '../lib/exporters';
import { Mandala, Toran } from '../components/ui';
import { remote } from '../lib/sync';
import { FundraiserCard, raisedTotal } from '../components/Fundraiser';
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
function Dashboard() {
    const { t, sync, connect, resolved } = useStore();
    const { info, refresh } = useEventInfo();
    if (!sync)
        return null;
    const isAdmin = sync.role === 'admin';
    const publicLink = `${siteBase()}?live=${encodeURIComponent(sync.url)}#/`;
    const adminLink = `${siteBase()}?live=${encodeURIComponent(sync.url)}#/admin`;
    const played = resolved ? resolved.ordered.filter((r) => r.done && !r.notNeeded).length : 0;
    return (_jsxs(_Fragment, { children: [_jsxs(AdminHero, { title: isAdmin ? 'Organizer dashboard' : 'Court volunteer', children: ["Signed in as ", _jsx("b", { style: { color: 'var(--ball)' }, children: sync.role }), info ? ` · connected to “${info.spreadsheet}”` : '', "."] }), _jsxs("div", { className: "grid grid-2", children: [_jsxs("div", { className: "card", children: [_jsxs("div", { className: "card-head", children: [_jsx("h2", { children: "Tournament" }), t && _jsxs("span", { className: "badge badge-final", children: [played, " matches played"] })] }), !t ? (_jsxs(_Fragment, { children: [_jsx("p", { className: "muted small", children: "When sign-ups close, build the draw from the registrations. Competitors see it the moment you create it." }), isAdmin && (_jsxs("a", { className: "btn btn-primary btn-lg", href: "#/setup", children: [_jsx(Wand2, { size: 18 }), " Build the draw"] }))] })) : (_jsxs("div", { className: "row", children: [_jsxs("a", { className: "btn btn-primary", href: "#/courts", children: [_jsx(LayoutGrid, { size: 16 }), " Court desk"] }), _jsx("a", { className: "btn", href: "#/", children: "Live home page" }), isAdmin && (_jsxs("a", { className: "btn", href: "#/settings", children: [_jsx(SettingsIcon, { size: 16 }), " Settings"] }))] }))] }), isAdmin && _jsx(RegistrationCard, { open: info?.registrationOpen ?? true, count: info?.registrations ?? 0, onChange: refresh }), isAdmin && info && _jsx(FundraisingCard, { info: info, onChange: refresh })] }), isAdmin && (_jsxs("div", { className: "card section", children: [_jsx("h2", { children: "Links" }), _jsxs("div", { className: "stack", style: { gap: 14 }, children: [_jsx(LinkRow, { label: "Registration link", url: `${siteBase()}?live=${encodeURIComponent(sync.url)}#/register`, hint: "Send this to players so they can sign up." }), _jsx(LinkRow, { label: "Players\u2019 link", url: publicLink, hint: "Live courts, brackets and scores. Read-only, no login." }), _jsx(LinkRow, { label: "Admin link", url: adminLink, hint: "Bookmark this. It opens straight to this page on any device (you\u2019ll still need the passcode)." })] })] })), _jsx("div", { className: "row section", children: _jsxs("button", { className: "btn btn-ghost", onClick: () => void connect({ url: sync.url, role: 'viewer' }), children: [_jsx(LogOut, { size: 16 }), " Sign out on this device"] }) })] }));
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
    }, [show, sync?.url, sync?.passcode, count]);
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
    const header = rows?.[0] ?? [];
    const col = (title) => header.indexOf(title);
    const body = rows?.slice(1) ?? [];
    const donationTotal = body.reduce((sum, r) => sum + (Number(String(r[col('Extra donation')] ?? '').replace(/[^0-9.]/g, '')) || 0), 0);
    return (_jsxs("div", { className: "card", children: [_jsxs("div", { className: "card-head", children: [_jsxs("h2", { children: [_jsx(ClipboardList, { size: 20, style: { verticalAlign: '-3px', marginRight: 6 } }), "Registration"] }), _jsx("span", { className: `badge ${t ? '' : open ? 'badge-final' : 'badge-warn'}`, children: t ? 'Closed (draw is out)' : open ? 'Open' : 'Closed' })] }), _jsxs("div", { className: "row-between", style: { flexWrap: 'wrap', gap: 10 }, children: [_jsxs("div", { children: [_jsx("div", { className: "display", style: { fontSize: '2.2rem', lineHeight: 1 }, children: count }), _jsx("div", { className: "small muted", children: "sign-ups so far" }), donationTotal > 0 && _jsxs("div", { className: "small bold", children: ["$", donationTotal, " in extra donations"] })] }), _jsxs("div", { className: "row", children: [_jsx("a", { className: "btn btn-sm", href: "#/register", children: "View form" }), !t && (_jsx("button", { className: "btn btn-sm", disabled: busy, onClick: toggle, children: open ? 'Close registration' : 'Reopen registration' })), _jsx("button", { className: "btn btn-sm btn-ghost", onClick: () => setShow((v) => !v), children: show ? 'Hide list' : 'See who signed up' })] })] }), error && (_jsx("div", { className: "alert alert-error small", style: { marginTop: 10 }, children: error })), show && (_jsx("div", { className: "table-wrap", style: { marginTop: 12 }, children: !rows ? (_jsx("div", { className: "muted small", children: "Loading\u2026" })) : body.length === 0 ? (_jsx("div", { className: "muted small", children: "No sign-ups yet." })) : (_jsxs("table", { className: "table signup-table", children: [_jsx("thead", { children: _jsxs("tr", { children: [_jsx("th", { children: "Name" }), _jsx("th", { children: "Partner" }), _jsx("th", { children: "Division" }), _jsx("th", { children: "School" }), _jsx("th", { children: "Paid" }), _jsx("th", { children: "Donation" })] }) }), _jsx("tbody", { children: body
                                .slice()
                                .reverse()
                                .map((r, i) => (_jsxs("tr", { children: [_jsx("td", { className: "bold", children: r[col('Full name')] }), _jsx("td", { children: r[col("Partner's full name")] || _jsx("span", { className: "muted", children: "Needs a partner" }) }), _jsx("td", { children: r[col('Division')] }), _jsx("td", { className: "small", children: r[col('School')] }), _jsx("td", { className: "small", children: r[col('Payment method')] }), _jsx("td", { className: "small", children: r[col('Extra donation')] })] }, i))) })] })) }))] }));
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
