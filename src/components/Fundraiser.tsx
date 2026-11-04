import { useState } from 'react';
import { Crown, HandHeart } from 'lucide-react';
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
