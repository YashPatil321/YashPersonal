import { useState } from 'react';
import type { ReactNode } from 'react';
import {
  Activity,
  Ellipsis,
  FileSpreadsheet,
  House,
  LayoutGrid,
  ListOrdered,
  LogIn,
  LogOut,
  Network,
  Plus,
  Settings as SettingsIcon,
  ShieldCheck,
  Smartphone,
  Trophy,
  Tv,
  UserRound,
} from 'lucide-react';
import { detectColumns, DEFAULT_IMPORT_OPTIONS, importRegistrations, seedTeams } from './lib/registrations';
import { sampleRegistrations } from './lib/sample';
import { buildTournament, courtNames, defaultDivisionSettings } from './lib/tournament';
import { BallIcon, CourtLines, Modal } from './components/ui';
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
  const [login, setLogin] = useState(false);
  const [more, setMore] = useState(false);

  if (page === 'tv' && t) return <TV />;

  return (
    <>
      <Header onLogin={() => setLogin(true)} />
      <main key={route.path}>
        <Page />
      </main>
      <BottomNav onMore={() => setMore(true)} />
      {login && <LoginModal onClose={() => setLogin(false)} />}
      {more && (
        <MoreSheet
          onClose={() => setMore(false)}
          onLogin={() => {
            setMore(false);
            setLogin(true);
          }}
        />
      )}
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
/* Navigation                                                         */
/* ------------------------------------------------------------------ */

interface NavItem {
  path: string;
  label: string;
  icon: ReactNode;
  match?: string[];
}

function useNavItems() {
  const { t, isAdmin } = useStore();
  const hasBrackets = !!t?.divisions.some((d) => d.settings.format !== 'round_robin');
  const all: NavItem[] = [];
  all.push({ path: '', label: 'Home', icon: <House size={18} /> });
  if (t) {
    all.push({ path: 'teams', label: t.settings.doubles ? 'My team' : 'Me', icon: <UserRound size={18} /> });
    all.push({ path: 'courts', label: 'Courts', icon: <LayoutGrid size={18} />, match: ['courts', 'score'] });
    all.push({ path: 'matches', label: 'Matches', icon: <ListOrdered size={18} /> });
    all.push({ path: 'standings', label: 'Standings', icon: <Trophy size={18} />, match: hasBrackets ? ['standings'] : ['standings', 'brackets'] });
    if (hasBrackets) all.push({ path: 'brackets', label: 'Brackets', icon: <Network size={18} /> });
    all.push({ path: 'tv', label: 'TV', icon: <Tv size={18} /> });
  }
  if (isAdmin && !t) all.push({ path: 'setup', label: 'Create', icon: <Plus size={18} /> });
  if (isAdmin) all.push({ path: 'settings', label: 'Settings', icon: <SettingsIcon size={18} /> });
  return all;
}

function isActive(item: NavItem, current: string) {
  return item.match ? item.match.includes(current) : item.path === current;
}

function Header({ onLogin }: { onLogin: () => void }) {
  const route = useRoute();
  const { t, sync, syncState } = useStore();
  const current = route.parts[0] ?? '';
  const items = useNavItems();
  const sub = t
    ? [t.date && new Date(t.date + 'T12:00:00').toLocaleDateString(undefined, { month: 'short', day: 'numeric' }), t.location]
        .filter(Boolean)
        .join(' · ') || 'Live results'
    : 'Brackets · scores · standings';

  return (
    <header className="app-header">
      <div className="header-inner">
        <a className="brand" href="#/">
          <BallIcon size={34} className="ball-spin" />
          <div style={{ minWidth: 0 }}>
            <div className="brand-title truncate">{t?.name ?? 'Pickleball Tournament'}</div>
            <div className="brand-sub truncate">{sub}</div>
          </div>
        </a>
        <nav className="nav">
          {items.map((item) => (
            <a key={item.path} href={`#/${item.path}`} className={isActive(item, current) ? 'active' : ''}>
              {item.label}
            </a>
          ))}
        </nav>
        <div className="header-actions">
          {sync && (
            <span className={`sync-pill ${syncState.status}`} title={syncState.message ?? 'Live sync'}>
              <span className="dot" />
              {syncState.status === 'synced'
                ? 'Live'
                : syncState.status === 'saving'
                  ? 'Saving'
                  : syncState.status === 'connecting'
                    ? 'Connecting'
                    : 'Offline'}
            </span>
          )}
          <AccountButton onLogin={onLogin} />
        </div>
      </div>
    </header>
  );
}

function BottomNav({ onMore }: { onMore: () => void }) {
  const route = useRoute();
  const { t } = useStore();
  const current = route.parts[0] ?? '';
  const items = useNavItems();
  const primaryPaths = t ? ['', 'teams', 'courts', 'standings'] : items.map((i) => i.path).slice(0, 4);
  const primary = items.filter((i) => primaryPaths.includes(i.path));
  const overflow = items.filter((i) => !primaryPaths.includes(i.path));
  const moreActive = overflow.some((i) => isActive(i, current)) && !(t && current === 'brackets');
  const cols = primary.length + (overflow.length || t ? 1 : 0);
  return (
    <nav className="bottom-nav" style={{ gridTemplateColumns: `repeat(${cols}, 1fr)` }}>
      {primary.map((item) => (
        <a
          key={item.path}
          href={`#/${item.path}`}
          className={isActive(item, current) || (item.path === 'standings' && current === 'brackets') ? 'active' : ''}
        >
          {item.icon}
          {item.label}
        </a>
      ))}
      {(overflow.length > 0 || t) && (
        <button className={moreActive ? 'active' : ''} onClick={onMore}>
          <Ellipsis size={18} />
          More
        </button>
      )}
    </nav>
  );
}

function MoreSheet({ onClose, onLogin }: { onClose: () => void; onLogin: () => void }) {
  const { t, sync, connect } = useStore();
  const items = useNavItems().filter((i) => !(t ? ['', 'teams', 'courts', 'standings'] : []).includes(i.path));
  return (
    <Modal title="More" onClose={onClose}>
      <div className="more-sheet">
        {items.map((item) => (
          <a key={item.path} href={`#/${item.path}`} onClick={onClose}>
            {item.icon}
            {item.label}
          </a>
        ))}
        {sync?.role === 'viewer' && (
          <button onClick={onLogin}>
            <LogIn size={18} /> Organizer login
          </button>
        )}
        {sync && sync.role !== 'viewer' && (
          <button
            onClick={() => {
              void connect({ url: sync.url, role: 'viewer' });
              onClose();
            }}
          >
            <LogOut size={18} /> Sign out ({sync.role})
          </button>
        )}
      </div>
    </Modal>
  );
}

function AccountButton({ onLogin }: { onLogin: () => void }) {
  const { sync, connect } = useStore();
  if (!sync) return null;
  if (sync.role === 'viewer') {
    return (
      <button className="btn btn-sm btn-glass" onClick={onLogin}>
        <LogIn size={15} /> Login
      </button>
    );
  }
  return (
    <button
      className="btn btn-sm btn-primary"
      title="Signed in. Click to sign out."
      onClick={() => {
        if (window.confirm(`You're signed in as ${sync.role}. Sign out on this device?`)) {
          void connect({ url: sync.url, role: 'viewer' });
        }
      }}
    >
      <ShieldCheck size={15} /> {sync.role === 'admin' ? 'Admin' : 'Scorer'}
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
    <Modal title="Organizer login" subtitle="Admins run the tournament. Scorers can enter scores." onClose={onClose}>
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
          <span className="muted tiny">Players don’t need to sign in. Live results are public.</span>
        </div>
      </form>
    </Modal>
  );
}

/* ------------------------------------------------------------------ */
/* Landing                                                            */
/* ------------------------------------------------------------------ */

function AdminOnly() {
  return (
    <div className="card empty">
      <h2 style={{ color: 'var(--ink)' }}>Organizers only</h2>
      <p>Tap “Login” at the top and enter the admin passcode.</p>
    </div>
  );
}

function createDemo() {
  const rows = sampleRegistrations();
  const res = importRegistrations(rows, detectColumns(rows[0]), DEFAULT_IMPORT_OPTIONS);
  return buildTournament(
    {
      name: 'Demo Pickleball Classic',
      date: new Date().toISOString().slice(0, 10),
      location: 'Riverside Park',
      courts: courtNames(4),
      minutesPerMatch: 20,
      doubles: true,
    },
    res.players,
    res.teams,
    res.divisions.map((d) => ({
      name: d.name,
      teamIds: seedTeams(d.teamIds, res.teams, 'rating'),
      settings: defaultDivisionSettings(d.teamIds.length),
    })),
  );
}

const FEATURES: Array<[ReactNode, string, string]> = [
  [<FileSpreadsheet size={20} />, 'Google Form → teams', 'Reads your sign-up sheet, matches partners who registered separately and pairs players who need one.'],
  [<Network size={20} />, 'Any format', 'Round robin, pools into playoffs, single or double elimination, all with byes and seeding handled.'],
  [<LayoutGrid size={20} />, 'Court desk', 'Sends the next match to each open court automatically and never double-books a team.'],
  [<Activity size={20} />, 'Live scoring', 'Tap-to-score that calls the score for you (“4-2-1”), rally scoring, or type in the final.'],
  [<Smartphone size={20} />, 'Players see everything', 'Live courts, “find my team” with wait times, standings, brackets and TV mode. No logins.'],
  [<ShieldCheck size={20} />, 'You stay in control', 'Admin and scorer passcodes. Competitors can look but not touch, and contact details stay private.'],
];

function Welcome() {
  const { sync, isAdmin, replace, connect } = useStore();
  const [joinUrl, setJoinUrl] = useState('');
  const [error, setError] = useState<string | null>(null);

  if (sync && !isAdmin) {
    return (
      <section className="hero" style={{ textAlign: 'center' }}>
        <CourtLines />
        <BallIcon size={88} />
        <div className="eyebrow" style={{ marginTop: 18 }}>
          Stay tuned
        </div>
        <h1 style={{ margin: '10px auto 14px' }}>Draw coming soon</h1>
        <p style={{ margin: '0 auto' }}>
          The organizer hasn’t published the brackets yet. This page updates by itself, so keep it open or check back shortly.
        </p>
      </section>
    );
  }

  const join = async () => {
    setError(null);
    const raw = joinUrl.trim();
    let url = raw;
    try {
      url = new URL(raw).searchParams.get('live') ?? raw;
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
      <section className="hero">
        <CourtLines />
        <BallIcon size={220} className="hero-ball" />
        <div className="eyebrow">Pickleball tournament manager</div>
        <h1>
          From Google Form <span className="hl">to final point.</span>
        </h1>
        <p>
          Turn sign-ups into teams, pools, brackets, court assignments, live scores and standings. Players follow along on
          their phones, and only you can change anything.
        </p>
        <div className="row">
          <a className="btn btn-primary btn-lg" href="#/setup">
            <Plus size={18} /> Create a tournament
          </a>
          <button
            className="btn btn-glass btn-lg"
            onClick={() => {
              replace(createDemo());
              navigate('/');
            }}
          >
            Try the demo
          </button>
        </div>
      </section>

      <div className="card" style={{ marginTop: 16 }}>
        <div className="row-between" style={{ flexWrap: 'wrap', gap: 12 }}>
          <div>
            <h3 style={{ margin: 0 }}>Playing in a tournament?</h3>
            <div className="muted small">Paste the link your organizer shared to follow it live.</div>
          </div>
          <div className="row" style={{ flex: '1 1 320px', flexWrap: 'nowrap' }}>
            <input
              className="input"
              placeholder="Tournament link"
              value={joinUrl}
              onChange={(e) => setJoinUrl(e.target.value)}
              onKeyDown={(e) => e.key === 'Enter' && joinUrl && join()}
            />
            <button className="btn btn-dark" disabled={!joinUrl.trim()} onClick={join}>
              Open
            </button>
          </div>
        </div>
        {error && (
          <div className="alert alert-error small" style={{ marginTop: 10 }}>
            {error}
          </div>
        )}
      </div>

      <div className="feature-list">
        {FEATURES.map(([icon, title, text]) => (
          <div className="card" key={title}>
            <span className="feature-icon">{icon}</span>
            <h3>{title}</h3>
            <div className="muted small">{text}</div>
          </div>
        ))}
      </div>
    </>
  );
}
