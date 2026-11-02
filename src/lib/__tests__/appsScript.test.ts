import { describe, expect, it } from 'vitest';
// @ts-expect-error — plain JS test harness
import { createAppsScript } from '../../../apps-script/harness.mjs';
import { finishMatch } from '../actions';
import { buildTournament, courtNames, defaultDivisionSettings } from '../tournament';
import type { Tournament } from '../types';

function tournament(): Tournament {
  const players: Tournament['players'] = {};
  const teams: Tournament['teams'] = {};
  const ids: string[] = [];
  for (let i = 0; i < 4; i++) {
    players[`p${i}`] = { id: `p${i}`, name: `Player ${i}`, email: `p${i}@example.com`, phone: '555-0100' };
    teams[`t${i}`] = { id: `t${i}`, name: `Team ${i}`, playerIds: [`p${i}`], divisionId: 'x' };
    ids.push(`t${i}`);
  }
  return buildTournament({ name: 'T', courts: courtNames(2), minutesPerMatch: 20, doubles: false }, players, teams, [
    { name: 'Open', teamIds: ids, settings: defaultDivisionSettings(4) },
  ]);
}

describe('Apps Script backend (Code.gs)', () => {
  const rows = [
    ['Timestamp', 'Name', 'Email'],
    ['1/1/2026', 'Alex', 'alex@example.com'],
  ];

  it('refuses everything without the right passcode, and the default passcode never works', () => {
    const fresh = createAppsScript({ registrations: rows }); // still "change-me"
    expect(fresh.post({ action: 'verify', passcode: 'change-me' }).ok).toBe(false);
    const api = createAppsScript({ registrations: rows, adminPasscode: 'secret', scorerPasscode: 'courts' });
    expect(api.post({ action: 'verify', passcode: 'nope' })).toMatchObject({ ok: false, auth: false });
    expect(api.post({ action: 'verify', passcode: 'secret' })).toMatchObject({ ok: true, role: 'admin' });
    expect(api.post({ action: 'verify', passcode: 'courts' })).toMatchObject({ ok: true, role: 'scorer' });
    expect(api.post({ action: 'saveState', state: tournament() }).ok).toBe(false);
  });

  it('only admins can read the raw form responses', () => {
    const api = createAppsScript({ registrations: rows, adminPasscode: 'secret', scorerPasscode: 'courts' });
    expect(api.get({ action: 'registrations' }).ok).toBe(false);
    expect(api.post({ action: 'registrations', passcode: 'courts' }).ok).toBe(false);
    expect(api.post({ action: 'registrations', passcode: 'secret' }).rows).toEqual(rows);
  });

  it('stores state across chunks, hides contact details from the public, and versions every write', () => {
    const api = createAppsScript({ adminPasscode: 'secret' });
    const t = tournament();
    // make the JSON big enough to need several 40k-character chunks
    t.location = 'x'.repeat(95000);
    const saved = api.post({ action: 'saveState', passcode: 'secret', state: t });
    expect(saved.ok).toBe(true);
    expect(saved.version).toBe(1);
    const stateSheet = api.sheets.find((s: { name: string }) => s.name === '_tournament_state');
    expect(stateSheet.cells.length).toBeGreaterThan(2);

    const pub = api.get({ action: 'state' });
    expect(pub.state.location.length).toBe(95000);
    expect(pub.state.players.p0.email).toBeUndefined();
    expect(pub.state.players.p0.phone).toBeUndefined();
    expect(pub.state.players.p0.name).toBe('Player 0');

    const full = api.post({ action: 'state', passcode: 'secret' });
    expect(full.state.players.p0.email).toBe('p0@example.com');
    expect(api.get({ action: 'version' }).version).toBe(1);
  });

  it('scorers can only change result fields; newer scores are never overwritten', () => {
    const api = createAppsScript({ adminPasscode: 'secret', scorerPasscode: 'courts' });
    const t = tournament();
    api.post({ action: 'saveState', passcode: 'secret', state: t });
    const first = Object.values(t.matches).find((m) => m.number === 1)!;

    // Scorer finishes a match but also tries to rename the slot sources — only results stick.
    const scored = finishMatch(t, first.id, [{ a: 11, b: 4 }]).matches[first.id];
    const tampered = { ...scored, a: { kind: 'team', teamId: 'hacker' } };
    const res = api.post({ action: 'patchMatches', passcode: 'courts', matches: [tampered] });
    expect(res.ok).toBe(true);
    const stored = api.post({ action: 'state', passcode: 'secret' }).state.matches[first.id];
    expect(stored.status).toBe('final');
    expect(stored.games).toEqual([{ a: 11, b: 4 }]);
    expect(stored.a).toEqual(first.a);

    // Admin re-saves an older copy of the whole tournament: the newer score survives.
    const resave = api.post({ action: 'saveState', passcode: 'secret', state: { ...t, name: 'Renamed' } });
    expect(resave.state.name).toBe('Renamed');
    expect(resave.state.matches[first.id].games).toEqual([{ a: 11, b: 4 }]);

    // Scorers can't save the whole tournament or clear it.
    expect(api.post({ action: 'saveState', passcode: 'courts', state: t }).ok).toBe(false);
    expect(api.post({ action: 'clearState', passcode: 'courts' }).ok).toBe(false);
  });
});
