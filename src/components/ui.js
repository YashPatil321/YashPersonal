import { Fragment as _Fragment, jsx as _jsx, jsxs as _jsxs } from "react/jsx-runtime";
import { useEffect } from 'react';
import { ExternalLink, HandHeart, X } from 'lucide-react';
import { BRAND } from '../brand';
export function Modal({ title, subtitle, onClose, children, wide, }) {
    useEffect(() => {
        const onKey = (e) => e.key === 'Escape' && onClose();
        window.addEventListener('keydown', onKey);
        const prev = document.body.style.overflow;
        document.body.style.overflow = 'hidden';
        return () => {
            window.removeEventListener('keydown', onKey);
            document.body.style.overflow = prev;
        };
    }, [onClose]);
    return (_jsx("div", { className: "modal-backdrop", onMouseDown: (e) => e.target === e.currentTarget && onClose(), children: _jsxs("div", { className: "modal", role: "dialog", "aria-modal": "true", style: wide ? { maxWidth: 760 } : undefined, children: [_jsxs("div", { className: "modal-head", children: [_jsxs("div", { style: { minWidth: 0 }, children: [_jsx("h2", { style: { margin: 0 }, children: title }), subtitle && _jsx("div", { className: "muted small", children: subtitle })] }), _jsx("button", { className: "btn btn-ghost btn-sm", onClick: onClose, "aria-label": "Close", children: _jsx(X, { size: 18 }) })] }), children] }) }));
}
export function Progress({ value, total }) {
    const pct = total ? Math.round((value / total) * 100) : 0;
    return (_jsx("div", { className: "progress", title: `${value} of ${total}`, children: _jsx("div", { style: { width: `${pct}%` } }) }));
}
export function ProgressRing({ value, total, label }) {
    const pct = total ? value / total : 0;
    const r = 64;
    const c = 2 * Math.PI * r;
    return (_jsxs("div", { className: "ring", children: [_jsxs("svg", { width: "148", height: "148", viewBox: "0 0 148 148", "aria-hidden": "true", children: [_jsx("circle", { cx: "74", cy: "74", r: r, fill: "none", stroke: "rgba(255,255,255,0.1)", strokeWidth: "10" }), _jsx("circle", { cx: "74", cy: "74", r: r, fill: "none", stroke: "var(--ball)", strokeWidth: "10", strokeLinecap: "round", strokeDasharray: `${c * pct} ${c}`, style: { filter: 'drop-shadow(0 0 6px rgba(212,255,58,0.6))', transition: 'stroke-dasharray .6s' } })] }), _jsxs("div", { className: "ring-label", children: [_jsxs("b", { children: [Math.round(pct * 100), "%"] }), _jsx("span", { children: label })] })] }));
}
export function Segmented({ value, options, onChange, }) {
    return (_jsx("div", { className: "segmented", role: "tablist", children: options.map((o) => (_jsx("button", { type: "button", role: "tab", "aria-selected": o.value === value, className: o.value === value ? 'on' : '', onClick: () => onChange(o.value), children: o.label }, String(o.value)))) }));
}
export function Empty({ title, children }) {
    return (_jsxs("div", { className: "card empty", children: [_jsx("h2", { style: { color: 'var(--ink)' }, children: title }), children] }));
}
/** A pickleball in SACS marigold. */
export function BallIcon({ size = 30, className }) {
    return (_jsxs("svg", { width: size, height: size, viewBox: "0 0 32 32", "aria-hidden": "true", className: className, children: [_jsx("defs", { children: _jsxs("radialGradient", { id: "ballShade", cx: "35%", cy: "30%", r: "75%", children: [_jsx("stop", { offset: "0%", stopColor: "#fff0b3" }), _jsx("stop", { offset: "55%", stopColor: "#ffb81c" }), _jsx("stop", { offset: "100%", stopColor: "#e07a00" })] }) }), _jsx("circle", { cx: "16", cy: "16", r: "15", fill: "url(#ballShade)" }), [
                [10, 8.5],
                [18, 6.5],
                [24, 12],
                [7.5, 16],
                [15, 14.5],
                [22.5, 20],
                [11.5, 23.5],
                [18.5, 25],
            ].map(([x, y], i) => (_jsx("circle", { cx: x, cy: y, r: "1.9", fill: "#8a3d00", opacity: "0.5" }, i)))] }));
}
/** Top-down court line art used as a background texture. */
export function CourtLines({ className = 'court-lines' }) {
    return (_jsx("svg", { className: className, viewBox: "0 0 880 400", preserveAspectRatio: "xMidYMid slice", "aria-hidden": "true", children: _jsxs("g", { fill: "none", stroke: "#fff", strokeWidth: "3", children: [_jsx("rect", { x: "40", y: "40", width: "800", height: "320" }), _jsx("line", { x1: "440", y1: "24", x2: "440", y2: "376", strokeWidth: "5", strokeDasharray: "2 6" }), _jsx("line", { x1: "313", y1: "40", x2: "313", y2: "360" }), _jsx("line", { x1: "567", y1: "40", x2: "567", y2: "360" }), _jsx("line", { x1: "40", y1: "200", x2: "313", y2: "200" }), _jsx("line", { x1: "567", y1: "200", x2: "840", y2: "200" })] }) }));
}
const AVATAR_COLORS = ['#8a2bb5', '#ff2e88', '#0f7b86', '#e85d04', '#c1121f', '#2a9d8f', '#7b2cbf', '#d97706', '#1d6fa5', '#b5179e'];
function hash(s) {
    let h = 0;
    for (let i = 0; i < s.length; i++)
        h = (h * 31 + s.charCodeAt(i)) | 0;
    return Math.abs(h);
}
export function initials(name) {
    const parts = name.trim().split(/\s+/).filter(Boolean);
    if (!parts.length)
        return '?';
    if (parts.length === 1)
        return parts[0].slice(0, 2).toUpperCase();
    return (parts[0][0] + parts[parts.length - 1][0]).toUpperCase();
}
export function Avatar({ name, size = 28 }) {
    return (_jsx("span", { className: "avatar", style: { ['--size']: `${size}px`, background: AVATAR_COLORS[hash(name) % AVATAR_COLORS.length] }, title: name, children: initials(name) }));
}
/** Overlapping player avatars for a team (or a dashed placeholder when unknown). */
export function TeamAvatars({ t, teamId, size = 28 }) {
    const team = teamId && teamId !== 'BYE' ? t.teams[teamId] : undefined;
    if (!team)
        return _jsx("span", { className: "tbd-dot", style: { width: size, height: size } });
    const names = team.playerIds.map((id) => t.players[id]?.name).filter((n) => !!n);
    if (!names.length)
        names.push(team.name);
    return (_jsx("span", { className: "avatars", children: names.slice(0, 2).map((n) => (_jsx(Avatar, { name: n, size: size }, n))) }));
}
export function minutesLabel(min) {
    if (min === undefined)
        return '';
    if (min <= 0)
        return 'Up now';
    if (min < 60)
        return `~${min} min`;
    const h = Math.floor(min / 60);
    const m = min % 60;
    return `~${h}h${m ? ` ${m}m` : ''}`;
}
export function timeAgo(ts) {
    if (!ts)
        return '';
    const s = Math.round((Date.now() - ts) / 1000);
    if (s < 60)
        return 'just now';
    if (s < 3600)
        return `${Math.floor(s / 60)} min ago`;
    return `${Math.floor(s / 3600)}h ago`;
}
/** Renders a name with the event wordmark (e.g. "SACS") set in the display font. */
export function BrandName({ name }) {
    const parts = name.split(BRAND.short);
    if (parts.length < 2)
        return _jsx(_Fragment, { children: name });
    return (_jsx(_Fragment, { children: parts.map((part, i) => (_jsxs("span", { children: [i > 0 && _jsx("span", { className: "wordmark", children: BRAND.short }), part] }, i))) }));
}
/** Marigold-and-mango-leaf garland (toran) used along the top of banners. */
export function Toran() {
    const petals = Array.from({ length: 8 }, (_, i) => {
        const a = (i / 8) * Math.PI * 2;
        return [Math.cos(a) * 5.5, Math.sin(a) * 5.5];
    });
    return (_jsxs("svg", { className: "toran", "aria-hidden": "true", preserveAspectRatio: "none", children: [_jsx("defs", { children: _jsxs("pattern", { id: "toranPattern", width: "64", height: "40", patternUnits: "userSpaceOnUse", children: [_jsx("path", { d: "M0 3 Q32 13 64 3", stroke: "#f7c873", strokeWidth: "1.5", fill: "none", opacity: "0.8" }), _jsx("path", { d: "M16 7 C11 13 12 21 16 26 C20 21 21 13 16 7 Z", fill: "#1f9d6b" }), _jsx("path", { d: "M48 7 C43 13 44 21 48 26 C52 21 53 13 48 7 Z", fill: "#178a5c" }), _jsx("line", { x1: "32", y1: "8", x2: "32", y2: "15", stroke: "#f7c873", strokeWidth: "1.2" }), _jsxs("g", { transform: "translate(32 22)", children: [petals.map(([x, y], i) => (_jsx("circle", { cx: x, cy: y, r: "4", fill: i % 2 ? '#ff9f1c' : '#ffb81c' }, i))), _jsx("circle", { r: "4.5", fill: "#f77f00" }), _jsx("circle", { r: "1.8", fill: "#ffd166" })] })] }) }), _jsx("rect", { width: "100%", height: "40", fill: "url(#toranPattern)" })] }));
}
/** Line-art mandala, drawn in currentColor. */
export function Mandala({ className = 'mandala' }) {
    const rings = [
        { n: 8, r: 62, rx: 16, ry: 40 },
        { n: 12, r: 112, rx: 13, ry: 32 },
        { n: 16, r: 158, rx: 10, ry: 24 },
        { n: 24, r: 196, rx: 6, ry: 13 },
    ];
    return (_jsxs("svg", { className: className, viewBox: "-225 -225 450 450", "aria-hidden": "true", children: [_jsxs("g", { fill: "none", stroke: "currentColor", strokeWidth: "2.2", children: [[24, 34, 88, 136, 180, 214].map((r) => (_jsx("circle", { r: r }, r))), rings.map((ring) => Array.from({ length: ring.n }, (_, i) => (_jsx("ellipse", { cx: "0", cy: -ring.r, rx: ring.rx, ry: ring.ry, transform: `rotate(${(360 / ring.n) * i})` }, `${ring.r}-${i}`))))] }), _jsx("g", { fill: "currentColor", children: Array.from({ length: 36 }, (_, i) => {
                    const a = (i / 36) * Math.PI * 2;
                    return _jsx("circle", { cx: Math.cos(a) * 205, cy: Math.sin(a) * 205, r: "3" }, i);
                }) })] }));
}
/** "Playing for a cause" card for the charity partner. */
export function CauseCard({ compact = false }) {
    return (_jsxs("div", { className: "cause", children: [_jsx("span", { className: "cause-icon", children: _jsx(HandHeart, { size: 22 }) }), _jsxs("div", { style: { minWidth: 0 }, children: [_jsxs("div", { className: "cause-title", children: ["Playing for ", BRAND.charity.name] }), _jsxs("div", { className: "cause-text", children: [BRAND.charity.pledge, !compact && ` ${BRAND.charity.blurb}`] })] }), _jsxs("div", { className: "row", style: { gap: 6, flexWrap: 'nowrap' }, children: [BRAND.donateUrl && (_jsxs("a", { className: "btn btn-sm btn-primary", href: BRAND.donateUrl, target: "_blank", rel: "noreferrer", children: ["Donate ", _jsx(ExternalLink, { size: 13 })] })), _jsxs("a", { className: "btn btn-sm", href: BRAND.charity.url, target: "_blank", rel: "noreferrer", children: ["Learn more ", _jsx(ExternalLink, { size: 13 })] })] })] }));
}
