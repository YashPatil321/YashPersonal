import { useState } from 'react';
import type { ReactNode } from 'react';
import { CheckCircle2, HandHeart, Users } from 'lucide-react';
import { BRAND } from '../brand';
import { remote } from '../lib/sync';
import type { RegistrationEntry } from '../lib/sync';
import { FundraiserSidebar } from '../components/Fundraiser';
import { CauseCard } from '../components/ui';
import { useStore } from '../state/store';
import { useEventInfo } from '../state/useEventInfo';

export const DIVISIONS: Array<{ value: 'Adults' | 'Kids/Teens' }> = [{ value: 'Adults' }, { value: 'Kids/Teens' }];
export const DONATION_CHOICES = ['No thanks', '$10', '$25', '$50', 'Other'];
export const PAYMENT_METHODS: Array<{ value: 'Zelle' | 'Venmo' | 'Cash at check-in'; hint?: string }> = [
  { value: 'Zelle', hint: BRAND.payment.zelle },
  { value: 'Venmo', hint: BRAND.payment.venmo },
  { value: 'Cash at check-in', hint: 'Pay on the day' },
];

const EMPTY: RegistrationEntry = {
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

type PartnerMode = 'join' | 'named' | 'solo';
const PARTNER_MODES: Array<{ mode: PartnerMode; value: string; hint: string }> = [
  { mode: 'join', value: 'Join my partner', hint: 'Already registered' },
  { mode: 'named', value: 'My partner will register', hint: 'Enter their name' },
  { mode: 'solo', value: 'I need a partner', hint: 'We’ll match you' },
];

const emailOk = (v: string) => /^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(v.trim());

function Choices({
  name,
  value,
  options,
  onChange,
  allowClear,
  compact,
}: {
  compact?: boolean;
  name: string;
  value: string;
  options: Array<{ value: string; hint?: string }>;
  onChange: (v: string) => void;
  allowClear?: boolean;
}) {
  return (
    <div className={`choice-grid ${compact ? 'compact' : ''}`} role="radiogroup" aria-label={name}>
      {options.map((o) => (
        <label key={o.value} className={`choice ${value === o.value ? 'on' : ''}`}>
          <input
            type="radio"
            name={name}
            value={o.value}
            checked={value === o.value}
            onChange={() => onChange(o.value)}
            onClick={() => allowClear && value === o.value && onChange('')}
          />
          <span className="choice-title">{o.value}</span>
          {o.hint && <span className="choice-hint">{o.hint}</span>}
        </label>
      ))}
    </div>
  );
}

function Hero({ children }: { children?: ReactNode }) {
  return (
    <section className="photo-banner" style={{ marginBottom: 16 }}>
      <img src="./photos/sacs-cast.webp" alt="The SACS 2026 cast on stage after the show" />
      <div className="photo-banner-text">
        <div className="eyebrow">{BRAND.eventName}</div>
        <h1>Register &amp; donate</h1>
        <div className="photo-banner-sub">{children}</div>
      </div>
    </section>
  );
}

export function Register() {
  const { t, sync, isAdmin } = useStore();
  const { info, loading, refresh } = useEventInfo();
  const [form, setForm] = useState<RegistrationEntry>(EMPTY);
  const [honeypot, setHoneypot] = useState('');
  const [donationChoice, setDonationChoice] = useState('No thanks');
  const [partnerMode, setPartnerMode] = useState<PartnerMode>('named');
  const [customDonation, setCustomDonation] = useState('');
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [done, setDone] = useState<{ name: string; partner?: string; count?: number; donation?: number } | null>(null);
  const set = (p: Partial<RegistrationEntry>) => setForm((f) => ({ ...f, ...p }));

  const intro = (
    <>
      Doubles, Adults &amp; Kids/Teens. Sign up as a pair or on your own (we’ll match you), with a ${BRAND.payment.feeAmount} donation per
      person. {BRAND.charity.pledge}
    </>
  );

  // Closed / not ready states
  let closed: ReactNode = null;
  if (t && t.published === true) {
    closed = (
      <>
        <h2>The draw is out!</h2>
        <p className="muted">Registration is closed. Find your team to see your court and when you play.</p>
        <a className="btn btn-primary" href="#/teams">
          <Users size={16} /> Find my team
        </a>
      </>
    );
  } else if (!sync) {
    closed = (
      <>
        <h2>Registration opens soon</h2>
        <p className="muted">Check back shortly. This page will take sign-ups as soon as the SACS team opens registration.</p>
        {isAdmin && (
          <a className="btn btn-primary" href="#/admin">
            Organizers: finish setup to open registration
          </a>
        )}
      </>
    );
  } else if (!loading && info && !info.registrationOpen) {
    closed = (
      <>
        <h2>Registration is closed</h2>
        <p className="muted">Sign-ups are closed for now. Questions? Reach out to the SACS team.</p>
      </>
    );
  }

  if (closed) {
    return (
      <>
        <Hero>{intro}</Hero>
        <div className="card empty" style={{ color: 'var(--ink)' }}>
          {closed}
        </div>
        <div style={{ marginTop: 16 }}>
          <CauseCard compact />
        </div>
      </>
    );
  }

  if (done) {
    return (
      <>
        <Hero>{intro}</Hero>
        <div className="card register-done">
          <CheckCircle2 size={44} color="var(--win)" />
          <h2>You’re in, {done.name.split(' ')[0]}!</h2>
          <p className="muted">
            {done.partner ? `You and ${done.partner} are registered.` : 'You’re registered. We’ll pair you with a partner.'}{' '}
            Thank you for playing for the {BRAND.charity.name}
            {done.donation ? `, and for your extra $${done.donation} donation` : ''}.
          </p>
          {done.count ? <p className="small bold">{done.count} sign-ups so far</p> : null}
          <div className="row" style={{ justifyContent: 'center' }}>
            <button
              className="btn"
              onClick={() => {
                setDone(null);
                setForm(EMPTY);
                setPartnerMode('named');
                setDonationChoice('No thanks');
                setCustomDonation('');
              }}
            >
              Register another team
            </button>
            <a className="btn btn-primary" href="#/">
              Back to home
            </a>
          </div>
        </div>
      </>
    );
  }

  const players = 1;
  const waiting = info?.waiting ?? [];
  const amountDue = BRAND.payment.feeAmount * players + (form.donation ?? 0);
  const names = form.name.trim();
  const noteText = `${names || 'your name'} – SACS Pickleball`;

  const submit = async () => {
    setError(null);
    if (!form.name.trim()) return setError('Please enter your full name.');
    if (!emailOk(form.email)) return setError('Please enter a valid email.');
    if (!form.division) return setError('Please choose Adults or Kids/Teens.');
    if (partnerMode === 'named' && !form.partnerName?.trim()) return setError('Please enter your partner’s name, or pick “I need a partner”.');
    if (partnerMode === 'join' && !form.joinId) return setError('Tap the partner you’re joining.');
    if (!form.payment) return setError('Please choose how you’re sending your donation.');
    if (!form.paid) return setError('Please confirm your donation.');
    if (donationChoice === 'Other' && !(form.donation && form.donation > 0))
      return setError('Enter a donation amount, or choose “No thanks”.');
    if (form.partnerEmail && !emailOk(form.partnerEmail)) return setError('Please check your partner’s email.');
    if (!sync) return;
    setBusy(true);
    try {
      const res = await remote.register(sync.url, form, honeypot);
      setDone({ name: form.name.trim(), partner: form.partnerName?.trim() || undefined, count: res.count, donation: form.donation });
      refresh();
      window.scrollTo({ top: 0 });
    } catch (e) {
      setError((e as Error).message || 'Something went wrong. Please try again.');
    } finally {
      setBusy(false);
    }
  };

  const toForm = () => document.getElementById('register-form')?.scrollIntoView({ behavior: 'smooth', block: 'start' });

  return (
    <div className="gf-page">
      <div className="gf-title">
        <h1>{BRAND.eventName}</h1>
        <div className="muted">{BRAND.when}</div>
      </div>
      <figure className="gf-photo">
        <img src="./photos/sacs-cast.webp" alt="The SACS 2026 cast on stage after the show" />
      </figure>
      <aside className="gf-side">
        <FundraiserSidebar info={info} onDonate={toForm} />
      </aside>
      <div className="gf-main">
        <div className="gf-organizer">
          <span className="gf-avatar">
            <HandHeart size={20} />
          </span>
          <div className="small">
            Organized by the <b>{BRAND.organizer}</b> in support of the{' '}
            <a href={BRAND.charity.url} target="_blank" rel="noreferrer">
              {BRAND.charity.name}
            </a>
            .
          </div>
        </div>
        <div className="gf-story">
          <p>
            Doubles play across {BRAND.courts} courts in two divisions, Adults and Kids/Teens. Every team plays at least{' '}
            {BRAND.minGames} games.
          </p>
          <p>
            Each player registers individually with a ${BRAND.payment.feeAmount} donation. {BRAND.charity.pledge}
          </p>
        </div>
        <h2 id="register-form" className="gf-form-title">
          Registration
        </h2>
      <form
        className="stack register-form"
        style={{ gap: 14 }}
        onSubmit={(e) => {
          e.preventDefault();
          void submit();
        }}
        noValidate
      >
        <div className="card">
          <h2>Your details</h2>
          <div className="form-grid">
            <label className="field">
              Full name *
              <input className="input" autoComplete="name" value={form.name} onChange={(e) => set({ name: e.target.value })} />
            </label>
            <label className="field">
              Email *
              <input
                className="input"
                type="email"
                autoComplete="email"
                value={form.email}
                onChange={(e) => set({ email: e.target.value })}
              />
            </label>
            <label className="field">
              Phone number
              <input className="input" type="tel" autoComplete="tel" value={form.phone} onChange={(e) => set({ phone: e.target.value })} />
            </label>
          </div>
          <div className="field" style={{ marginTop: 14 }}>
            Division *
            <Choices
              name="Division"
              value={form.division}
              onChange={(v) => set({ division: v as RegistrationEntry['division'] })}
              options={DIVISIONS}
            />
          </div>
        </div>

        <div className="card">
          <h2>Partner</h2>
          <p className="muted small" style={{ marginTop: -4 }}>
            Each player registers separately.
          </p>
          <Choices
            name="Partner"
            value={PARTNER_MODES.find((m) => m.mode === partnerMode)!.value}
            onChange={(v) => {
              const mode = PARTNER_MODES.find((m) => m.value === v)!.mode;
              setPartnerMode(mode);
              set({ joinId: undefined, partnerName: mode === 'named' ? form.partnerName : '', partnerSeparate: mode !== 'solo', paid: false });
            }}
            options={PARTNER_MODES.filter((m) => m.mode !== 'join' || waiting.length > 0)}
          />
          {partnerMode === 'join' && (
            <div className="join-list" role="radiogroup" aria-label="Who are you joining?">
              {waiting.map((w) => (
                <label key={w.id} className={`join-item ${form.joinId === w.id ? 'on' : ''}`}>
                  <input
                    type="radio"
                    name="join"
                    checked={form.joinId === w.id}
                    onChange={() => set({ joinId: w.id, division: w.division, partnerSeparate: true, paid: false })}
                  />
                  <span>
                    <b>{w.name}</b>
                    {w.partner ? <span className="small muted"> · partner: {w.partner}</span> : null}
                    <span className="small muted"> · {w.division}</span>
                  </span>
                </label>
              ))}
              <p className="small muted" style={{ margin: '6px 0 0' }}>
                Not listed? Choose “My partner will register” and enter their name.
              </p>
            </div>
          )}
          {partnerMode === 'named' && (
            <>
              <label className="field" style={{ marginTop: 12 }}>
                Partner’s full name *
                <input className="input" value={form.partnerName} onChange={(e) => set({ partnerName: e.target.value })} />
              </label>
              <p className="small muted" style={{ margin: '8px 0 0' }}>
                When your partner registers, they’ll select your name to join your team.
              </p>
            </>
          )}
          {partnerMode === 'solo' && (
            <p className="small muted" style={{ margin: '10px 0 0' }}>We’ll match you with another player.</p>
          )}
        </div>

        <div className="card">
          <h2>Notes</h2>
          <label className="field">
            Anything we should know? (optional)
            <textarea
              className="input"
              style={{ minHeight: 80, fontFamily: 'inherit', fontSize: '0.95rem' }}
              value={form.notes}
              onChange={(e) => set({ notes: e.target.value })}
            />
          </label>
          {/* Honeypot: hidden from people, bots fill it in */}
          <input
            className="hp"
            tabIndex={-1}
            autoComplete="off"
            aria-hidden="true"
            name="website"
            value={honeypot}
            onChange={(e) => setHoneypot(e.target.value)}
          />
        </div>

        <div className="card">
          <h2>Payment</h2>
          <p className="muted small" style={{ marginTop: -4 }}>
            Registration is a ${BRAND.payment.feeAmount} donation per player.
          </p>
          <div className="field" style={{ marginBottom: 14 }}>
            Additional donation (optional)
            <Choices
              name="Extra donation"
              value={donationChoice}
              onChange={(v) => {
                setDonationChoice(v);
                if (v === 'Other') set({ donation: Number(customDonation) || 0, paid: false });
                else set({ donation: v === 'No thanks' ? 0 : Number(v.replace('$', '')), paid: false });
              }}
              options={DONATION_CHOICES.map((value) => ({ value }))}
              compact
            />
            {donationChoice === 'Other' && (
              <input
                className="input"
                style={{ marginTop: 8, maxWidth: 200 }}
                inputMode="decimal"
                placeholder="$ amount"
                aria-label="Other donation amount"
                value={customDonation}
                onChange={(e) => {
                  const v = e.target.value.replace(/[^0-9.]/g, '').slice(0, 7);
                  setCustomDonation(v);
                  set({ donation: Number(v) || 0, paid: false });
                }}
              />
            )}
          </div>
          <div className="total-box" aria-live="polite">
            <div className="total-line">
              <span>Registration</span>
              <b>${BRAND.payment.feeAmount * players}</b>
            </div>
            <div className="total-line">
              <span>Additional donation</span>
              <b>{form.donation ? `$${form.donation}` : '$0'}</b>
            </div>
            <div className="total-line total-sum">
              <span>Total</span>
              <b>${amountDue}</b>
            </div>
            <div className="total-note">
              Please include <b>{noteText}</b> in the payment note.
            </div>
          </div>
          <div className="field" style={{ marginTop: 10 }}>
            Payment method *
            <Choices
              name="Payment method"
              value={form.payment}
              onChange={(v) => set({ payment: v as RegistrationEntry['payment'], paid: false })}
              options={PAYMENT_METHODS}
            />
          </div>
          <label className="check" style={{ marginTop: 14 }}>
            <input type="checkbox" checked={!!form.anonymous} onChange={(e) => set({ anonymous: e.target.checked })} />
            List my donation as anonymous
          </label>
          <label className="check" style={{ marginTop: 10, fontWeight: 600 }}>
            <input type="checkbox" checked={form.paid} onChange={(e) => set({ paid: e.target.checked })} />
            {form.payment === 'Cash at check-in'
              ? `I’ll pay $${amountDue} in cash at check-in. *`
              : `I’ve sent $${amountDue}${form.payment ? ` via ${form.payment}` : ''}. *`}
          </label>
        </div>

        {error && <div className="alert alert-error">{error}</div>}
        <div className="row">
          <button className="btn btn-primary btn-lg" type="submit" disabled={busy}>
            {busy ? 'Submitting…' : 'Complete registration'}
          </button>
        </div>
      </form>
      </div>
    </div>
  );
}
