import { jsx as _jsx, jsxs as _jsxs } from "react/jsx-runtime";
import { useState } from 'react';
import { CheckCircle2 } from 'lucide-react';
import { BRAND } from '../brand';
import { remote } from '../lib/sync';
import { useStore } from '../state/store';
const AMOUNTS = ['$10', '$25', '$50', '$100', 'Other'];
const METHODS = [
    { value: 'Zelle', hint: BRAND.payment.zelle },
    { value: 'Venmo', hint: BRAND.payment.venmo },
    { value: 'Cash at check-in', hint: 'Pay on the day' },
];
const emailOk = (v) => /^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(v.trim());
/** Give without playing. Saved apart from sign-ups, counted in the fundraising total. */
export function DonateForm({ onDone }) {
    const { sync } = useStore();
    const [name, setName] = useState('');
    const [email, setEmail] = useState('');
    const [choice, setChoice] = useState('$25');
    const [other, setOther] = useState('');
    const [payment, setPayment] = useState('');
    const [anonymous, setAnonymous] = useState(false);
    const [paid, setPaid] = useState(false);
    const [honeypot, setHoneypot] = useState('');
    const [busy, setBusy] = useState(false);
    const [error, setError] = useState(null);
    const [done, setDone] = useState(null);
    const amount = choice === 'Other' ? Number(other) || 0 : Number(choice.replace('$', ''));
    const submit = async () => {
        setError(null);
        if (!name.trim())
            return setError('Please enter your name.');
        if (!emailOk(email))
            return setError('Please enter a valid email.');
        if (!(amount > 0))
            return setError('Please enter a donation amount.');
        if (!payment)
            return setError('Please choose a payment method.');
        if (!paid)
            return setError('Please confirm your donation.');
        if (!sync)
            return;
        setBusy(true);
        try {
            await remote.donate(sync.url, { name, email, amount, payment, paid, anonymous }, honeypot);
            setDone(amount);
            onDone?.();
            window.scrollTo({ top: 0 });
        }
        catch (e) {
            setError(e.message || 'Something went wrong. Please try again.');
        }
        finally {
            setBusy(false);
        }
    };
    if (done !== null) {
        return (_jsxs("div", { className: "card register-done", children: [_jsx(CheckCircle2, { size: 44, color: "var(--win)" }), _jsxs("h2", { children: ["Thank you, ", name.trim().split(' ')[0]] }), _jsxs("p", { className: "muted", children: ["Your $", done, " donation supports SACS and the ", BRAND.charity.name, "."] }), _jsx("div", { className: "row", style: { justifyContent: 'center' }, children: _jsx("a", { className: "btn btn-primary", href: "#/", children: "Back to home" }) })] }));
    }
    return (_jsxs("form", { className: "stack register-form", style: { gap: 14 }, noValidate: true, onSubmit: (e) => {
            e.preventDefault();
            void submit();
        }, children: [_jsxs("div", { className: "card", children: [_jsx("h2", { children: "Your details" }), _jsxs("div", { className: "form-grid", children: [_jsxs("label", { className: "field", children: ["Full name *", _jsx("input", { className: "input", autoComplete: "name", value: name, onChange: (e) => setName(e.target.value) })] }), _jsxs("label", { className: "field", children: ["Email *", _jsx("input", { className: "input", type: "email", autoComplete: "email", value: email, onChange: (e) => setEmail(e.target.value) })] })] })] }), _jsxs("div", { className: "card", children: [_jsx("h2", { children: "Donation" }), _jsxs("div", { className: "field", children: ["Amount *", _jsx("div", { className: "choice-grid compact", role: "radiogroup", "aria-label": "Amount", children: AMOUNTS.map((a) => (_jsxs("label", { className: `choice ${choice === a ? 'on' : ''}`, children: [_jsx("input", { type: "radio", name: "amount", checked: choice === a, onChange: () => { setChoice(a); setPaid(false); } }), _jsx("span", { className: "choice-title", children: a })] }, a))) }), choice === 'Other' && (_jsx("input", { className: "input", style: { marginTop: 8, maxWidth: 200 }, inputMode: "decimal", placeholder: "$ amount", "aria-label": "Other amount", value: other, onChange: (e) => { setOther(e.target.value.replace(/[^0-9.]/g, '').slice(0, 7)); setPaid(false); } }))] }), _jsxs("label", { className: "check", style: { marginTop: 12 }, children: [_jsx("input", { type: "checkbox", checked: anonymous, onChange: (e) => setAnonymous(e.target.checked) }), "List my donation as anonymous (optional)"] }), _jsxs("div", { className: "field", style: { marginTop: 14 }, children: ["Payment method *", _jsx("div", { className: "choice-grid", role: "radiogroup", "aria-label": "Payment method", children: METHODS.map((m) => (_jsxs("label", { className: `choice ${payment === m.value ? 'on' : ''}`, children: [_jsx("input", { type: "radio", name: "donate-payment", checked: payment === m.value, onChange: () => { setPayment(m.value); setPaid(false); } }), _jsx("span", { className: "choice-title", children: m.value }), m.hint && _jsx("span", { className: "choice-hint", children: m.hint })] }, m.value))) })] }), amount > 0 && (_jsxs("div", { className: "total-box", style: { marginTop: 14 }, children: [_jsxs("div", { className: "total-line total-sum", children: [_jsx("span", { children: "Total" }), _jsxs("b", { children: ["$", amount] })] }), _jsxs("div", { className: "total-note", children: ["Please include ", _jsxs("b", { children: [name.trim() || 'your name', " \u2013 SACS donation"] }), " in the payment note."] })] })), _jsxs("label", { className: "check", style: { marginTop: 12, fontWeight: 600 }, children: [_jsx("input", { type: "checkbox", checked: paid, onChange: (e) => setPaid(e.target.checked) }), payment === 'Cash at check-in'
                                ? `I’ll pay $${amount || 0} in cash at the event. *`
                                : `I’ve sent $${amount || 0}${payment ? ` via ${payment}` : ''}. *`] })] }), _jsx("div", { className: "hp", "aria-hidden": "true", children: _jsxs("label", { children: ["Website", _jsx("input", { tabIndex: -1, autoComplete: "off", value: honeypot, onChange: (e) => setHoneypot(e.target.value) })] }) }), error && _jsx("div", { className: "alert alert-error", children: error }), _jsx("div", { className: "row", children: _jsx("button", { className: "btn btn-primary btn-lg", type: "submit", disabled: busy, children: busy ? 'Submitting…' : 'Donate' }) })] }));
}
