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
export const PAYMENT_METHODS: Array<{ value: 'Zelle' | 'Venmo' | 'Cash at check-in' }> = [
  { value: 'Zelle' },
  { value: 'Venmo' },
  { value: 'Cash at check-in' },
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

type PartnerMode = 'solo' | 'both' | 'separate' | 'join';
const PARTNER_MODES: Array<{ mode: PartnerMode; value: string; hint: string }> = [
  { mode: 'solo', value: 'Pair me with someone', hint: 'We’ll find you a partner' },
  { mode: 'both', value: 'I’m signing up my partner too', hint: `You give $${BRAND.payment.feeAmount * 2} for both` },
  { mode: 'separate', value: 'My partner will sign up on their own', hint: `You each give $${BRAND.payment.feeAmount}` },
  { mode: 'join', value: 'Join a partner', hint: 'They already signed up' },
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
  const [partnerMode, setPartnerMode] = useState<PartnerMode>('solo');
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
                setPartnerMode('solo');
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

  const players = partnerMode === 'both' && form.partnerName?.trim() ? 2 : 1;
  const amountDue = BRAND.payment.feeAmount * players + (form.donation ?? 0);
  const names = [form.name.trim(), players === 2 ? form.partnerName?.trim() : ''].filter(Boolean).join(' & ');
  const noteText = `${names || 'your name'} – SACS Pickleball`;

  const submit = async () => {
    setError(null);
    if (!form.name.trim()) return setError('Please enter your full name.');
    if (!emailOk(form.email)) return setError('Please enter a valid email.');
    if (!form.division) return setError('Please choose Adults or Kids/Teens.');
    if ((partnerMode === 'both' || partnerMode === 'separate') && !form.partnerName?.trim()) return setError('Please enter your partner’s name.');
    if (partnerMode === 'join' && !form.joinId) return setError('Pick the partner you’re joining.');
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
      <h1 className="gf-title">
        {BRAND.eventName}: play for SACS &amp; Akshaya Patra
      </h1>
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
            <b>South Asian Culture Show</b> is organizing this fundraiser for the{' '}
            <a href={BRAND.charity.url} target="_blank" rel="noreferrer">
              {BRAND.charity.name}
            </a>
            .
          </div>
        </div>
        <div className="gf-story">
          <p>
            Grab a partner (or come solo and we’ll pair you) and play in the {BRAND.eventName} on {BRAND.when}: doubles on{' '}
            {BRAND.courts} courts, with an Adults division and a Kids/Teens division. Every team is guaranteed at least{' '}
            {BRAND.minGames} games.
          </p>
          <p>
            It’s a <b>${BRAND.payment.feeAmount} donation per person</b> to play (${BRAND.payment.feeAmount * 2} for a team of two), and you can add more if you’d like. {BRAND.charity.pledge}{' '}
            {BRAND.charity.blurb}
          </p>
        </div>
        <h2 id="register-form" className="gf-form-title">
          Register &amp; donate
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
          <h2>You</h2>
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
              <span className="hint">In case we need to reach you on tournament day.</span>
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
          <h2>Your partner</h2>
          <Choices
            name="Partner"
            value={PARTNER_MODES.find((m) => m.mode === partnerMode)!.value}
            onChange={(v) => {
              const mode = PARTNER_MODES.find((m) => m.value === v)!.mode;
              setPartnerMode(mode);
              set({
                partnerSeparate: mode === 'separate',
                joinId: undefined,
                partnerName: mode === 'solo' || mode === 'join' ? '' : form.partnerName,
                partnerEmail: mode === 'both' ? form.partnerEmail : '',
                paid: false,
              });
            }}
            options={PARTNER_MODES.filter((m) => m.mode !== 'join' || (info?.waiting.length ?? 0) > 0)}
          />
          {(partnerMode === 'both' || partnerMode === 'separate') && (
            <div className="form-grid" style={{ marginTop: 12 }}>
              <label className="field">
                Partner’s full name *
                <input className="input" value={form.partnerName} onChange={(e) => set({ partnerName: e.target.value })} />
              </label>
              {partnerMode === 'both' && (
                <label className="field">
                  Partner’s email
                  <input className="input" type="email" value={form.partnerEmail} onChange={(e) => set({ partnerEmail: e.target.value })} />
                </label>
              )}
            </div>
          )}
          {partnerMode === 'separate' && (
            <p className="small muted" style={{ margin: '10px 0 0' }}>
              Tell {form.partnerName?.trim().split(' ')[0] || 'your partner'} to sign up and choose <b>Join a partner</b>. You each give ${BRAND.payment.feeAmount}.
            </p>
          )}
          {partnerMode === 'join' && (
            <div className="join-list" role="radiogroup" aria-label="Who are you joining?">
              {(info?.waiting ?? []).map((w) => (
                <label key={w.id} className={`join-item ${form.joinId === w.id ? 'on' : ''}`}>
                  <input
                    type="radio"
                    name="join"
                    checked={form.joinId === w.id}
                    onChange={() => set({ joinId: w.id, division: w.division, partnerSeparate: true, paid: false })}
                  />
                  <span>
                    <b>{w.name}</b> is waiting for {w.partner || 'a partner'}
                    <span className="small muted"> · {w.division}</span>
                  </span>
                </label>
              ))}
              <p className="small muted" style={{ margin: '6px 0 0' }}>
                Don’t see them? They haven’t signed up yet. Choose “My partner will sign up on their own” instead.
              </p>
            </div>
          )}
        </div>

        <div className="card">
          <h2>Extras</h2>
          <label className="field">
            Anything else we should know?
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
          <h2>Your donation</h2>
          <div className="price-callout">
            <div className="price-big">
              ${BRAND.payment.feeAmount} <span>per person</span>
            </div>
            <div className="small">
              Required to play. Signing up with a partner? That’s <b>${BRAND.payment.feeAmount * 2}</b> for the two of you.
            </div>
          </div>
          <p className="muted small">{BRAND.charity.pledge}</p>
          <div className="field" style={{ marginBottom: 14 }}>
            Want to give more? (optional)
            <span className="hint">Add it to your required donation and send it all as one payment.</span>
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
              <span>
                Required: ${BRAND.payment.feeAmount} per person × {players} {players === 1 ? 'person' : 'people'}
              </span>
              <b>${BRAND.payment.feeAmount * players}</b>
            </div>
            <div className="total-line">
              <span>Extra donation</span>
              <b>{form.donation ? `$${form.donation}` : '$0'}</b>
            </div>
            <div className="total-line total-sum">
              <span>Total to send</span>
              <b>${amountDue}</b>
            </div>
            <div className="total-note">
              Send <b>${amountDue}</b> in one payment. In the Zelle/Venmo note, write <b>{noteText}</b>.
            </div>
          </div>
          <ul className="small pay-list">
            <li>
              <b>Zelle</b>
              {BRAND.payment.zelle ? ` to ${BRAND.payment.zelle}` : ''}
            </li>
            <li>
              <b>Venmo</b>
              {BRAND.payment.venmo ? ` ${BRAND.payment.venmo}` : ''}
            </li>
            <li>
              <b>Cash</b> at check-in
            </li>
          </ul>
          <div className="field" style={{ marginTop: 10 }}>
            How are you sending it? *
            <Choices
              name="Payment method"
              value={form.payment}
              onChange={(v) => set({ payment: v as RegistrationEntry['payment'], paid: false })}
              options={PAYMENT_METHODS}
            />
          </div>
          <label className="check" style={{ marginTop: 14 }}>
            <input type="checkbox" checked={!!form.anonymous} onChange={(e) => set({ anonymous: e.target.checked })} />
            Show me as “Anonymous” on the donations list
          </label>
          <label className="check" style={{ marginTop: 10, fontWeight: 600 }}>
            <input type="checkbox" checked={form.paid} onChange={(e) => set({ paid: e.target.checked })} />
            {form.payment === 'Cash at check-in'
              ? `I’ll bring $${amountDue} in cash to check-in. *`
              : `I’ve sent $${amountDue}${form.payment ? ` by ${form.payment}` : ''} with my name in the note. *`}
          </label>
        </div>

        {error && <div className="alert alert-error">{error}</div>}
        <div className="row">
          <button className="btn btn-primary btn-lg" type="submit" disabled={busy}>
            {busy ? 'Registering…' : 'Register'}
          </button>
        </div>
      </form>
      </div>
    </div>
  );
}
