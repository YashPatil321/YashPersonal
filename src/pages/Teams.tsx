import { useMemo, useState } from 'react';
import { matchQueue, waitEstimates } from '../lib/actions';
import { teamMatches, teamRecord } from '../lib/resolve';
import { MatchCard } from '../components/match';
import { Search } from 'lucide-react';
import { Empty, TeamAvatars, minutesLabel } from '../components/ui';
import { useMatchDialog } from '../components/useMatchDialog';
import { navigate } from '../state/router';
import { useTournament } from '../state/store';

export function Teams() {
  const { t, resolved } = useTournament();
  const [q, setQ] = useState('');
  const needle = q.trim().toLowerCase();

  const matches = useMemo(() => {
    return Object.values(t.teams).filter((team) => {
      if (!needle) return true;
      if (team.name.toLowerCase().includes(needle)) return true;
      return team.playerIds.some((id) => t.players[id]?.name.toLowerCase().includes(needle));
    });
  }, [t, needle]);

  return (
    <>
      <div className="page-head">
        <div>
          <div className="eyebrow">{Object.keys(t.teams).length} {t.settings.doubles ? 'teams' : 'players'}</div>
          <h1>Find your {t.settings.doubles ? 'team' : 'name'}</h1>
        </div>
      </div>
      <div className="search-box" style={{ marginBottom: 18 }}>
        <Search size={20} />
        <input
          className="input"
          autoFocus
          placeholder="Type your name…"
          value={q}
          onChange={(e) => setQ(e.target.value)}
          onKeyDown={(e) => {
            if (e.key === 'Enter' && matches.length === 1) navigate(`/teams/${matches[0].id}`);
          }}
          aria-label={`Find your ${t.settings.doubles ? 'team' : 'name'}`}
        />
      </div>
      {t.divisions.map((d) => {
        const list = d.teamIds.filter((id) => matches.some((m) => m.id === id));
        if (!list.length) return null;
        return (
          <div key={d.id} style={{ marginBottom: 18 }}>
            {t.divisions.length > 1 && <div className="eyebrow" style={{ margin: '0 0 8px 4px' }}>{d.name}</div>}
            <div className="card list-card">
              {list.map((id) => {
                const team = t.teams[id];
                const rec = teamRecord(resolved, id);
                const live = teamMatches(resolved, id).find((r) => r.m.status === 'live' && !r.done);
                return (
                  <a key={id} className="list-row auto-first" href={`#/teams/${id}`} style={{ color: 'inherit', textDecoration: 'none' }}>
                    <TeamAvatars t={t} teamId={id} size={30} />
                    <span className="truncate">
                      <span className="bold">{team.name}</span>
                      <span className="muted small" style={{ display: 'block' }}>
                        Seed {d.teamIds.indexOf(id) + 1}
                        {team.rating !== undefined ? ` · ${team.rating.toFixed(2)}` : ''}
                      </span>
                    </span>
                    <span className="row" style={{ gap: 6 }}>
                      {live && <span className="badge badge-live">{live.m.court ?? 'Live'}</span>}
                      <span className="wl num">
                        {rec.wins}-{rec.losses}
                      </span>
                    </span>
                  </a>
                );
              })}
            </div>
          </div>
        );
      })}
      {!matches.length && <Empty title="No one by that name">Check the spelling, or ask the tournament desk.</Empty>}
    </>
  );
}

export function TeamDetail({ teamId }: { teamId: string }) {
  const { t, resolved, isAdmin, update } = useTournament();
  const { open, dialog } = useMatchDialog();
  const team = t.teams[teamId];
  if (!team) return <Empty title="Team not found" />;
  const division = t.divisions.find((d) => d.id === team.divisionId);
  const all = teamMatches(resolved, teamId);
  const rec = teamRecord(resolved, teamId);
  const queue = matchQueue(resolved);
  const waits = waitEstimates(t, resolved);
  const upcoming = all.filter((r) => !r.done);
  const played = all.filter((r) => r.done);
  const rd = division ? resolved.divisions[division.id] : undefined;
  const place = rd?.placements.find((p) => p.teamIds.includes(teamId))?.place;

  const rename = (name: string) =>
    update((tt) => ({ ...tt, teams: { ...tt.teams, [teamId]: { ...tt.teams[teamId], name } }, updatedAt: Date.now() }));
  const renamePlayer = (id: string, name: string) =>
    update((tt) => ({ ...tt, players: { ...tt.players, [id]: { ...tt.players[id], name } }, updatedAt: Date.now() }));

  return (
    <>
      <div className="page-head">
        <div style={{ minWidth: 0 }}>
          <a className="small bold" href="#/teams">
            ← All {t.settings.doubles ? 'teams' : 'players'}
          </a>
          <div className="row" style={{ gap: 12, marginTop: 8, flexWrap: 'nowrap' }}>
            <TeamAvatars t={t} teamId={teamId} size={44} />
            <h1 style={{ margin: 0 }}>{team.name}</h1>
          </div>
          <div className="muted">
            {division?.name} · Record <b className="num">{rec.wins}-{rec.losses}</b>
            {place && ` · Finished #${place}`}
          </div>
        </div>
        {isAdmin && (
          <label className="check">
            <input
              type="checkbox"
              checked={!!team.checkedIn}
              onChange={(e) =>
                update((tt) => ({
                  ...tt,
                  teams: { ...tt.teams, [teamId]: { ...tt.teams[teamId], checkedIn: e.target.checked } },
                  updatedAt: Date.now(),
                }))
              }
            />
            Checked in
          </label>
        )}
      </div>

      <div className="grid grid-2">
        <div className="card">
          <h3>{t.settings.doubles ? 'Players' : 'Player'}</h3>
          <div className="stack">
            {team.playerIds.map((id) => {
              const p = t.players[id];
              if (!p) return null;
              return (
                <div key={id}>
                  {isAdmin ? (
                    <input className="inline-input" defaultValue={p.name} onBlur={(e) => e.target.value.trim() && e.target.value !== p.name && renamePlayer(id, e.target.value.trim())} />
                  ) : (
                    <div className="bold">{p.name}</div>
                  )}
                  <div className="muted small" style={{ paddingLeft: isAdmin ? 7 : 0 }}>
                    {[p.skillLabel && `Skill: ${p.skillLabel}`, isAdmin && p.email, isAdmin && p.phone].filter(Boolean).join(' · ')}
                  </div>
                </div>
              );
            })}
          </div>
          {isAdmin && (
            <label className="field" style={{ marginTop: 12 }}>
              Team display name
              <input className="input" defaultValue={team.name} onBlur={(e) => e.target.value.trim() && e.target.value !== team.name && rename(e.target.value.trim())} />
            </label>
          )}
        </div>

        <div className="card">
          <h3>Next up</h3>
          {upcoming.length === 0 ? (
            <div className="muted">{played.length ? 'No more scheduled matches.' : 'No matches scheduled.'}</div>
          ) : (
            <div className="stack">
              {upcoming.slice(0, 3).map((r) => {
                const pos = queue.findIndex((q) => q.r.m.id === r.m.id);
                return (
                  <MatchCard
                    key={r.m.id}
                    t={t}
                    r={r}
                    onOpen={open}
                    extra={
                      r.m.status === 'live' ? (
                        <div className="match-meta">
                          <span className="badge badge-live">Playing now{r.m.court ? ` on ${r.m.court}` : ''}</span>
                        </div>
                      ) : pos >= 0 ? (
                        <div className="match-meta">
                          <span className="badge badge-accent">#{pos + 1} in the queue</span>
                          <span>{queue[pos].blocked ? 'after your current match' : minutesLabel(waits.get(r.m.id))}</span>
                        </div>
                      ) : (
                        <div className="match-meta">Waiting on earlier results</div>
                      )
                    }
                  />
                );
              })}
            </div>
          )}
        </div>
      </div>

      {played.length > 0 && (
        <>
          <div className="section-title">
            <h2>Results</h2>
          </div>
          <div className="grid grid-courts">
            {played
              .slice()
              .reverse()
              .map((r) => (
                <MatchCard key={r.m.id} t={t} r={r} onOpen={open} />
              ))}
          </div>
        </>
      )}
      {dialog}
    </>
  );
}
