import { Fragment as _Fragment, jsx as _jsx, jsxs as _jsxs } from "react/jsx-runtime";
import { useState } from 'react';
import { Crown, HandHeart, Star } from 'lucide-react';
import { Modal } from './ui';
import { BRAND } from '../brand';
/** Total raised = $20 per player + extra donations + money raised elsewhere. */
export function raisedTotal(info) {
    const f = info.fundraising;
    return Math.round((f.players || info.registrations) * BRAND.payment.feeAmount + f.donations + f.extra);
}
const money = (n) => `$${n.toLocaleString('en-US', { maximumFractionDigits: 0 })}`;
/** GoFundMe-style progress card. */
export function FundraiserCard({ info, cta }) {
    if (!info)
        return null;
    const raised = raisedTotal(info);
    const goal = info.fundraising.goal;
    if (!raised && !goal)
        return null;
    const pct = goal ? Math.min(100, Math.round((raised / goal) * 100)) : 0;
    const supporters = info.fundraising.players || info.registrations;
    const donationCount = info.fundraising.list?.length ?? info.registrations;
    return (_jsxs("div", { className: "fund-card", children: [_jsxs("div", { className: "fund-top", children: [_jsxs("div", { children: [_jsx("div", { className: "fund-raised", children: money(raised) }), _jsxs("div", { className: "small muted", children: ["raised", goal ? ` of ${money(goal)}` : ''] })] }), goal > 0 && _jsxs("div", { className: "fund-pct", children: [pct, "%"] })] }), goal > 0 && (_jsx("div", { className: "fund-bar", role: "progressbar", "aria-valuenow": pct, "aria-valuemin": 0, "aria-valuemax": 100, children: _jsx("div", { style: { width: `${pct}%` } }) })), _jsxs("div", { className: "fund-stats", children: [_jsxs("span", { children: [_jsx("b", { children: donationCount }), " ", donationCount === 1 ? 'donation' : 'donations'] }), _jsxs("span", { children: [_jsx("b", { children: supporters }), " ", supporters === 1 ? 'player' : 'players'] })] }), cta && (_jsxs("div", { className: "row", style: { marginTop: 12 }, children: [_jsxs("a", { className: "btn btn-primary", href: "#/register", children: [_jsx(HandHeart, { size: 16 }), " Register & donate"] }), BRAND.donateUrl && (_jsx("a", { className: "btn", href: BRAND.donateUrl, target: "_blank", rel: "noreferrer", children: "Just donate" }))] }))] }));
}
function gifts(info) {
    return (info.fundraising.list ?? []).map((d) => ({
        name: d.name,
        amount: d.players * BRAND.payment.feeAmount + d.extra,
        at: d.at,
    }));
}
function when(at) {
    const t = Date.parse(at);
    if (Number.isNaN(t))
        return '';
    const days = Math.floor((Date.now() - t) / 86400000);
    if (days <= 0)
        return 'today';
    if (days === 1)
        return 'yesterday';
    if (days < 30)
        return `${days} days ago`;
    return new Date(t).toLocaleDateString(undefined, { month: 'short', day: 'numeric' });
}
/** GoFundMe-style list of every donation with the top donor highlighted. */
export function DonationWall({ info }) {
    const [all, setAll] = useState(false);
    if (!info)
        return null;
    const list = gifts(info);
    if (!list.length)
        return null;
    const top = list.reduce((best, g) => (g.amount > best.amount ? g : best), list[0]);
    const shown = all ? list : list.slice(0, 8);
    return (_jsxs("div", { className: "donation-wall", children: [_jsxs("div", { className: "top-donor", children: [_jsx("span", { className: "top-icon", children: _jsx(Crown, { size: 20 }) }), _jsxs("div", { style: { minWidth: 0 }, children: [_jsx("div", { className: "eyebrow", children: "Top donor" }), _jsx("div", { className: "top-name", children: top.name })] }), _jsx("div", { className: "top-amount", children: money(top.amount) })] }), _jsxs("div", { className: "card list-card", style: { marginTop: 10 }, children: [_jsxs("div", { className: "row-between", style: { padding: '12px 14px 4px' }, children: [_jsx("h3", { style: { margin: 0 }, children: "Donations" }), _jsxs("span", { className: "small muted", children: [list.length, " so far"] })] }), shown.map((g, i) => (_jsxs("div", { className: "donation-row", children: [_jsx("span", { className: "donation-heart", children: _jsx(HandHeart, { size: 16 }) }), _jsx("span", { className: "truncate bold", children: g.name }), _jsx("span", { className: "donation-amount", children: money(g.amount) }), _jsx("span", { className: "tiny muted donation-when", children: when(g.at) })] }, i))), list.length > 8 && (_jsx("div", { style: { padding: '8px 14px 12px' }, children: _jsx("button", { className: "btn btn-sm btn-ghost", onClick: () => setAll((v) => !v), children: all ? 'Show fewer' : `See all ${list.length}` }) }))] })] }));
}
/** GoFundMe-style short time: "44 mins", "2 hrs", "3 d". */
function ago(at) {
    const t = Date.parse(at);
    if (Number.isNaN(t))
        return '';
    const m = Math.max(1, Math.floor((Date.now() - t) / 60000));
    if (m < 60)
        return `${m} min${m === 1 ? '' : 's'}`;
    const h = Math.floor(m / 60);
    if (h < 24)
        return `${h} hr${h === 1 ? '' : 's'}`;
    const d = Math.floor(h / 24);
    if (d < 30)
        return `${d} d`;
    return new Date(t).toLocaleDateString(undefined, { month: 'short', day: 'numeric' });
}
function Ring({ pct }) {
    const r = 30;
    const c = 2 * Math.PI * r;
    return (_jsxs("svg", { className: "gf-ring", viewBox: "0 0 72 72", role: "img", "aria-label": `${pct}% of goal`, children: [_jsx("circle", { cx: "36", cy: "36", r: r, className: "gf-ring-track" }), _jsx("circle", { cx: "36", cy: "36", r: r, className: "gf-ring-fill", strokeDasharray: c, strokeDashoffset: c * (1 - pct / 100), transform: "rotate(-90 36 36)" }), _jsxs("text", { x: "36", y: "41", textAnchor: "middle", children: [pct, "%"] })] }));
}
function GiftRow({ g, tag }) {
    return (_jsxs("div", { className: "gf-gift", children: [_jsx("span", { className: "gf-gift-icon", children: _jsx(HandHeart, { size: 18 }) }), _jsxs("div", { style: { minWidth: 0 }, children: [_jsx("div", { className: "truncate bold", children: g.name }), _jsxs("div", { className: "small", children: [_jsx("b", { children: money(g.amount) }), tag ? (_jsxs(_Fragment, { children: [' ', "\u00B7 ", _jsx("span", { className: "gf-tag", children: tag })] })) : g.at ? (_jsxs("span", { className: "muted", children: [" \u00B7 ", ago(g.at)] })) : null] })] })] }));
}
/** The sticky GoFundMe-style card: ring, raised of goal, buttons, recent + top donations. */
export function FundraiserSidebar({ info, onRegister }) {
    const [modal, setModal] = useState(null);
    const [copied, setCopied] = useState(false);
    const raised = info ? raisedTotal(info) : 0;
    const goal = info?.fundraising.goal ?? 0;
    const pct = goal ? Math.min(100, Math.round((raised / goal) * 100)) : 0;
    const list = info ? gifts(info) : [];
    const top = list.length ? list.reduce((best, g) => (g.amount > best.amount ? g : best), list[0]) : null;
    const recent = list.filter((g) => g !== top).slice(0, 2);
    const share = async () => {
        const url = window.location.href;
        const data = { title: BRAND.eventName, text: `Play or donate: ${BRAND.eventName}`, url };
        try {
            if (navigator.share)
                return await navigator.share(data);
            await navigator.clipboard.writeText(url);
            setCopied(true);
            setTimeout(() => setCopied(false), 2000);
        }
        catch {
            /* cancelled */
        }
    };
    const modalList = modal === 'top' ? [...list].sort((a, b) => b.amount - a.amount) : list;
    return (_jsxs("div", { className: "gf-card", children: [_jsxs("div", { className: "gf-head", children: [_jsxs("div", { style: { minWidth: 0 }, children: [_jsxs("div", { className: "gf-raised", children: [money(raised), " ", _jsx("span", { children: "raised" })] }), _jsxs("div", { className: "small muted", children: [goal ? `${money(goal)} goal · ` : '', list.length || info?.registrations || 0, " ", (list.length || info?.registrations) === 1 ? 'donation' : 'donations'] })] }), goal > 0 && _jsx(Ring, { pct: pct })] }), _jsxs("div", { className: "gf-actions", children: [_jsx("a", { className: "btn btn-primary btn-lg gf-btn", href: "#/register", onClick: onRegister, children: "Register to play" }), _jsx("a", { className: "btn btn-lg gf-btn gf-share", href: "#/register?donate=1", children: "Donate" }), _jsx("button", { className: "btn btn-sm btn-ghost gf-btn", type: "button", onClick: () => void share(), children: copied ? 'Link copied' : 'Share' }), BRAND.donateUrl && (_jsx("a", { className: "btn gf-btn", href: BRAND.donateUrl, target: "_blank", rel: "noreferrer", children: "Just donate" }))] }), top ? (_jsxs("div", { className: "gf-list", children: [recent.slice(0, 1).map((g, i) => (_jsx(GiftRow, { g: g }, `r${i}`))), _jsx(GiftRow, { g: top, tag: "Top donation" }), recent.slice(1).map((g, i) => (_jsx(GiftRow, { g: g }, `s${i}`)))] })) : (_jsx("p", { className: "small muted", style: { margin: '14px 0 0' }, children: "No donations yet." })), list.length > 0 && (_jsxs("div", { className: "gf-more", children: [_jsx("button", { className: "btn btn-sm", type: "button", onClick: () => setModal('all'), children: "See all" }), _jsxs("button", { className: "btn btn-sm", type: "button", onClick: () => setModal('top'), children: [_jsx(Star, { size: 14 }), " See top"] })] })), modal && (_jsx(Modal, { title: modal === 'top' ? 'Top donations' : `Donations (${list.length})`, subtitle: `${money(raised)} raised${goal ? ` of ${money(goal)}` : ''}`, onClose: () => setModal(null), children: _jsx("div", { className: "gf-modal-list", children: modalList.map((g, i) => (_jsx(GiftRow, { g: g, tag: modal === 'top' && i === 0 ? 'Top donation' : undefined }, i))) }) }))] }));
}
