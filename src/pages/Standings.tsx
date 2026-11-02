import { useState } from 'react';
import { Bracket } from '../components/Bracket';
import { Podium, StandingsTable } from '../components/Standings';
import { Empty, Segmented } from '../components/ui';
import { useMatchDialog } from '../components/useMatchDialog';
import { FORMAT_LABELS } from '../lib/tournament';
import { useRoute } from '../state/router';
import { useTournament } from '../state/store';

function DrawTabs({ current }: { current: 'standings' | 'brackets' }) {
  const { t } = useTournament();
  if (!t.divisions.some((d) => d.settings.format !== 'round_robin')) return null;
  return (
    <div className="segmented">
      <a href="#/standings" className={current === 'standings' ? 'on' : ''}>
        Standings
      </a>
      <a href="#/brackets" className={current === 'brackets' ? 'on' : ''}>
        Brackets
      </a>
    </div>
  );
}

function DivisionPicker({ value, onChange }: { value: string; onChange: (id: string) => void }) {
  const { t } = useTournament();
  if (t.divisions.length < 2) return null;
  return (
    <div style={{ marginBottom: 14, overflowX: 'auto' }}>
      <Segmented value={value} onChange={onChange} options={t.divisions.map((d) => ({ value: d.id, label: d.name }))} />
    </div>
  );
}

function useDivisionParam(filter?: (formatId: string) => boolean) {
  const { t } = useTournament();
  const route = useRoute();
  const candidates = t.divisions.filter((d) => !filter || filter(d.settings.format));
  const initial = route.query.get('d');
  const [id, setId] = useState(
    candidates.find((d) => d.id === initial)?.id ?? candidates[0]?.id ?? t.divisions[0]?.id ?? '',
  );
  return [id, setId] as const;
}

export function Standings() {
  const { t, resolved } = useTournament();
  const [divisionId, setDivisionId] = useDivisionParam();
  const rd = resolved.divisions[divisionId];
  if (!rd) return <Empty title="No divisions yet" />;
  const { division } = rd;
  const advance = division.settings.advancePerPool;

  return (
    <>
      <div className="page-head">
        <div>
          <div className="eyebrow">{FORMAT_LABELS[division.settings.format]}</div>
          <h1>Standings</h1>
        </div>
        <DrawTabs current="standings" />
      </div>
      <DivisionPicker value={divisionId} onChange={setDivisionId} />

      {rd.placements.length > 0 && (
        <div className="card" style={{ marginBottom: 14 }}>
          <h2>{rd.complete ? 'Final results' : 'Results so far'}</h2>
          <Podium t={t} placements={rd.placements} limit={8} />
        </div>
      )}

      {division.settings.format === 'round_robin' && rd.rrStandings && (
        <div className="card">
          <StandingsTable t={t} rows={rd.rrStandings} />
        </div>
      )}

      {division.settings.format === 'pools_playoff' && (
        <>
          <p className="muted small">
            Top {advance} from each pool advance to the playoffs. Ties are broken by head-to-head, then point
            differential, then points scored.
            {!rd.poolsComplete && ' Playoff seeding locks in once every pool match is final.'}
          </p>
          <div className="grid grid-2">
            {division.pools.map((p) => (
              <div className="card" key={p.id}>
                <h3>{p.name}</h3>
                <StandingsTable
                  t={t}
                  rows={rd.poolStandings[p.id] ?? []}
                  advancing={rd.poolsComplete ? 0 : advance}
                  qualified={rd.poolsComplete ? rd.qualified : undefined}
                />
              </div>
            ))}
          </div>
        </>
      )}

      {(division.settings.format === 'single_elim' || division.settings.format === 'double_elim') && (
        <div className="card">
          <p className="muted" style={{ margin: 0 }}>
            This division is a straight {FORMAT_LABELS[division.settings.format].toLowerCase()} bracket —{' '}
            <a href={`#/brackets?d=${division.id}`}>see the bracket</a>.
          </p>
        </div>
      )}
    </>
  );
}

export function Brackets() {
  const { t, resolved } = useTournament();
  const [divisionId, setDivisionId] = useDivisionParam((f) => f !== 'round_robin');
  const { open, dialog } = useMatchDialog();
  const withBrackets = t.divisions.filter((d) => d.settings.format !== 'round_robin');
  if (!withBrackets.length)
    return (
      <Empty title="No brackets">
        <p>Every division is a round robin — check the Standings page.</p>
      </Empty>
    );
  const rd = resolved.divisions[divisionId];

  return (
    <>
      <div className="page-head">
        <div>
          <div className="eyebrow">Playoffs</div>
          <h1>Brackets</h1>
        </div>
        <DrawTabs current="brackets" />
      </div>
      {withBrackets.length > 1 && (
        <div style={{ marginBottom: 14, overflowX: 'auto' }}>
          <Segmented value={divisionId} onChange={setDivisionId} options={withBrackets.map((d) => ({ value: d.id, label: d.name }))} />
        </div>
      )}
      {rd && (
        <>
          {rd.division.settings.format === 'pools_playoff' && !rd.poolsComplete && (
            <div className="alert" style={{ marginBottom: 14 }}>
              Playoff spots fill in automatically once pool play finishes ({rd.matches.filter((r) => r.m.stage === 'pool' && r.done).length}
              /{rd.matches.filter((r) => r.m.stage === 'pool').length} pool matches done).
            </div>
          )}
          {rd.placements.length > 0 && rd.complete && (
            <div className="card" style={{ marginBottom: 14 }}>
              <h2>Champions</h2>
              <Podium t={t} placements={rd.placements} />
            </div>
          )}
          <Bracket t={t} rd={rd} onOpen={open} />
        </>
      )}
      {dialog}
    </>
  );
}
