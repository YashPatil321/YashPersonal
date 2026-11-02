import { useEffect, useRef, useState } from 'react';
import { finishMatch, saveLiveScore, startMatch } from '../lib/actions';
import { describeRules, isGameComplete, matchDecided, winnerFromGames } from '../lib/scoring';
import { teamName } from '../lib/tournament';
import type { GameScore, ServeState } from '../lib/types';
import { slotName, stageLabel } from '../components/match';
import { Empty, Segmented } from '../components/ui';
import { navigate } from '../state/router';
import { load, save, useTournament } from '../state/store';

type Mode = 'sideout' | 'rally' | 'simple';

interface Snapshot {
  games: GameScore[];
  serve: ServeState;
}

export function Scorekeeper({ matchId }: { matchId: string }) {
  const { t, resolved, canScore, update } = useTournament();
  const r = resolved.matches[matchId];
  const m = t.matches[matchId];
  const doubles = t.settings.doubles;

  const [mode, setModeState] = useState<Mode>(() => load<Mode>('pbt.scoremode') ?? 'sideout');
  const setMode = (v: Mode) => {
    setModeState(v);
    save('pbt.scoremode', v);
  };
  const [games, setGames] = useState<GameScore[]>(() => (m?.games.length ? m.games : [{ a: 0, b: 0 }]));
  const [serve, setServe] = useState<ServeState>(() => m?.serve ?? { side: 'a', server: doubles ? 2 : 1 });
  const history = useRef<Snapshot[]>([]);
  const [, force] = useState(0);

  // Mark the match live when the scorekeeper opens it.
  useEffect(() => {
    if (canScore && m && m.status === 'pending' && r?.ready) update((tt) => startMatch(tt, matchId));
  }, []);

  if (!r || !m) return <Empty title="Match not found" />;
  const nameA = slotName(t, r.a, m.a).text;
  const nameB = slotName(t, r.b, m.b).text;
  const rules = r.rules;
  const teamsKnown = r.ready || r.done;

  if (!canScore || m.status === 'final' || !teamsKnown) {
    return (
      <div className="scorer">
        <a href="#/courts" className="small">
          ← Courts
        </a>
        <div className="card" style={{ marginTop: 10 }}>
          <h2>
            {nameA} vs {nameB}
          </h2>
          <p className="muted">
            {m.status === 'final'
              ? `Final: ${m.games.map((g) => `${g.a}-${g.b}`).join(', ')} — ${teamName(t, r.winner as string)} won.`
              : !teamsKnown
                ? 'This match is waiting for earlier results.'
                : 'You need a scorer or admin passcode to keep score (Settings → Live sync).'}
          </p>
        </div>
      </div>
    );
  }

  const idx = games.length - 1;
  const game = games[idx];
  const gameOver = isGameComplete(game, rules);
  const decided = matchDecided(games, rules);

  const commit = (nextGames: GameScore[], nextServe: ServeState) => {
    history.current.push({ games, serve });
    if (history.current.length > 200) history.current.shift();
    setGames(nextGames);
    setServe(nextServe);
    update((tt) => saveLiveScore(tt, matchId, nextGames, mode === 'simple' ? undefined : nextServe));
    force((n) => n + 1);
  };

  const addPoint = (side: 'a' | 'b', delta = 1) => {
    const g = { ...game, [side]: Math.max(0, game[side] + delta) };
    commit([...games.slice(0, idx), g], serve);
  };

  const rallyWon = (side: 'a' | 'b') => {
    if (gameOver) return;
    if (mode === 'rally') {
      const g = { ...game, [side]: game[side] + 1 };
      commit([...games.slice(0, idx), g], { side, server: 1 });
      return;
    }
    if (side === serve.side) {
      const g = { ...game, [side]: game[side] + 1 };
      commit([...games.slice(0, idx), g], serve);
    } else if (doubles && serve.server === 1) {
      commit(games, { ...serve, server: 2 });
    } else {
      commit(games, { side: serve.side === 'a' ? 'b' : 'a', server: 1 });
    }
  };

  const undo = () => {
    const prev = history.current.pop();
    if (!prev) return;
    setGames(prev.games);
    setServe(prev.serve);
    update((tt) => saveLiveScore(tt, matchId, prev.games, mode === 'simple' ? undefined : prev.serve));
    force((n) => n + 1);
  };

  const nextGame = () => {
    // The team that received first last game serves first now.
    const first: 'a' | 'b' = games.length % 2 === 1 ? 'b' : 'a';
    commit([...games, { a: 0, b: 0 }], { side: first, server: doubles ? 2 : 1 });
  };

  const finish = () => {
    if (!winnerFromGames(games)) {
      window.alert('Nobody is ahead yet — keep playing or enter the final score from the Courts page.');
      return;
    }
    update((tt) => finishMatch(tt, matchId, games));
    navigate('/courts');
  };

  const servingScore = game[serve.side];
  const receivingScore = game[serve.side === 'a' ? 'b' : 'a'];
  const call =
    mode === 'sideout'
      ? doubles
        ? `${servingScore}-${receivingScore}-${serve.server}`
        : `${servingScore}-${receivingScore}`
      : `${game.a}-${game.b}`;

  const atStart = game.a === 0 && game.b === 0;
  const showServe = mode !== 'simple';

  return (
    <div className="scorer">
      <div className="row-between" style={{ marginBottom: 10 }}>
        <a href="#/courts" className="small">
          ← Courts
        </a>
        <span className="small muted">
          M{m.number} · {stageLabel(t, m)}
          {m.court ? ` · ${m.court}` : ''}
        </span>
      </div>

      <div className="row-between" style={{ marginBottom: 12, flexWrap: 'wrap' }}>
        <Segmented<Mode>
          value={mode}
          onChange={setMode}
          options={[
            { value: 'sideout', label: 'Side-out' },
            { value: 'rally', label: 'Rally' },
            { value: 'simple', label: '+/−' },
          ]}
        />
        <span className="tiny muted">{describeRules(rules)}</span>
      </div>

      {showServe && (
        <div className="card card-tight" style={{ marginBottom: 12 }}>
          <div className="tiny muted center">{mode === 'sideout' ? 'Score call' : 'Score'}</div>
          <div className="call">{call}</div>
          <div className="tiny muted center">
            Serving: <b>{serve.side === 'a' ? nameA : nameB}</b>
            {mode === 'sideout' && doubles ? ` · server ${serve.server}` : ''}
          </div>
        </div>
      )}

      <div className="scorer-teams">
        {(['a', 'b'] as const).map((side) => (
          <div key={side} className={`scorer-side ${showServe && serve.side === side ? 'serving' : ''}`}>
            <div className="team">{side === 'a' ? nameA : nameB}</div>
            <div className="points">{game[side]}</div>
            {mode === 'simple' ? (
              <>
                <button className="tap" onClick={() => addPoint(side, 1)} disabled={gameOver}>
                  +1
                </button>
                <button className="tap secondary" onClick={() => addPoint(side, -1)}>
                  −1
                </button>
              </>
            ) : (
              <button className="tap" onClick={() => rallyWon(side)} disabled={gameOver}>
                Won rally
              </button>
            )}
          </div>
        ))}
      </div>

      {gameOver && (
        <div className="alert alert-ok" style={{ marginTop: 12 }}>
          <div className="bold">
            Game {games.length} to {game.a > game.b ? nameA : nameB} ({Math.max(game.a, game.b)}-{Math.min(game.a, game.b)})
          </div>
          <div className="row" style={{ marginTop: 8 }}>
            {decided ? (
              <button className="btn btn-primary btn-lg" onClick={finish}>
                Finish match — {decided === 'a' ? nameA : nameB} wins
              </button>
            ) : (
              <button className="btn btn-primary btn-lg" onClick={nextGame}>
                Start game {games.length + 1}
              </button>
            )}
          </div>
        </div>
      )}

      <div className="row" style={{ marginTop: 14, justifyContent: 'center' }}>
        <button className="btn" onClick={undo} disabled={!history.current.length}>
          ↶ Undo
        </button>
        {showServe && atStart && (
          <button
            className="btn"
            onClick={() => commit(games, { side: serve.side === 'a' ? 'b' : 'a', server: doubles ? 2 : 1 })}
          >
            Switch first server
          </button>
        )}
        {!decided && (
          <button
            className="btn btn-ghost"
            onClick={() => {
              if (window.confirm('End the match now with the current scores?')) finish();
            }}
          >
            End match early
          </button>
        )}
      </div>

      {games.length > 1 && (
        <div className="center muted small" style={{ marginTop: 14 }}>
          {games.map((g, i) => (
            <span key={i} style={{ marginRight: 12 }}>
              G{i + 1}: {g.a}-{g.b}
            </span>
          ))}
        </div>
      )}
      {mode === 'sideout' && (
        <p className="tiny muted center" style={{ marginTop: 16 }}>
          Traditional scoring: only the serving team scores. Tap the team that won each rally — server rotation and side-outs
          are handled for you. Games start at {doubles ? '0-0-2' : '0-0'}.
        </p>
      )}
    </div>
  );
}
