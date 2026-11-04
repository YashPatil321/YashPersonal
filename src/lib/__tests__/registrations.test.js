import { describe, expect, it } from 'vitest';
import { seededRandom } from '../ids';
import { DEFAULT_IMPORT_OPTIONS, detectColumns, distinctTeamNames, importRegistrations, teamDisplayName, isNoPartner, pairFreeAgents, parseSkill, seedTeams, } from '../registrations';
import { classifyGoogleUrl } from '../sheets';
import { quickDraw } from '../quickDraw';
describe('detectColumns', () => {
    it('maps a typical Google Form doubles sign-up', () => {
        const headers = [
            'Timestamp',
            'Email Address',
            'Full Name',
            'Phone Number',
            'Skill Level (DUPR or self-rating)',
            'Which division?',
            "Partner's Name (leave blank if you need a partner)",
            "Partner's Email",
            "Partner's Skill Level",
        ];
        expect(detectColumns(headers)).toEqual({
            timestamp: 0,
            email: 1,
            name: 2,
            phone: 3,
            skill: 4,
            division: 5,
            partnerName: 6,
            partnerEmail: 7,
            partnerSkill: 8,
        });
    });
    it('handles first/last name and player 2 columns', () => {
        const m = detectColumns(['First Name', 'Last Name', 'Player 2 First Name', 'Player 2 Last Name', 'Event']);
        expect(m).toMatchObject({ name: 0, lastName: 1, partnerName: 2, partnerLastName: 3, division: 4 });
    });
});
describe('value parsing', () => {
    it('parses skill text', () => {
        expect(parseSkill('3.5')).toBe(3.5);
        expect(parseSkill('3.0 - 3.5')).toBe(3.25);
        expect(parseSkill('DUPR 4.12')).toBe(4.12);
        expect(parseSkill('Beginner')).toBe(2.5);
        expect(parseSkill('Intermediate')).toBe(3.25);
        expect(parseSkill('Advanced')).toBe(4);
        expect(parseSkill('')).toBeUndefined();
    });
    it('recognises "no partner" answers', () => {
        for (const v of ['', 'N/A', 'none', 'Need a partner', 'Looking for one', 'TBD', '?'])
            expect(isNoPartner(v)).toBe(true);
        expect(isNoPartner('Jamie Lee')).toBe(false);
    });
});
describe('importRegistrations', () => {
    const header = ['Timestamp', 'Name', 'Email', 'Skill', 'Division', 'Partner Name'];
    const rows = [
        header,
        ['1/1/2026 10:00:00', 'Alex Kim', 'alex@x.com', '3.5', "Men's Doubles", 'Jordan Lee'],
        ['1/1/2026 10:05:00', 'jordan lee', 'jordan@x.com', '3.0', "Men's Doubles", 'Alex Kim'],
        ['1/1/2026 10:10:00', 'Sam Park', 'sam@x.com', '4.0', "Men's Doubles", 'Chris Wu'], // partner not registered
        ['1/1/2026 10:20:00', 'Pat Moe', 'pat@x.com', '2.5', "Men's Doubles", ''],
        ['1/1/2026 10:21:00', 'Lou Dobbs', 'lou@x.com', '4.5', "Men's Doubles", 'n/a'],
        ['1/1/2026 10:22:00', 'Ray Ng', 'ray@x.com', '3.0', "Men's Doubles", ''],
        ['1/1/2026 10:30:00', 'Alex Kim', 'alex@x.com', '3.5', "Men's Doubles", 'Jordan Lee'], // duplicate
        ['1/1/2026 11:00:00', 'Dana Fox', 'dana@x.com', '3.5', 'Mixed Doubles, Womens Doubles', 'Alex Kim'],
    ];
    const mapping = detectColumns(header);
    it('pairs mutual partners, creates unregistered partners, pairs free agents, dedupes', () => {
        const res = importRegistrations(rows, mapping, DEFAULT_IMPORT_OPTIONS, seededRandom(1));
        const mens = res.divisions.find((d) => d.name === "Men's Doubles");
        const names = mens.teamIds.map((id) => res.teams[id].name.split(' & ').sort().join(' & '));
        expect(names).toContain('Alex & Jordan');
        expect(names).toContain('Chris & Sam');
        // 3 free agents → one balanced pair + one leftover (most recent = Ray Ng)
        expect(mens.teamIds.length).toBe(3);
        expect(res.unmatched.map((u) => res.players[u.playerId].name)).toEqual(['Ray Ng']);
        expect(names).toContain('Lou & Pat');
        expect(res.warnings.some((w) => w.includes('Duplicate registration for Alex Kim'))).toBe(true);
        // Checkbox answers split into two divisions; Dana's partner Alex isn't in those divisions → new teams
        expect(res.divisions.map((d) => d.name)).toEqual(["Men's Doubles", 'Mixed Doubles', 'Womens Doubles']);
        // Alex is one player object even though he appears as Dana's partner too
        const alexIds = Object.values(res.players).filter((p) => p.name === 'Alex Kim');
        expect(alexIds.length).toBe(1);
        // Ratings averaged
        const ak = Object.values(res.teams).find((t) => t.name.includes('Jordan'));
        expect(ak.rating).toBe(3.25);
    });
    it('singles mode: one competitor per row', () => {
        const res = importRegistrations(rows, mapping, { ...DEFAULT_IMPORT_OPTIONS, doubles: false });
        const mens = res.divisions.find((d) => d.name === "Men's Doubles");
        expect(mens.teamIds.length).toBe(6);
    });
});
describe('pairing & seeding', () => {
    const players = [5, 4, 3, 2].map((r, i) => ({ id: `p${i}`, name: `P${i}`, rating: r }));
    it('balanced pairs strongest with weakest', () => {
        const { teams } = pairFreeAgents(players, 'balanced');
        expect(teams.map((t) => t.map((p) => p.rating))).toEqual([
            [5, 2],
            [4, 3],
        ]);
    });
    it('similar pairs neighbours', () => {
        const { teams } = pairFreeAgents(players, 'similar');
        expect(teams.map((t) => t.map((p) => p.rating))).toEqual([
            [5, 4],
            [3, 2],
        ]);
    });
    it('seeds by rating, unrated last', () => {
        const teams = {
            a: { id: 'a', name: 'a', playerIds: [], divisionId: 'd', rating: 3 },
            b: { id: 'b', name: 'b', playerIds: [], divisionId: 'd' },
            c: { id: 'c', name: 'c', playerIds: [], divisionId: 'd', rating: 4 },
        };
        expect(seedTeams(['a', 'b', 'c'], teams, 'rating')).toEqual(['c', 'a', 'b']);
    });
});
describe('classifyGoogleUrl', () => {
    it('recognises link types', () => {
        expect(classifyGoogleUrl('https://docs.google.com/spreadsheets/d/abc123/edit#gid=42')).toEqual({
            kind: 'sheet',
            id: 'abc123',
            gid: '42',
        });
        expect(classifyGoogleUrl('https://docs.google.com/spreadsheets/d/e/2PACX-xyz/pubhtml').kind).toBe('published');
        expect(classifyGoogleUrl('https://docs.google.com/spreadsheets/d/e/2PACX-xyz/pubhtml').url).toContain('output=csv');
        expect(classifyGoogleUrl('https://script.google.com/macros/s/AKfy/exec').kind).toBe('appsScript');
        expect(classifyGoogleUrl('https://docs.google.com/forms/d/e/1FAIp/viewform').kind).toBe('form');
    });
});
describe('team names', () => {
    const p = (id, name) => ({ id, name });
    it('names a team by first names, like "Yash & Rhea"', () => {
        expect(teamDisplayName([p('a', 'Yash Patil'), p('b', 'Rhea Jain')])).toBe('Yash & Rhea');
        expect(teamDisplayName([p('a', 'Yash Patil')])).toBe('Yash Patil');
    });
    it('adds last initials, then full names, only when two teams would clash', () => {
        const players = {
            a: p('a', 'Arjun Shah'), b: p('b', 'Priya Kumar'),
            c: p('c', 'Arjun Mehta'), d: p('d', 'Priya Rao'),
            e: p('e', 'Yash Patil'), f: p('f', 'Rhea Jain'),
        };
        const team = (id, ids) => ({ id, name: teamDisplayName(ids.map((x) => players[x])), playerIds: ids, divisionId: 'x' });
        const out = distinctTeamNames({ t1: team('t1', ['a', 'b']), t2: team('t2', ['c', 'd']), t3: team('t3', ['e', 'f']) }, players);
        expect(out.t1.name).toBe('Arjun S. & Priya K.');
        expect(out.t2.name).toBe('Arjun M. & Priya R.');
        expect(out.t3.name).toBe('Yash & Rhea');
    });
});
describe('quickDraw', () => {
    it('turns website sign-ups into a draft draw with first-name teams in the two divisions', () => {
        const header = ['Timestamp', 'Full name', 'Email', 'Phone number', 'Division', "Partner's full name", "Partner's email", 'Anything else we should know?', 'Payment method', 'Payment confirmed', 'Extra donation', 'Anonymous'];
        const row = (name, division, partner = '') => ['11/3/2026', name, `${name.split(' ')[0].toLowerCase()}@x.com`, '', division, partner, '', '', 'Zelle', 'Yes, sent', '', ''];
        const rows = [
            header,
            row('Yash Patil', 'Kids/Teens', 'Rhea Jain'),
            row('Arjun Shah', 'Adults', 'Priya Kumar'),
            row('Dev Rao', 'Adults'),
            row('Maya Iyer', 'Adults'),
            row('Sam Lee', 'Adults'),
            row('Neel Das', 'Kids/Teens', 'Anya Roy'),
        ];
        const d = quickDraw(rows);
        expect(d.t.published).toBe(false);
        expect(d.t.divisions.map((x) => x.name)).toEqual(['Adults', 'Kids/Teens']);
        expect(d.t.courts.length).toBe(10);
        const names = Object.values(d.t.teams).map((x) => x.name);
        expect(names).toEqual(expect.arrayContaining(['Yash & Rhea', 'Arjun & Priya', 'Neel & Anya']));
        expect(d.needPartner.length).toBe(1); // 3 solo adults: one pair + one left over
        expect(d.teams).toBe(5);
        const kids = d.t.divisions[1];
        expect(kids.teamIds.map((id) => d.t.teams[id].name).sort()).toEqual(['Neel & Anya', 'Yash & Rhea']);
        expect(Object.values(d.t.matches).length).toBeGreaterThan(0);
    });
});
describe('people who share an email', () => {
    it('keeps siblings who signed up with a parent’s email as separate teams', () => {
        const header = ['Timestamp', 'Full name', 'Email', 'Phone number', 'Division', "Partner's full name", "Partner's email", 'Anything else we should know?', 'Payment method', 'Payment confirmed', 'Extra donation', 'Anonymous'];
        const rows = [
            header,
            ['1', 'Arjun Shah', 'mom@x.com', '', 'Kids/Teens', 'Priya Kumar', 'mom@x.com', '', 'Zelle', 'Yes, sent', '', ''],
            ['2', 'Sam Shah', 'mom@x.com', '', 'Kids/Teens', 'Tara Lee', '', '', 'Zelle', 'Yes, sent', '', ''],
        ];
        const d = quickDraw(rows);
        expect(Object.values(d.t.teams).map((x) => x.name).sort()).toEqual(['Arjun & Priya', 'Sam & Tara']);
    });
});
describe('partners who sign up on their own', () => {
    const header = ['Timestamp', 'Full name', 'Email', 'Phone number', 'Division', "Partner's full name", "Partner's email", 'Anything else we should know?', 'Payment method', 'Payment confirmed', 'Extra donation', 'Anonymous', 'Partner pays separately'];
    it('puts two separate sign-ups on one team', () => {
        const d = quickDraw([
            header,
            ['1', 'Yash Patil', 'y@x.com', '', 'Kids/Teens', 'Rhea Jain', '', '', 'Zelle', 'Yes, sent', '', '', 'Yes'],
            ['2', 'Rhea Jain', 'r@x.com', '', 'Kids/Teens', 'Yash Patil', '', '', 'Venmo', 'Yes, sent', '', '', 'Yes'],
        ]);
        expect(Object.values(d.t.teams).map((x) => x.name)).toEqual(['Yash & Rhea']);
        expect(d.notSignedUp).toEqual([]);
    });
    it('flags a partner who never signed up', () => {
        const d = quickDraw([header, ['1', 'Yash Patil', 'y@x.com', '', 'Kids/Teens', 'Rhea Jain', '', '', 'Zelle', 'Yes, sent', '', '', 'Yes']]);
        expect(Object.values(d.t.teams).map((x) => x.name)).toEqual(['Yash & Rhea']);
        expect(d.notSignedUp).toEqual(['Rhea Jain (with Yash Patil)']);
    });
});
