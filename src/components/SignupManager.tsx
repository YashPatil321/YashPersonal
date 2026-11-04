import { useState } from 'react';
import { Pencil, Plus, Trash2 } from 'lucide-react';
import { BRAND } from '../brand';
import { remote } from '../lib/sync';
import type { RegistrationEntry } from '../lib/sync';
import { Modal } from './ui';

const DIVISIONS: RegistrationEntry['division'][] = ['Adults', 'Kids/Teens'];
const PAYMENTS: RegistrationEntry['payment'][] = ['Zelle', 'Venmo', 'Cash at check-in'];

const BLANK: RegistrationEntry = {
  name: '',
  email: '',
  phone: '',
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
export function rowToEntry(header: string[], row: string[]): RegistrationEntry {
  const get = (title: string) => String(row[header.indexOf(title)] ?? '').trim();
  const paid = get('Payment confirmed');
  const payment = get('Payment method');
  return {
    name: get('Full name'),
    email: get('Email'),
    phone: get('Phone number'),
    division: (DIVISIONS.includes(get('Division') as RegistrationEntry['division']) ? get('Division') : '') as RegistrationEntry['division'],
    partnerName: get("Partner's full name"),
    partnerEmail: get("Partner's email"),
    notes: get('Anything else we should know?'),
    payment: (PAYMENTS.includes(payment as RegistrationEntry['payment']) ? payment : '') as RegistrationEntry['payment'],
    paid: /^yes/i.test(paid),
    donation: Number(get('Extra donation').replace(/[^0-9.]/g, '')) || 0,
    anonymous: /^yes/i.test(get('Anonymous')),
    partnerSeparate: /^yes/i.test(get('Partner pays separately')),
  };
}

export interface SignupTarget {
  /** 1 = first sign-up; undefined = new sign-up. */
  row?: number;
  stamp?: string;
  entry: RegistrationEntry;
}

/** Add or edit one sign-up by hand. */
export function SignupDialog({
  url,
  passcode,
  target,
  onClose,
  onSaved,
}: {
  url: string;
  passcode: string;
  target: SignupTarget;
  onClose: () => void;
  onSaved: () => void;
}) {
  const [form, setForm] = useState<RegistrationEntry>({ ...BLANK, ...target.entry });
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const set = (p: Partial<RegistrationEntry>) => setForm((f) => ({ ...f, ...p }));
  const editing = target.row !== undefined;
  const players = form.partnerName?.trim() && !form.partnerSeparate ? 2 : 1;
  const due = players * BRAND.payment.feeAmount + (form.donation || 0);

  const save = async () => {
    setError(null);
    if (!form.name.trim()) return setError('Enter a name.');
    if (!form.division) return setError('Choose a division.');
    setBusy(true);
    try {
      if (editing) await remote.editRegistration(url, passcode, target.row!, target.stamp ?? '', form);
      else await remote.addRegistration(url, passcode, form);
      onSaved();
      onClose();
    } catch (e) {
      setError((e as Error).message);
    } finally {
      setBusy(false);
    }
  };

  return (
    <Modal title={editing ? `Edit ${target.entry.name || 'sign-up'}` : 'Add a sign-up'} subtitle="Saved straight to the sign-up sheet." onClose={onClose} wide>
      <div className="stack" style={{ gap: 12 }}>
        <div className="form-grid">
          <label className="field">
            Full name *
            <input className="input" value={form.name} onChange={(e) => set({ name: e.target.value })} autoFocus />
          </label>
          <label className="field">
            Email
            <input className="input" type="email" value={form.email} onChange={(e) => set({ email: e.target.value })} />
          </label>
          <label className="field">
            Phone
            <input className="input" value={form.phone} onChange={(e) => set({ phone: e.target.value })} />
          </label>
          <label className="field">
            Division *
            <select className="input" value={form.division} onChange={(e) => set({ division: e.target.value as RegistrationEntry['division'] })}>
              <option value="">Choose…</option>
              {DIVISIONS.map((d) => (
                <option key={d}>{d}</option>
              ))}
            </select>
          </label>
          <label className="field">
            Partner’s full name
            <input className="input" value={form.partnerName} onChange={(e) => set({ partnerName: e.target.value })} placeholder="Blank = needs a partner" />
          </label>
          <label className="field">
            Partner’s email
            <input className="input" type="email" value={form.partnerEmail} onChange={(e) => set({ partnerEmail: e.target.value })} />
          </label>
          <label className="field">
            Paying by
            <select className="input" value={form.payment} onChange={(e) => set({ payment: e.target.value as RegistrationEntry['payment'] })}>
              <option value="">Not sure yet</option>
              {PAYMENTS.map((p) => (
                <option key={p}>{p}</option>
              ))}
            </select>
          </label>
          <label className="field">
            Extra donation ($)
            <input
              className="input"
              inputMode="decimal"
              value={form.donation || ''}
              onChange={(e) => set({ donation: Number(e.target.value.replace(/[^0-9.]/g, '')) || 0 })}
            />
          </label>
        </div>
        <label className="field">
          Notes
          <input className="input" value={form.notes} onChange={(e) => set({ notes: e.target.value })} />
        </label>
        <label className="check" style={{ fontWeight: 600 }}>
          <input type="checkbox" checked={form.paid} onChange={(e) => set({ paid: e.target.checked })} />
          Paid ${due} (${BRAND.payment.feeAmount} per person × {players}
          {form.donation ? ` + $${form.donation} extra` : ''})
        </label>
        {form.partnerName?.trim() && (
          <label className="check">
            <input type="checkbox" checked={!!form.partnerSeparate} onChange={(e) => set({ partnerSeparate: e.target.checked })} />
            Their partner signs up and pays on their own
          </label>
        )}
        <label className="check">
          <input type="checkbox" checked={!!form.anonymous} onChange={(e) => set({ anonymous: e.target.checked })} />
          Show as “Anonymous” on the donations list
        </label>
        {error && <div className="alert alert-error small">{error}</div>}
        <div className="row">
          <button className="btn btn-primary" disabled={busy} onClick={() => void save()}>
            {busy ? 'Saving…' : editing ? 'Save changes' : 'Add sign-up'}
          </button>
          <button className="btn btn-ghost" onClick={onClose}>
            Cancel
          </button>
        </div>
      </div>
    </Modal>
  );
}

/** The sign-up list with edit and delete on every row, plus "Add a sign-up". */
export function SignupTable({
  url,
  passcode,
  rows,
  onChanged,
}: {
  url: string;
  passcode: string;
  rows: string[][];
  onChanged: () => void;
}) {
  const [target, setTarget] = useState<SignupTarget | null>(null);
  const [error, setError] = useState<string | null>(null);
  const header = rows[0] ?? [];
  const col = (title: string) => header.indexOf(title);
  const body = rows.slice(1);

  const remove = async (row: number, r: string[]) => {
    if (!window.confirm(`Delete ${r[col('Full name')]}'s sign-up? This removes the row from the sheet.`)) return;
    setError(null);
    try {
      await remote.deleteRegistration(url, passcode, row, r[0]);
      onChanged();
    } catch (e) {
      setError((e as Error).message);
    }
  };

  return (
    <>
      <div className="row" style={{ margin: '12px 0 8px' }}>
        <button className="btn btn-primary btn-sm" onClick={() => setTarget({ entry: BLANK })}>
          <Plus size={15} /> Add a sign-up
        </button>
        <span className="small muted">Walk-ups, phone sign-ups, anyone. Works even when registration is closed.</span>
      </div>
      {error && <div className="alert alert-error small">{error}</div>}
      <div className="table-wrap">
        {body.length === 0 ? (
          <div className="muted small">No sign-ups yet.</div>
        ) : (
          <table className="table signup-table">
            <thead>
              <tr>
                <th>Name</th>
                <th>Partner</th>
                <th>Division</th>
                <th>Paid</th>
                <th>Owes</th>
                <th aria-label="Actions" />
              </tr>
            </thead>
            <tbody>
              {body
                .map((r, i) => ({ r, row: i + 1 }))
                .reverse()
                .map(({ r, row }) => {
                  const e = rowToEntry(header, r);
                  const players = e.partnerName && !e.partnerSeparate ? 2 : 1;
                  return (
                    <tr key={`${row}-${r[0]}`}>
                      <td className="bold">{e.name}</td>
                      <td>
                        {e.partnerName || <span className="muted">Needs a partner</span>}
                        {e.partnerSeparate && <div className="tiny muted">pays on their own</div>}
                      </td>
                      <td>{e.division}</td>
                      <td className="small">
                        {r[col('Payment confirmed')] || '—'}
                        {e.payment ? <div className="tiny muted">{e.payment}</div> : null}
                      </td>
                      <td className="small">
                        ${players * BRAND.payment.feeAmount + (e.donation || 0)}
                        <div className="tiny muted">
                          ${BRAND.payment.feeAmount} × {players}
                          {e.donation ? ` + $${e.donation}` : ''}
                        </div>
                      </td>
                      <td>
                        <div className="row" style={{ gap: 4, flexWrap: 'nowrap' }}>
                          <button className="btn btn-ghost btn-sm" aria-label={`Edit ${e.name}`} onClick={() => setTarget({ row, stamp: r[0], entry: e })}>
                            <Pencil size={15} />
                          </button>
                          <button className="btn btn-ghost btn-sm" aria-label={`Delete ${e.name}`} onClick={() => void remove(row, r)}>
                            <Trash2 size={15} />
                          </button>
                        </div>
                      </td>
                    </tr>
                  );
                })}
            </tbody>
          </table>
        )}
      </div>
      {target && <SignupDialog url={url} passcode={passcode} target={target} onClose={() => setTarget(null)} onSaved={onChanged} />}
    </>
  );
}
