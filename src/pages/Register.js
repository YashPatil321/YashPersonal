import { Fragment as _Fragment, jsx as _jsx, jsxs as _jsxs } from "react/jsx-runtime";
import { useState } from 'react';
import { CheckCircle2, HandHeart, Users } from 'lucide-react';
import { BRAND } from '../brand';
import { remote } from '../lib/sync';
import { FundraiserSidebar } from '../components/Fundraiser';
import { CauseCard } from '../components/ui';
import { useStore } from '../state/store';
import { useEventInfo } from '../state/useEventInfo';
export const DIVISIONS = [{ value: 'Adults' }, { value: 'Kids/Teens' }];
export const DONATION_CHOICES = ['No thanks', '$10', '$25', '$50', 'Other'];
export const PAYMENT_METHODS = [
    { value: 'Zelle' },
    { value: 'Venmo' },
    { value: 'Cash at check-in' },
];
const EMPTY = {
    name: '',
    email: '',
    phone: '',
    school: '',
    division: '',
    partnerName: '',
    partnerEmail: '',
    notes: '',
    payment: '',
    paid: false,
    donation: 0,
    anonymous: false,
};
const emailOk = (v) => /^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(v.trim());
function Choices({ name, value, options, onChange, allowClear, compact, }) {
    return (_jsx("div", { className: `choice-grid ${compact ? 'compact' : ''}`, role: "radiogroup", "aria-label": name, children: options.map((o) => (_jsxs("label", { className: `choice ${value === o.value ? 'on' : ''}`, children: [_jsx("input", { type: "radio", name: name, value: o.value, checked: value === o.value, onChange: () => onChange(o.value), onClick: () => allowClear && value === o.value && onChange('') }), _jsx("span", { className: "choice-title", children: o.value }), o.hint && _jsx("span", { className: "choice-hint", children: o.hint })] }, o.value))) }));
}
function Hero({ children }) {
    return (_jsxs("section", { className: "photo-banner", style: { marginBottom: 16 }, children: [_jsx("img", { src: "./photos/sacs-cast.webp", alt: "The SACS 2026 cast on stage after the show" }), _jsxs("div", { className: "photo-banner-text", children: [_jsx("div", { className: "eyebrow", children: BRAND.eventName }), _jsx("h1", { children: "Register & donate" }), _jsx("div", { className: "photo-banner-sub", children: children })] })] }));
}
export function Register() {
    const { t, sync, isAdmin } = useStore();
    const { info, loading, refresh } = useEventInfo();
    const [form, setForm] = useState(EMPTY);
    const [honeypot, setHoneypot] = useState('');
    const [donationChoice, setDonationChoice] = useState('No thanks');
    const [customDonation, setCustomDonation] = useState('');
    const [busy, setBusy] = useState(false);
    const [error, setError] = useState(null);
    const [done, setDone] = useState(null);
    const set = (p) => setForm((f) => ({ ...f, ...p }));
    const intro = (_jsxs(_Fragment, { children: ["Doubles, Adults & Kids/Teens. Sign up as a pair or on your own (we\u2019ll match you), with a $", BRAND.payment.feeAmount, " donation per player. ", BRAND.charity.pledge] }));
    // Closed / not ready states
    let closed = null;
    if (t) {
        closed = (_jsxs(_Fragment, { children: [_jsx("h2", { children: "The draw is out!" }), _jsx("p", { className: "muted", children: "Registration is closed. Find your team to see your court and when you play." }), _jsxs("a", { className: "btn btn-primary", href: "#/teams", children: [_jsx(Users, { size: 16 }), " Find my team"] })] }));
    }
    else if (!sync) {
        closed = (_jsxs(_Fragment, { children: [_jsx("h2", { children: "Registration opens soon" }), _jsx("p", { className: "muted", children: "Check back shortly. This page will take sign-ups as soon as the SACS team opens registration." }), isAdmin && (_jsx("a", { className: "btn btn-primary", href: "#/admin", children: "Organizers: finish setup to open registration" }))] }));
    }
    else if (!loading && info && !info.registrationOpen) {
        closed = (_jsxs(_Fragment, { children: [_jsx("h2", { children: "Registration is closed" }), _jsx("p", { className: "muted", children: "Sign-ups are closed for now. Questions? Reach out to the SACS team." })] }));
    }
    if (closed) {
        return (_jsxs(_Fragment, { children: [_jsx(Hero, { children: intro }), _jsx("div", { className: "card empty", style: { color: 'var(--ink)' }, children: closed }), _jsx("div", { style: { marginTop: 16 }, children: _jsx(CauseCard, { compact: true }) })] }));
    }
    if (done) {
        return (_jsxs(_Fragment, { children: [_jsx(Hero, { children: intro }), _jsxs("div", { className: "card register-done", children: [_jsx(CheckCircle2, { size: 44, color: "var(--win)" }), _jsxs("h2", { children: ["You\u2019re in, ", done.name.split(' ')[0], "!"] }), _jsxs("p", { className: "muted", children: [done.partner ? `You and ${done.partner} are registered.` : 'You’re registered. We’ll pair you with a partner.', ' ', "Thank you for playing for the ", BRAND.charity.name, done.donation ? `, and for your extra $${done.donation} donation` : '', "."] }), done.count ? _jsxs("p", { className: "small bold", children: [done.count, " sign-ups so far"] }) : null, _jsxs("div", { className: "row", style: { justifyContent: 'center' }, children: [_jsx("button", { className: "btn", onClick: () => {
                                        setDone(null);
                                        setForm(EMPTY);
                                        setDonationChoice('No thanks');
                                        setCustomDonation('');
                                    }, children: "Register another team" }), _jsx("a", { className: "btn btn-primary", href: "#/", children: "Back to home" })] })] })] }));
    }
    const players = form.partnerName?.trim() ? 2 : 1;
    const amountDue = BRAND.payment.feeAmount * players + (form.donation ?? 0);
    const names = [form.name.trim(), form.partnerName?.trim()].filter(Boolean).join(' & ');
    const noteText = `${names || 'your name'} – SACS Pickleball`;
    const submit = async () => {
        setError(null);
        if (!form.name.trim())
            return setError('Please enter your full name.');
        if (!emailOk(form.email))
            return setError('Please enter a valid email.');
        if (!form.division)
            return setError('Please choose Adults or Kids/Teens.');
        if (!form.payment)
            return setError('Please choose how you’re sending your donation.');
        if (!form.paid)
            return setError('Please confirm your donation.');
        if (donationChoice === 'Other' && !(form.donation && form.donation > 0))
            return setError('Enter a donation amount, or choose “No thanks”.');
        if (form.partnerEmail && !emailOk(form.partnerEmail))
            return setError('Please check your partner’s email.');
        if (!sync)
            return;
        setBusy(true);
        try {
            const res = await remote.register(sync.url, form, honeypot);
            setDone({ name: form.name.trim(), partner: form.partnerName?.trim() || undefined, count: res.count, donation: form.donation });
            refresh();
            window.scrollTo({ top: 0 });
        }
        catch (e) {
            setError(e.message || 'Something went wrong. Please try again.');
        }
        finally {
            setBusy(false);
        }
    };
    const toForm = () => document.getElementById('register-form')?.scrollIntoView({ behavior: 'smooth', block: 'start' });
    return (_jsxs("div", { className: "gf-page", children: [_jsxs("h1", { className: "gf-title", children: [BRAND.eventName, ": play for SACS & Akshaya Patra"] }), _jsx("figure", { className: "gf-photo", children: _jsx("img", { src: "./photos/sacs-cast.webp", alt: "The SACS 2026 cast on stage after the show" }) }), _jsx("aside", { className: "gf-side", children: _jsx(FundraiserSidebar, { info: info, onDonate: toForm }) }), _jsxs("div", { className: "gf-main", children: [_jsxs("div", { className: "gf-organizer", children: [_jsx("span", { className: "gf-avatar", children: _jsx(HandHeart, { size: 20 }) }), _jsxs("div", { className: "small", children: [_jsx("b", { children: "South Asian Culture Show" }), " is organizing this fundraiser for the", ' ', _jsx("a", { href: BRAND.charity.url, target: "_blank", rel: "noreferrer", children: BRAND.charity.name }), "."] })] }), _jsxs("div", { className: "gf-story", children: [_jsxs("p", { children: ["Grab a partner (or come solo and we\u2019ll pair you) and play in the ", BRAND.eventName, ": ", BRAND.courts, " courts, about", ' ', BRAND.hours, " hours of doubles, with an Adults division and a Kids/Teens division."] }), _jsxs("p", { children: ["Every player gives a required $", BRAND.payment.feeAmount, " donation, and you can add more if you\u2019d like. ", BRAND.charity.pledge, ' ', BRAND.charity.blurb] })] }), _jsx("h2", { id: "register-form", className: "gf-form-title", children: "Register & donate" }), _jsxs("form", { className: "stack register-form", style: { gap: 14 }, onSubmit: (e) => {
                            e.preventDefault();
                            void submit();
                        }, noValidate: true, children: [_jsxs("div", { className: "card", children: [_jsx("h2", { children: "You" }), _jsxs("div", { className: "form-grid", children: [_jsxs("label", { className: "field", children: ["Full name *", _jsx("input", { className: "input", autoComplete: "name", value: form.name, onChange: (e) => set({ name: e.target.value }) })] }), _jsxs("label", { className: "field", children: ["Email *", _jsx("input", { className: "input", type: "email", autoComplete: "email", value: form.email, onChange: (e) => set({ email: e.target.value }) })] }), _jsxs("label", { className: "field", children: ["Phone number", _jsx("input", { className: "input", type: "tel", autoComplete: "tel", value: form.phone, onChange: (e) => set({ phone: e.target.value }) }), _jsx("span", { className: "hint", children: "In case we need to reach you on tournament day." })] }), _jsxs("label", { className: "field", children: ["School", _jsx("input", { className: "input", value: form.school, onChange: (e) => set({ school: e.target.value }) })] })] }), _jsxs("div", { className: "field", style: { marginTop: 14 }, children: ["Division *", _jsx(Choices, { name: "Division", value: form.division, onChange: (v) => set({ division: v }), options: DIVISIONS })] })] }), _jsxs("div", { className: "card", children: [_jsx("h2", { children: "Your partner" }), _jsx("p", { className: "muted small", style: { marginTop: -4 }, children: "Optional. Leave this blank and we\u2019ll pair you with someone. Only one of you needs to register." }), _jsxs("div", { className: "form-grid", children: [_jsxs("label", { className: "field", children: ["Partner\u2019s full name", _jsx("input", { className: "input", value: form.partnerName, onChange: (e) => set({ partnerName: e.target.value }) })] }), _jsxs("label", { className: "field", children: ["Partner\u2019s email", _jsx("input", { className: "input", type: "email", value: form.partnerEmail, onChange: (e) => set({ partnerEmail: e.target.value }) })] })] })] }), _jsxs("div", { className: "card", children: [_jsx("h2", { children: "Extras" }), _jsxs("label", { className: "field", children: ["Anything else we should know?", _jsx("textarea", { className: "input", style: { minHeight: 80, fontFamily: 'inherit', fontSize: '0.95rem' }, value: form.notes, onChange: (e) => set({ notes: e.target.value }) })] }), _jsx("input", { className: "hp", tabIndex: -1, autoComplete: "off", "aria-hidden": "true", name: "website", value: honeypot, onChange: (e) => setHoneypot(e.target.value) })] }), _jsxs("div", { className: "card", children: [_jsx("h2", { children: "Your donation" }), _jsxs("p", { className: "muted small", style: { marginTop: -4 }, children: ["Required: ", _jsxs("b", { children: ["$", BRAND.payment.feeAmount, " per player"] }), " ($", BRAND.payment.feeAmount * 2, " for a pair).", ' ', BRAND.charity.pledge] }), _jsxs("div", { className: "field", style: { marginBottom: 14 }, children: ["Want to give more? (optional)", _jsx("span", { className: "hint", children: "Add it to your required donation and send it all as one payment." }), _jsx(Choices, { name: "Extra donation", value: donationChoice, onChange: (v) => {
                                                    setDonationChoice(v);
                                                    if (v === 'Other')
                                                        set({ donation: Number(customDonation) || 0, paid: false });
                                                    else
                                                        set({ donation: v === 'No thanks' ? 0 : Number(v.replace('$', '')), paid: false });
                                                }, options: DONATION_CHOICES.map((value) => ({ value })), compact: true }), donationChoice === 'Other' && (_jsx("input", { className: "input", style: { marginTop: 8, maxWidth: 200 }, inputMode: "decimal", placeholder: "$ amount", "aria-label": "Other donation amount", value: customDonation, onChange: (e) => {
                                                    const v = e.target.value.replace(/[^0-9.]/g, '').slice(0, 7);
                                                    setCustomDonation(v);
                                                    set({ donation: Number(v) || 0, paid: false });
                                                } }))] }), _jsxs("div", { className: "alert alert-ok small", style: { marginBottom: 12 }, children: ["Total to send: ", _jsxs("b", { children: ["$", amountDue] }), _jsxs("span", { className: "muted", children: [' ', "($", BRAND.payment.feeAmount, " \u00D7 ", players, " ", players === 1 ? 'player' : 'players', form.donation ? ` + $${form.donation} extra` : '', ")"] }), _jsxs("div", { style: { marginTop: 4 }, children: ["In the Zelle/Venmo note, write", ' ', _jsx("b", { children: noteText }), "."] })] }), _jsxs("ul", { className: "small pay-list", children: [_jsxs("li", { children: [_jsx("b", { children: "Zelle" }), BRAND.payment.zelle ? ` to ${BRAND.payment.zelle}` : ''] }), _jsxs("li", { children: [_jsx("b", { children: "Venmo" }), BRAND.payment.venmo ? ` ${BRAND.payment.venmo}` : ''] }), _jsxs("li", { children: [_jsx("b", { children: "Cash" }), " at check-in"] })] }), _jsxs("div", { className: "field", style: { marginTop: 10 }, children: ["How are you sending it? *", _jsx(Choices, { name: "Payment method", value: form.payment, onChange: (v) => set({ payment: v, paid: false }), options: PAYMENT_METHODS })] }), _jsxs("label", { className: "check", style: { marginTop: 14 }, children: [_jsx("input", { type: "checkbox", checked: !!form.anonymous, onChange: (e) => set({ anonymous: e.target.checked }) }), "Show me as \u201CAnonymous\u201D on the donations list"] }), _jsxs("label", { className: "check", style: { marginTop: 10, fontWeight: 600 }, children: [_jsx("input", { type: "checkbox", checked: form.paid, onChange: (e) => set({ paid: e.target.checked }) }), form.payment === 'Cash at check-in'
                                                ? `I’ll bring $${amountDue} in cash to check-in. *`
                                                : `I’ve sent $${amountDue}${form.payment ? ` by ${form.payment}` : ''} with my name in the note. *`] })] }), error && _jsx("div", { className: "alert alert-error", children: error }), _jsx("div", { className: "row", children: _jsx("button", { className: "btn btn-primary btn-lg", type: "submit", disabled: busy, children: busy ? 'Registering…' : 'Register' }) })] })] })] }));
}
