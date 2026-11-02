import { Crown } from 'lucide-react';
import type { StandingRow } from '../lib/resolve';
import { teamName } from '../lib/tournament';
import type { Tournament } from '../lib/types';
import { TeamAvatars } from './ui';

export function StandingsTable({
  t,
  rows,
  advancing = 0,
  qualified,
}: {
  t: Tournament;
  rows: StandingRow[];
  /** Highlight the top N rows as advancing. */
  advancing?: number;
  qualified?: Set<string>;
}) {
  return (
    <div className="table-wrap">
      <table className="table">
        <thead>
          <tr>
            <th>#</th>
            <th>Team</th>
            <th className="num" title="Wins-Losses">
              W-L
            </th>
            <th className="num" title="Games won-lost">
              Games
            </th>
            <th className="num" title="Points for">
              PF
            </th>
            <th className="num" title="Points against">
              PA
            </th>
            <th className="num" title="Point differential">
              +/-
            </th>
          </tr>
        </thead>
        <tbody>
          {rows.map((r) => {
            const adv = qualified ? qualified.has(r.teamId) : r.played > 0 && r.rank <= advancing;
            return (
              <tr key={r.teamId} className={adv ? 'advancing' : ''}>
                <td>
                  <span className="rank">{r.rank}</span>
                </td>
                <td className="team-cell">
                  <a href={`#/teams/${r.teamId}`} className="row" style={{ gap: 9, flexWrap: 'nowrap' }}>
                    <TeamAvatars t={t} teamId={r.teamId} size={26} />
                    <span className="truncate">{teamName(t, r.teamId)}</span>
                    {qualified?.has(r.teamId) && <span className="badge badge-accent">In</span>}
                  </a>
                </td>
                <td className="num wl">
                  {r.wins}-{r.losses}
                </td>
                <td className="num">
                  {r.gamesWon}-{r.gamesLost}
                </td>
                <td className="num">{r.pointsFor}</td>
                <td className="num">{r.pointsAgainst}</td>
                <td className={`num bold ${r.diff > 0 ? 'diff-pos' : r.diff < 0 ? 'diff-neg' : ''}`}>
                  {r.diff > 0 ? `+${r.diff}` : r.diff}
                </td>
              </tr>
            );
          })}
        </tbody>
      </table>
    </div>
  );
}

/** 1-2-3 podium plus a list of the remaining places. */
export function Podium({
  t,
  placements,
  limit = 3,
}: {
  t: Tournament;
  placements: Array<{ place: number; teamIds: string[] }>;
  limit?: number;
}) {
  const flat = placements.flatMap((p) => p.teamIds.map((id) => ({ place: p.place, id })));
  if (!flat.length) return null;
  const first = flat.find((x) => x.place === 1);
  const second = flat.find((x) => x.place === 2);
  const thirds = flat.filter((x) => x.place === 3);
  const rest = flat.filter((x) => x.place > 3 && x.place <= limit);

  const Step = ({ x, cls }: { x?: { place: number; id: string }; cls: string }) =>
    x ? (
      <div className={`podium-step ${cls}`}>
        {cls === 'p1' && <Crown size={22} className="crown" />}
        <TeamAvatars t={t} teamId={x.id} size={cls === 'p1' ? 36 : 30} />
        <a className="who" href={`#/teams/${x.id}`}>
          {teamName(t, x.id)}
        </a>
        <div className="block">{x.place}</div>
      </div>
    ) : (
      <div />
    );

  return (
    <div>
      <div className="podium3">
        <Step x={second} cls="p2" />
        <Step x={first} cls="p1" />
        <Step x={thirds[0]} cls="p3" />
      </div>
      {(thirds.length > 1 || rest.length > 0) && (
        <div className="podium-rest">
          {[...thirds.slice(1), ...rest].map((x) => (
            <div key={x.id} className="podium-row">
              <span className="medal">{x.place}</span>
              <TeamAvatars t={t} teamId={x.id} size={24} />
              <a className="bold truncate" href={`#/teams/${x.id}`} style={{ color: 'inherit' }}>
                {teamName(t, x.id)}
              </a>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
