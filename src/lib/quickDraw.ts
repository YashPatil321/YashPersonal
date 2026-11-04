import { BRAND } from '../brand';
import { uid } from './ids';
import { DEFAULT_IMPORT_OPTIONS, detectColumns, distinctTeamNames, importRegistrations } from './registrations';
import { buildTournament, courtNames, defaultDivisionSettings } from './tournament';
import type { Team, Tournament } from './types';

/** Which of the two divisions a sign-up's answer belongs to. */
export function fixedDivision(name: string): (typeof BRAND.divisions)[number] {
  return /kid|teen|youth|junior|child|student/i.test(name) ? 'Kids/Teens' : 'Adults';
}

export interface QuickDraw {
  t: Tournament;
  teams: number;
  /** Players who signed up alone and had no one left to pair with. */
  needPartner: string[];
  warnings: string[];
}

/**
 * One click from sign-ups to a draft draw: read the sheet rows, keep pairs who
 * signed up together, pair up solo players, put everyone in Adults or Kids/Teens,
 * and schedule it so every team plays at least 3 games. Saved as a draft.
 */
export function quickDraw(rows: string[][]): QuickDraw {
  const res = importRegistrations(rows, detectColumns(rows[0] ?? []), { ...DEFAULT_IMPORT_OPTIONS, doubles: true });
  const teams: Record<string, Team> = { ...res.teams };
  const players = { ...res.players };

  // Anyone left without a partner still gets a spot (as a one-player team) so the
  // organizer can see them and add a partner in one tap.
  const needPartner: string[] = [];
  const leftovers = new Map<string, string[]>();
  for (const u of res.unmatched) {
    const p = players[u.playerId];
    if (!p) continue;
    const team: Team = { id: uid('t'), name: p.name, playerIds: [p.id], divisionId: '' };
    teams[team.id] = team;
    needPartner.push(p.name);
    const key = fixedDivision(u.division);
    leftovers.set(key, [...(leftovers.get(key) ?? []), team.id]);
  }

  const divisions = BRAND.divisions.map((name) => {
    const teamIds = [
      ...res.divisions.filter((d) => fixedDivision(d.name) === name).flatMap((d) => d.teamIds),
      ...(leftovers.get(name) ?? []),
    ];
    return { name, teamIds, settings: defaultDivisionSettings(teamIds.length) };
  });

  const t = buildTournament(
    {
      name: BRAND.eventName,
      date: BRAND.date,
      courts: courtNames(BRAND.courts),
      minutesPerMatch: 20,
      doubles: true,
      hoursAvailable: BRAND.hours,
    },
    players,
    distinctTeamNames(teams, players),
    divisions,
  );
  return {
    t: { ...t, published: false },
    teams: divisions.reduce((n, d) => n + d.teamIds.length, 0),
    needPartner,
    warnings: res.warnings,
  };
}
