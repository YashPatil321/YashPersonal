import { useEffect } from 'react';
import type { ReactNode } from 'react';
import { X } from 'lucide-react';
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

/** A pickleball (lime with holes). */
export function BallIcon({ size = 30, className }: { size?: number; className?: string }) {
  return (
    <svg width={size} height={size} viewBox="0 0 32 32" aria-hidden="true" className={className}>
      <defs>
        <radialGradient id="ballShade" cx="35%" cy="30%" r="75%">
          <stop offset="0%" stopColor="#f2ff9a" />
          <stop offset="55%" stopColor="#d4ff3a" />
          <stop offset="100%" stopColor="#a6cf12" />
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
        <circle key={i} cx={x} cy={y} r="1.9" fill="#5f7a00" opacity="0.55" />
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

const AVATAR_COLORS = ['#2b5fd9', '#ff5a36', '#0f9f58', '#8b5cf6', '#e11d74', '#0e9fb5', '#d97706', '#4f46e5', '#0d9488', '#db2777'];

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
