import { useEffect } from 'react';
import type { ReactNode } from 'react';
import { ExternalLink, HandHeart, X } from 'lucide-react';
import { BRAND } from '../brand';
import type { Tournament } from '../lib/types';

export function Modal({
  title,
  subtitle,
  onClose,
  children,
  wide,
}: {
  title: ReactNode;
  subtitle?: ReactNode;
  onClose: () => void;
  children: ReactNode;
  wide?: boolean;
}) {
  useEffect(() => {
    const onKey = (e: KeyboardEvent) => e.key === 'Escape' && onClose();
    window.addEventListener('keydown', onKey);
    const prev = document.body.style.overflow;
    document.body.style.overflow = 'hidden';
    return () => {
      window.removeEventListener('keydown', onKey);
      document.body.style.overflow = prev;
    };
  }, [onClose]);
  return (
    <div className="modal-backdrop" onMouseDown={(e) => e.target === e.currentTarget && onClose()}>
      <div className="modal" role="dialog" aria-modal="true" style={wide ? { maxWidth: 760 } : undefined}>
        <div className="modal-head">
          <div style={{ minWidth: 0 }}>
            <h2 style={{ margin: 0 }}>{title}</h2>
            {subtitle && <div className="muted small">{subtitle}</div>}
          </div>
          <button className="btn btn-ghost btn-sm" onClick={onClose} aria-label="Close">
            <X size={18} />
          </button>
        </div>
        {children}
      </div>
    </div>
  );
}

export function Progress({ value, total }: { value: number; total: number }) {
  const pct = total ? Math.round((value / total) * 100) : 0;
  return (
    <div className="progress" title={`${value} of ${total}`}>
      <div style={{ width: `${pct}%` }} />
    </div>
  );
}

export function ProgressRing({ value, total, label }: { value: number; total: number; label: string }) {
  const pct = total ? value / total : 0;
  const r = 64;
  const c = 2 * Math.PI * r;
  return (
    <div className="ring">
      <svg width="148" height="148" viewBox="0 0 148 148" aria-hidden="true">
        <circle cx="74" cy="74" r={r} fill="none" stroke="rgba(255,255,255,0.1)" strokeWidth="10" />
        <circle
          cx="74"
          cy="74"
          r={r}
          fill="none"
          stroke="var(--ball)"
          strokeWidth="10"
          strokeLinecap="round"
          strokeDasharray={`${c * pct} ${c}`}
          style={{ filter: 'drop-shadow(0 0 6px rgba(212,255,58,0.6))', transition: 'stroke-dasharray .6s' }}
        />
      </svg>
      <div className="ring-label">
        <b>{Math.round(pct * 100)}%</b>
        <span>{label}</span>
      </div>
    </div>
  );
}

export function Segmented<T extends string | number>({
  value,
  options,
  onChange,
}: {
  value: T;
  options: Array<{ value: T; label: ReactNode }>;
  onChange: (v: T) => void;
}) {
  return (
    <div className="segmented" role="tablist">
      {options.map((o) => (
        <button
          key={String(o.value)}
          type="button"
          role="tab"
          aria-selected={o.value === value}
          className={o.value === value ? 'on' : ''}
          onClick={() => onChange(o.value)}
        >
          {o.label}
        </button>
      ))}
    </div>
  );
}

export function Empty({ title, children }: { title: string; children?: ReactNode }) {
  return (
    <div className="card empty">
      <h2 style={{ color: 'var(--ink)' }}>{title}</h2>
      {children}
    </div>
  );
}

/** A pickleball in SACS marigold. */
export function BallIcon({ size = 30, className }: { size?: number; className?: string }) {
  return (
    <svg width={size} height={size} viewBox="0 0 32 32" aria-hidden="true" className={className}>
      <defs>
        <radialGradient id="ballShade" cx="35%" cy="30%" r="75%">
          <stop offset="0%" stopColor="#fff0b3" />
          <stop offset="55%" stopColor="#ffb81c" />
          <stop offset="100%" stopColor="#e07a00" />
        </radialGradient>
      </defs>
      <circle cx="16" cy="16" r="15" fill="url(#ballShade)" />
      {[
        [10, 8.5],
        [18, 6.5],
        [24, 12],
        [7.5, 16],
        [15, 14.5],
        [22.5, 20],
        [11.5, 23.5],
        [18.5, 25],
      ].map(([x, y], i) => (
        <circle key={i} cx={x} cy={y} r="1.9" fill="#8a3d00" opacity="0.5" />
      ))}
    </svg>
  );
}

/** Top-down court line art used as a background texture. */
export function CourtLines({ className = 'court-lines' }: { className?: string }) {
  return (
    <svg className={className} viewBox="0 0 880 400" preserveAspectRatio="xMidYMid slice" aria-hidden="true">
      <g fill="none" stroke="#fff" strokeWidth="3">
        <rect x="40" y="40" width="800" height="320" />
        <line x1="440" y1="24" x2="440" y2="376" strokeWidth="5" strokeDasharray="2 6" />
        <line x1="313" y1="40" x2="313" y2="360" />
        <line x1="567" y1="40" x2="567" y2="360" />
        <line x1="40" y1="200" x2="313" y2="200" />
        <line x1="567" y1="200" x2="840" y2="200" />
      </g>
    </svg>
  );
}

const AVATAR_COLORS = ['#8a2bb5', '#ff2e88', '#0f7b86', '#e85d04', '#c1121f', '#2a9d8f', '#7b2cbf', '#d97706', '#1d6fa5', '#b5179e'];

function hash(s: string): number {
  let h = 0;
  for (let i = 0; i < s.length; i++) h = (h * 31 + s.charCodeAt(i)) | 0;
  return Math.abs(h);
}

export function initials(name: string): string {
  const parts = name.trim().split(/\s+/).filter(Boolean);
  if (!parts.length) return '?';
  if (parts.length === 1) return parts[0].slice(0, 2).toUpperCase();
  return (parts[0][0] + parts[parts.length - 1][0]).toUpperCase();
}

export function Avatar({ name, size = 28 }: { name: string; size?: number }) {
  return (
    <span
      className="avatar"
      style={{ ['--size' as string]: `${size}px`, background: AVATAR_COLORS[hash(name) % AVATAR_COLORS.length] }}
      title={name}
    >
      {initials(name)}
    </span>
  );
}

/** Overlapping player avatars for a team (or a dashed placeholder when unknown). */
export function TeamAvatars({ t, teamId, size = 28 }: { t: Tournament; teamId: string | null | undefined; size?: number }) {
  const team = teamId && teamId !== 'BYE' ? t.teams[teamId] : undefined;
  if (!team) return <span className="tbd-dot" style={{ width: size, height: size }} />;
  const names = team.playerIds.map((id) => t.players[id]?.name).filter((n): n is string => !!n);
  if (!names.length) names.push(team.name);
  return (
    <span className="avatars">
      {names.slice(0, 2).map((n) => (
        <Avatar key={n} name={n} size={size} />
      ))}
    </span>
  );
}

export function minutesLabel(min: number | undefined): string {
  if (min === undefined) return '';
  if (min <= 0) return 'Up now';
  if (min < 60) return `~${min} min`;
  const h = Math.floor(min / 60);
  const m = min % 60;
  return `~${h}h${m ? ` ${m}m` : ''}`;
}

export function timeAgo(ts: number | undefined): string {
  if (!ts) return '';
  const s = Math.round((Date.now() - ts) / 1000);
  if (s < 60) return 'just now';
  if (s < 3600) return `${Math.floor(s / 60)} min ago`;
  return `${Math.floor(s / 3600)}h ago`;
}

/** Renders a name with the event wordmark (e.g. "SACS") set in the display font. */
export function BrandName({ name }: { name: string }) {
  const parts = name.split(BRAND.short);
  if (parts.length < 2) return <>{name}</>;
  return (
    <>
      {parts.map((part, i) => (
        <span key={i}>
          {i > 0 && <span className="wordmark">{BRAND.short}</span>}
          {part}
        </span>
      ))}
    </>
  );
}

/** Marigold-and-mango-leaf garland (toran) used along the top of banners. */
export function Toran() {
  const petals = Array.from({ length: 8 }, (_, i) => {
    const a = (i / 8) * Math.PI * 2;
    return [Math.cos(a) * 5.5, Math.sin(a) * 5.5];
  });
  return (
    <svg className="toran" aria-hidden="true" preserveAspectRatio="none">
      <defs>
        <pattern id="toranPattern" width="64" height="40" patternUnits="userSpaceOnUse">
          <path d="M0 3 Q32 13 64 3" stroke="#f7c873" strokeWidth="1.5" fill="none" opacity="0.8" />
          <path d="M16 7 C11 13 12 21 16 26 C20 21 21 13 16 7 Z" fill="#1f9d6b" />
          <path d="M48 7 C43 13 44 21 48 26 C52 21 53 13 48 7 Z" fill="#178a5c" />
          <line x1="32" y1="8" x2="32" y2="15" stroke="#f7c873" strokeWidth="1.2" />
          <g transform="translate(32 22)">
            {petals.map(([x, y], i) => (
              <circle key={i} cx={x} cy={y} r="4" fill={i % 2 ? '#ff9f1c' : '#ffb81c'} />
            ))}
            <circle r="4.5" fill="#f77f00" />
            <circle r="1.8" fill="#ffd166" />
          </g>
        </pattern>
      </defs>
      <rect width="100%" height="40" fill="url(#toranPattern)" />
    </svg>
  );
}

/** Line-art mandala, drawn in currentColor. */
export function Mandala({ className = 'mandala' }: { className?: string }) {
  const rings = [
    { n: 8, r: 62, rx: 16, ry: 40 },
    { n: 12, r: 112, rx: 13, ry: 32 },
    { n: 16, r: 158, rx: 10, ry: 24 },
    { n: 24, r: 196, rx: 6, ry: 13 },
  ];
  return (
    <svg className={className} viewBox="-225 -225 450 450" aria-hidden="true">
      <g fill="none" stroke="currentColor" strokeWidth="2.2">
        {[24, 34, 88, 136, 180, 214].map((r) => (
          <circle key={r} r={r} />
        ))}
        {rings.map((ring) =>
          Array.from({ length: ring.n }, (_, i) => (
            <ellipse key={`${ring.r}-${i}`} cx="0" cy={-ring.r} rx={ring.rx} ry={ring.ry} transform={`rotate(${(360 / ring.n) * i})`} />
          )),
        )}
      </g>
      <g fill="currentColor">
        {Array.from({ length: 36 }, (_, i) => {
          const a = (i / 36) * Math.PI * 2;
          return <circle key={i} cx={Math.cos(a) * 205} cy={Math.sin(a) * 205} r="3" />;
        })}
      </g>
    </svg>
  );
}

/** "Playing for a cause" card for the charity partner. */
export function CauseCard({ compact = false }: { compact?: boolean }) {
  return (
    <div className="cause">
      <span className="cause-icon">
        <HandHeart size={22} />
      </span>
      <div style={{ minWidth: 0 }}>
        <div className="cause-title">{BRAND.charity.name}</div>
        <div className="cause-text">
          {BRAND.charity.blurb}
          {!compact && ` ${BRAND.charity.pledge}`}
        </div>
      </div>
      <div className="row" style={{ gap: 6, flexWrap: 'nowrap' }}>
        {BRAND.donateUrl && (
          <a className="btn btn-sm btn-primary" href={BRAND.donateUrl} target="_blank" rel="noreferrer">
            Donate <ExternalLink size={13} />
          </a>
        )}
        <a className="btn btn-sm" href={BRAND.charity.url} target="_blank" rel="noreferrer">
          Learn more <ExternalLink size={13} />
        </a>
      </div>
    </div>
  );
}
