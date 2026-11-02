export type ID = string;

export interface Player {
  id: ID;
  name: string;
  email?: string;
  phone?: string;
  /** Numeric skill rating (e.g. DUPR / self-rated 3.5). */
  rating?: number;
  /** Raw skill text from the form. */
  skillLabel?: string;
  gender?: string;
}

export interface Team {
  id: ID;
  name: string;
  playerIds: ID[];
  divisionId: ID;
  /** Average player rating, if known. */
  rating?: number;
  checkedIn?: boolean;
  notes?: string;
}

export type FormatType = 'round_robin' | 'pools_playoff' | 'single_elim' | 'double_elim';

export interface ScoringRules {
  /** Best of N games (1, 3 or 5). */
  bestOf: number;
  /** Points needed to win a game (11, 15, 21). */
  pointsToWin: number;
  /** Win-by margin (usually 2). */
  winBy: number;
  /** Optional hard cap: first to this score wins regardless of margin. */
  cap?: number;
}

export interface DivisionSettings {
  format: FormatType;
  /** Scoring for round robin / pool play / early bracket rounds. */
  scoring: ScoringRules;
  /** Scoring for semifinals & finals (falls back to `scoring`). */
  finalsScoring?: ScoringRules;
  poolCount: number;
  advancePerPool: number;
  playoffFormat: 'single_elim' | 'double_elim';
  thirdPlaceMatch: boolean;
  grandFinalReset: boolean;
  /** Round robin: play each opponent this many times. */
  roundRobinCycles: number;
}

export interface Pool {
  id: ID;
  name: string;
  teamIds: ID[];
}

export interface Division {
  id: ID;
  name: string;
  settings: DivisionSettings;
  /** Teams in seed order (index 0 = seed 1). */
  teamIds: ID[];
  pools: Pool[];
}

/** Where a team in a match slot comes from. Resolved lazily from results. */
export type SlotSource =
  | { kind: 'team'; teamId: ID }
  | { kind: 'bye' }
  | { kind: 'winner'; matchId: ID }
  | { kind: 'loser'; matchId: ID }
  /** Overall qualifier rank out of pool play (1 = best pool finisher). */
  | { kind: 'qualifier'; rank: number };

export interface GameScore {
  a: number;
  b: number;
}

export type MatchStatus = 'pending' | 'live' | 'final';

export type MatchStage = 'rr' | 'pool' | 'winners' | 'losers' | 'final' | 'reset' | 'third';

export interface ServeState {
  side: 'a' | 'b';
  /** Server number in doubles (1 or 2). */
  server: 1 | 2;
}

export interface Match {
  id: ID;
  divisionId: ID;
  stage: MatchStage;
  poolId?: ID;
  /** Round within the stage (1-based). */
  round: number;
  /** Position within the round (0-based), used for bracket layout. */
  slot: number;
  /** Global display number (0 for byes). */
  number: number;
  /** Play-order depth used for queueing (lower plays first). */
  depth: number;
  label?: string;
  a: SlotSource;
  b: SlotSource;
  /** True when one side is structurally a bye — never played. */
  bye?: boolean;
  /** Use the finals scoring rules for this match. */
  finals?: boolean;

  // ---- mutable result fields ----
  status: MatchStatus;
  games: GameScore[];
  court?: string;
  /** Side that forfeited. */
  forfeit?: 'a' | 'b';
  /** Teams that were in the match when the result was entered. */
  resultTeams?: [ID, ID];
  serve?: ServeState;
  calledAt?: number;
  finishedAt?: number;
  updatedAt: number;
}

export interface TournamentSettings {
  /** Automatically call the next match onto a court when one finishes. */
  autoCall: boolean;
  /** Average minutes per match, used for wait estimates. */
  minutesPerMatch: number;
  doubles: boolean;
}

export interface Tournament {
  id: ID;
  name: string;
  date?: string;
  location?: string;
  courts: string[];
  players: Record<ID, Player>;
  teams: Record<ID, Team>;
  divisions: Division[];
  matches: Record<ID, Match>;
  settings: TournamentSettings;
  createdAt: number;
  updatedAt: number;
}

export const BYE = 'BYE' as const;
export type SlotValue = ID | typeof BYE | null;
