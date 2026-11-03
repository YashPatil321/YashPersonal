import { useState } from 'react';
import type { ReactNode } from 'react';
import { CheckCircle2, ClipboardList, Users } from 'lucide-react';
import { BRAND } from '../brand';
import { remote } from '../lib/sync';
import type { RegistrationEntry } from '../lib/sync';
import { CauseCard, Mandala, Toran } from '../components/ui';
import { useStore } from '../state/store';
import { useEventInfo } from '../state/useEventInfo';

export const SKILL_LEVELS = ['Beginner (new to pickleball)', 'Intermediate (2.5 - 3.5)', 'Advanced (4.0+)'];
export const BRACKETS: Array<{ value: string; hint: string }> = [
  { value: 'Competitive', hint: 'Play to win. Seeded by skill.' },
  { value: 'Just for fun', hint: 'Relaxed games, all levels welcome.' },
];

const EMPTY: RegistrationEntry = {
  name: '',
  email: '',
  phone: '',
  school: '',
  skill: '',
  bracket: '',
  partnerName: '',
  partnerEmail: '',
  partnerSkill: '',
  teamName: '',
  notes: '',
};

const emailOk = (v: string) => /^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(v.trim());

function Choices({
  name,
  value,
  options,
  onChange,
  allowClear,
}: {
  name: string;
  value: string;
  options: Array<{ value: string; hint?: string }>;
  onChange: (v: string) => void;
  allowClear?: boolean;
}) {
  return (
    <div className="choice-grid" role="radiogroup" aria-label={name}>
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
    <section className="hero-banner" style={{ marginBottom: 16 }}>
      <Toran />
      <Mandala />
      <div className="eyebrow">{BRAND.eventName} · Registration</div>
      <h1>Register your team</h1>
      <div style={{ color: 'var(--on-night-muted)', maxWidth: 640 }}>{children}</div>
    </section>
  );
}

export function Register() {
  const { t, sync, isAdmin } = useStore();
  const { info, loading, refresh } = useEventInfo();
  const [form, setForm] = useState<RegistrationEntry>(EMPTY);
  const [honeypot, setHoneypot] = useState('');
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [done, setDone] = useState<{ name: string; partner?: string; count?: number } | null>(null);
  const set = (p: Partial<RegistrationEntry>) => setForm((f) => ({ ...f, ...p }));

  const intro = (
    <>
      Doubles. Sign up as a pair, or sign up on your own and we’ll match you with a partner. {BRAND.charity.pledge}
    </>
  );

  // Closed / not ready states
  let closed: ReactNode = null;
  if (t) {
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
            Thank you for playing for the {BRAND.charity.name}.
          </p>
          {done.count ? <p className="small bold">{done.count} sign-ups so far</p> : null}
          <div className="row" style={{ justifyContent: 'center' }}>
            <button
              className="btn"
              onClick={() => {
                setDone(null);
                setForm(EMPTY);
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

  const submit = async () => {
    setError(null);
    if (!form.name.trim()) return setError('Please enter your full name.');
    if (!emailOk(form.email)) return setError('Please enter a valid email.');
    if (!form.skill) return setError('Please choose your skill level.');
    if (!form.bracket) return setError('Please choose a bracket.');
    if (form.partnerEmail && !emailOk(form.partnerEmail)) return setError('Please check your partner’s email.');
    if (!sync) return;
    setBusy(true);
    try {
      const res = await remote.register(sync.url, form, honeypot);
      setDone({ name: form.name.trim(), partner: form.partnerName?.trim() || undefined, count: res.count });
      refresh();
      window.scrollTo({ top: 0 });
    } catch (e) {
      setError((e as Error).message || 'Something went wrong. Please try again.');
    } finally {
      setBusy(false);
    }
  };

  return (
    <>
      <Hero>
        {intro}
        {info && info.registrations > 0 && (
          <div style={{ marginTop: 10 }}>
            <span className="chip">
              <ClipboardList size={14} /> {info.registrations} signed up so far
            </span>
          </div>
        )}
      </Hero>

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
            <label className="field">
              School
              <input className="input" value={form.school} onChange={(e) => set({ school: e.target.value })} />
            </label>
          </div>
          <div className="field" style={{ marginTop: 14 }}>
            Skill level *
            <Choices name="Skill level" value={form.skill} onChange={(v) => set({ skill: v })} options={SKILL_LEVELS.map((v) => ({ value: v }))} />
          </div>
          <div className="field" style={{ marginTop: 14 }}>
            Bracket *
            <Choices name="Bracket" value={form.bracket ?? ''} onChange={(v) => set({ bracket: v })} options={BRACKETS} />
          </div>
        </div>

        <div className="card">
          <h2>Your partner</h2>
          <p className="muted small" style={{ marginTop: -4 }}>
            Optional. Leave this blank and we’ll pair you with someone. Only one of you needs to register.
          </p>
          <div className="form-grid">
            <label className="field">
              Partner’s full name
              <input className="input" value={form.partnerName} onChange={(e) => set({ partnerName: e.target.value })} />
            </label>
            <label className="field">
              Partner’s email
              <input className="input" type="email" value={form.partnerEmail} onChange={(e) => set({ partnerEmail: e.target.value })} />
            </label>
          </div>
          <div className="field" style={{ marginTop: 14 }}>
            Partner’s skill level
            <Choices
              name="Partner's skill level"
              value={form.partnerSkill ?? ''}
              onChange={(v) => set({ partnerSkill: v })}
              options={SKILL_LEVELS.map((v) => ({ value: v }))}
              allowClear
            />
          </div>
        </div>

        <div className="card">
          <h2>Extras</h2>
          <div className="form-grid">
            <label className="field">
              Team name (optional)
              <input className="input" value={form.teamName} onChange={(e) => set({ teamName: e.target.value })} />
            </label>
          </div>
          <label className="field" style={{ marginTop: 14 }}>
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

        {error && <div className="alert alert-error">{error}</div>}
        <div className="row">
          <button className="btn btn-primary btn-lg" type="submit" disabled={busy}>
            {busy ? 'Registering…' : 'Register'}
          </button>
          <span className="small muted">{BRAND.charity.pledge}</span>
        </div>
      </form>
    </>
  );
}
