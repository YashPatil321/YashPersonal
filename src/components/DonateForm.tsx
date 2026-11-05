import { useState } from 'react';
import { CheckCircle2 } from 'lucide-react';
import { BRAND } from '../brand';
import { remote } from '../lib/sync';
import type { DonationEntry } from '../lib/sync';
import { useStore } from '../state/store';

const AMOUNTS = ['$10', '$25', '$50', '$100', 'Other'];
const METHODS: Array<{ value: DonationEntry['payment']; hint: string }> = [
  { value: 'Zelle', hint: BRAND.payment.zelle },
  { value: 'Venmo', hint: BRAND.payment.venmo },
  { value: 'Cash at check-in', hint: 'Pay on the day' },
];
const emailOk = (v: string) => /^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(v.trim());

/** Give without playing. Saved apart from sign-ups, counted in the fundraising total. */
export function DonateForm({ onDone }: { onDone?: () => void }) {
  const { sync } = useStore();
  const [name, setName] = useState('');
  const [email, setEmail] = useState('');
  const [choice, setChoice] = useState('$25');
  const [other, setOther] = useState('');
  const [payment, setPayment] = useState<DonationEntry['payment']>('');
  const [anonymous, setAnonymous] = useState(false);
  const [paid, setPaid] = useState(false);
  const [honeypot, setHoneypot] = useState('');
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [done, setDone] = useState<number | null>(null);

  const amount = choice === 'Other' ? Number(other) || 0 : Number(choice.replace('$', ''));

  const submit = async () => {
    setError(null);
    if (!name.trim()) return setError('Please enter your name.');
    if (email.trim() && !emailOk(email)) return setError('Please check your email.');
    if (!(amount > 0)) return setError('Please enter a donation amount.');
    if (!payment) return setError('Please choose a payment method.');
    if (!paid) return setError('Please confirm your donation.');
    if (!sync) return;
    setBusy(true);
    try {
      await remote.donate(sync.url, { name, email, amount, payment, paid, anonymous }, honeypot);
      setDone(amount);
      onDone?.();
      window.scrollTo({ top: 0 });
    } catch (e) {
      setError((e as Error).message || 'Something went wrong. Please try again.');
    } finally {
      setBusy(false);
    }
  };

  if (done !== null) {
    return (
      <div className="card register-done">
        <CheckCircle2 size={44} color="var(--win)" />
        <h2>Thank you, {name.trim().split(' ')[0]}</h2>
        <p className="muted">
          Your ${done} donation supports SACS and the {BRAND.charity.name}.
        </p>
        <div className="row" style={{ justifyContent: 'center' }}>
          <a className="btn btn-primary" href="#/">
            Back to home
          </a>
        </div>
      </div>
    );
  }

  return (
    <form
      className="stack register-form"
      style={{ gap: 14 }}
      noValidate
      onSubmit={(e) => {
        e.preventDefault();
        void submit();
      }}
    >
      <div className="card">
        <h2>Your details</h2>
        <div className="form-grid">
          <label className="field">
            Full name *
            <input className="input" autoComplete="name" value={name} onChange={(e) => setName(e.target.value)} />
          </label>
          <label className="field">
            Email (optional)
            <input className="input" type="email" autoComplete="email" value={email} onChange={(e) => setEmail(e.target.value)} />
          </label>
        </div>
      </div>

      <div className="card">
        <h2>Donation</h2>
        <div className="field">
          Amount *
          <div className="choice-grid compact" role="radiogroup" aria-label="Amount">
            {AMOUNTS.map((a) => (
              <label key={a} className={`choice ${choice === a ? 'on' : ''}`}>
                <input type="radio" name="amount" checked={choice === a} onChange={() => { setChoice(a); setPaid(false); }} />
                <span className="choice-title">{a}</span>
              </label>
            ))}
          </div>
          {choice === 'Other' && (
            <input
              className="input"
              style={{ marginTop: 8, maxWidth: 200 }}
              inputMode="decimal"
              placeholder="$ amount"
              aria-label="Other amount"
              value={other}
              onChange={(e) => { setOther(e.target.value.replace(/[^0-9.]/g, '').slice(0, 7)); setPaid(false); }}
            />
          )}
        </div>
        <label className="check" style={{ marginTop: 12 }}>
          <input type="checkbox" checked={anonymous} onChange={(e) => setAnonymous(e.target.checked)} />
          List my donation as anonymous (optional)
        </label>
        <div className="field" style={{ marginTop: 14 }}>
          Payment method *
          <div className="choice-grid" role="radiogroup" aria-label="Payment method">
            {METHODS.map((m) => (
              <label key={m.value} className={`choice ${payment === m.value ? 'on' : ''}`}>
                <input type="radio" name="donate-payment" checked={payment === m.value} onChange={() => { setPayment(m.value); setPaid(false); }} />
                <span className="choice-title">{m.value}</span>
                {m.hint && <span className="choice-hint">{m.hint}</span>}
              </label>
            ))}
          </div>
        </div>
        {amount > 0 && (
          <div className="total-box" style={{ marginTop: 14 }}>
            <div className="total-line total-sum">
              <span>Total</span>
              <b>${amount}</b>
            </div>
            <div className="total-note">
              Please include <b>{name.trim() || 'your name'} – SACS donation</b> in the payment note.
            </div>
          </div>
        )}
        <label className="check" style={{ marginTop: 12, fontWeight: 600 }}>
          <input type="checkbox" checked={paid} onChange={(e) => setPaid(e.target.checked)} />
          {payment === 'Cash at check-in'
            ? `I’ll pay $${amount || 0} in cash at the event. *`
            : `I’ve sent $${amount || 0}${payment ? ` via ${payment}` : ''}. *`}
        </label>
      </div>

      <div className="hp" aria-hidden="true">
        <label>
          Website
          <input tabIndex={-1} autoComplete="off" value={honeypot} onChange={(e) => setHoneypot(e.target.value)} />
        </label>
      </div>
      {error && <div className="alert alert-error">{error}</div>}
      <div className="row">
        <button className="btn btn-primary btn-lg" type="submit" disabled={busy}>
          {busy ? 'Submitting…' : 'Donate'}
        </button>
      </div>
    </form>
  );
}
