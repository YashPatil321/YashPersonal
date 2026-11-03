import { CalendarDays, ChevronRight, Clock, MapPin, Search, Trophy, Zap } from 'lucide-react';
import { courtStatus, fillCourts, matchQueue, waitEstimates } from '../lib/actions';
import { clockAfter, formatDuration, projectSchedule } from '../lib/schedule';
import { FORMAT_LABELS, teamName } from '../lib/tournament';
import { divisionName, MatchCard, stageLabel } from '../components/match';
import { MiniCourt } from '../components/MiniCourt';
import { Podium } from '../components/Standings';
import { BRAND } from '../brand';
import { BrandName, CauseCard, Mandala, Progress, ProgressRing, TeamAvatars, Toran, minutesLabel, timeAgo } from '../components/ui';
import { useMatchDialog } from '../components/useMatchDialog';
import { useTournament } from '../state/store';

export function Overview() {
  const { t, resolved, canScore, update, sync } = useTournament();
  const { open, dialog } = useMatchDialog();

  const total = resolved.ordered.filter((r) => !r.notNeeded).length;
  const done = resolved.ordered.filter((r) => r.done && !r.notNeeded).length;
  const courts = courtStatus(t, resolved);
  const live = courts.filter((c) => c.match);
  const queue = matchQueue(resolved).filter((q) => !q.blocked);
  const waits = waitEstimates(t, resolved);
  const recent = resolved.ordered
    .filter((r) => r.m.status === 'final' && r.m.finishedAt)
    .sort((a, b) => (b.m.finishedAt ?? 0) - (a.m.finishedAt ?? 0))
    .slice(0, 6);
  const started = resolved.ordered.some((r) => r.m.status !== 'pending');
  const finished = total > 0 && done === total;
  const projection = projectSchedule(t, { fromNow: started });
  const calledTimes = Object.values(t.matches)
    .map((m) => m.calledAt)
    .filter((x): x is number => typeof x === 'number');
  const firstCall = calledTimes.length ? Math.min(...calledTimes) : undefined;
  const budget = t.settings.hoursAvailable ? t.settings.hoursAvailable * 60 : undefined;
  const elapsed = firstCall ? (Date.now() - firstCall) / 60000 : 0;
  const overBy = budget && started && !finished ? elapsed + projection.minutes - budget : 0;
  const dateText = t.date
    ? new Date(t.date + 'T12:00:00').toLocaleDateString(undefined, { weekday: 'short', month: 'short', day: 'numeric' })
    : null;

  return (
    <>
      <section className="hero-banner">
        <Toran />
        <Mandala />
        <div className="hero-grid">
          <div style={{ minWidth: 0 }}>
            <div className="eyebrow">
              {BRAND.organizer} · {finished ? 'Final results are in' : started ? 'Live now' : 'Draw is set'}
            </div>
            <h1>
              <BrandName name={t.name} />
            </h1>
            <div className="row">
              {dateText && (
                <span className="chip">
                  <CalendarDays size={14} /> {dateText}
                </span>
              )}
              {t.location && (
                <span className="chip">
                  <MapPin size={14} /> {t.location}
                </span>
              )}
              {sync && (
                <span className="chip">
                  <span className="serve-ball" style={{ margin: 0, width: 8, height: 8 }} /> Live scores
                </span>
              )}
              {!finished && projection.matches > 0 && (
                <span className="chip" title="Estimated from courts, match length and the bracket order">
                  <Clock size={14} />
                  {started
                    ? `Wraps up ~${clockAfter(projection.minutes)}`
                    : `~${formatDuration(projection.minutes)} of play${budget ? ` · ${formatDuration(budget)} booked` : ''}`}
                </span>
              )}
            </div>
          </div>
          <ProgressRing value={done} total={total} label="played" />
        </div>
        <div className="stat-strip">
          <div className="stat">
            <div className="value">
              {done}
              <small>/{total}</small>
            </div>
            <div className="label">Matches done</div>
          </div>
          <div className="stat">
            <div className="value">
              {live.length}
              <small>/{t.courts.length}</small>
            </div>
            <div className="label">Courts live</div>
          </div>
          <div className="stat">
            <div className="value">{Object.keys(t.teams).length}</div>
            <div className="label">
              {t.settings.doubles ? 'Teams' : 'Players'} · {t.divisions.length} div
            </div>
          </div>
        </div>
      </section>

      {canScore && overBy > 5 && (
        <div className="alert alert-warn" style={{ marginTop: 16 }}>
          <b>Running long:</b> on pace to finish about {formatDuration(overBy)} after your {t.settings.hoursAvailable} hours. Keep
          every court busy (turn on Auto-call on the Courts page) and consider shorter games for the remaining rounds.
        </div>
      )}

      {canScore && !started && (
        <div className="cta-strip">
          <div>
            <h3>Ready to play?</h3>
            <div className="small">Send the first {Math.min(t.courts.length, queue.length)} matches to the courts.</div>
          </div>
          <button className="btn btn-dark btn-lg" onClick={() => update(fillCourts)}>
            <Zap size={18} /> Start tournament
          </button>
        </div>
      )}

      <div style={{ marginTop: 16 }}>
        <CauseCard compact />
      </div>

      <a className="card row-between" href="#/teams" style={{ marginTop: 16, color: 'inherit', textDecoration: 'none' }}>
        <span className="row" style={{ gap: 12, flexWrap: 'nowrap', minWidth: 0 }}>
          <span className="feature-icon" style={{ width: 38, height: 38, flexShrink: 0 }}>
            <Search size={18} />
          </span>
          <span>
            <span className="bold">Find your {t.settings.doubles ? 'team' : 'name'}</span>
            <span className="muted small" style={{ display: 'block' }}>
              See when you play next, your court and your results
            </span>
          </span>
        </span>
        <ChevronRight size={20} className="muted" />
      </a>

      {live.length > 0 && (
        <>
          <div className="section-title">
            <h2>On court now</h2>
            <a className="small bold" href="#/courts">
              All courts →
            </a>
          </div>
          <div className="grid grid-courts">
            {live.map(({ court, match }) => (
              <div key={court} onClick={() => open(match!)} style={{ cursor: 'pointer' }}>
                <MiniCourt
                  t={t}
                  court={court}
                  match={match}
                  meta={
                    <>
                      <span className="match-no">M{match!.m.number}</span>
                      <span className="truncate">
                        {t.divisions.length > 1 ? `${divisionName(t, match!.m.divisionId)} · ` : ''}
                        {stageLabel(t, match!.m)}
                      </span>
                    </>
                  }
                />
              </div>
            ))}
          </div>
        </>
      )}

      {queue.length > 0 && (
        <>
          <div className="section-title">
            <h2>Up next</h2>
          </div>
          <div className="grid grid-courts">
            {queue.slice(0, 6).map((q, i) => (
              <MatchCard
                key={q.r.m.id}
                t={t}
                r={q.r}
                onOpen={open}
                extra={
                  <div className="match-meta">
                    <span className="badge badge-accent">#{i + 1} in line</span>
                    <span className="bold">{minutesLabel(waits.get(q.r.m.id))}</span>
                  </div>
                }
              />
            ))}
          </div>
        </>
      )}

      <div className="section-title">
        <h2>Divisions</h2>
      </div>
      <div className="grid grid-2">
        {t.divisions.map((d) => {
          const rd = resolved.divisions[d.id];
          return (
            <div className="card" key={d.id}>
              <div className="card-head">
                <div style={{ minWidth: 0 }}>
                  <div className="eyebrow">{FORMAT_LABELS[d.settings.format]}</div>
                  <h2 style={{ margin: '2px 0 0' }} className="truncate">
                    {d.name}
                  </h2>
                </div>
                {rd.complete && (
                  <span className="badge badge-accent">
                    <Trophy size={12} /> Done
                  </span>
                )}
              </div>
              <div className="row-between small muted" style={{ marginBottom: 8 }}>
                <span>
                  {d.teamIds.length} {t.settings.doubles ? 'teams' : 'players'}
                </span>
                <span className="num bold">
                  {rd.progress.done}/{rd.progress.total} matches
                </span>
              </div>
              <Progress value={rd.progress.done} total={rd.progress.total} />
              {rd.placements.length > 0 && (
                <div style={{ marginTop: 14 }}>
                  <Podium t={t} placements={rd.placements} />
                </div>
              )}
              <div className="row" style={{ marginTop: 14 }}>
                <a className="btn btn-sm" href={`#/standings?d=${d.id}`}>
                  Standings
                </a>
                {d.settings.format !== 'round_robin' && (
                  <a className="btn btn-sm" href={`#/brackets?d=${d.id}`}>
                    Bracket
                  </a>
                )}
                <a className="btn btn-sm btn-ghost" href={`#/matches?d=${d.id}`}>
                  Matches
                </a>
              </div>
            </div>
          );
        })}
      </div>

      {recent.length > 0 && (
        <>
          <div className="section-title">
            <h2>Latest results</h2>
          </div>
          <div className="card list-card">
            {recent.map((r) => (
              <div key={r.m.id} className="list-row" onClick={() => open(r)} role="button" tabIndex={0}>
                <span className="match-no">M{r.m.number}</span>
                <span className="row" style={{ gap: 10, flexWrap: 'nowrap', minWidth: 0 }}>
                  <TeamAvatars t={t} teamId={r.winner as string} size={26} />
                  <span className="truncate">
                    <b>{teamName(t, r.winner as string)}</b> <span className="muted">def.</span> {teamName(t, r.loser as string)}
                  </span>
                </span>
                <span className="right">
                  <span className="display" style={{ fontSize: '1.15rem', fontWeight: 800 }}>
                    {r.m.forfeit
                      ? 'W/O'
                      : r.m.games.map((g) => (r.winnerSide === 'a' ? `${g.a}-${g.b}` : `${g.b}-${g.a}`)).join(', ')}
                  </span>
                  <span className="tiny muted" style={{ display: 'block' }}>
                    {timeAgo(r.m.finishedAt)}
                  </span>
                </span>
              </div>
            ))}
          </div>
        </>
      )}
      {dialog}
    </>
  );
}
