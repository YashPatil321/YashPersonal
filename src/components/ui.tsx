import { useEffect } from 'react';
import type { ReactNode } from 'react';

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
            ✕
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
      <h3 style={{ color: 'var(--ink)' }}>{title}</h3>
      {children}
    </div>
  );
}

export function BallIcon({ size = 30 }: { size?: number }) {
  return (
    <svg width={size} height={size} viewBox="0 0 32 32" aria-hidden="true">
      <circle cx="16" cy="16" r="15" fill="#d4f04c" stroke="#1f2a04" strokeWidth="1.5" />
      {[
        [10, 9],
        [18, 7],
        [23, 13],
        [8, 17],
        [15, 15],
        [22, 21],
        [12, 24],
        [18, 25],
      ].map(([x, y], i) => (
        <circle key={i} cx={x} cy={y} r="1.9" fill="#1f2a04" opacity="0.8" />
      ))}
    </svg>
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
