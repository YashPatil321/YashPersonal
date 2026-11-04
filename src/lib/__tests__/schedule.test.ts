import { describe, expect, it } from 'vitest';
import { finishMatch } from '../actions';
import { resolveTournament } from '../resolve';
import { matchMinutes, projectSchedule } from '../schedule';
import { buildTournament, courtNames, defaultDivisionSettings } from '../tournament';
import type { DivisionSettings, Player, Team, Tournament } from '../types';

function make(divs: Array<{ n: number; settings: Partial<DivisionSettings> }>, courts: number, minutes = 20): Tournament {
  const players: Record<string, Player> = {};
  const teams: Record<string, Team> = {};
  const divisions = divs.map((d, di) => {
    const ids: string[] = [];
    for (let i = 0; i < d.n; i++) {
      const id = `d${di}t${i}`;
      players[id] = { id, name: id };
      teams[id] = { id, name: id, playerIds: [id], divisionId: 'x' };
      ids.push(id);
    }
    return { name: `D${di}`, teamIds: ids, settings: { ...defaultDivisionSettings(d.n), ...d.settings } };
  });
  return buildTournament({ name: 'T', courts: courtNames(courts), minutesPerMatch: minutes, doubles: true }, players, teams, divisions);
}

describe('projectSchedule', () => {
  it('match length scales with games and points', () => {
    const base = { bestOf: 1, pointsToWin: 11, winBy: 2 };
    expect(matchMinutes(base, 20)).toBe(20);
    expect(matchMinutes({ ...base, bestOf: 3 }, 20)).toBe(48);
    expect(Math.round(matchMinutes({ ...base, pointsToWin: 15 }, 22))).toBe(30);
  });

  it('round robin is limited by teams, not courts', () => {
    expect(projectSchedule(make([{ n: 4, settings: { format: 'round_robin' } }], 2)).minutes).toBe(60);
    expect(projectSchedule(make([{ n: 4, settings: { format: 'round_robin' } }], 10)).minutes).toBe(60);
    expect(projectSchedule(make([{ n: 4, settings: { format: 'round_robin' } }], 1)).minutes).toBe(120);
  });

  it('brackets wait for earlier rounds', () => {
    expect(projectSchedule(make([{ n: 8, settings: { format: 'single_elim' } }], 4)).minutes).toBe(60);
    expect(projectSchedule(make([{ n: 8, settings: { format: 'single_elim' } }], 2)).minutes).toBe(80);
  });

  it('counts down as matches finish', () => {
    let t = make([{ n: 6, settings: { format: 'round_robin' } }], 3);
    const before = projectSchedule(t, { fromNow: true });
    for (let i = 0; i < 5; i++) {
      const r = resolveTournament(t).ordered.find((x) => x.ready)!;
      t = finishMatch(t, r.m.id, [{ a: 11, b: 5 }]);
    }
    const after = projectSchedule(t, { fromNow: true });
    expect(after.matches).toBe(before.matches - 5);
    expect(after.minutes).toBeLessThan(before.minutes);
    while (resolveTournament(t).ordered.some((x) => x.ready)) {
      const r = resolveTournament(t).ordered.find((x) => x.ready)!;
      t = finishMatch(t, r.m.id, [{ a: 11, b: 5 }]);
    }
    expect(projectSchedule(t, { fromNow: true })).toEqual({ minutes: 0, matches: 0 });
  });

  it('a 40-team, two-division event fits in 4 hours on 10 courts', () => {
    const t = make(
      [
        { n: 20, settings: { format: 'pools_playoff', poolCount: 4, advancePerPool: 2 } },
        { n: 20, settings: { format: 'pools_playoff', poolCount: 4, advancePerPool: 2 } },
      ],
      10,
    );
    const p = projectSchedule(t);
    expect(p.matches).toBe(94);
    // 94 matches × 20 min / 10 courts ≈ 188 min is the floor; pools of 5 need 5 rounds + 3 bracket rounds.
    expect(p.minutes).toBeGreaterThanOrEqual(188);
    expect(p.minutes).toBeLessThanOrEqual(240);
  });
});

describe('default draw', () => {
  it('guarantees every team at least 3 games before playoffs', () => {
    for (let n = 2; n <= 60; n++) {
      const t = make([{ n, settings: {} }], 10);
      const games: Record<string, number> = {};
      for (const m of Object.values(t.matches)) {
        if (m.bye || (m.stage !== 'rr' && m.stage !== 'pool')) continue;
        for (const s of [m.a, m.b]) if (s.kind === 'team') games[s.teamId] = (games[s.teamId] ?? 0) + 1;
      }
      const fewest = Math.min(...Object.keys(t.teams).map((id) => games[id] ?? 0));
      expect(fewest, `${n} teams`).toBeGreaterThanOrEqual(3);
    }
  });
});
