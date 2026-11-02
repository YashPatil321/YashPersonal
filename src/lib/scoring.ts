import type { DivisionSettings, GameScore, Match, ScoringRules } from './types';

export const DEFAULT_SCORING: ScoringRules = { bestOf: 1, pointsToWin: 11, winBy: 2 };

export function gamesNeeded(rules: ScoringRules): number {
  return Math.floor(rules.bestOf / 2) + 1;
}

/** Is this game finished under the rules? */
export function isGameComplete(g: GameScore, rules: ScoringRules): boolean {
  const hi = Math.max(g.a, g.b);
  const lo = Math.min(g.a, g.b);
  if (rules.cap && hi >= rules.cap && hi > lo) return true;
  return hi >= rules.pointsToWin && hi - lo >= rules.winBy;
}

export function gameWinner(g: GameScore): 'a' | 'b' | null {
  if (g.a > g.b) return 'a';
  if (g.b > g.a) return 'b';
  return null;
}

export function gamesWon(games: GameScore[]): [number, number] {
  let a = 0;
  let b = 0;
  for (const g of games) {
    const w = gameWinner(g);
    if (w === 'a') a++;
    else if (w === 'b') b++;
  }
  return [a, b];
}

/**
 * Winner of a set of games: whichever side won more games.
 * (We deliberately don't require "proper" scores so organizers can
 * record time-capped or shortened games — see `scoreWarnings`.)
 */
export function winnerFromGames(games: GameScore[]): 'a' | 'b' | null {
  const [a, b] = gamesWon(games);
  if (a > b) return 'a';
  if (b > a) return 'b';
  return null;
}

/** Has one side clinched the match under the rules? */
export function matchDecided(games: GameScore[], rules: ScoringRules): 'a' | 'b' | null {
  const need = gamesNeeded(rules);
  let a = 0;
  let b = 0;
  for (const g of games) {
    if (!isGameComplete(g, rules)) continue;
    if (g.a > g.b) a++;
    else b++;
  }
  if (a >= need) return 'a';
  if (b >= need) return 'b';
  return null;
}

/** Human-readable warnings for a score that doesn't look like a legal result. */
export function scoreWarnings(games: GameScore[], rules: ScoringRules): string[] {
  const warnings: string[] = [];
  const played = games.filter((g) => g.a > 0 || g.b > 0);
  played.forEach((g, i) => {
    if (g.a === g.b) warnings.push(`Game ${i + 1} is tied.`);
    else if (!isGameComplete(g, rules)) {
      warnings.push(
        `Game ${i + 1} (${g.a}-${g.b}) isn't a finished game to ${rules.pointsToWin}, win by ${rules.winBy}.`,
      );
    }
  });
  const need = gamesNeeded(rules);
  const [a, b] = gamesWon(played);
  if (rules.bestOf > 1 && Math.max(a, b) < need) {
    warnings.push(`Best of ${rules.bestOf} needs ${need} game wins.`);
  }
  if (Math.max(a, b) > need) warnings.push(`More games entered than a best of ${rules.bestOf}.`);
  return warnings;
}

export function rulesForMatch(match: Match, settings: DivisionSettings): ScoringRules {
  if (match.finals && settings.finalsScoring) return settings.finalsScoring;
  return settings.scoring;
}

export function describeRules(rules: ScoringRules): string {
  const games = rules.bestOf === 1 ? '1 game' : `Best of ${rules.bestOf}`;
  const cap = rules.cap ? `, cap ${rules.cap}` : '';
  return `${games} to ${rules.pointsToWin}, win by ${rules.winBy}${cap}`;
}

/** Score games for a forfeit: the non-forfeiting side wins every needed game to pointsToWin-0. */
export function forfeitGames(forfeitSide: 'a' | 'b', rules: ScoringRules): GameScore[] {
  const need = gamesNeeded(rules);
  return Array.from({ length: need }, () =>
    forfeitSide === 'a' ? { a: 0, b: rules.pointsToWin } : { a: rules.pointsToWin, b: 0 },
  );
}
