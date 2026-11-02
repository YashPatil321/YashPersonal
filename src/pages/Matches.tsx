import { useMemo, useState } from 'react';
import type { ResolvedMatch } from '../lib/resolve';
import { teamName } from '../lib/tournament';
import { MatchRow, stageLabel } from '../components/match';
import { Segmented } from '../components/ui';
import { useMatchDialog } from '../components/useMatchDialog';
import { useRoute } from '../state/router';
import { useTournament } from '../state/store';

type StatusFilter = 'all' | 'upcoming' | 'live' | 'final';

export function Matches() {
  const { t, resolved } = useTournament();
  const route = useRoute();
  const { open, dialog } = useMatchDialog();
  const [division, setDivision] = useState(route.query.get('d') ?? 'all');
  const [status, setStatus] = useState<StatusFilter>('all');
  const [q, setQ] = useState('');

  const filtered = useMemo(() => {
    const needle = q.trim().toLowerCase();
    return resolved.ordered.filter((r) => {
      if (division !== 'all' && r.m.divisionId !== division) return false;
      if (status === 'live' && !(r.m.status === 'live' && !r.done)) return false;
      if (status === 'final' && !(r.m.status === 'final')) return false;
      if (status === 'upcoming' && (r.done || r.m.status === 'live')) return false;
      if (needle) {
        const names = [r.a, r.b].map((x) => (typeof x === 'string' ? teamName(t, x).toLowerCase() : '')).join(' ');
        const players = [r.a, r.b]
          .flatMap((x) => (typeof x === 'string' ? t.teams[x]?.playerIds ?? [] : []))
          .map((id) => t.players[id]?.name.toLowerCase() ?? '')
          .join(' ');
        if (!names.includes(needle) && !players.includes(needle) && `m${r.m.number}` !== needle) return false;
      }
      return true;
    });
  }, [resolved, division, status, q, t]);

  // Group by division → stage heading
  const groups = useMemo(() => {
    const out: Array<{ key: string; title: string; matches: ResolvedMatch[] }> = [];
    const index = new Map<string, number>();
    for (const r of filtered) {
      const div = t.divisions.find((d) => d.id === r.m.divisionId)!;
      const sub =
        r.m.stage === 'pool' || r.m.stage === 'rr'
          ? r.m.stage === 'pool'
            ? stageLabel(t, r.m).split(' · ')[0]
            : 'Round robin'
          : r.m.stage === 'losers'
            ? 'Losers bracket'
            : 'Playoffs';
      const key = `${div.id}|${sub}`;
      if (!index.has(key)) {
        index.set(key, out.length);
        out.push({ key, title: t.divisions.length > 1 ? `${div.name} — ${sub}` : sub, matches: [] });
      }
      out[index.get(key)!].matches.push(r);
    }
    return out;
  }, [filtered, t]);

  return (
    <>
      <div className="page-head">
        <h1>Matches</h1>
        <button className="btn btn-sm no-print" onClick={() => window.print()}>
          Print
        </button>
      </div>
      <div className="card no-print" style={{ marginBottom: 14 }}>
        <div className="form-grid">
          <label className="field">
            Search team or player
            <input className="input" placeholder="e.g. Kim, or M12" value={q} onChange={(e) => setQ(e.target.value)} />
          </label>
          {t.divisions.length > 1 && (
            <label className="field">
              Division
              <select className="input" value={division} onChange={(e) => setDivision(e.target.value)}>
                <option value="all">All divisions</option>
                {t.divisions.map((d) => (
                  <option key={d.id} value={d.id}>
                    {d.name}
                  </option>
                ))}
              </select>
            </label>
          )}
        </div>
        <div style={{ marginTop: 10 }}>
          <Segmented<StatusFilter>
            value={status}
            onChange={setStatus}
            options={[
              { value: 'all', label: 'All' },
              { value: 'upcoming', label: 'Upcoming' },
              { value: 'live', label: 'Live' },
              { value: 'final', label: 'Final' },
            ]}
          />
        </div>
      </div>

      {groups.length === 0 && <div className="card empty">No matches match those filters.</div>}
      {groups.map((g) => (
        <div key={g.key} style={{ marginBottom: 18 }}>
          <h3 className="muted" style={{ fontSize: '0.85rem', textTransform: 'uppercase', letterSpacing: '0.05em' }}>
            {g.title}
          </h3>
          <div className="card" style={{ padding: 0 }}>
            {g.matches.map((r) => (
              <MatchRow
                key={r.m.id}
                t={t}
                r={r}
                onOpen={open}
                right={<span className="tiny muted nowrap">{r.m.stage === 'pool' || r.m.stage === 'rr' ? '' : r.m.label}</span>}
              />
            ))}
          </div>
        </div>
      ))}
      {dialog}
    </>
  );
}
