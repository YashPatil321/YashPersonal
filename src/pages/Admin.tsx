import { useEffect, useState } from 'react';
import type { ReactNode } from 'react';
import { Check, ClipboardList, Copy, Download, ExternalLink, LayoutGrid, LogOut, Settings as SettingsIcon, Wand2 } from 'lucide-react';
import setupScript from '../../apps-script/Code.gs?raw';
import { BRAND } from '../brand';
import { download } from '../lib/exporters';
import { Mandala, Toran } from '../components/ui';
import { remote } from '../lib/sync';
import { FundraiserCard, raisedTotal } from '../components/Fundraiser';
import type { EventInfo } from '../state/useEventInfo';
import { SignupTable } from '../components/SignupManager';
import { DivisionsCard, EventCard, PlayersCard } from './Settings';
import { useStore } from '../state/store';
import { useEventInfo } from '../state/useEventInfo';

function useCopy() {
  const [copied, setCopied] = useState<string | null>(null);
  const copy = async (key: string, text: string) => {
    try {
      await navigator.clipboard.writeText(text);
      setCopied(key);
      setTimeout(() => setCopied((c) => (c === key ? null : c)), 1800);
    } catch {
      setCopied(null);
    }
  };
  return { copied, copy };
}

function siteBase() {
  return `${window.location.origin}${window.location.pathname}`;
}

function AdminHero({ title, children }: { title: string; children?: ReactNode }) {
  return (
    <section className="hero-banner" style={{ marginBottom: 16 }}>
      <Toran />
      <Mandala />
      <div className="eyebrow">{BRAND.eventName} · Organizers</div>
      <h1>{title}</h1>
      {children && <div style={{ color: 'var(--on-night-muted)', maxWidth: 620 }}>{children}</div>}
    </section>
  );
}

function Step({ n, title, children }: { n: number; title: string; children: ReactNode }) {
  return (
    <div className="card admin-step">
      <span className="step-num">{n}</span>
      <div style={{ minWidth: 0 }}>
        <h3>{title}</h3>
        {children}
      </div>
    </div>
  );
}

function LinkRow({ label, url, hint }: { label: string; url: string; hint?: string }) {
  const { copied, copy } = useCopy();
  return (
    <div className="link-row">
      <div className="small bold">{label}</div>
      {hint && <div className="tiny muted">{hint}</div>}
      <div className="row" style={{ flexWrap: 'nowrap', marginTop: 6 }}>
        <input className="input" readOnly value={url} onFocus={(e) => e.target.select()} />
        <button className="btn btn-sm" onClick={() => copy(label, url)} aria-label={`Copy ${label}`}>
          {copied === label ? <Check size={15} /> : <Copy size={15} />}
        </button>
        <a className="btn btn-sm" href={url} target="_blank" rel="noreferrer" aria-label={`Open ${label}`}>
          <ExternalLink size={15} />
        </a>
      </div>
    </div>
  );
}

/** Step-by-step: create the sign-up form + backend, then connect this site. */
function SetupGuide() {
  const { connect } = useStore();
  const { copied, copy } = useCopy();
  const [url, setUrl] = useState('');
  const [passcode, setPasscode] = useState('');
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const submit = async () => {
    setBusy(true);
    setError(null);
    try {
      const clean = url.trim().replace(/\/dev$/, '/exec');
      await connect({ url: clean, passcode: passcode.trim(), role: 'viewer' });
    } catch (e) {
      const msg = (e as Error).message;
      setError(/^wrong passcode/i.test(msg) ? 'The web app answered, but that passcode isn’t right.' : `Couldn't connect: ${msg}`);
    } finally {
      setBusy(false);
    }
  };

  return (
    <>
      <AdminHero title="Organizer setup">
        Open registration on the site and turn on live scores. Takes about 3 minutes in your Google account, no coding.
        Sign-ups land in a Google Sheet that only you can see.
      </AdminHero>
      <div className="stack" style={{ gap: 12 }}>
        <Step n={1} title="Copy the setup script">
          <p className="muted small">
            It creates the Google Sheet that collects sign-ups from the site’s Register tab, plus your passcodes.
          </p>
          <div className="row">
            <button className="btn btn-primary" onClick={() => copy('script', setupScript)}>
              {copied === 'script' ? <Check size={16} /> : <Copy size={16} />} {copied === 'script' ? 'Copied!' : 'Copy script'}
            </button>
            <button className="btn" onClick={() => download('Code.gs', setupScript)}>
              <Download size={16} /> Download
            </button>
            <a className="btn btn-dark" href="https://script.new" target="_blank" rel="noreferrer">
              Open script.new <ExternalLink size={14} />
            </a>
          </div>
        </Step>
        <Step n={2} title="Paste it and run “setup”">
          <ol className="small steps-list">
            <li>
              In the tab that opened (sign in with the account that should own the sheet, e.g. the SACS exec account), select
              everything in the editor and paste. Press <b>Save</b>.
            </li>
            <li>
              In the toolbar, pick <b>setup</b> from the function menu and press <b>Run</b>. Allow access when Google asks.
            </li>
            <li>
              The <b>Execution log</b> shows the sign-ups sheet and your <b>admin</b> and <b>scorer</b> passcodes.
            </li>
          </ol>
        </Step>
        <Step n={3} title="Deploy it as a web app">
          <ol className="small steps-list">
            <li>
              <b>Deploy → New deployment</b>, then the gear icon → <b>Web app</b>.
            </li>
            <li>
              Execute as: <b>Me</b>. Who has access: <b>Anyone</b>. Press <b>Deploy</b>.
            </li>
            <li>
              Copy the <b>Web app URL</b> (it ends in <code>/exec</code>).
            </li>
          </ol>
        </Step>
        <Step n={4} title="Connect this site">
          <div className="form-grid">
            <label className="field">
              Web app URL
              <input
                className="input"
                placeholder="https://script.google.com/macros/s/…/exec"
                value={url}
                onChange={(e) => setUrl(e.target.value)}
              />
            </label>
            <label className="field">
              Admin passcode
              <input
                className="input"
                type="password"
                placeholder="sacs-……"
                value={passcode}
                onChange={(e) => setPasscode(e.target.value)}
                onKeyDown={(e) => e.key === 'Enter' && url && passcode && submit()}
              />
            </label>
          </div>
          {error && (
            <div className="alert alert-error small" style={{ marginTop: 10 }}>
              {error}
            </div>
          )}
          <div className="row" style={{ marginTop: 12 }}>
            <button className="btn btn-primary" disabled={!url.trim() || !passcode.trim() || busy} onClick={submit}>
              {busy ? 'Connecting…' : 'Connect'}
            </button>
          </div>
        </Step>
        <p className="small muted" style={{ margin: '4px 4px 0' }}>
          Just testing? <a href="#/setup">Build a draw on this device only</a> from a CSV or a shared sheet link. Nobody else
          will see it.
        </p>
      </div>
    </>
  );
}

function LoginCard() {
  const { sync, connect } = useStore();
  const [passcode, setPasscode] = useState('');
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  if (!sync) return null;
  const submit = async () => {
    setBusy(true);
    setError(null);
    try {
      await connect({ url: sync.url, passcode: passcode.trim(), role: 'viewer' });
    } catch (e) {
      const msg = (e as Error).message;
      setError(/^wrong passcode/i.test(msg) ? 'That passcode isn’t right.' : msg);
    } finally {
      setBusy(false);
    }
  };
  return (
    <>
      <AdminHero title="Organizer login">Admins run the tournament. Court volunteers use the scorer passcode.</AdminHero>
      <div className="card" style={{ maxWidth: 520 }}>
        <form
          className="stack"
          onSubmit={(e) => {
            e.preventDefault();
            void submit();
          }}
        >
          <label className="field">
            Passcode
            <input className="input" type="password" autoFocus value={passcode} onChange={(e) => setPasscode(e.target.value)} />
          </label>
          {error && <div className="alert alert-error small">{error}</div>}
          <div>
            <button className="btn btn-primary" disabled={!passcode.trim() || busy} type="submit">
              {busy ? 'Checking…' : 'Sign in'}
            </button>
          </div>
        </form>
      </div>
    </>
  );
}

function Dashboard() {
  const { t, sync, connect, resolved, update } = useStore();
  const { info, refresh } = useEventInfo();
  if (!sync) return null;
  const isAdmin = sync.role === 'admin';
  const publicLink = `${siteBase()}?live=${encodeURIComponent(sync.url)}#/`;
  const adminLink = `${siteBase()}?live=${encodeURIComponent(sync.url)}#/admin`;
  const played = resolved ? resolved.ordered.filter((r) => r.done && !r.notNeeded).length : 0;

  return (
    <>
      <AdminHero title={isAdmin ? 'Organizer dashboard' : 'Court volunteer'}>
        Signed in as <b style={{ color: 'var(--ball)' }}>{sync.role}</b>
        {info ? ` · connected to “${info.spreadsheet}”` : ''}.
      </AdminHero>

      <div className="grid grid-2">
        <div className="card">
          <div className="card-head">
            <h2>Tournament</h2>
            {t && t.published === false ? (
              <span className="badge badge-warn">Draft · players can’t see it</span>
            ) : (
              t && <span className="badge badge-final">Published · {played} matches played</span>
            )}
          </div>
          {t && isAdmin && t.published === false && (
            <div className="row" style={{ marginBottom: 10 }}>
              <button
                className="btn btn-primary"
                onClick={() => {
                  if (window.confirm('Publish the draw? Everyone will see the courts, teams and schedule, and registration closes.'))
                    update((tt) => ({ ...tt, published: true, updatedAt: Date.now() }));
                }}
              >
                Publish to players
              </button>
              <span className="small muted">Check courts and matchups first. You can still edit everything after publishing.</span>
            </div>
          )}
          {t && isAdmin && t.published !== false && (
            <div className="row" style={{ marginBottom: 10 }}>
              <button
                className="btn btn-sm btn-ghost"
                onClick={() => {
                  if (window.confirm('Hide the draw from players? They’ll see the home page again until you publish.'))
                    update((tt) => ({ ...tt, published: false, updatedAt: Date.now() }));
                }}
              >
                Hide from players (back to draft)
              </button>
            </div>
          )}
          {!t ? (
            <>
              <p className="muted small">
                When sign-ups close, build the draw from the registrations. Competitors see it the moment you create it.
              </p>
              {isAdmin && (
                <a className="btn btn-primary btn-lg" href="#/setup">
                  <Wand2 size={18} /> Build the draw
                </a>
              )}
            </>
          ) : (
            <div className="row">
              <a className="btn btn-primary" href="#/courts">
                <LayoutGrid size={16} /> Court desk
              </a>
              <a className="btn" href="#/">
                Home page
              </a>
              {isAdmin && (
                <a className="btn" href="#/settings">
                  <SettingsIcon size={16} /> Settings
                </a>
              )}
            </div>
          )}
        </div>

        {isAdmin && <RegistrationCard open={info?.registrationOpen ?? true} count={info?.registrations ?? 0} onChange={refresh} />}
        {isAdmin && info && <FundraisingCard info={info} onChange={refresh} />}
      </div>

      {isAdmin && (
        <>
          <div className="section-title">
            <h2>Courts, time &amp; teams</h2>
          </div>
          {t ? (
            <div className="stack" style={{ gap: 14 }}>
              <EventCard />
              <DivisionsCard />
              <PlayersCard />
            </div>
          ) : (
            <div className="card">
              <p className="muted small" style={{ marginTop: 0 }}>
                You set the number of courts, the game length and how long you have the courts in step 1 of building the draw,
                and you can rename teams, swap partners and add walk-ins in step 4. After the draw is out, you can change all of
                it right here: add or rename courts, change the timing, add late teams, fix names, and add divisions.
              </p>
              <a className="btn btn-primary" href="#/setup">
                <Wand2 size={16} /> Build the draw
              </a>
            </div>
          )}
        </>
      )}

      {isAdmin && (
        <div className="card section">
          <h2>Links</h2>
          <div className="stack" style={{ gap: 14 }}>
            <LinkRow
              label="Registration link"
              url={`${siteBase()}?live=${encodeURIComponent(sync.url)}#/register`}
              hint="Send this to players so they can sign up."
            />
            <LinkRow label="Players’ link" url={publicLink} hint="Live courts, brackets and scores. Read-only, no login." />
            <LinkRow
              label="Admin link"
              url={adminLink}
              hint="Bookmark this. It opens straight to this page on any device (you’ll still need the passcode)."
            />
          </div>
        </div>
      )}

      <div className="row section">
        <button className="btn btn-ghost" onClick={() => void connect({ url: sync.url, role: 'viewer' })}>
          <LogOut size={16} /> Sign out on this device
        </button>
      </div>
    </>
  );
}

export function Admin() {
  const { sync } = useStore();
  if (!sync) return <SetupGuide />;
  if (sync.role === 'viewer') return <LoginCard />;
  return <Dashboard />;
}

/** Sign-up count, open/close switch, and the list of who has registered. */
function RegistrationCard({ open, count, onChange }: { open: boolean; count: number; onChange: () => void }) {
  const { t, sync } = useStore();
  const [rows, setRows] = useState<string[][] | null>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [show, setShow] = useState(false);
  const [tick, setTick] = useState(0);

  useEffect(() => {
    if (!show || !sync?.passcode) return;
    let alive = true;
    remote
      .registrations(sync.url, sync.passcode)
      .then((r) => alive && setRows(r))
      .catch((e) => alive && setError((e as Error).message));
    return () => {
      alive = false;
    };
  }, [show, sync?.url, sync?.passcode, count, tick]);

  if (!sync?.passcode) return null;
  const toggle = async () => {
    setBusy(true);
    setError(null);
    try {
      await remote.setRegistration(sync.url, sync.passcode!, !open);
      onChange();
    } catch (e) {
      setError((e as Error).message);
    } finally {
      setBusy(false);
    }
  };

  const drawOut = !!t && t.published !== false;
  const header = rows?.[0] ?? [];
  const col = (title: string) => header.indexOf(title);
  const body = rows?.slice(1) ?? [];
  const donationTotal = body.reduce((sum, r) => sum + (Number(String(r[col('Extra donation')] ?? '').replace(/[^0-9.]/g, '')) || 0), 0);

  return (
    <div className="card" style={{ gridColumn: '1 / -1' }}>
      <div className="card-head">
        <h2>
          <ClipboardList size={20} style={{ verticalAlign: '-3px', marginRight: 6 }} />
          Registration
        </h2>
        <span className={`badge ${drawOut ? '' : open ? 'badge-final' : 'badge-warn'}`}>{drawOut ? 'Closed (draw is out)' : open ? 'Open' : 'Closed'}</span>
      </div>
      <div className="row-between" style={{ flexWrap: 'wrap', gap: 10 }}>
        <div>
          <div className="display" style={{ fontSize: '2.2rem', lineHeight: 1 }}>
            {count}
          </div>
          <div className="small muted">sign-ups so far</div>
          {donationTotal > 0 && <div className="small bold">${donationTotal} in extra donations</div>}
        </div>
        <div className="row">
          <a className="btn btn-sm" href="#/register">
            View form
          </a>
          {!drawOut && (
            <button className="btn btn-sm" disabled={busy} onClick={toggle}>
              {open ? 'Close registration' : 'Reopen registration'}
            </button>
          )}
          <button className="btn btn-sm btn-ghost" onClick={() => setShow((v) => !v)}>
            {show ? 'Hide sign-ups' : 'Manage sign-ups'}
          </button>
        </div>
      </div>
      {error && (
        <div className="alert alert-error small" style={{ marginTop: 10 }}>
          {error}
        </div>
      )}
      {show && rows && sync.passcode && (
        <SignupTable
          url={sync.url}
          passcode={sync.passcode}
          rows={rows}
          onChanged={() => {
            setTick((n) => n + 1);
            onChange();
          }}
        />
      )}
      {show && !rows && !error && <div className="muted small" style={{ marginTop: 12 }}>Loading…</div>}
    </div>
  );
}

/** Goal and money raised outside the form, shown on the public progress bar. */
function FundraisingCard({ info, onChange }: { info: EventInfo; onChange: () => void }) {
  const { sync } = useStore();
  const [goal, setGoal] = useState(String(info.fundraising.goal || ''));
  const [extra, setExtra] = useState(String(info.fundraising.extra || ''));
  const [busy, setBusy] = useState(false);
  const [msg, setMsg] = useState<string | null>(null);
  if (!sync?.passcode) return null;
  const save = async () => {
    setBusy(true);
    setMsg(null);
    try {
      await remote.setFundraising(sync.url, sync.passcode!, Number(goal) || 0, Number(extra) || 0);
      setMsg('Saved. The progress bar updates for everyone.');
      onChange();
    } catch (e) {
      setMsg((e as Error).message);
    } finally {
      setBusy(false);
    }
  };
  return (
    <div className="card" style={{ gridColumn: '1 / -1' }}>
      <h2>Fundraising</h2>
      <FundraiserCard info={info} />
      <p className="small muted" style={{ margin: '12px 0' }}>
        Raised = {info.fundraising.players || info.registrations} players × ${BRAND.payment.feeAmount || 0} required donation + $
        {info.fundraising.donations} in
        extra donations + money raised elsewhere. Currently ${raisedTotal(info)}.
        {!BRAND.payment.feeAmount && ' The required donation amount isn’t set yet, so it isn’t counted.'}
      </p>
      <div className="form-grid">
        <label className="field">
          Goal ($)
          <input className="input" inputMode="numeric" value={goal} onChange={(e) => setGoal(e.target.value.replace(/[^0-9]/g, ''))} />
        </label>
        <label className="field">
          Raised elsewhere ($)
          <input className="input" inputMode="numeric" value={extra} onChange={(e) => setExtra(e.target.value.replace(/[^0-9]/g, ''))} />
          <span className="hint">Cash at the event, GoFundMe, sponsors… anything not entered through the form.</span>
        </label>
      </div>
      <div className="row" style={{ marginTop: 10 }}>
        <button className="btn btn-primary btn-sm" disabled={busy} onClick={save}>
          {busy ? 'Saving…' : 'Save'}
        </button>
        {msg && <span className="small muted">{msg}</span>}
      </div>
    </div>
  );
}
