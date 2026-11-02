import { useState } from 'react';
import { detectColumns, DEFAULT_IMPORT_OPTIONS, importRegistrations, seedTeams } from './lib/registrations';
import { sampleRegistrations } from './lib/sample';
import { buildTournament, courtNames, defaultDivisionSettings } from './lib/tournament';
import { BallIcon, Modal } from './components/ui';
import { Courts } from './pages/Courts';
import { Matches } from './pages/Matches';
import { Overview } from './pages/Overview';
import { Scorekeeper } from './pages/Scorekeeper';
import { Settings } from './pages/Settings';
import { Setup } from './pages/Setup';
import { Brackets, Standings } from './pages/Standings';
import { TeamDetail, Teams } from './pages/Teams';
import { TV } from './pages/TV';
import { navigate, useRoute } from './state/router';
import { useStore } from './state/store';

export function App() {
  const route = useRoute();
  const { t } = useStore();
  const [page] = route.parts;

  if (page === 'tv' && t) return <TV />;

  return (
    <>
      <Header />
      <main>
        <Page />
      </main>
    </>
  );
}

function Page() {
  const route = useRoute();
  const { t, isAdmin } = useStore();
  const [page, id] = route.parts;

  if (page === 'setup') return isAdmin ? <Setup /> : <AdminOnly />;
  if (page === 'settings') return <Settings />;
  if (!t) return <Welcome />;
  switch (page) {
    case undefined:
      return <Overview />;
    case 'courts':
      return <Courts />;
    case 'matches':
      return <Matches />;
    case 'standings':
      return <Standings />;
    case 'brackets':
      return <Brackets />;
    case 'teams':
      return id ? <TeamDetail teamId={id} /> : <Teams />;
    case 'score':
      return id ? <Scorekeeper matchId={id} /> : <Courts />;
    default:
      return <Overview />;
  }
}

/* ------------------------------------------------------------------ */

function Header() {
  const route = useRoute();
  const { t, sync, syncState, isAdmin } = useStore();
  const [login, setLogin] = useState(false);
  const current = route.parts[0] ?? '';
  const hasBrackets = !!t?.divisions.some((d) => d.settings.format !== 'round_robin');

  const links: Array<[string, string]> = t
    ? [
        ['', 'Home'],
        ['teams', t.settings.doubles ? 'Find my team' : 'Find me'],
        ['courts', 'Courts'],
        ['matches', 'Matches'],
        ['standings', 'Standings'],
        ...(hasBrackets ? ([['brackets', 'Brackets']] as Array<[string, string]>) : []),
        ['tv', 'TV'],
      ]
    : [['', 'Home']];
  if (isAdmin) links.push(['settings', 'Settings']);
  if (isAdmin && !t) links.push(['setup', 'Create']);

  return (
    <header className="app-header">
      <div className="header-inner">
        <div className="header-top">
          <a className="brand" href="#/">
            <BallIcon />
            <div style={{ minWidth: 0 }}>
              <div className="brand-title truncate">{t?.name ?? 'Pickleball Tournament'}</div>
              <div className="brand-sub truncate">
                {t
                  ? [t.date && new Date(t.date + 'T12:00:00').toLocaleDateString(undefined, { month: 'short', day: 'numeric' }), t.location]
                      .filter(Boolean)
                      .join(' · ') || 'Live results'
                  : 'Brackets · scores · standings'}
              </div>
            </div>
          </a>
          {sync && (
            <span className={`sync-pill ${syncState.status}`} title={syncState.message ?? 'Live sync'}>
              <span className="dot" />
              {syncState.status === 'synced' ? 'Live' : syncState.status === 'saving' ? 'Saving' : syncState.status === 'connecting' ? 'Connecting' : 'Offline'}
            </span>
          )}
          <AccountButton onLogin={() => setLogin(true)} />
        </div>
        <nav className="nav">
          {links.map(([path, label]) => (
            <a key={path} href={`#/${path}`} className={current === path ? 'active' : ''}>
              {label}
            </a>
          ))}
        </nav>
      </div>
      {login && <LoginModal onClose={() => setLogin(false)} />}
    </header>
  );
}

function AccountButton({ onLogin }: { onLogin: () => void }) {
  const { sync, connect } = useStore();
  if (!sync) return null;
  if (sync.role === 'viewer') {
    return (
      <button className="btn btn-sm" style={{ background: 'rgba(255,255,255,0.14)', color: 'inherit', borderColor: 'transparent' }} onClick={onLogin}>
        Organizer login
      </button>
    );
  }
  return (
    <button
      className="btn btn-sm"
      style={{ background: 'var(--accent)', color: 'var(--accent-ink)', borderColor: 'transparent' }}
      title="Signed in — click to sign out"
      onClick={() => {
        if (window.confirm(`You're signed in as ${sync.role}. Sign out on this device?`)) {
          void connect({ url: sync.url, role: 'viewer' });
        }
      }}
    >
      {sync.role === 'admin' ? 'Admin' : 'Scorer'} ✓
    </button>
  );
}

function LoginModal({ onClose }: { onClose: () => void }) {
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
      onClose();
    } catch (e) {
      const msg = (e as Error).message;
      setError(/^wrong passcode/i.test(msg) ? 'That passcode isn’t right.' : msg);
    } finally {
      setBusy(false);
    }
  };

  return (
    <Modal title="Organizer login" subtitle="Admins run the tournament; scorers can enter scores." onClose={onClose}>
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
        <div className="row">
          <button className="btn btn-primary" disabled={!passcode.trim() || busy} type="submit">
            {busy ? 'Checking…' : 'Sign in'}
          </button>
          <span className="muted tiny">Players don’t need to sign in — the live results are public.</span>
        </div>
      </form>
    </Modal>
  );
}

/* ------------------------------------------------------------------ */

function AdminOnly() {
  return (
    <div className="card empty">
      <h3 style={{ color: 'var(--ink)' }}>Organizers only</h3>
      <p>Use “Organizer login” at the top with the admin passcode.</p>
    </div>
  );
}

function createDemo() {
  const rows = sampleRegistrations();
  const res = importRegistrations(rows, detectColumns(rows[0]), DEFAULT_IMPORT_OPTIONS);
  return buildTournament(
    { name: 'Demo Pickleball Classic', date: new Date().toISOString().slice(0, 10), location: 'Riverside Park', courts: courtNames(4), minutesPerMatch: 20, doubles: true },
    res.players,
    res.teams,
    res.divisions.map((d) => ({
      name: d.name,
      teamIds: seedTeams(d.teamIds, res.teams, 'rating'),
      settings: defaultDivisionSettings(d.teamIds.length),
    })),
  );
}

function Welcome() {
  const { sync, isAdmin, replace, connect } = useStore();
  const [joinUrl, setJoinUrl] = useState('');
  const [error, setError] = useState<string | null>(null);

  if (sync && !isAdmin) {
    return (
      <div className="hero">
        <BallIcon size={64} />
        <h1>Draw coming soon</h1>
        <p>The organizer hasn’t published the brackets yet. This page updates by itself — keep it open or check back shortly.</p>
      </div>
    );
  }

  const join = async () => {
    setError(null);
    const raw = joinUrl.trim();
    let url = raw;
    try {
      const u = new URL(raw);
      url = u.searchParams.get('live') ?? raw;
    } catch {
      /* not a URL with params */
    }
    try {
      await connect({ url, role: 'viewer' });
    } catch (e) {
      setError(`Couldn't open that tournament: ${(e as Error).message}`);
    }
  };

  return (
    <>
      <div className="hero">
        <BallIcon size={64} />
        <h1>Run your pickleball tournament from a Google Form</h1>
        <p>
          Import sign-ups from Google Sheets and get teams, pools, brackets, court assignments, live scoring and standings.
          Players follow along on their phones; only you can change anything.
        </p>
        <div className="row" style={{ justifyContent: 'center' }}>
          <a className="btn btn-primary btn-lg" href="#/setup">
            Create a tournament
          </a>
          <button
            className="btn btn-lg"
            onClick={() => {
              replace(createDemo());
              navigate('/');
            }}
          >
            Try a demo
          </button>
        </div>
      </div>

      <div className="card" style={{ maxWidth: 640, margin: '0 auto' }}>
        <h3>Player? Open the live tournament</h3>
        <div className="row">
          <input
            className="input"
            style={{ flex: '1 1 260px' }}
            placeholder="Paste the link the organizer shared"
            value={joinUrl}
            onChange={(e) => setJoinUrl(e.target.value)}
            onKeyDown={(e) => e.key === 'Enter' && joinUrl && join()}
          />
          <button className="btn" disabled={!joinUrl.trim()} onClick={join}>
            Open
          </button>
        </div>
        {error && (
          <div className="alert alert-error small" style={{ marginTop: 10 }}>
            {error}
          </div>
        )}
      </div>

      <div className="feature-list" style={{ maxWidth: 1000, margin: '28px auto 0' }}>
        {[
          ['Google Form → teams', 'Auto-detects your form questions, matches partners who signed up separately and pairs players who need a partner.'],
          ['Any format', 'Round robin, pool play into playoffs, single or double elimination — per division, with byes and seeding handled.'],
          ['Court desk', 'Calls the next match to each open court automatically and never double-books a team.'],
          ['Live scoring', 'Tap-to-score with side-out server calls (“4-2-1”), rally scoring, or just type the final score.'],
          ['Players see everything', 'Public live page, “find my team” with wait times, standings, brackets and a TV mode — no logins.'],
          ['You stay in control', 'Admin and scorer passcodes; competitors can look but not touch. Contact details stay private.'],
        ].map(([title, text]) => (
          <div className="card" key={title}>
            <h3>{title}</h3>
            <div className="muted small">{text}</div>
          </div>
        ))}
      </div>
    </>
  );
}
