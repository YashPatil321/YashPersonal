import { forfeitGames } from './scoring';
import { resolveTournament } from './resolve';
import type { Resolved, ResolvedMatch } from './resolve';
import type { GameScore, Match, Tournament } from './types';

/* ------------------------------------------------------------------ */
/* Court queue                                                        */
/* ------------------------------------------------------------------ */

export interface QueueItem {
  r: ResolvedMatch;
  /** A team in this match is currently playing on another court. */
  blocked: boolean;
}

export function liveMatches(resolved: Resolved): ResolvedMatch[] {
  return resolved.ordered.filter((r) => r.m.status === 'live' && !r.done);
}

export function busyTeams(resolved: Resolved): Set<string> {
  const busy = new Set<string>();
  for (const r of liveMatches(resolved)) {
    if (typeof r.a === 'string') busy.add(r.a);
    if (typeof r.b === 'string') busy.add(r.b);
  }
  return busy;
}

/** Matches ready to be called to a court, in play order. */
export function matchQueue(resolved: Resolved): QueueItem[] {
  const busy = busyTeams(resolved);
  return resolved.ordered
    .filter((r) => r.ready && !r.stale && r.m.status === 'pending')
    .sort((x, y) => x.m.depth - y.m.depth || x.m.number - y.m.number)
    .map((r) => ({ r, blocked: busy.has(r.a as string) || busy.has(r.b as string) }));
}

export function nextMatchToCall(resolved: Resolved): ResolvedMatch | undefined {
  return matchQueue(resolved).find((q) => !q.blocked)?.r;
}

export function courtStatus(t: Tournament, resolved: Resolved): Array<{ court: string; match?: ResolvedMatch }> {
  const live = liveMatches(resolved);
  return t.courts.map((court) => ({ court, match: live.find((r) => r.m.court === court) }));
}

/** Rough wait estimate in minutes for each queued (unblocked) match. */
export function waitEstimates(t: Tournament, resolved: Resolved): Map<string, number> {
  const courts = Math.max(1, t.courts.length);
  const free = courtStatus(t, resolved).filter((c) => !c.match).length;
  const per = t.settings.minutesPerMatch || 20;
  const out = new Map<string, number>();
  let p = 0;
  for (const q of matchQueue(resolved)) {
    if (q.blocked) continue;
    out.set(q.r.m.id, p < free ? 0 : Math.ceil((p - free + 1) / courts) * per);
    p++;
  }
  return out;
}

/* ------------------------------------------------------------------ */
/* Mutations (pure)                                                   */
/* ------------------------------------------------------------------ */

function patchMatch(t: Tournament, id: string, fields: Partial<Match>, now = Date.now()): Tournament {
  const m = t.matches[id];
  if (!m) return t;
  return { ...t, matches: { ...t.matches, [id]: { ...m, ...fields, updatedAt: now } }, updatedAt: now };
}

export function callMatch(t: Tournament, id: string, court: string): Tournament {
  return patchMatch(t, id, { status: 'live', court, calledAt: Date.now() });
}

export function startMatch(t: Tournament, id: string): Tournament {
  return patchMatch(t, id, { status: 'live', calledAt: t.matches[id]?.calledAt ?? Date.now() });
}

export function unassignMatch(t: Tournament, id: string): Tournament {
  return patchMatch(t, id, { status: 'pending', court: undefined, calledAt: undefined, serve: undefined });
}

/** Save in-progress scores without finishing the match. */
export function saveLiveScore(t: Tournament, id: string, games: GameScore[], serve?: Match['serve']): Tournament {
  const m = t.matches[id];
  if (!m) return t;
  return patchMatch(t, id, { games, serve, status: m.status === 'final' ? 'final' : 'live' });
}

export function finishMatch(
  t: Tournament,
  id: string,
  games: GameScore[],
  opts: { forfeit?: 'a' | 'b' } = {},
): Tournament {
  const before = resolveTournament(t);
  const r = before.matches[id];
  if (!r || typeof r.a !== 'string' || typeof r.b !== 'string' || r.a === 'BYE' || r.b === 'BYE') return t;
  const finalGames = opts.forfeit ? forfeitGames(opts.forfeit, r.rules) : games;
  const court = t.matches[id].court;
  let next = patchMatch(t, id, {
    status: 'final',
    games: finalGames,
    forfeit: opts.forfeit,
    resultTeams: [r.a, r.b],
    finishedAt: Date.now(),
    serve: undefined,
  });
  if (court && t.settings.autoCall) {
    const after = resolveTournament(next);
    const stillBusy = liveMatches(after).some((x) => x.m.court === court);
    const candidate = nextMatchToCall(after);
    if (!stillBusy && candidate) next = callMatch(next, candidate.m.id, court);
  }
  return next;
}

/** Re-open a finished match (to correct a score). */
export function reopenMatch(t: Tournament, id: string): Tournament {
  const m = t.matches[id];
  if (!m) return t;
  return patchMatch(t, id, {
    status: m.court ? 'live' : 'pending',
    forfeit: undefined,
    resultTeams: undefined,
    finishedAt: undefined,
  });
}

/** Wipe a result completely. */
export function resetMatch(t: Tournament, id: string): Tournament {
  return patchMatch(t, id, {
    status: 'pending',
    games: [],
    forfeit: undefined,
    resultTeams: undefined,
    finishedAt: undefined,
    court: undefined,
    calledAt: undefined,
    serve: undefined,
  });
}

/** Fill every open court with the next available match. */
export function fillCourts(t: Tournament): Tournament {
  let next = t;
  for (const court of t.courts) {
    const resolved = resolveTournament(next);
    if (liveMatches(resolved).some((r) => r.m.court === court)) continue;
    const candidate = nextMatchToCall(resolved);
    if (!candidate) break;
    next = callMatch(next, candidate.m.id, court);
  }
  return next;
}

/**
 * Organizer override: put specific teams into a match (fix a matchup, fill a
 * bracket slot by hand). Clears any in-progress score for the old pairing.
 */
export function setMatchTeams(t: Tournament, id: string, a: string, b: string): Tournament {
  const m = t.matches[id];
  if (!m || !a || !b || a === b || m.status === 'final') return t;
  if (!t.teams[a] || !t.teams[b]) return t;
  return patchMatch(t, id, {
    a: { kind: 'team', teamId: a },
    b: { kind: 'team', teamId: b },
    bye: undefined,
    games: [],
    serve: undefined,
  });
}
