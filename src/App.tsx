import { useState } from 'react';
import type { ReactNode } from 'react';
import {
  Activity,
  ClipboardList,
  Ellipsis,
  House,
  LayoutGrid,
  LogIn,
  LogOut,
  Settings as SettingsIcon,
  ShieldCheck,
  Trophy,
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
import { useRoute } from './state/router';
import { useStore } from './state/store';
import { useEventInfo } from './state/useEventInfo';

export function App() {
  const route = useRoute();
  const [login, setLogin] = useState(false);
  const [more, setMore] = useState(false);


  return (
    <>
      <Header />
      <DraftBar />
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

/** Organizers only: the draw is a draft until they publish it. */
function DraftBar() {
  const { t, isAdmin, update } = useStore();
  const route = useRoute();
  if (!t || !isAdmin || t.published === true || route.parts[0] === 'admin') return null;
  return (
    <div className="draft-bar" role="status">
      <span>
        <b>Draft.</b> Only organizers can see this draw. Edit courts, matchups and teams as much as you like.
      </span>
      <button
        className="btn btn-primary btn-sm"
        onClick={() => {
          if (window.confirm('Publish the draw? Everyone will see the courts, teams and schedule, and registration closes.'))
            update((tt) => ({ ...tt, published: true, updatedAt: Date.now() }));
        }}
      >
        Publish to players
      </button>
    </div>
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
  const all: NavItem[] = [
    { path: '', label: 'Home', icon: <House size={18} /> },
    { path: 'teams', label: 'My team', icon: <UserRound size={18} /> },
    { path: 'courts', label: 'Courts', icon: <LayoutGrid size={18} />, match: ['courts', 'score', 'matches'] },
    { path: 'standings', label: 'Standings', icon: <Trophy size={18} />, match: ['standings', 'brackets'] },
  ];
  if (isAdmin) all.push({ path: 'admin', label: 'Organizer', icon: <SettingsIcon size={18} /> });
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
    : BRAND.organizer;

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
          {sync && t && sync.role !== 'viewer' && (
            <span className={`sync-pill ${syncState.status}`} title={syncState.message ?? 'Saved to the Google Sheet'}>
              <span className="dot" />
              {syncState.status === 'synced'
                ? 'Synced'
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


function Landing() {
  const { info } = useEventInfo();
  return (
    <>
      <section className="hero">
        <Toran />
        <Mandala />
        <div className="eyebrow">{BRAND.organizer}</div>
        <h1>
          <span className="wordmark hero-wordmark">{BRAND.short}</span>
          Pickleball <span className="hl">Tournament</span>
        </h1>
        <p>A doubles tournament supporting SACS and the {BRAND.charity.name}.</p>
        <dl className="facts">
          <div>
            <dt>Date</dt>
            <dd>{BRAND.when}</dd>
          </div>
          <div>
            <dt>Registration</dt>
            <dd>${BRAND.payment.feeAmount} per player</dd>
          </div>
          <div>
            <dt>Divisions</dt>
            <dd>Adults · Kids/Teens</dd>
          </div>
          <div>
            <dt>Format</dt>
            <dd>{BRAND.minGames}-game minimum</dd>
          </div>
        </dl>
        <div className="row" style={{ gap: 14, alignItems: 'center' }}>
          <a className="btn btn-primary btn-lg" href="#/register">
            Register
          </a>
          <a className="btn btn-lg btn-on-night" href="#/register?donate=1">
            Donate
          </a>
        </div>
      </section>

      <div style={{ marginTop: 16 }}>
        <FundraiserCard info={info} />
      </div>
      <div style={{ marginTop: 16 }}>
        <CauseCard />
      </div>

      <div className="section-title">
        <h2>About SACS</h2>
      </div>
      <div className="about-sacs card">
        <p style={{ margin: 0 }}>
          The {BRAND.organizer} is a student-run dance production with more than 100 performers from five San Diego high
          schools. Proceeds from the tournament support the show and the {BRAND.charity.name}.
        </p>
        <div className="photo-grid">
          <figure>
            <img src="./photos/sacs-bhangra.webp" alt="SACS dancers in matching white and colored costumes" loading="lazy" />
          </figure>
          <figure>
            <img src="./photos/sacs-guys.webp" alt="SACS dancers posing together on the steps after the show" loading="lazy" />
          </figure>
        </div>
      </div>

    </>
  );
}
