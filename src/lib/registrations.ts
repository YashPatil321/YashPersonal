import { shuffle, uid } from './ids';
import type { Player, Team } from './types';

/* ------------------------------------------------------------------ */
/* Column mapping                                                     */
/* ------------------------------------------------------------------ */

export type FieldKey =
  | 'timestamp'
  | 'name'
  | 'lastName'
  | 'email'
  | 'phone'
  | 'skill'
  | 'gender'
  | 'division'
  | 'teamName'
  | 'partnerName'
  | 'partnerLastName'
  | 'partnerEmail'
  | 'partnerPhone'
  | 'partnerSkill';

export type ColumnMapping = Partial<Record<FieldKey, number>>;

export const FIELD_LABELS: Record<FieldKey, string> = {
  timestamp: 'Timestamp',
  name: 'Player name (or first name)',
  lastName: 'Player last name',
  email: 'Player email',
  phone: 'Player phone',
  skill: 'Player skill / rating',
  gender: 'Gender',
  division: 'Division / event',
  teamName: 'Team name',
  partnerName: 'Partner name (or first name)',
  partnerLastName: 'Partner last name',
  partnerEmail: 'Partner email',
  partnerPhone: 'Partner phone',
  partnerSkill: 'Partner skill / rating',
};

export const FIELD_ORDER: FieldKey[] = [
  'name',
  'lastName',
  'email',
  'phone',
  'skill',
  'gender',
  'division',
  'teamName',
  'partnerName',
  'partnerLastName',
  'partnerEmail',
  'partnerPhone',
  'partnerSkill',
  'timestamp',
];

const norm = (s: string) => s.toLowerCase().replace(/[^a-z0-9]+/g, ' ').trim();

/** Guess which spreadsheet column holds which field, from the header row. */
export function detectColumns(headers: string[]): ColumnMapping {
  const mapping: ColumnMapping = {};
  const used = new Set<number>();
  const H = headers.map(norm);

  const take = (key: FieldKey, test: (h: string) => boolean) => {
    if (mapping[key] !== undefined) return;
    const idx = H.findIndex((h, i) => !used.has(i) && test(h));
    if (idx >= 0) {
      mapping[key] = idx;
      used.add(idx);
    }
  };

  const isPartner = (h: string) => /\b(partner|teammate|player 2|player two|second player|p2)\b/.test(h);
  const isFirst = (h: string) => /\bfirst\b/.test(h);
  const isLast = (h: string) => /\b(last|surname|family)\b/.test(h);
  const isEmail = (h: string) => /\be ?mail\b/.test(h);
  const isPhone = (h: string) => /\b(phone|cell|mobile|number|tel)\b/.test(h) && !/\bdupr\b/.test(h);
  const isSkill = (h: string) => /\b(skill|level|rating|dupr|utpr|ntrp|ability)\b/.test(h);

  take('timestamp', (h) => /\btimestamp\b/.test(h));

  // Partner fields first so the generic ones don't steal them
  take('partnerEmail', (h) => isPartner(h) && isEmail(h));
  take('partnerPhone', (h) => isPartner(h) && isPhone(h));
  take('partnerSkill', (h) => isPartner(h) && isSkill(h));
  take('partnerLastName', (h) => isPartner(h) && isLast(h));
  take('partnerName', (h) => isPartner(h) && (/\bname\b/.test(h) || isFirst(h)));
  take('partnerName', (h) => isPartner(h) && !isEmail(h) && !isPhone(h) && !isSkill(h) && !/\b(need|looking|have|do you)\b/.test(h));

  take('teamName', (h) => /\bteam name\b/.test(h));
  take('email', (h) => isEmail(h));
  take('phone', (h) => isPhone(h));
  take('skill', (h) => isSkill(h));
  take('gender', (h) => /\b(gender|sex)\b/.test(h));
  take('division', (h) => /\b(division|event|category|bracket|flight|age group|draw)\b/.test(h));
  take('lastName', (h) => isLast(h) && !isPartner(h));
  take('name', (h) => (isFirst(h) || /\bname\b/.test(h)) && !isPartner(h) && !/\bteam\b/.test(h));
  take('name', (h) => /\b(player|participant|registrant)\b/.test(h) && !isPartner(h));
  return mapping;
}

/* ------------------------------------------------------------------ */
/* Value parsing                                                      */
/* ------------------------------------------------------------------ */

/** Turn "3.5", "3.0 - 3.5", "DUPR 4.12", "Intermediate" into a number. */
export function parseSkill(raw: string | undefined): number | undefined {
  if (!raw) return undefined;
  const s = raw.trim().toLowerCase();
  if (!s) return undefined;
  const nums = (s.match(/\d+(?:\.\d+)?/g) ?? []).map(Number).filter((n) => n > 0 && n <= 8);
  if (nums.length >= 2 && /\d\s*(-|–|to)\s*\d/.test(s)) return round2((nums[0] + nums[1]) / 2);
  if (nums.length >= 1) return round2(nums[0]);
  if (/novice|new|never|first/.test(s)) return 2.0;
  if (/advanced beginner|beginner\+|high beginner/.test(s)) return 2.75;
  if (/beginner/.test(s)) return 2.5;
  if (/low(er)? intermediate|intermediate-/.test(s)) return 3.0;
  if (/high(er)? intermediate|intermediate\+|upper intermediate/.test(s)) return 3.5;
  if (/intermediate/.test(s)) return 3.25;
  if (/advanced|competitive/.test(s)) return 4.0;
  if (/expert|elite|pro|open/.test(s)) return 4.75;
  return undefined;
}

const round2 = (n: number) => Math.round(n * 100) / 100;

const NO_PARTNER =
  /^(n\/?a|na|none|no|nope|tbd|tba|unknown|any|anyone|-+|\?+|need( a)? partner.*|looking.*|please (find|match|assign).*|no partner.*|match me.*|free agent.*|single|solo)$/i;

export function isNoPartner(value: string | undefined): boolean {
  if (!value) return true;
  const v = value.trim();
  return v === '' || NO_PARTNER.test(v);
}

export const nameKey = (s: string) =>
  s
    .toLowerCase()
    .normalize('NFD')
    .replace(/[̀-ͯ]/g, '')
    .replace(/[^a-z ]+/g, ' ')
    .replace(/\s+/g, ' ')
    .trim();

function titleCase(s: string): string {
  const t = s.trim().replace(/\s+/g, ' ');
  if (t !== t.toLowerCase() && t !== t.toUpperCase()) return t; // respect intended casing
  return t.toLowerCase().replace(/(^|[\s'-])([a-z])/g, (_, p, c) => p + c.toUpperCase());
}

/* ------------------------------------------------------------------ */
/* Building teams                                                     */
/* ------------------------------------------------------------------ */

export type PairingStrategy = 'balanced' | 'similar' | 'random';

export interface ImportOptions {
  doubles: boolean;
  /** Split "Men's Doubles, Mixed Doubles" checkbox answers into multiple divisions. */
  splitDivisions: boolean;
  defaultDivision: string;
  pairing: PairingStrategy;
  dedupe: boolean;
  /** Treat the first row as headers (true for Google Sheets). */
  hasHeader: boolean;
}

export const DEFAULT_IMPORT_OPTIONS: ImportOptions = {
  doubles: true,
  splitDivisions: true,
  defaultDivision: 'Open',
  pairing: 'balanced',
  dedupe: true,
  hasHeader: true,
};

export interface ImportedDivision {
  name: string;
  teamIds: string[];
}

export interface ImportResult {
  players: Record<string, Player>;
  teams: Record<string, Team>;
  /** divisionName → team ids (registration order). */
  divisions: ImportedDivision[];
  /** Players who still need a partner, per division. */
  unmatched: Array<{ playerId: string; division: string }>;
  warnings: string[];
  rowCount: number;
}

interface Entry {
  row: number;
  player: Player;
  partnerName?: string;
  partnerEmail?: string;
  partnerPhone?: string;
  partnerSkill?: string;
  teamName?: string;
  division: string;
  timestamp?: number;
}

function cell(row: string[], idx: number | undefined): string {
  if (idx === undefined || idx < 0) return '';
  return (row[idx] ?? '').trim();
}

function joinName(first: string, last: string): string {
  const f = first.trim();
  const l = last.trim();
  if (!l) return titleCase(f);
  if (!f) return titleCase(l);
  return titleCase(`${f} ${l}`);
}

const firstName = (name: string) => name.trim().split(/\s+/)[0] || name.trim();
const withInitial = (name: string) => {
  const parts = name.trim().split(/\s+/);
  return parts.length > 1 ? `${parts[0]} ${parts[parts.length - 1][0].toUpperCase()}.` : parts[0];
};

/** Team name from its players: "Yash & Rhea" (a solo player keeps their full name). */
export function teamDisplayName(players: Player[], teamName?: string): string {
  if (teamName?.trim()) return teamName.trim();
  if (players.length === 1) return players[0].name.trim();
  return players.map((p) => firstName(p.name)).join(' & ');
}

/** Every automatic style of name a team of these players could have. */
export function autoTeamNames(players: Player[]): string[] {
  if (players.length === 1) return [players[0].name.trim()];
  return [
    players.map((p) => firstName(p.name)).join(' & '),
    players.map((p) => withInitial(p.name)).join(' & '),
    players.map((p) => p.name.trim()).join(' & '),
  ];
}

/**
 * Make automatic team names unique: "Yash & Rhea" stays as is, but two teams
 * that would both be "Arjun & Priya" become "Arjun S. & Priya K." (then full names).
 * Teams with a custom name are left alone.
 */
export function distinctTeamNames(teams: Record<string, Team>, players: Record<string, Player>): Record<string, Team> {
  const out: Record<string, Team> = { ...teams };
  const members = (t: Team) => t.playerIds.map((id) => players[id]).filter(Boolean);
  const isAuto = (t: Team) => autoTeamNames(members(t)).includes(t.name);
  for (let level = 0; level < 3; level++) {
    const counts = new Map<string, number>();
    Object.values(out).forEach((t) => counts.set(t.name.toLowerCase(), (counts.get(t.name.toLowerCase()) ?? 0) + 1));
    let changed = false;
    for (const t of Object.values(out)) {
      if ((counts.get(t.name.toLowerCase()) ?? 0) < 2 || !isAuto(t)) continue;
      const options = autoTeamNames(members(t));
      const next = options[Math.min(options.length - 1, options.indexOf(t.name) + 1)];
      if (next && next !== t.name) {
        out[t.id] = { ...t, name: next };
        changed = true;
      }
    }
    if (!changed) break;
  }
  return out;
}

export function averageRating(players: Player[]): number | undefined {
  const r = players.map((p) => p.rating).filter((x): x is number => typeof x === 'number');
  if (!r.length) return undefined;
  return round2(r.reduce((s, x) => s + x, 0) / r.length);
}

function namesMatch(a: string, b: string): boolean {
  const x = nameKey(a);
  const y = nameKey(b);
  if (!x || !y) return false;
  if (x === y) return true;
  const xs = x.split(' ');
  const ys = y.split(' ');
  // "Bob Smith" vs "Robert Bob Smith" / "Bob J Smith": first & last tokens match
  if (xs.length >= 2 && ys.length >= 2 && xs[0] === ys[0] && xs[xs.length - 1] === ys[ys.length - 1]) return true;
  return false;
}

/**
 * Parse spreadsheet rows (Google Form responses) into players, teams and divisions.
 * Rows can be one player per row (with optional partner) or one team per row.
 */
export function importRegistrations(
  rows: string[][],
  mapping: ColumnMapping,
  options: ImportOptions,
  random: () => number = Math.random,
): ImportResult {
  const warnings: string[] = [];
  const body = options.hasHeader ? rows.slice(1) : rows;
  const players: Record<string, Player> = {};
  const teams: Record<string, Team> = {};

  // 1) Rows → entries (one per division the player signed up for)
  let entries: Entry[] = [];
  body.forEach((row, i) => {
    const rowNum = i + (options.hasHeader ? 2 : 1);
    const name = joinName(cell(row, mapping.name), cell(row, mapping.lastName));
    if (!name) {
      if (row.some((c) => c.trim())) warnings.push(`Row ${rowNum}: no player name — skipped.`);
      return;
    }
    const skillRaw = cell(row, mapping.skill);
    const player: Player = {
      id: uid('pl'),
      name,
      email: cell(row, mapping.email).toLowerCase() || undefined,
      phone: cell(row, mapping.phone) || undefined,
      skillLabel: skillRaw || undefined,
      rating: parseSkill(skillRaw),
      gender: cell(row, mapping.gender) || undefined,
    };
    const divRaw = cell(row, mapping.division);
    let divisions = [divRaw || options.defaultDivision];
    if (divRaw && options.splitDivisions) {
      divisions = divRaw
        .split(/\s*[,;]\s*/)
        .map((d) => d.trim())
        .filter(Boolean);
    }
    const partnerName = joinName(cell(row, mapping.partnerName), cell(row, mapping.partnerLastName));
    const ts = Date.parse(cell(row, mapping.timestamp));
    for (const division of divisions) {
      entries.push({
        row: rowNum,
        player,
        partnerName: isNoPartner(partnerName) ? undefined : partnerName,
        partnerEmail: cell(row, mapping.partnerEmail).toLowerCase() || undefined,
        partnerPhone: cell(row, mapping.partnerPhone) || undefined,
        partnerSkill: cell(row, mapping.partnerSkill) || undefined,
        teamName: cell(row, mapping.teamName) || undefined,
        division,
        timestamp: Number.isNaN(ts) ? undefined : ts,
      });
    }
  });

  // 2) De-duplicate (same person + same division → keep the latest submission)
  if (options.dedupe) {
    const latest = new Map<string, Entry>();
    for (const e of entries) {
      const who = e.player.email || nameKey(e.player.name);
      const key = `${who}|${e.division.toLowerCase()}`;
      const prev = latest.get(key);
      if (prev) {
        const keepNew = (e.timestamp ?? e.row) >= (prev.timestamp ?? prev.row);
        warnings.push(
          `Duplicate registration for ${e.player.name} in ${e.division} (rows ${prev.row} & ${e.row}) — kept row ${
            keepNew ? e.row : prev.row
          }.`,
        );
        if (keepNew) latest.set(key, e);
      } else latest.set(key, e);
    }
    const keep = new Set(latest.values());
    entries = entries.filter((e) => keep.has(e));
  }

  // One Player object per real person across divisions
  const personKey = (p: Player) => p.email || nameKey(p.name);
  const people = new Map<string, Player>();
  const peopleByName = new Map<string, Player>();
  for (const e of entries) {
    const k = personKey(e.player);
    const existing = people.get(k);
    if (existing) e.player = existing;
    else {
      people.set(k, e.player);
      players[e.player.id] = e.player;
      if (!peopleByName.has(nameKey(e.player.name))) peopleByName.set(nameKey(e.player.name), e.player);
    }
  }
  const findPerson = (email: string | undefined, name: string | undefined): Player | undefined =>
    (email ? people.get(email) : undefined) ?? (name ? peopleByName.get(nameKey(name)) ?? people.get(nameKey(name)) : undefined);

  // 3) Group by division (preserving first-seen order)
  const divisionOrder: string[] = [];
  const byDivision = new Map<string, Entry[]>();
  for (const e of entries) {
    const key = e.division;
    if (!byDivision.has(key)) {
      byDivision.set(key, []);
      divisionOrder.push(key);
    }
    byDivision.get(key)!.push(e);
  }

  const divisions: ImportedDivision[] = [];
  const unmatched: ImportResult['unmatched'] = [];

  for (const divName of divisionOrder) {
    const list = byDivision.get(divName)!;
    const teamIds: string[] = [];
    const makeTeam = (members: Player[], teamName?: string) => {
      const team: Team = {
        id: uid('t'),
        name: teamDisplayName(members, teamName),
        playerIds: members.map((p) => p.id),
        divisionId: divName, // replaced with a real division id later
        rating: averageRating(members),
      };
      teams[team.id] = team;
      teamIds.push(team.id);
    };

    if (!options.doubles) {
      list.forEach((e) => makeTeam([e.player], e.teamName));
      divisions.push({ name: divName, teamIds });
      continue;
    }

    const teamed = new Set<Entry>();
    const freeAgents: Entry[] = [];
    const findRegistered = (e: Entry): Entry | undefined =>
      list.find(
        (f) =>
          f !== e &&
          !teamed.has(f) &&
          ((e.partnerEmail && f.player.email && e.partnerEmail === f.player.email) ||
            (e.partnerName && namesMatch(e.partnerName, f.player.name))),
      );

    for (const e of list) {
      if (teamed.has(e)) continue;
      if (!e.partnerName && !e.partnerEmail) {
        freeAgents.push(e);
        continue;
      }
      const f = findRegistered(e);
      if (f) {
        teamed.add(e);
        teamed.add(f);
        if (f.partnerName && !namesMatch(f.partnerName, e.player.name) && !(f.partnerEmail && f.partnerEmail === e.player.email)) {
          warnings.push(
            `${e.player.name} listed ${f.player.name} as partner, but ${f.player.name} listed ${f.partnerName}. Paired ${e.player.name} & ${f.player.name} — please double-check.`,
          );
        }
        makeTeam([e.player, f.player], e.teamName || f.teamName);
      } else {
        // Partner didn't register separately — create them from the row.
        const pName = e.partnerName || e.partnerEmail!;
        const key = e.partnerEmail || nameKey(pName);
        let partner = findPerson(e.partnerEmail, e.partnerName);
        if (!partner) {
          partner = {
            id: uid('pl'),
            name: titleCase(pName),
            email: e.partnerEmail,
            phone: e.partnerPhone,
            skillLabel: e.partnerSkill,
            rating: parseSkill(e.partnerSkill),
          };
          people.set(key, partner);
          peopleByName.set(nameKey(partner.name), partner);
          players[partner.id] = partner;
        }
        teamed.add(e);
        makeTeam([e.player, partner], e.teamName);
      }
    }

    // Pair up free agents
    const paired = pairFreeAgents(
      freeAgents.map((e) => e.player),
      options.pairing,
      random,
    );
    paired.teams.forEach((pair) => makeTeam(pair));
    if (paired.leftover) {
      unmatched.push({ playerId: paired.leftover.id, division: divName });
      warnings.push(`${paired.leftover.name} (${divName}) has no partner yet — pair them manually on the Teams step.`);
    }
    if (paired.teams.length) {
      warnings.push(
        `${paired.teams.length * 2} player${paired.teams.length > 1 ? 's' : ''} without a partner in ${divName} were paired automatically (${
          options.pairing
        }).`,
      );
    }
    divisions.push({ name: divName, teamIds });
  }

  return { players, teams: distinctTeamNames(teams, players), divisions, unmatched, warnings, rowCount: body.length };
}

/**
 * Pair free agents.
 * - balanced: strongest with weakest so every team's average is similar
 * - similar:  neighbours by rating (competitive pairs)
 * - random
 */
export function pairFreeAgents(
  players: Player[],
  strategy: PairingStrategy,
  random: () => number = Math.random,
): { teams: Player[][]; leftover?: Player } {
  if (players.length < 2) return { teams: [], leftover: players[0] };
  let list: Player[];
  if (strategy === 'random') list = shuffle(players, random);
  else list = players.slice().sort((a, b) => (b.rating ?? 0) - (a.rating ?? 0));

  let leftover: Player | undefined;
  if (list.length % 2 === 1) {
    // Leave out the most recently registered player
    leftover = players[players.length - 1];
    list = list.filter((p) => p !== leftover);
  }
  const teams: Player[][] = [];
  if (strategy === 'balanced') {
    for (let i = 0; i < list.length / 2; i++) teams.push([list[i], list[list.length - 1 - i]]);
  } else {
    for (let i = 0; i < list.length; i += 2) teams.push([list[i], list[i + 1]]);
  }
  return { teams, leftover };
}

/* ------------------------------------------------------------------ */
/* Seeding                                                            */
/* ------------------------------------------------------------------ */

export type SeedingMethod = 'rating' | 'random' | 'registration';

export function seedTeams(
  teamIds: string[],
  teams: Record<string, Team>,
  method: SeedingMethod,
  random: () => number = Math.random,
): string[] {
  if (method === 'registration') return teamIds.slice();
  if (method === 'random') return shuffle(teamIds, random);
  // Rated teams first (high → low), then unrated in registration order
  const idx = new Map(teamIds.map((id, i) => [id, i]));
  return teamIds.slice().sort((a, b) => {
    const ra = teams[a]?.rating;
    const rb = teams[b]?.rating;
    if (ra !== undefined && rb !== undefined && ra !== rb) return rb - ra;
    if (ra !== undefined && rb === undefined) return -1;
    if (rb !== undefined && ra === undefined) return 1;
    return idx.get(a)! - idx.get(b)!;
  });
}
