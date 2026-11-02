import type { StandingRow } from '../lib/resolve';
import { teamName } from '../lib/tournament';
import type { Tournament } from '../lib/types';

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
            <th className="num">#</th>
            <th>Team</th>
            <th className="num" title="Wins-Losses">W-L</th>
            <th className="num" title="Games won-lost">Games</th>
            <th className="num" title="Points for">PF</th>
            <th className="num" title="Points against">PA</th>
            <th className="num" title="Point differential">+/-</th>
          </tr>
        </thead>
        <tbody>
          {rows.map((r) => {
            const adv = qualified ? qualified.has(r.teamId) : r.rank <= advancing;
            return (
              <tr key={r.teamId} className={adv ? 'advancing' : ''}>
                <td className="num muted">{r.rank}</td>
                <td className="team-cell">
                  <a href={`#/teams/${r.teamId}`}>{teamName(t, r.teamId)}</a>
                  {qualified?.has(r.teamId) && (
                    <span className="badge badge-final" style={{ marginLeft: 6 }}>
                      Advances
                    </span>
                  )}
                </td>
                <td className="num bold">
                  {r.wins}-{r.losses}
                </td>
                <td className="num">
                  {r.gamesWon}-{r.gamesLost}
                </td>
                <td className="num">{r.pointsFor}</td>
                <td className="num">{r.pointsAgainst}</td>
                <td className="num bold">{r.diff > 0 ? `+${r.diff}` : r.diff}</td>
              </tr>
            );
          })}
        </tbody>
      </table>
    </div>
  );
}

export function Podium({ t, placements, limit = 3 }: { t: Tournament; placements: Array<{ place: number; teamIds: string[] }>; limit?: number }) {
  const shown = placements.filter((p) => p.place <= limit);
  if (!shown.length) return null;
  return (
    <div className="podium">
      {shown.flatMap((p) =>
        p.teamIds.map((id) => (
          <div key={id} className="podium-row">
            <span className={`medal ${p.place <= 3 ? `medal-${p.place}` : 'medal-n'}`}>{p.place}</span>
            <a className="bold" href={`#/teams/${id}`} style={{ color: 'inherit' }}>
              {teamName(t, id)}
            </a>
          </div>
        )),
      )}
    </div>
  );
}
