import { Fragment as _Fragment, jsx as _jsx, jsxs as _jsxs } from "react/jsx-runtime";
import { useState } from 'react';
import { Pencil, Plus, Trash2 } from 'lucide-react';
import { BRAND } from '../brand';
import { remote } from '../lib/sync';
import { Modal } from './ui';
const DIVISIONS = ['Adults', 'Kids/Teens'];
const PAYMENTS = ['Zelle', 'Venmo', 'Cash at check-in'];
const BLANK = {
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
/** Read one sheet row back into the form's shape, by column title. */
export function rowToEntry(header, row) {
    const get = (title) => String(row[header.indexOf(title)] ?? '').trim();
    const paid = get('Payment confirmed');
    const payment = get('Payment method');
    return {
        name: get('Full name'),
        email: get('Email'),
        phone: get('Phone number'),
        school: get('School'),
        division: (DIVISIONS.includes(get('Division')) ? get('Division') : ''),
        partnerName: get("Partner's full name"),
        partnerEmail: get("Partner's email"),
        notes: get('Anything else we should know?'),
        payment: (PAYMENTS.includes(payment) ? payment : ''),
        paid: /^yes/i.test(paid),
        donation: Number(get('Extra donation').replace(/[^0-9.]/g, '')) || 0,
        anonymous: /^yes/i.test(get('Anonymous')),
    };
}
/** Add or edit one sign-up by hand. */
export function SignupDialog({ url, passcode, target, onClose, onSaved, }) {
    const [form, setForm] = useState({ ...BLANK, ...target.entry });
    const [busy, setBusy] = useState(false);
    const [error, setError] = useState(null);
    const set = (p) => setForm((f) => ({ ...f, ...p }));
    const editing = target.row !== undefined;
    const players = form.partnerName?.trim() ? 2 : 1;
    const due = players * BRAND.payment.feeAmount + (form.donation || 0);
    const save = async () => {
        setError(null);
        if (!form.name.trim())
            return setError('Enter a name.');
        if (!form.division)
            return setError('Choose a division.');
        setBusy(true);
        try {
            if (editing)
                await remote.editRegistration(url, passcode, target.row, target.stamp ?? '', form);
            else
                await remote.addRegistration(url, passcode, form);
            onSaved();
            onClose();
        }
        catch (e) {
            setError(e.message);
        }
        finally {
            setBusy(false);
        }
    };
    return (_jsx(Modal, { title: editing ? `Edit ${target.entry.name || 'sign-up'}` : 'Add a sign-up', subtitle: "Saved straight to the sign-up sheet.", onClose: onClose, wide: true, children: _jsxs("div", { className: "stack", style: { gap: 12 }, children: [_jsxs("div", { className: "form-grid", children: [_jsxs("label", { className: "field", children: ["Full name *", _jsx("input", { className: "input", value: form.name, onChange: (e) => set({ name: e.target.value }), autoFocus: true })] }), _jsxs("label", { className: "field", children: ["Email", _jsx("input", { className: "input", type: "email", value: form.email, onChange: (e) => set({ email: e.target.value }) })] }), _jsxs("label", { className: "field", children: ["Phone", _jsx("input", { className: "input", value: form.phone, onChange: (e) => set({ phone: e.target.value }) })] }), _jsxs("label", { className: "field", children: ["School", _jsx("input", { className: "input", value: form.school, onChange: (e) => set({ school: e.target.value }) })] }), _jsxs("label", { className: "field", children: ["Division *", _jsxs("select", { className: "input", value: form.division, onChange: (e) => set({ division: e.target.value }), children: [_jsx("option", { value: "", children: "Choose\u2026" }), DIVISIONS.map((d) => (_jsx("option", { children: d }, d)))] })] }), _jsxs("label", { className: "field", children: ["Partner\u2019s full name", _jsx("input", { className: "input", value: form.partnerName, onChange: (e) => set({ partnerName: e.target.value }), placeholder: "Blank = needs a partner" })] }), _jsxs("label", { className: "field", children: ["Partner\u2019s email", _jsx("input", { className: "input", type: "email", value: form.partnerEmail, onChange: (e) => set({ partnerEmail: e.target.value }) })] }), _jsxs("label", { className: "field", children: ["Paying by", _jsxs("select", { className: "input", value: form.payment, onChange: (e) => set({ payment: e.target.value }), children: [_jsx("option", { value: "", children: "Not sure yet" }), PAYMENTS.map((p) => (_jsx("option", { children: p }, p)))] })] }), _jsxs("label", { className: "field", children: ["Extra donation ($)", _jsx("input", { className: "input", inputMode: "decimal", value: form.donation || '', onChange: (e) => set({ donation: Number(e.target.value.replace(/[^0-9.]/g, '')) || 0 }) })] })] }), _jsxs("label", { className: "field", children: ["Notes", _jsx("input", { className: "input", value: form.notes, onChange: (e) => set({ notes: e.target.value }) })] }), _jsxs("label", { className: "check", style: { fontWeight: 600 }, children: [_jsx("input", { type: "checkbox", checked: form.paid, onChange: (e) => set({ paid: e.target.checked }) }), "Paid $", due, " ($", BRAND.payment.feeAmount, " per person \u00D7 ", players, form.donation ? ` + $${form.donation} extra` : '', ")"] }), _jsxs("label", { className: "check", children: [_jsx("input", { type: "checkbox", checked: !!form.anonymous, onChange: (e) => set({ anonymous: e.target.checked }) }), "Show as \u201CAnonymous\u201D on the donations list"] }), error && _jsx("div", { className: "alert alert-error small", children: error }), _jsxs("div", { className: "row", children: [_jsx("button", { className: "btn btn-primary", disabled: busy, onClick: () => void save(), children: busy ? 'Saving…' : editing ? 'Save changes' : 'Add sign-up' }), _jsx("button", { className: "btn btn-ghost", onClick: onClose, children: "Cancel" })] })] }) }));
}
/** The sign-up list with edit and delete on every row, plus "Add a sign-up". */
export function SignupTable({ url, passcode, rows, onChanged, }) {
    const [target, setTarget] = useState(null);
    const [error, setError] = useState(null);
    const header = rows[0] ?? [];
    const col = (title) => header.indexOf(title);
    const body = rows.slice(1);
    const remove = async (row, r) => {
        if (!window.confirm(`Delete ${r[col('Full name')]}'s sign-up? This removes the row from the sheet.`))
            return;
        setError(null);
        try {
            await remote.deleteRegistration(url, passcode, row, r[0]);
            onChanged();
        }
        catch (e) {
            setError(e.message);
        }
    };
    return (_jsxs(_Fragment, { children: [_jsxs("div", { className: "row", style: { margin: '12px 0 8px' }, children: [_jsxs("button", { className: "btn btn-primary btn-sm", onClick: () => setTarget({ entry: BLANK }), children: [_jsx(Plus, { size: 15 }), " Add a sign-up"] }), _jsx("span", { className: "small muted", children: "Walk-ups, phone sign-ups, anyone. Works even when registration is closed." })] }), error && _jsx("div", { className: "alert alert-error small", children: error }), _jsx("div", { className: "table-wrap", children: body.length === 0 ? (_jsx("div", { className: "muted small", children: "No sign-ups yet." })) : (_jsxs("table", { className: "table signup-table", children: [_jsx("thead", { children: _jsxs("tr", { children: [_jsx("th", { children: "Name" }), _jsx("th", { children: "Partner" }), _jsx("th", { children: "Division" }), _jsx("th", { children: "Paid" }), _jsx("th", { children: "Owes" }), _jsx("th", { "aria-label": "Actions" })] }) }), _jsx("tbody", { children: body
                                .map((r, i) => ({ r, row: i + 1 }))
                                .reverse()
                                .map(({ r, row }) => {
                                const e = rowToEntry(header, r);
                                const players = e.partnerName ? 2 : 1;
                                return (_jsxs("tr", { children: [_jsx("td", { className: "bold", children: e.name }), _jsx("td", { children: e.partnerName || _jsx("span", { className: "muted", children: "Needs a partner" }) }), _jsx("td", { children: e.division }), _jsxs("td", { className: "small", children: [r[col('Payment confirmed')] || '—', e.payment ? _jsx("div", { className: "tiny muted", children: e.payment }) : null] }), _jsxs("td", { className: "small", children: ["$", players * BRAND.payment.feeAmount + (e.donation || 0), _jsxs("div", { className: "tiny muted", children: ["$", BRAND.payment.feeAmount, " \u00D7 ", players, e.donation ? ` + $${e.donation}` : ''] })] }), _jsx("td", { children: _jsxs("div", { className: "row", style: { gap: 4, flexWrap: 'nowrap' }, children: [_jsx("button", { className: "btn btn-ghost btn-sm", "aria-label": `Edit ${e.name}`, onClick: () => setTarget({ row, stamp: r[0], entry: e }), children: _jsx(Pencil, { size: 15 }) }), _jsx("button", { className: "btn btn-ghost btn-sm", "aria-label": `Delete ${e.name}`, onClick: () => void remove(row, r), children: _jsx(Trash2, { size: 15 }) })] }) })] }, `${row}-${r[0]}`));
                            }) })] })) }), target && _jsx(SignupDialog, { url: url, passcode: passcode, target: target, onClose: () => setTarget(null), onSaved: onChanged })] }));
}
