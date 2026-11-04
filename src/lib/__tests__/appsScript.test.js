import { describe, expect, it } from 'vitest';
// @ts-expect-error — plain JS test harness
import { createAppsScript } from '../../../apps-script/harness.mjs';
import { finishMatch } from '../actions';
import { detectColumns, DEFAULT_IMPORT_OPTIONS, importRegistrations } from '../registrations';
import { buildTournament, courtNames, defaultDivisionSettings } from '../tournament';
function tournament() {
    const players = {};
    const teams = {};
    const ids = [];
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
        const stateSheet = api.sheets.find((s) => s.name === '_tournament_state');
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
    it('keeps a draft draw hidden from players until the organizer publishes it', () => {
        const api = createAppsScript({ adminPasscode: 'secret', scorerPasscode: 'courts' });
        const draft = { ...tournament(), published: false };
        expect(api.post({ action: 'saveState', passcode: 'secret', state: draft }).ok).toBe(true);
        expect(api.get({ action: 'state' }).state).toBeNull();
        expect(api.post({ action: 'state', passcode: 'courts' }).state).toBeNull();
        expect(api.post({ action: 'state', passcode: 'secret' }).state.published).toBe(false);
        expect(api.get({ action: 'ping' }).registrationOpen).toBe(true); // sign-ups stay open
        api.post({ action: 'saveState', passcode: 'secret', state: { ...draft, published: true } });
        expect(api.get({ action: 'state' }).state.name).toBe('T');
        expect(api.get({ action: 'ping' }).registrationOpen).toBe(false);
    });
    it('scorers can only change result fields; newer scores are never overwritten', () => {
        const api = createAppsScript({ adminPasscode: 'secret', scorerPasscode: 'courts' });
        const t = tournament();
        api.post({ action: 'saveState', passcode: 'secret', state: t });
        const first = Object.values(t.matches).find((m) => m.number === 1);
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
    it('setup() creates the sign-up sheet and passcodes in a fresh script project', () => {
        const api = createAppsScript({ standalone: true });
        expect(api.post({ action: 'verify', passcode: 'change-me' })).toMatchObject({ ok: false, auth: false });
        expect(api.get({ action: 'ping' }).ok).toBe(false);
        const log = api.setup();
        expect(log).toContain('SACS Pickleball Tournament is set up');
        expect(log).toContain('/#/register');
        const admin = api.props.get('ADMIN_PASSCODE');
        const scorer = api.props.get('SCORER_PASSCODE');
        expect(admin).toMatch(/^sacs-[0-9a-f]{6}$/);
        expect(scorer).toMatch(/^court-[0-9a-f]{4}$/);
        expect(log).toContain(admin);
        expect(api.forms.size).toBe(0);
        const book = api.books.get(api.props.get('SHEET_ID'));
        expect(book.getSheets().map((s) => s.name)).toEqual(['Registrations']);
        api.setup(); // idempotent
        expect(api.books.size).toBe(1);
        expect(api.props.get('ADMIN_PASSCODE')).toBe(admin);
        expect(api.get({ action: 'ping' })).toMatchObject({ ok: true, registrationOpen: true, registrations: 0 });
        expect(api.post({ action: 'verify', passcode: admin }).role).toBe('admin');
        expect(api.post({ action: 'verify', passcode: scorer }).role).toBe('scorer');
    });
    it('takes sign-ups from the website and hands them to the draw builder', () => {
        const api = createAppsScript({ standalone: true });
        api.setup();
        const admin = api.props.get('ADMIN_PASSCODE');
        const register = (entry, website = '') => api.post({ action: 'register', entry, website });
        expect(register({ name: '', email: 'x@y.com', skill: 'Advanced (4.0+)' })).toMatchObject({ ok: false });
        expect(register({ name: 'Riya Shah', email: 'not-an-email', skill: 'Advanced (4.0+)' })).toMatchObject({ ok: false });
        expect(register({ name: 'Riya Shah', email: 'riya@example.com' })).toMatchObject({ ok: false }); // division + payment required
        expect(register({ name: 'Bot', email: 'bot@spam.com', skill: 'x' }, 'http://spam')).toEqual({ ok: true }); // honeypot
        const base = { name: 'Riya Shah', email: 'riya@example.com', skill: 'Advanced (4.0+)' };
        expect(register({ ...base, division: 'Seniors', payment: 'Zelle', paid: true })).toMatchObject({ ok: false });
        expect(register({ ...base, division: 'Adults', payment: '', paid: true })).toMatchObject({ ok: false });
        expect(register({ ...base, division: 'Adults', payment: 'Zelle', paid: true, donation: '-5' })).toMatchObject({
            ok: false,
            error: 'Please check the donation amount.',
        });
        expect(register({ ...base, division: 'Adults', payment: 'Zelle', paid: false })).toMatchObject({ ok: false, error: 'Please confirm your donation.' });
        expect(register({
            name: 'Riya Shah',
            email: 'riya@example.com',
            phone: '+1 858 555 0100',
            division: 'Adults', payment: 'Zelle', paid: true,
            partnerName: 'Arjun Rao',
            notes: '=HYPERLINK("x")',
            donation: '25',
        })).toMatchObject({ ok: true, count: 1 });
        expect(register({ name: 'Maya Iyer', email: 'maya@example.com', skill: 'Beginner (new to pickleball)', division: 'Kids/Teens', payment: 'Cash at check-in', paid: true })).toMatchObject({ ok: true, count: 2 });
        expect(register({ name: 'Dev Patel', email: 'dev@example.com', skill: 'Advanced (4.0+)', division: 'Kids/Teens', payment: 'Cash at check-in', paid: true })).toMatchObject({ ok: true, count: 3 });
        expect(api.get({ action: 'ping' }).registrations).toBe(3);
        // Organizers can add sign-ups by hand, even while registration is closed
        const scorer = api.props.get('SCORER_PASSCODE');
        const add = (entry, passcode = admin) => api.post({ action: 'addRegistration', passcode, entry });
        api.post({ action: 'setRegistration', passcode: admin, open: false });
        expect(register({ ...base, division: 'Adults', payment: 'Zelle', paid: true })).toMatchObject({ ok: false, error: 'Registration is closed.' });
        expect(add({ name: 'Walk Up', division: 'Adults' }, scorer)).toMatchObject({ ok: false });
        expect(add({ name: '', division: 'Adults' })).toMatchObject({ ok: false });
        expect(add({ name: 'Walk Up', division: 'Seniors' })).toMatchObject({ ok: false });
        expect(add({ name: 'Walk Up', division: 'Adults', payment: 'Cash at check-in', paid: true })).toMatchObject({ ok: true, count: 4 });
        api.post({ action: 'setRegistration', passcode: admin, open: true });
        const walkUp = api.post({ action: 'registrations', passcode: admin }).rows[4];
        expect(walkUp[1]).toBe('Walk Up');
        expect(walkUp.slice(-4)).toEqual(['Cash at check-in', 'Yes (added by organizer)', '', '']);
        expect(add({ name: 'Unpaid Pal', email: 'nope', division: 'Kids/Teens' })).toMatchObject({ ok: false }); // bad email still rejected
        expect(add({ name: 'Unpaid Pal', division: 'Kids/Teens' })).toMatchObject({ ok: true, count: 5 });
        // ...and edit or delete any sign-up
        const listRows = () => api.post({ action: 'registrations', passcode: admin }).rows;
        const stamp5 = listRows()[5][0];
        expect(api.post({ action: 'deleteRegistration', passcode: scorer, row: 5, stamp: stamp5 }).ok).toBe(false);
        expect(api.post({ action: 'deleteRegistration', passcode: admin, row: 5, stamp: 'wrong' })).toMatchObject({ ok: false });
        expect(api.post({ action: 'deleteRegistration', passcode: admin, row: 9, stamp: stamp5 })).toMatchObject({ ok: false });
        expect(api.post({ action: 'editRegistration', passcode: admin, row: 5, stamp: stamp5, entry: { name: 'Unpaid Pal', division: 'Nope' } })).toMatchObject({ ok: false });
        expect(api.post({
            action: 'editRegistration', passcode: admin, row: 5, stamp: stamp5,
            entry: { name: 'Paid Pal', partnerName: 'New Partner', division: 'Adults', payment: 'Venmo', paid: true, donation: '10' },
        })).toMatchObject({ ok: true, count: 5 });
        const edited = listRows()[5];
        expect(edited[0]).toBe(stamp5); // timestamp kept
        expect(edited.slice(1, 2).concat(edited.slice(4, 6))).toEqual(['Paid Pal', 'Adults', 'New Partner']);
        expect(edited.slice(-4)).toEqual(['Venmo', 'Yes', '$10', '']);
        expect(api.post({ action: 'deleteRegistration', passcode: admin, row: 5, stamp: stamp5 })).toMatchObject({ ok: true, count: 4 });
        expect(api.post({ action: 'deleteRegistration', passcode: admin, row: 4, stamp: listRows()[4][0] })).toMatchObject({ ok: true, count: 3 });
        expect(api.get({ action: 'ping' }).registrations).toBe(3);
        const fund = api.get({ action: 'ping' }).fundraising;
        expect(fund).toMatchObject({ donations: 25, donors: 1, players: 4, goal: 0, extra: 0 });
        expect(fund.list.map((d) => d.name)).toEqual(['Dev P.', 'Maya I.', 'Riya S. & Arjun R.']);
        expect(fund.list[2]).toMatchObject({ players: 2, extra: 25 });
        expect(JSON.stringify(fund)).not.toMatch(/@example\.com|Shah|Iyer/);
        expect(api.post({ action: 'setFundraising', passcode: api.props.get('SCORER_PASSCODE'), goal: 1 }).ok).toBe(false);
        expect(api.post({ action: 'setFundraising', passcode: admin, goal: 3000, extra: 150 }).fundraising).toMatchObject({ goal: 3000, extra: 150 });
        // Only the admin can read them; headers import cleanly
        expect(api.post({ action: 'registrations', passcode: api.props.get('SCORER_PASSCODE') }).ok).toBe(false);
        const rows = api.post({ action: 'registrations', passcode: admin }).rows;
        expect(rows.length).toBe(4);
        expect(rows[1][7]).toBe('HYPERLINK("x")'); // formula prefix stripped
        expect(rows[0].slice(-4)).toEqual(['Payment method', 'Payment confirmed', 'Extra donation', 'Anonymous']);
        expect(rows[0]).not.toContain('Skill level');
        expect(rows[0]).not.toContain('Team name (optional)');
        expect(rows[0]).not.toContain('School');
        expect(rows[1].slice(-4)).toEqual(['Zelle', 'Yes, sent', '$25', '']);
        expect(rows[2].slice(-4)).toEqual(['Cash at check-in', 'Will pay cash at check-in', '', '']);
        expect(detectColumns(rows[0])).toMatchObject({
            timestamp: 0, name: 1, email: 2, phone: 3, division: 4, partnerName: 5, partnerEmail: 6,
        });
        const res = importRegistrations(rows, detectColumns(rows[0]), DEFAULT_IMPORT_OPTIONS);
        expect(res.divisions.map((d) => d.name)).toEqual(['Adults', 'Kids/Teens']);
        const riyaTeam = Object.values(res.teams).find((t) => t.playerIds.some((id) => res.players[id].name === 'Arjun Rao'));
        expect(riyaTeam.playerIds.map((id) => res.players[id].name)).toEqual(['Riya Shah', 'Arjun Rao']);
        expect(res.divisions[1].teamIds.length).toBe(1); // two free agents paired
        // Organizer can close registration; publishing the draw also closes it
        expect(api.post({ action: 'setRegistration', passcode: admin, open: false })).toMatchObject({ ok: true, registrationOpen: false });
        expect(register({ name: 'Late', email: 'late@example.com', skill: 'Advanced (4.0+)', division: 'Adults', payment: 'Venmo', paid: true })).toMatchObject({ ok: false, error: 'Registration is closed.' });
        api.post({ action: 'setRegistration', passcode: admin, open: true });
        expect(api.post({ action: 'saveState', passcode: admin, state: tournament() }).ok).toBe(true);
        expect(api.get({ action: 'ping' }).registrationOpen).toBe(false);
        expect(register({ name: 'Late', email: 'late@example.com', skill: 'Advanced (4.0+)' })).toMatchObject({ ok: false });
    });
});
