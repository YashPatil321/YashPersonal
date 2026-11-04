import { HandHeart } from 'lucide-react';
import { BRAND } from '../brand';
import type { EventInfo } from '../state/useEventInfo';

/** Total raised = entry fees (per registration) + extra donations + money raised elsewhere. */
export function raisedTotal(info: EventInfo): number {
  const f = info.fundraising;
  return Math.round(info.registrations * BRAND.payment.feeAmount + f.donations + f.extra);
}

const money = (n: number) => `$${n.toLocaleString('en-US', { maximumFractionDigits: 0 })}`;

/** GoFundMe-style progress card. */
export function FundraiserCard({ info, cta }: { info: EventInfo | null; cta?: boolean }) {
  if (!info) return null;
  const raised = raisedTotal(info);
  const goal = info.fundraising.goal;
  if (!raised && !goal) return null;
  const pct = goal ? Math.min(100, Math.round((raised / goal) * 100)) : 0;
  const supporters = info.registrations;
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
          <b>{supporters}</b> {supporters === 1 ? 'sign-up' : 'sign-ups'}
        </span>
        {info.fundraising.donors > 0 && (
          <span>
            <b>{info.fundraising.donors}</b> extra {info.fundraising.donors === 1 ? 'donation' : 'donations'}
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
