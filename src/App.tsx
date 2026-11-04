import { useState } from 'react';
import type { ReactNode } from 'react';
import {
  Activity,
  CalendarClock,
  ClipboardList,
  Ellipsis,
  House,
  LayoutGrid,
  ListOrdered,
  LogIn,
  LogOut,
  Network,
  Settings as SettingsIcon,
  ShieldCheck,
  Trophy,
  Tv,
  UserRound,
} from 'lucide-react';
import { BRAND } from './brand';
import { FundraiserCard } from './components/Fundraiser';
import { BallIcon, BrandName, CauseCard, Mandala, Modal, Toran } from './components/ui';
import { Admin } from './pages/Admin';
import { Courts } from './pages/Courts';
import { Matches } from './pages/Matches';
import { Overview } from './pages/Overview';
import { Register } from './pages/Register';
import { Scorekeeper } from './pages/Scorekeeper';
import { Settings } from './pages/Settings';
import { Setup } from './pages/Setup';
import { Brackets, Standings } from './pages/Standings';
import { TeamDetail, Teams } from './pages/Teams';
import { TV } from './pages/TV';
import { useRoute } from './state/router';
import { useStore } from './state/store';
import { useEventInfo } from './state/useEventInfo';

export function App() {
  const route = useRoute();
  const { t } = useStore();
  const [page] = route.parts;
  const [login, setLogin] = useState(false);
  const [more, setMore] = useState(false);

  if (page === 'tv' && t) return <TV />;

  return (
    <>
      <Header />
      <main key={route.path}>
        <Page onLogin={() => setLogin(true)} />
      </main>
      <Footer />
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

function Page({ onLogin }: { onLogin: () => void }) {
  const route = useRoute();
  const { t, isAdmin } = useStore();
  const [page, id] = route.parts;

  if (page === 'admin') return <Admin />;
  if (page === 'register') return <Register />;
  if (page === 'setup') return isAdmin ? <Setup /> : <AdminOnly onLogin={onLogin} />;
  if (page === 'settings') return isAdmin ? <Settings /> : <AdminOnly onLogin={onLogin} />;
  if (!t) return <Landing />;
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

/** Public navigation. Organizer pages only appear once the organizer has a draw on this device. */
function useNavItems() {
  const { t, isAdmin } = useStore();
  if (!t)
    return [
      { path: '', label: 'Home', icon: <House size={18} /> },
      { path: 'register', label: 'Register', icon: <ClipboardList size={18} /> },
    ] as NavItem[];
  const hasBrackets = t.divisions.some((d) => d.settings.format !== 'round_robin');
  const all: NavItem[] = [
    { path: '', label: 'Home', icon: <House size={18} /> },
    { path: 'teams', label: t.settings.doubles ? 'My team' : 'Me', icon: <UserRound size={18} /> },
    { path: 'courts', label: 'Courts', icon: <LayoutGrid size={18} />, match: ['courts', 'score'] },
    { path: 'matches', label: 'Matches', icon: <ListOrdered size={18} /> },
    {
      path: 'standings',
      label: 'Standings',
      icon: <Trophy size={18} />,
      match: hasBrackets ? ['standings'] : ['standings', 'brackets'],
    },
  ];
  if (hasBrackets) all.push({ path: 'brackets', label: 'Brackets', icon: <Network size={18} /> });
  all.push({ path: 'tv', label: 'TV', icon: <Tv size={18} /> });
  if (isAdmin) all.push({ path: 'settings', label: 'Settings', icon: <SettingsIcon size={18} /> });
  return all;
}

function isActive(item: NavItem, current: string) {
  return item.match ? item.match.includes(current) : item.path === current;
}

function Header() {
  const route = useRoute();
  const { t, sync, syncState } = useStore();
  const current = route.parts[0] ?? '';
  const items = useNavItems();
  const sub = t
    ? [t.date && new Date(t.date + 'T12:00:00').toLocaleDateString(undefined, { month: 'short', day: 'numeric' }), t.location]
        .filter(Boolean)
        .join(' · ') || BRAND.organizer
    : `${BRAND.organizer} · ${BRAND.tagline}`;

  return (
    <header className="app-header">
      <div className="header-inner">
        <a className="brand" href="#/">
          <BallIcon size={34} className="ball-spin" />
          <div style={{ minWidth: 0 }}>
            <div className="brand-title truncate">
              <BrandName name={t?.name ?? BRAND.eventName} />
            </div>
            <div className="brand-sub truncate">{sub}</div>
          </div>
        </a>
        {items.length > 0 && (
          <nav className="nav">
            {items.map((item) => (
              <a key={item.path} href={`#/${item.path}`} className={isActive(item, current) ? 'active' : ''}>
                {item.label}
              </a>
            ))}
          </nav>
        )}
        <div className="header-actions">
          {sync && t && (
            <span className={`sync-pill ${syncState.status}`} title={syncState.message ?? 'Live scores'}>
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
          <RoleBadge />
        </div>
      </div>
    </header>
  );
}

function BottomNav({ onMore }: { onMore: () => void }) {
  const route = useRoute();
  const current = route.parts[0] ?? '';
  const items = useNavItems();
  if (!items.length) return null;
  const primaryPaths = ['', 'teams', 'courts', 'standings', 'register'];
  const primary = items.filter((i) => primaryPaths.includes(i.path));
  const overflow = items.filter((i) => !primaryPaths.includes(i.path));
  const moreActive = overflow.some((i) => isActive(i, current)) && current !== 'brackets';
  const showMore = overflow.length > 0;
  return (
    <nav className="bottom-nav" style={{ gridTemplateColumns: `repeat(${primary.length + (showMore ? 1 : 0)}, 1fr)` }}>
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
      {showMore && (
        <button className={moreActive ? 'active' : ''} onClick={onMore}>
          <Ellipsis size={18} />
          More
        </button>
      )}
    </nav>
  );
}

function MoreSheet({ onClose, onLogin }: { onClose: () => void; onLogin: () => void }) {
  const { sync, connect } = useStore();
  const items = useNavItems().filter((i) => !['', 'teams', 'courts', 'standings'].includes(i.path));
  return (
    <Modal title="More" onClose={onClose}>
      <div className="more-sheet">
        {items.map((item) => (
          <a key={item.path} href={`#/${item.path}`} onClick={onClose}>
            {item.icon}
            {item.label}
          </a>
        ))}
        <a href={BRAND.charity.url} target="_blank" rel="noreferrer">
          <Activity size={18} /> About {BRAND.charity.name}
        </a>
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

function RoleBadge() {
  const { sync, connect } = useStore();
  if (!sync || sync.role === 'viewer') return null;
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

function Footer() {
  return (
    <footer className="site-footer">
      <div className="footer-inner">
        <div>
          <div className="brand-title">
            <BrandName name={BRAND.eventName} />
          </div>
          <div className="small muted">
            Hosted by the {BRAND.organizer}. {BRAND.charity.pledge}
          </div>
        </div>
        <div className="row">
          <a className="small" href={BRAND.charity.url} target="_blank" rel="noreferrer">
            {BRAND.charity.name}
          </a>
          <a className="btn btn-ghost btn-sm" href="#/admin">
            Organizer
          </a>
        </div>
      </div>
    </footer>
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
    <Modal title="Organizer login" subtitle="For the SACS team running the tournament." onClose={onClose}>
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
          <span className="muted tiny">Players don’t need to sign in.</span>
        </div>
      </form>
    </Modal>
  );
}

/* ------------------------------------------------------------------ */
/* Landing                                                            */
/* ------------------------------------------------------------------ */

function AdminOnly({ onLogin }: { onLogin: () => void }) {
  const { sync } = useStore();
  return (
    <div className="card empty">
      <h2 style={{ color: 'var(--ink)' }}>Organizers only</h2>
      <p>This page is for the SACS team running the tournament.</p>
      {sync?.role === 'viewer' ? (
        <button className="btn btn-primary" onClick={onLogin}>
          <LogIn size={16} /> Organizer login
        </button>
      ) : (
        <a className="btn btn-primary" href="#/admin">
          Go to the organizer page
        </a>
      )}
    </div>
  );
}

const DAY_OF: Array<[ReactNode, string, string]> = [
  [<UserRound size={20} />, 'Find your team', 'Type your name to see your court, when you play next and how you’re doing.'],
  [<LayoutGrid size={20} />, 'Live courts', 'All courts update point by point, so you know exactly when you’re up.'],
  [<Trophy size={20} />, 'Standings & brackets', 'Follow every pool and the playoff race all the way to the final.'],
];

function Landing() {
  const { info } = useEventInfo();
  return (
    <>
      <section className="hero">
        <Toran />
        <Mandala />
        <div className="eyebrow">{BRAND.organizer} presents</div>
        <h1>
          <span className="wordmark hero-wordmark">{BRAND.short}</span>
          Pickleball <span className="hl">Tournament</span>
        </h1>
        <p>
          Grab a partner and play for a cause. {BRAND.charity.pledge}
        </p>
        <div className="row" style={{ marginBottom: 22 }}>
          <span className="chip">
            <UserRound size={14} /> Adult &amp; Kids divisions
          </span>
          <span className="chip">
            <LayoutGrid size={14} /> {BRAND.courts} courts
          </span>
          <span className="chip">
            <CalendarClock size={14} /> About {BRAND.hours} hours of play
          </span>
          <span className="chip">
            <Activity size={14} /> Live scores on your phone
          </span>
        </div>
        <div className="row" style={{ gap: 14, alignItems: 'center' }}>
          <a className="btn btn-primary btn-lg" href="#/register">
            <ClipboardList size={18} /> Register your team
          </a>
          {info && info.registrations > 0 && (
            <span className="chip">
              <UserRound size={14} /> {info.registrations} signed up
            </span>
          )}
        </div>
        <div className="draw-soon" style={{ marginTop: 16 }}>
          <span className="dot" /> The draw comes out when sign-ups close. Keep this page handy: it turns into the live
          scoreboard on tournament day.
        </div>
      </section>

      <div style={{ marginTop: 16 }}>
        <FundraiserCard info={info} cta />
      </div>
      <div style={{ marginTop: 16 }}>
        <CauseCard />
      </div>

      <div className="section-title">
        <h2>On tournament day</h2>
      </div>
      <div className="feature-list" style={{ marginTop: 0 }}>
        {DAY_OF.map(([icon, title, text]) => (
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
