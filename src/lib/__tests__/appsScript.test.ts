import { describe, expect, it } from 'vitest';
// @ts-expect-error — plain JS test harness
import { createAppsScript } from '../../../apps-script/harness.mjs';
import { finishMatch } from '../actions';
import { detectColumns, DEFAULT_IMPORT_OPTIONS, importRegistrations } from '../registrations';
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

  it('setup() builds the SACS sign-up form, response sheet and passcodes in a fresh script project', () => {
    const api = createAppsScript({ standalone: true });
    expect(api.post({ action: 'verify', passcode: 'change-me' })).toMatchObject({ ok: false, auth: false });
    expect(api.get({ action: 'ping' }).ok).toBe(false);

    const log = api.setup();
    expect(log).toContain('SACS Pickleball Tournament is set up');
    const admin = api.props.get('ADMIN_PASSCODE');
    const scorer = api.props.get('SCORER_PASSCODE');
    expect(admin).toMatch(/^sacs-[0-9a-f]{6}$/);
    expect(scorer).toMatch(/^court-[0-9a-f]{4}$/);
    expect(log).toContain(admin);

    // One form, linked to one new spreadsheet whose only tab is the responses tab
    expect(api.forms.size).toBe(1);
    const form = [...api.forms.values()][0];
    expect(form.title).toBe('SACS Pickleball Tournament Registration');
    expect(form.description).toContain('Akshaya Patra Foundation');
    expect(form.confirmation).toContain('pickleball-tournament-jet.vercel.app');
    const book = api.books.get(api.props.get('SHEET_ID'));
    expect(book.getSheets().map((s: { name: string }) => s.name)).toEqual(['Form Responses 1']);

    // Running setup again reuses everything
    api.setup();
    expect(api.forms.size).toBe(1);
    expect(api.props.get('ADMIN_PASSCODE')).toBe(admin);

    // The site can reach it and reads the form link from ping
    const ping = api.get({ action: 'ping' });
    expect(ping).toMatchObject({ ok: true, formUrl: form.getPublishedUrl() });
    expect(api.post({ action: 'verify', passcode: admin }).role).toBe('admin');
    expect(api.post({ action: 'verify', passcode: scorer }).role).toBe('scorer');

    // Responses come back with headers the importer understands
    const rows = api.post({ action: 'registrations', passcode: admin }).rows as string[][];
    expect(detectColumns(rows[0])).toMatchObject({
      timestamp: 0,
      name: 1,
      email: 2,
      phone: 3,
      skill: 5,
      division: 6,
      partnerName: 7,
      partnerEmail: 8,
      partnerSkill: 9,
      teamName: 10,
    });
    const sample = [
      rows[0],
      ['11/1/2026 9:00', 'Riya Shah', 'riya@example.com', '', 'Del Norte', 'Intermediate (2.5 - 3.5)', 'Competitive', 'Arjun Rao', '', 'Advanced (4.0+)', 'Dink Dynasty', ''],
      ['11/1/2026 9:05', 'Maya Iyer', 'maya@example.com', '', 'Westview', 'Beginner (new to pickleball)', 'Just for fun', '', '', '', '', ''],
      ['11/1/2026 9:07', 'Dev Patel', 'dev@example.com', '', 'Torrey Pines', 'Advanced (4.0+)', 'Just for fun', '', '', '', '', ''],
    ];
    const res = importRegistrations(sample, detectColumns(rows[0]), DEFAULT_IMPORT_OPTIONS);
    expect(res.divisions.map((d) => d.name)).toEqual(['Competitive', 'Just for fun']);
    const team = Object.values(res.teams).find((t) => t.name === 'Dink Dynasty')!;
    expect(team.rating).toBe(3.5); // (3.0 + 4.0) / 2
    expect(res.divisions[1].teamIds.length).toBe(1); // the two free agents were paired

    // State storage works in the created spreadsheet
    expect(api.post({ action: 'saveState', passcode: admin, state: tournament() }).ok).toBe(true);
    expect(api.get({ action: 'state' }).state.name).toBe('T');
  });
});
