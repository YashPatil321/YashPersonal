import { Fragment as _Fragment, jsx as _jsx, jsxs as _jsxs } from "react/jsx-runtime";
import { useState } from 'react';
import { Activity, HandHeart, CalendarClock, ClipboardList, Ellipsis, House, LayoutGrid, ListOrdered, LogIn, LogOut, Network, Settings as SettingsIcon, ShieldCheck, Trophy, Tv, UserRound, } from 'lucide-react';
import { BRAND } from './brand';
import { FundraiserCard } from './components/Fundraiser';
import { BallIcon, BrandName, CauseCard, Mandala, Modal, Toran } from './components/ui';
import { Admin } from './pages/Admin';
import { Courts } from './pages/Courts';
import { Matches } from './pages/Matches';
import { Overview } from './pages/Overview';
import { Register } from './pages/Register';
import { Scorekeeper } from './pages/Scorekeeper';
import { Settings } from './pages/Settings';
import { Setup } from './pages/Setup';
import { Brackets, Standings } from './pages/Standings';
import { TeamDetail, Teams } from './pages/Teams';
import { TV } from './pages/TV';
import { useRoute } from './state/router';
import { useStore } from './state/store';
import { useEventInfo } from './state/useEventInfo';
export function App() {
    const route = useRoute();
    const { t } = useStore();
    const [page] = route.parts;
    const [login, setLogin] = useState(false);
    const [more, setMore] = useState(false);
    if (page === 'tv' && t)
        return _jsx(TV, {});
    return (_jsxs(_Fragment, { children: [_jsx(Header, {}), _jsx(DraftBar, {}), _jsx("main", { children: _jsx(Page, { onLogin: () => setLogin(true) }) }, route.path), _jsx(Footer, {}), _jsx(BottomNav, { onMore: () => setMore(true) }), login && _jsx(LoginModal, { onClose: () => setLogin(false) }), more && (_jsx(MoreSheet, { onClose: () => setMore(false), onLogin: () => {
                    setMore(false);
                    setLogin(true);
                } }))] }));
}
/** Organizers only: the draw is a draft until they publish it. */
function DraftBar() {
    const { t, isAdmin, update } = useStore();
    if (!t || !isAdmin || t.published !== false)
        return null;
    return (_jsxs("div", { className: "draft-bar", role: "status", children: [_jsxs("span", { children: [_jsx("b", { children: "Draft." }), " Only organizers can see this draw. Edit courts, matchups and teams as much as you like."] }), _jsx("button", { className: "btn btn-primary btn-sm", onClick: () => {
                    if (window.confirm('Publish the draw? Everyone will see the courts, teams and schedule, and registration closes.'))
                        update((tt) => ({ ...tt, published: true, updatedAt: Date.now() }));
                }, children: "Publish to players" })] }));
}
function Page({ onLogin }) {
    const route = useRoute();
    const { t, isAdmin } = useStore();
    const [page, id] = route.parts;
    if (page === 'admin')
        return _jsx(Admin, {});
    if (page === 'register')
        return _jsx(Register, {});
    if (page === 'setup')
        return isAdmin ? _jsx(Setup, {}) : _jsx(AdminOnly, { onLogin: onLogin });
    if (page === 'settings')
        return isAdmin ? _jsx(Settings, {}) : _jsx(AdminOnly, { onLogin: onLogin });
    if (!t)
        return _jsx(Landing, {});
    switch (page) {
        case undefined:
            return _jsx(Overview, {});
        case 'courts':
            return _jsx(Courts, {});
        case 'matches':
            return _jsx(Matches, {});
        case 'standings':
            return _jsx(Standings, {});
        case 'brackets':
            return _jsx(Brackets, {});
        case 'teams':
            return id ? _jsx(TeamDetail, { teamId: id }) : _jsx(Teams, {});
        case 'score':
            return id ? _jsx(Scorekeeper, { matchId: id }) : _jsx(Courts, {});
        default:
            return _jsx(Overview, {});
    }
}
/** Public navigation. Organizer pages only appear once the organizer has a draw on this device. */
function useNavItems() {
    const { t, isAdmin } = useStore();
    if (!t)
        return [
            { path: '', label: 'Home', icon: _jsx(House, { size: 18 }) },
            { path: 'register', label: 'Register', icon: _jsx(ClipboardList, { size: 18 }) },
        ];
    const hasBrackets = t.divisions.some((d) => d.settings.format !== 'round_robin');
    const all = [
        { path: '', label: 'Home', icon: _jsx(House, { size: 18 }) },
        { path: 'teams', label: t.settings.doubles ? 'My team' : 'Me', icon: _jsx(UserRound, { size: 18 }) },
        { path: 'courts', label: 'Courts', icon: _jsx(LayoutGrid, { size: 18 }), match: ['courts', 'score'] },
        { path: 'matches', label: 'Matches', icon: _jsx(ListOrdered, { size: 18 }) },
        {
            path: 'standings',
            label: 'Standings',
            icon: _jsx(Trophy, { size: 18 }),
            match: hasBrackets ? ['standings'] : ['standings', 'brackets'],
        },
    ];
    if (hasBrackets)
        all.push({ path: 'brackets', label: 'Brackets', icon: _jsx(Network, { size: 18 }) });
    all.push({ path: 'tv', label: 'TV', icon: _jsx(Tv, { size: 18 }) });
    if (isAdmin)
        all.push({ path: 'settings', label: 'Settings', icon: _jsx(SettingsIcon, { size: 18 }) });
    return all;
}
function isActive(item, current) {
    return item.match ? item.match.includes(current) : item.path === current;
}
function Header() {
    const route = useRoute();
    const { t, sync, syncState } = useStore();
    const current = route.parts[0] ?? '';
    const items = useNavItems();
    const sub = t
        ? [t.date && new Date(t.date + 'T12:00:00').toLocaleDateString(undefined, { month: 'short', day: 'numeric' }), t.location]
            .filter(Boolean)
            .join(' · ') || BRAND.organizer
        : `${BRAND.organizer} · ${BRAND.tagline}`;
    return (_jsx("header", { className: "app-header", children: _jsxs("div", { className: "header-inner", children: [_jsxs("a", { className: "brand", href: "#/", children: [_jsx(BallIcon, { size: 34, className: "ball-spin" }), _jsxs("div", { style: { minWidth: 0 }, children: [_jsx("div", { className: "brand-title truncate", children: _jsx(BrandName, { name: t?.name ?? BRAND.eventName }) }), _jsx("div", { className: "brand-sub truncate", children: sub })] })] }), items.length > 0 && (_jsx("nav", { className: "nav", children: items.map((item) => (_jsx("a", { href: `#/${item.path}`, className: isActive(item, current) ? 'active' : '', children: item.label }, item.path))) })), _jsxs("div", { className: "header-actions", children: [sync && t && (_jsxs("span", { className: `sync-pill ${syncState.status}`, title: syncState.message ?? 'Saved to the Google Sheet', children: [_jsx("span", { className: "dot" }), syncState.status === 'synced'
                                    ? 'Synced'
                                    : syncState.status === 'saving'
                                        ? 'Saving'
                                        : syncState.status === 'connecting'
                                            ? 'Connecting'
                                            : 'Offline'] })), _jsx(RoleBadge, {})] })] }) }));
}
function BottomNav({ onMore }) {
    const route = useRoute();
    const current = route.parts[0] ?? '';
    const items = useNavItems();
    if (!items.length)
        return null;
    const primaryPaths = ['', 'teams', 'courts', 'standings', 'register'];
    const primary = items.filter((i) => primaryPaths.includes(i.path));
    const overflow = items.filter((i) => !primaryPaths.includes(i.path));
    const moreActive = overflow.some((i) => isActive(i, current)) && current !== 'brackets';
    const showMore = overflow.length > 0;
    return (_jsxs("nav", { className: "bottom-nav", style: { gridTemplateColumns: `repeat(${primary.length + (showMore ? 1 : 0)}, 1fr)` }, children: [primary.map((item) => (_jsxs("a", { href: `#/${item.path}`, className: isActive(item, current) || (item.path === 'standings' && current === 'brackets') ? 'active' : '', children: [item.icon, item.label] }, item.path))), showMore && (_jsxs("button", { className: moreActive ? 'active' : '', onClick: onMore, children: [_jsx(Ellipsis, { size: 18 }), "More"] }))] }));
}
function MoreSheet({ onClose, onLogin }) {
    const { sync, connect } = useStore();
    const items = useNavItems().filter((i) => !['', 'teams', 'courts', 'standings'].includes(i.path));
    return (_jsx(Modal, { title: "More", onClose: onClose, children: _jsxs("div", { className: "more-sheet", children: [items.map((item) => (_jsxs("a", { href: `#/${item.path}`, onClick: onClose, children: [item.icon, item.label] }, item.path))), _jsxs("a", { href: BRAND.charity.url, target: "_blank", rel: "noreferrer", children: [_jsx(Activity, { size: 18 }), " About ", BRAND.charity.name] }), sync?.role === 'viewer' && (_jsxs("button", { onClick: onLogin, children: [_jsx(LogIn, { size: 18 }), " Organizer login"] })), sync && sync.role !== 'viewer' && (_jsxs("button", { onClick: () => {
                        void connect({ url: sync.url, role: 'viewer' });
                        onClose();
                    }, children: [_jsx(LogOut, { size: 18 }), " Sign out (", sync.role, ")"] }))] }) }));
}
function RoleBadge() {
    const { sync, connect } = useStore();
    if (!sync || sync.role === 'viewer')
        return null;
    return (_jsxs("button", { className: "btn btn-sm btn-primary", title: "Signed in. Click to sign out.", onClick: () => {
            if (window.confirm(`You're signed in as ${sync.role}. Sign out on this device?`)) {
                void connect({ url: sync.url, role: 'viewer' });
            }
        }, children: [_jsx(ShieldCheck, { size: 15 }), " ", sync.role === 'admin' ? 'Admin' : 'Scorer'] }));
}
function Footer() {
    return (_jsx("footer", { className: "site-footer", children: _jsxs("div", { className: "footer-inner", children: [_jsxs("div", { children: [_jsx("div", { className: "brand-title", children: _jsx(BrandName, { name: BRAND.eventName }) }), _jsxs("div", { className: "small muted", children: ["Hosted by the ", BRAND.organizer, ". ", BRAND.charity.pledge] })] }), _jsxs("div", { className: "row", children: [_jsx("a", { className: "small", href: BRAND.charity.url, target: "_blank", rel: "noreferrer", children: BRAND.charity.name }), _jsx("a", { className: "btn btn-ghost btn-sm", href: "#/admin", children: "Organizer" })] })] }) }));
}
function LoginModal({ onClose }) {
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
            onClose();
        }
        catch (e) {
            const msg = e.message;
            setError(/^wrong passcode/i.test(msg) ? 'That passcode isn’t right.' : msg);
        }
        finally {
            setBusy(false);
        }
    };
    return (_jsx(Modal, { title: "Organizer login", subtitle: "For the SACS team running the tournament.", onClose: onClose, children: _jsxs("form", { className: "stack", onSubmit: (e) => {
                e.preventDefault();
                void submit();
            }, children: [_jsxs("label", { className: "field", children: ["Passcode", _jsx("input", { className: "input", type: "password", autoFocus: true, value: passcode, onChange: (e) => setPasscode(e.target.value) })] }), error && _jsx("div", { className: "alert alert-error small", children: error }), _jsxs("div", { className: "row", children: [_jsx("button", { className: "btn btn-primary", disabled: !passcode.trim() || busy, type: "submit", children: busy ? 'Checking…' : 'Sign in' }), _jsx("span", { className: "muted tiny", children: "Players don\u2019t need to sign in." })] })] }) }));
}
/* ------------------------------------------------------------------ */
/* Landing                                                            */
/* ------------------------------------------------------------------ */
function AdminOnly({ onLogin }) {
    const { sync } = useStore();
    return (_jsxs("div", { className: "card empty", children: [_jsx("h2", { style: { color: 'var(--ink)' }, children: "Organizers only" }), _jsx("p", { children: "This page is for the SACS team running the tournament." }), sync?.role === 'viewer' ? (_jsxs("button", { className: "btn btn-primary", onClick: onLogin, children: [_jsx(LogIn, { size: 16 }), " Organizer login"] })) : (_jsx("a", { className: "btn btn-primary", href: "#/admin", children: "Go to the organizer page" }))] }));
}
const DAY_OF = [
    [_jsx(UserRound, { size: 20 }), 'Find your team', 'Type your name to see your court, when you play next and how you’re doing.'],
    [_jsx(LayoutGrid, { size: 20 }), 'Courts & schedule', `${BRAND.minGames}+ games for every team, across ${BRAND.courts} courts. See which court you’re on and when you’re up.`],
    [_jsx(Trophy, { size: 20 }), 'Standings & brackets', 'Follow every pool and the playoff race all the way to the final.'],
];
function Landing() {
    const { info } = useEventInfo();
    return (_jsxs(_Fragment, { children: [_jsxs("section", { className: "hero", children: [_jsx(Toran, {}), _jsx(Mandala, {}), _jsxs("div", { className: "eyebrow", children: [BRAND.organizer, " presents"] }), _jsxs("h1", { children: [_jsx("span", { className: "wordmark hero-wordmark", children: BRAND.short }), "Pickleball ", _jsx("span", { className: "hl", children: "Tournament" })] }), _jsxs("p", { children: ["Grab a partner and play for a cause. ", BRAND.charity.pledge] }), _jsxs("div", { className: "row", style: { marginBottom: 22 }, children: [_jsxs("span", { className: "chip", children: [_jsx(UserRound, { size: 14 }), " Adults & Kids/Teens divisions"] }), _jsxs("span", { className: "chip", children: [_jsx(HandHeart, { size: 14 }), " $", BRAND.payment.feeAmount, " per person"] }), _jsxs("span", { className: "chip", children: [_jsx(LayoutGrid, { size: 14 }), " ", BRAND.courts, " courts"] }), _jsxs("span", { className: "chip", children: [_jsx(CalendarClock, { size: 14 }), " ", BRAND.when] }), _jsxs("span", { className: "chip", children: [_jsx(Activity, { size: 14 }), " At least ", BRAND.minGames, " games per team"] })] }), _jsxs("div", { className: "row", style: { gap: 14, alignItems: 'center' }, children: [_jsxs("a", { className: "btn btn-primary btn-lg", href: "#/register", children: [_jsx(ClipboardList, { size: 18 }), " Register your team"] }), info && info.registrations > 0 && (_jsxs("span", { className: "chip", children: [_jsx(UserRound, { size: 14 }), " ", info.registrations, " signed up"] }))] }), _jsxs("div", { className: "draw-soon", style: { marginTop: 16 }, children: [_jsx("span", { className: "dot" }), " The draw comes out when sign-ups close. Keep this page handy: on tournament day it shows your court, your matches and the brackets."] })] }), _jsx("div", { style: { marginTop: 16 }, children: _jsx(FundraiserCard, { info: info, cta: true }) }), _jsx("div", { style: { marginTop: 16 }, children: _jsx(CauseCard, {}) }), _jsx("div", { className: "section-title", children: _jsx("h2", { children: "Who we are" }) }), _jsxs("div", { className: "about-sacs card", children: [_jsxs("p", { style: { margin: 0 }, children: ["The ", _jsx("b", { children: BRAND.organizer }), " is a student-run dance production: over 100 high schoolers from five San Diego schools, putting on one big show every year. This tournament helps fund the show and gives back to the", ' ', BRAND.charity.name, "."] }), _jsxs("div", { className: "photo-grid", children: [_jsx("figure", { children: _jsx("img", { src: "./photos/sacs-bhangra.webp", alt: "SACS dancers in matching white and colored costumes", loading: "lazy" }) }), _jsx("figure", { children: _jsx("img", { src: "./photos/sacs-guys.webp", alt: "SACS dancers posing together on the steps after the show", loading: "lazy" }) })] })] }), _jsx("div", { className: "section-title", children: _jsx("h2", { children: "On tournament day" }) }), _jsx("div", { className: "feature-list", style: { marginTop: 0 }, children: DAY_OF.map(([icon, title, text]) => (_jsxs("div", { className: "card", children: [_jsx("span", { className: "feature-icon", children: icon }), _jsx("h3", { children: title }), _jsx("div", { className: "muted small", children: text })] }, title))) })] }));
}
