import { useState } from 'react';
import { Crown, HandHeart, Star, TrendingUp } from 'lucide-react';
import { Modal } from './ui';
import { BRAND } from '../brand';
import type { EventInfo } from '../state/useEventInfo';

/** Total raised = $20 per player + extra donations + money raised elsewhere. */
export function raisedTotal(info: EventInfo): number {
  const f = info.fundraising;
  return Math.round((f.players || info.registrations) * BRAND.payment.feeAmount + f.donations + f.extra);
}

const money = (n: number) => `$${n.toLocaleString('en-US', { maximumFractionDigits: 0 })}`;

/** GoFundMe-style progress card. */
export function FundraiserCard({ info, cta }: { info: EventInfo | null; cta?: boolean }) {
  if (!info) return null;
  const raised = raisedTotal(info);
  const goal = info.fundraising.goal;
  if (!raised && !goal) return null;
  const pct = goal ? Math.min(100, Math.round((raised / goal) * 100)) : 0;
  const supporters = info.fundraising.players || info.registrations;
  return (
    <div className="fund-card">
      <div className="fund-top">
        <div>
          <div className="fund-raised">{money(raised)}</div>
          <div className="small muted">
            raised{goal ? ` of ${money(goal)} goal` : ''} for SACS and the {BRAND.charity.name}
          </div>
        </div>
        {goal > 0 && <div className="fund-pct">{pct}%</div>}
      </div>
      {goal > 0 && (
        <div className="fund-bar" role="progressbar" aria-valuenow={pct} aria-valuemin={0} aria-valuemax={100}>
          <div style={{ width: `${pct}%` }} />
        </div>
      )}
      <div className="fund-stats">
        <span>
          <b>{info.registrations}</b> {info.registrations === 1 ? 'donation' : 'donations'}
        </span>
        <span>
          <b>{supporters}</b> {supporters === 1 ? 'player' : 'players'}
        </span>
        {info.fundraising.donors > 0 && (
          <span>
            <b>{info.fundraising.donors}</b> gave extra
          </span>
        )}
      </div>
      {cta && (
        <div className="row" style={{ marginTop: 12 }}>
          <a className="btn btn-primary" href="#/register">
            <HandHeart size={16} /> Register &amp; donate
          </a>
          {BRAND.donateUrl && (
            <a className="btn" href={BRAND.donateUrl} target="_blank" rel="noreferrer">
              Just donate
            </a>
          )}
        </div>
      )}
    </div>
  );
}

interface Gift {
  name: string;
  amount: number;
  at: string;
}

function gifts(info: EventInfo): Gift[] {
  return (info.fundraising.list ?? []).map((d) => ({
    name: d.name,
    amount: d.players * BRAND.payment.feeAmount + d.extra,
    at: d.at,
  }));
}

function when(at: string): string {
  const t = Date.parse(at);
  if (Number.isNaN(t)) return '';
  const days = Math.floor((Date.now() - t) / 86400000);
  if (days <= 0) return 'today';
  if (days === 1) return 'yesterday';
  if (days < 30) return `${days} days ago`;
  return new Date(t).toLocaleDateString(undefined, { month: 'short', day: 'numeric' });
}

/** GoFundMe-style list of every donation with the top donor highlighted. */
export function DonationWall({ info }: { info: EventInfo | null }) {
  const [all, setAll] = useState(false);
  if (!info) return null;
  const list = gifts(info);
  if (!list.length) return null;
  const top = list.reduce((best, g) => (g.amount > best.amount ? g : best), list[0]);
  const shown = all ? list : list.slice(0, 8);
  return (
    <div className="donation-wall">
      <div className="top-donor">
        <span className="top-icon">
          <Crown size={20} />
        </span>
        <div style={{ minWidth: 0 }}>
          <div className="eyebrow">Top donor</div>
          <div className="top-name">{top.name}</div>
        </div>
        <div className="top-amount">{money(top.amount)}</div>
      </div>
      <div className="card list-card" style={{ marginTop: 10 }}>
        <div className="row-between" style={{ padding: '12px 14px 4px' }}>
          <h3 style={{ margin: 0 }}>Donations</h3>
          <span className="small muted">{list.length} so far</span>
        </div>
        {shown.map((g, i) => (
          <div className="donation-row" key={i}>
            <span className="donation-heart">
              <HandHeart size={16} />
            </span>
            <span className="truncate bold">{g.name}</span>
            <span className="donation-amount">{money(g.amount)}</span>
            <span className="tiny muted donation-when">{when(g.at)}</span>
          </div>
        ))}
        {list.length > 8 && (
          <div style={{ padding: '8px 14px 12px' }}>
            <button className="btn btn-sm btn-ghost" onClick={() => setAll((v) => !v)}>
              {all ? 'Show fewer' : `See all ${list.length}`}
            </button>
          </div>
        )}
      </div>
    </div>
  );
}

/** GoFundMe-style short time: "44 mins", "2 hrs", "3 d". */
function ago(at: string): string {
  const t = Date.parse(at);
  if (Number.isNaN(t)) return '';
  const m = Math.max(1, Math.floor((Date.now() - t) / 60000));
  if (m < 60) return `${m} min${m === 1 ? '' : 's'}`;
  const h = Math.floor(m / 60);
  if (h < 24) return `${h} hr${h === 1 ? '' : 's'}`;
  const d = Math.floor(h / 24);
  if (d < 30) return `${d} d`;
  return new Date(t).toLocaleDateString(undefined, { month: 'short', day: 'numeric' });
}

function Ring({ pct }: { pct: number }) {
  const r = 30;
  const c = 2 * Math.PI * r;
  return (
    <svg className="gf-ring" viewBox="0 0 72 72" role="img" aria-label={`${pct}% of goal`}>
      <circle cx="36" cy="36" r={r} className="gf-ring-track" />
      <circle
        cx="36"
        cy="36"
        r={r}
        className="gf-ring-fill"
        strokeDasharray={c}
        strokeDashoffset={c * (1 - pct / 100)}
        transform="rotate(-90 36 36)"
      />
      <text x="36" y="41" textAnchor="middle">
        {pct}%
      </text>
    </svg>
  );
}

function GiftRow({ g, tag }: { g: Gift; tag?: string }) {
  return (
    <div className="gf-gift">
      <span className="gf-gift-icon">
        <HandHeart size={18} />
      </span>
      <div style={{ minWidth: 0 }}>
        <div className="truncate bold">{g.name}</div>
        <div className="small">
          <b>{money(g.amount)}</b>
          {tag ? (
            <>
              {' '}
              · <span className="gf-tag">{tag}</span>
            </>
          ) : g.at ? (
            <span className="muted"> · {ago(g.at)}</span>
          ) : null}
        </div>
      </div>
    </div>
  );
}

/** The sticky GoFundMe-style card: ring, raised of goal, buttons, recent + top donations. */
export function FundraiserSidebar({ info, onDonate }: { info: EventInfo | null; onDonate: () => void }) {
  const [modal, setModal] = useState<'all' | 'top' | null>(null);
  const [copied, setCopied] = useState(false);
  const raised = info ? raisedTotal(info) : 0;
  const goal = info?.fundraising.goal ?? 0;
  const pct = goal ? Math.min(100, Math.round((raised / goal) * 100)) : 0;
  const list = info ? gifts(info) : [];
  const top = list.length ? list.reduce((best, g) => (g.amount > best.amount ? g : best), list[0]) : null;
  const recent = list.filter((g) => g !== top).slice(0, 2);
  const lastDay = list.filter((g) => Date.now() - Date.parse(g.at) < 86400000).length;

  const share = async () => {
    const url = window.location.href;
    const data = { title: BRAND.eventName, text: `Play or donate: ${BRAND.eventName}`, url };
    try {
      if (navigator.share) return await navigator.share(data);
      await navigator.clipboard.writeText(url);
      setCopied(true);
      setTimeout(() => setCopied(false), 2000);
    } catch {
      /* cancelled */
    }
  };

  const modalList = modal === 'top' ? [...list].sort((a, b) => b.amount - a.amount) : list;

  return (
    <div className="gf-card">
      <div className="gf-head">
        <div style={{ minWidth: 0 }}>
          <div className="gf-raised">
            {money(raised)} <span>raised</span>
          </div>
          <div className="small muted">
            {goal ? `${money(goal)} goal · ` : ''}
            {list.length || info?.registrations || 0} {(list.length || info?.registrations) === 1 ? 'donation' : 'donations'}
          </div>
        </div>
        {goal > 0 && <Ring pct={pct} />}
      </div>
      <div className="gf-actions">
        <button className="btn btn-primary btn-lg gf-btn" type="button" onClick={onDonate}>
          Register &amp; donate
        </button>
        <button className="btn btn-lg gf-btn gf-share" type="button" onClick={() => void share()}>
          {copied ? 'Link copied!' : 'Share'}
        </button>
        {BRAND.donateUrl && (
          <a className="btn gf-btn" href={BRAND.donateUrl} target="_blank" rel="noreferrer">
            Just donate
          </a>
        )}
      </div>
      <div className="gf-price">
        <b>${BRAND.payment.feeAmount} per person</b> to play · ${BRAND.payment.feeAmount * 2} for a team of two
      </div>
      {lastDay > 0 && (
        <div className="gf-trend">
          <span className="gf-trend-icon">
            <TrendingUp size={16} />
          </span>
          <b>{lastDay === 1 ? '1 person' : `${lastDay} people`} just donated</b>
        </div>
      )}
      {top ? (
        <div className="gf-list">
          {recent.slice(0, 1).map((g, i) => (
            <GiftRow key={`r${i}`} g={g} />
          ))}
          <GiftRow g={top} tag="Top donation" />
          {recent.slice(1).map((g, i) => (
            <GiftRow key={`s${i}`} g={g} />
          ))}
        </div>
      ) : (
        <p className="small muted" style={{ margin: '14px 0 0' }}>
          Be the first to donate. It’s ${BRAND.payment.feeAmount} per person to play.
        </p>
      )}
      {list.length > 0 && (
        <div className="gf-more">
          <button className="btn btn-sm" type="button" onClick={() => setModal('all')}>
            See all
          </button>
          <button className="btn btn-sm" type="button" onClick={() => setModal('top')}>
            <Star size={14} /> See top
          </button>
        </div>
      )}
      {modal && (
        <Modal
          title={modal === 'top' ? 'Top donations' : `Donations (${list.length})`}
          subtitle={`${money(raised)} raised${goal ? ` of ${money(goal)}` : ''}`}
          onClose={() => setModal(null)}
        >
          <div className="gf-modal-list">
            {modalList.map((g, i) => (
              <GiftRow key={i} g={g} tag={modal === 'top' && i === 0 ? 'Top donation' : undefined} />
            ))}
          </div>
        </Modal>
      )}
    </div>
  );
}
