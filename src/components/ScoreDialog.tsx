import { Fragment, useMemo, useState } from 'react';
import { callMatch, finishMatch, reopenMatch, resetMatch, saveLiveScore, setMatchTeams, unassignMatch } from '../lib/actions';
import { describeRules, scoreWarnings, winnerFromGames } from '../lib/scoring';
import { teamName } from '../lib/tournament';
import type { GameScore } from '../lib/types';
import { useTournament } from '../state/store';
import { divisionName, slotName, stageLabel, StatusBadge } from './match';
import { Modal } from './ui';

export function ScoreDialog({ matchId, onClose }: { matchId: string; onClose: () => void }) {
  const { t, resolved, canScore, isAdmin, update } = useTournament();
  const r = resolved.matches[matchId];
  const m = t.matches[matchId];
  const rules = r?.rules;
  const columns = Math.max(rules?.bestOf ?? 1, m?.games.length ?? 0, 1);

  const [games, setGames] = useState<Array<{ a: string; b: string }>>(() =>
    Array.from({ length: columns }, (_, i) => ({
      a: m?.games[i] ? String(m.games[i].a) : '',
      b: m?.games[i] ? String(m.games[i].b) : '',
    })),
  );
  const [confirmClear, setConfirmClear] = useState(false);

  const parsed: GameScore[] = useMemo(
    () =>
      games
        .map((g) => ({ a: Number(g.a) || 0, b: Number(g.b) || 0 }))
        .filter((g, i) => games[i].a !== '' || games[i].b !== '' || g.a > 0 || g.b > 0),
    [games],
  );

  if (!r || !m || !rules) return null;

  const nameA = slotName(t, r.a, m.a);
  const nameB = slotName(t, r.b, m.b);
  const teamsKnown = typeof r.a === 'string' && typeof r.b === 'string' && r.a !== 'BYE' && r.b !== 'BYE';
  const winner = winnerFromGames(parsed);
  const warnings = parsed.length ? scoreWarnings(parsed, rules) : [];
  const editable = canScore && teamsKnown && !r.notNeeded;
  const busyCourts = new Set(
    resolved.ordered.filter((x) => x.m.status === 'live' && !x.done && x.m.id !== m.id).map((x) => x.m.court),
  );

  const setCell = (i: number, side: 'a' | 'b', v: string) => {
    const clean = v.replace(/[^0-9]/g, '').slice(0, 2);
    setGames((prev) => prev.map((g, j) => (j === i ? { ...g, [side]: clean } : g)));
  };

  const saveFinal = () => {
    update((tt) => finishMatch(tt, m.id, parsed));
    onClose();
  };
  const saveProgress = () => {
    update((tt) => saveLiveScore(tt, m.id, parsed, tt.matches[m.id].serve));
    onClose();
  };
  const forfeit = (side: 'a' | 'b') => {
    const who = side === 'a' ? nameA.text : nameB.text;
    if (!window.confirm(`Record a forfeit by ${who}?`)) return;
    update((tt) => finishMatch(tt, m.id, [], { forfeit: side }));
    onClose();
  };

  return (
    <Modal
      title={
        <span>
          {nameA.text} <span className="muted">vs</span> {nameB.text}
        </span>
      }
      subtitle={
        <>
          M{m.number} · {t.divisions.length > 1 ? `${divisionName(t, m.divisionId)} · ` : ''}
          {stageLabel(t, m)} · {describeRules(rules)}
        </>
      }
      onClose={onClose}
    >
      <div className="row" style={{ marginBottom: 12 }}>
        <StatusBadge r={r} />
        {m.court && <span className="badge">{m.court}</span>}
      </div>

      {r.stale && (
        <div className="alert alert-warn" style={{ marginBottom: 12 }}>
          An earlier result was changed, so the teams in this match are different from when this score was entered.
          Please re-enter the score (or clear it).
        </div>
      )}
      {r.notNeeded && (
        <div className="alert" style={{ marginBottom: 12 }}>
          The winners-bracket champion won the grand final, so this reset match isn't needed.
        </div>
      )}
      {!teamsKnown && !r.notNeeded && (
        <div className="alert" style={{ marginBottom: 12 }}>
          Waiting for earlier results: <b>{nameA.text}</b> vs <b>{nameB.text}</b>.
        </div>
      )}

      {teamsKnown && (
        <div className="score-grid" style={{ ['--games' as string]: columns }}>
          <div />
          {games.map((_, i) => (
            <div key={i} className="head">
              Game {i + 1}
            </div>
          ))}
          {(['a', 'b'] as const).map((side) => (
            <Fragment key={side}>
              <div className="bold truncate" title={side === 'a' ? nameA.text : nameB.text}>
                {winner === side && <span className="check-mark">✓ </span>}
                {side === 'a' ? nameA.text : nameB.text}
              </div>
              {games.map((g, i) => (
                <input
                  key={i}
                  className="score-input"
                  inputMode="numeric"
                  pattern="[0-9]*"
                  aria-label={`${side === 'a' ? nameA.text : nameB.text} game ${i + 1}`}
                  value={g[side]}
                  disabled={!editable}
                  onChange={(e) => setCell(i, side, e.target.value)}
                  onFocus={(e) => e.target.select()}
                />
              ))}
            </Fragment>
          ))}
        </div>
      )}

      {editable && warnings.length > 0 && (
        <div className="alert alert-warn small" style={{ marginTop: 12 }}>
          {warnings.map((w) => (
            <div key={w}>{w}</div>
          ))}
          <div className="muted tiny" style={{ marginTop: 4 }}>
            You can still save it (e.g. for time-capped games).
          </div>
        </div>
      )}

      {editable && (
        <>
          <div className="row" style={{ marginTop: 16 }}>
            <button className="btn btn-primary btn-lg" disabled={!winner} onClick={saveFinal}>
              {winner ? `Save final — ${teamName(t, winner === 'a' ? r.a : r.b)} wins` : 'Enter scores to finish'}
            </button>
            {m.status !== 'final' && parsed.length > 0 && (
              <button className="btn" onClick={saveProgress}>
                Save as in-progress
              </button>
            )}
          </div>

          <div className="section" style={{ marginTop: 18 }}>
            <div className="form-grid">
              <label className="field">
                Court
                <select
                  className="input"
                  value={m.court ?? ''}
                  disabled={m.status === 'final'}
                  onChange={(e) => {
                    const court = e.target.value;
                    update((tt) => (court ? callMatch(tt, m.id, court) : unassignMatch(tt, m.id)));
                  }}
                >
                  <option value="">Not on a court</option>
                  {t.courts.map((c) => (
                    <option key={c} value={c}>
                      {c}
                      {busyCourts.has(c) ? ' (busy)' : ''}
                    </option>
                  ))}
                </select>
              </label>
            </div>
          </div>

          <div className="row" style={{ marginTop: 16 }}>
            <a className="btn btn-sm" href={`#/score/${m.id}`} onClick={onClose}>
              Open live scorekeeper
            </a>
            {m.status !== 'final' && (
              <>
                <button className="btn btn-sm btn-ghost" onClick={() => forfeit('a')}>
                  {nameA.text.split(' / ')[0]}… forfeits
                </button>
                <button className="btn btn-sm btn-ghost" onClick={() => forfeit('b')}>
                  {nameB.text.split(' / ')[0]}… forfeits
                </button>
              </>
            )}
            {m.status === 'final' && (
              <button
                className="btn btn-sm btn-ghost"
                onClick={() => {
                  update((tt) => reopenMatch(tt, m.id));
                }}
              >
                Reopen match
              </button>
            )}
            {(m.status === 'final' || m.games.length > 0) &&
              (confirmClear ? (
                <button
                  className="btn btn-sm btn-danger"
                  onClick={() => {
                    update((tt) => resetMatch(tt, m.id));
                    onClose();
                  }}
                >
                  Really clear the result?
                </button>
              ) : (
                <button className="btn btn-sm btn-ghost btn-danger" onClick={() => setConfirmClear(true)}>
                  Clear result
                </button>
              ))}
          </div>
          {m.status === 'final' && (
            <p className="muted tiny" style={{ marginTop: 10 }}>
              Changing a finished result updates standings and who advances automatically. Later matches that were
              already played with different teams will be flagged “Check score”.
            </p>
          )}
        </>
      )}

      {isAdmin && m.status !== 'final' && (
        <MatchupEditor
          key={`${String(r.a)}-${String(r.b)}`}
          divisionId={m.divisionId}
          a={typeof r.a === 'string' && r.a !== 'BYE' ? r.a : ''}
          b={typeof r.b === 'string' && r.b !== 'BYE' ? r.b : ''}
          onSave={(a, b) => update((tt) => setMatchTeams(tt, m.id, a, b))}
        />
      )}
    </Modal>
  );
}

/** Organizer-only: swap which teams play in this match. */
function MatchupEditor({
  divisionId,
  a,
  b,
  onSave,
}: {
  divisionId: string;
  a: string;
  b: string;
  onSave: (a: string, b: string) => void;
}) {
  const { t } = useTournament();
  const [open, setOpen] = useState(false);
  const [teamA, setTeamA] = useState(a);
  const [teamB, setTeamB] = useState(b);
  const division = t.divisions.find((d) => d.id === divisionId);
  const ids = division?.teamIds ?? Object.keys(t.teams);
  if (!open) {
    return (
      <div style={{ marginTop: 14 }}>
        <button className="btn btn-sm btn-ghost" onClick={() => setOpen(true)}>
          Edit matchup
        </button>
      </div>
    );
  }
  const select = (value: string, onChange: (v: string) => void, label: string) => (
    <label className="field">
      {label}
      <select className="input" value={value} onChange={(e) => onChange(e.target.value)}>
        <option value="">Choose a team…</option>
        {ids.map((id) => (
          <option key={id} value={id}>
            {t.teams[id]?.name}
          </option>
        ))}
      </select>
    </label>
  );
  return (
    <div className="card card-tight" style={{ marginTop: 14, background: 'var(--surface-2)' }}>
      <h3 style={{ marginBottom: 8 }}>Edit matchup</h3>
      <div className="form-grid">
        {select(teamA, setTeamA, 'Team A')}
        {select(teamB, setTeamB, 'Team B')}
      </div>
      {teamA && teamA === teamB && <div className="alert alert-warn small" style={{ marginTop: 8 }}>Pick two different teams.</div>}
      <p className="tiny muted" style={{ margin: '8px 0 0' }}>
        This replaces the teams in this match only. Any score already entered for it is cleared.
      </p>
      <div className="row" style={{ marginTop: 10 }}>
        <button
          className="btn btn-primary btn-sm"
          disabled={!teamA || !teamB || teamA === teamB || (teamA === a && teamB === b)}
          onClick={() => {
            onSave(teamA, teamB);
            setOpen(false);
          }}
        >
          Save matchup
        </button>
        <button className="btn btn-sm btn-ghost" onClick={() => setOpen(false)}>
          Cancel
        </button>
      </div>
    </div>
  );
}
