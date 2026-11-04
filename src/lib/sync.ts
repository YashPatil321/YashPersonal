import type { Match, Tournament } from './types';

export type Role = 'admin' | 'scorer' | 'viewer';

/** One sign-up from the website's Register tab (keys match the Apps Script REG_FIELDS). */
export interface RegistrationEntry {
  name: string;
  email: string;
  phone?: string;
  school?: string;
  skill: string;
  division: 'Adult' | 'Kids' | '';
  partnerName?: string;
  partnerEmail?: string;
  partnerSkill?: string;
  teamName?: string;
  notes?: string;
  payment: 'Zelle' | 'Venmo' | 'Cash at check-in' | '';
  /** The registrant ticked "I've paid" (or will bring cash). */
  paid: boolean;
}

export interface SyncConfig {
  /** Google Apps Script web-app URL (…/exec). */
  url: string;
  passcode?: string;
  role: Role;
}

export interface RemoteState {
  version: number;
  state: Tournament | null;
}

async function getJSON(url: string, action: string): Promise<any> {
  const res = await fetch(`${url}?action=${action}&t=${Date.now()}`, { redirect: 'follow' });
  if (!res.ok) throw new Error(`HTTP ${res.status}`);
  const data = await res.json();
  if (!data.ok) throw new Error(data.error || 'Request failed');
  return data;
}

async function postJSON(url: string, body: unknown): Promise<any> {
  // text/plain keeps this a "simple" CORS request (Apps Script can't answer preflights)
  const res = await fetch(url, {
    method: 'POST',
    redirect: 'follow',
    headers: { 'Content-Type': 'text/plain;charset=utf-8' },
    body: JSON.stringify(body),
  });
  if (!res.ok) throw new Error(`HTTP ${res.status}`);
  const data = await res.json();
  if (!data.ok) {
    const err = new Error(data.error || 'Request failed') as Error & { auth?: boolean };
    if (data.auth === false) err.auth = true;
    throw err;
  }
  return data;
}

export const remote = {
  ping: (url: string) =>
    getJSON(url, 'ping') as Promise<{
      spreadsheet: string;
      version: number;
      scorerEnabled: boolean;
      registrationOpen?: boolean;
      registrations?: number;
    }>,
  /** Public: save one sign-up from the Register tab. `website` is a honeypot that must stay empty. */
  register: (url: string, entry: RegistrationEntry, website = ''): Promise<{ count?: number }> =>
    postJSON(url, { action: 'register', entry, website }),
  setRegistration: (url: string, passcode: string, open: boolean): Promise<{ registrationOpen: boolean }> =>
    postJSON(url, { action: 'setRegistration', passcode, open }),
  registrations: async (url: string, passcode: string): Promise<string[][]> =>
    (await postJSON(url, { action: 'registrations', passcode })).rows,
  version: async (url: string) => (await getJSON(url, 'version')).version as number,
  /** Public read (no contact details), or the full state when an admin passcode is given. */
  state: async (url: string, passcode?: string): Promise<RemoteState> => {
    const d = passcode ? await postJSON(url, { action: 'state', passcode }) : await getJSON(url, 'state');
    return { version: d.version, state: d.state };
  },
  verify: async (url: string, passcode: string): Promise<Role> => (await postJSON(url, { action: 'verify', passcode })).role,
  saveState: (url: string, passcode: string, state: Tournament | null): Promise<RemoteState> =>
    postJSON(url, { action: state ? 'saveState' : 'clearState', passcode, state }),
  patchMatches: (url: string, passcode: string, matches: Match[]): Promise<RemoteState> =>
    postJSON(url, { action: 'patchMatches', passcode, matches }),
  writeTables: (url: string, passcode: string, tables: Record<string, unknown[][]>) =>
    postJSON(url, { action: 'writeTables', passcode, tables }),
};

/**
 * Work out what changed between two tournament snapshots.
 * Score-only changes are sent as small match patches; anything else
 * (teams, divisions, settings) is sent as a full save.
 */
export function diffTournament(
  prev: Tournament | null,
  next: Tournament | null,
): { full: boolean; matchIds: string[] } {
  if (!prev || !next || prev.id !== next.id) return { full: true, matchIds: [] };
  const keys = new Set([...Object.keys(prev), ...Object.keys(next)]) as Set<keyof Tournament>;
  for (const k of keys) {
    if (k === 'matches' || k === 'updatedAt') continue;
    if (prev[k] !== next[k]) return { full: true, matchIds: [] };
  }
  const prevIds = Object.keys(prev.matches);
  const nextIds = Object.keys(next.matches);
  if (prevIds.length !== nextIds.length || nextIds.some((id) => !prev.matches[id])) return { full: true, matchIds: [] };
  return { full: false, matchIds: nextIds.filter((id) => prev.matches[id] !== next.matches[id]) };
}
