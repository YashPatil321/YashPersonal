import { useEffect, useMemo, useState } from 'react';
import type { Dispatch, ReactNode, SetStateAction } from 'react';
import { parseCSV } from '../lib/csv';
import { clampPoolCount } from '../lib/generate';
import { uid } from '../lib/ids';
import {
  averageRating,
  DEFAULT_IMPORT_OPTIONS,
  detectColumns,
  FIELD_LABELS,
  FIELD_ORDER,
  importRegistrations,
  seedTeams,
  distinctTeamNames,
  teamDisplayName,
} from '../lib/registrations';
import type { ColumnMapping, FieldKey, ImportOptions, PairingStrategy, SeedingMethod } from '../lib/registrations';
import { sampleRegistrations } from '../lib/sample';
import { describeRules } from '../lib/scoring';
import { formatDuration, projectSchedule } from '../lib/schedule';
import { classifyGoogleUrl, fetchSheetRows } from '../lib/sheets';
import {
  buildTournament,
  courtNames,
  defaultDivisionSettings,
  estimateDivision,
  FORMAT_LABELS,
} from '../lib/tournament';
import type { DivisionSettings, FormatType, Player, ScoringRules, Team } from '../lib/types';
import { Segmented } from '../components/ui';
import { BRAND } from '../brand';
import { navigate } from '../state/router';
import { load, save, useStore } from '../state/store';

const LS_DRAFT = 'pbt.draft.v1';

interface DraftDivision {
  id: string;
  name: string;
  teamIds: string[];
  settings: DivisionSettings;
  seeding: SeedingMethod;
}

interface Draft {
  step: number;
  info: {
    name: string;
    date: string;
    location: string;
    courtCount: number;
    minutesPerMatch: number;
    hours?: number;
    doubles: boolean;
  };
  sourceTab: 'sheet' | 'upload' | 'paste' | 'sample';
  sheetUrl: string;
  pasted: string;
  rows: string[][] | null;
  mapping: ColumnMapping;
  options: ImportOptions;
  importKey: string | null;
  players: Record<string, Player>;
  teams: Record<string, Team>;
  divisions: DraftDivision[];
  unmatched: Array<{ playerId: string; divisionId: string }>;
  warnings: string[];
}

function emptyDraft(): Draft {
  return {
    step: 0,
    info: {
      name: BRAND.eventName,
      date: BRAND.date,
      location: '',
      courtCount: 10,
      minutesPerMatch: 20,
      hours: 4,
      doubles: true,
    },
    sourceTab: 'sheet',
    sheetUrl: '',
    pasted: '',
    rows: null,
    mapping: {},
    options: { ...DEFAULT_IMPORT_OPTIONS },
    importKey: null,
    players: {},
    teams: {},
    divisions: [],
    unmatched: [],
    warnings: [],
  };
}

const STEPS = ['Event', 'Registrations', 'Columns', 'Teams', 'Format', 'Create'];

export function Setup() {
  const { t, replace, sync } = useStore();
  const [draft, setDraft] = useState<Draft>(() => load<Draft>(LS_DRAFT) ?? emptyDraft());
  useEffect(() => save(LS_DRAFT, draft), [draft]);
  const patch = (p: Partial<Draft>) => setDraft((d) => ({ ...d, ...p }));
  const go = (step: number) => {
    setDraft((d) => ({ ...d, step }));
    window.scrollTo({ top: 0 });
  };

  const importKey = useMemo(
    () => (draft.rows ? JSON.stringify([draft.mapping, draft.options, draft.rows.length, draft.rows[1]]) : null),
    [draft.rows, draft.mapping, draft.options],
  );

  /** Run the importer (only if inputs changed, so manual team edits survive back/next). */
  const runImport = () => {
    if (!draft.rows) return;
    if (draft.importKey === importKey && draft.divisions.length) return go(3);
    const res = importRegistrations(draft.rows, draft.mapping, { ...draft.options, doubles: draft.info.doubles });
    // Exactly two divisions. Anything else (an old sheet, a typo) goes to the closest one.
    const fixedName = (name: string) => (/kid|teen|youth|junior|child|student/i.test(name) ? 'Kids/Teens' : 'Adults');
    const divisions: DraftDivision[] = BRAND.divisions.map((name) => {
      const teamIds = res.divisions.filter((d) => fixedName(d.name) === name).flatMap((d) => d.teamIds);
      return { id: uid('d'), name, teamIds, settings: defaultDivisionSettings(teamIds.length), seeding: 'rating' as const };
    });
    const moved = res.divisions.filter((d) => !(BRAND.divisions as readonly string[]).includes(d.name));
    if (moved.length)
      res.warnings.push(`Put “${moved.map((d) => d.name).join('”, “')}” sign-ups into ${[...new Set(moved.map((d) => fixedName(d.name)))].join(' / ')}. Move any team that’s in the wrong division.`);
    const idOf = (name: string) => divisions.find((d) => d.name === fixedName(name))!.id;
    const nameToId = new Map(res.divisions.map((d) => [d.name, idOf(d.name)]));
    const teams = { ...res.teams };
    for (const d of divisions) for (const id of d.teamIds) teams[id] = { ...teams[id], divisionId: d.id };
    setDraft((prev) => ({
      ...prev,
      importKey,
      players: res.players,
      teams,
      divisions,
      unmatched: res.unmatched.map((u) => ({ playerId: u.playerId, divisionId: nameToId.get(u.division) ?? '' })),
      warnings: res.warnings,
      step: 3,
    }));
    window.scrollTo({ top: 0 });
  };

  const create = () => {
    const info = draft.info;
    const divisions = draft.divisions
      .filter((d) => d.teamIds.length >= 2)
      .map((d) => ({
        id: d.id,
        name: d.name,
        settings: d.settings,
        teamIds: seedTeams(d.teamIds, draft.teams, d.seeding),
      }));
    const tournament = buildTournament(
      {
        name: info.name.trim() || BRAND.eventName,
        date: info.date || undefined,
        location: info.location.trim() || undefined,
        courts: courtNames(Math.max(1, info.courtCount)),
        minutesPerMatch: info.minutesPerMatch,
        doubles: info.doubles,
        hoursAvailable: info.hours ?? 4,
      },
      draft.players,
      distinctTeamNames(draft.teams, draft.players),
      divisions,
    );
    replace({ ...tournament, published: false });
    save(LS_DRAFT, null);
    navigate('/');
  };

  const step = draft.step;
  return (
    <>
      <div className="page-head">
        <div>
          <div className="eyebrow">Organizer tools</div>
          <h1>Build the draw</h1>
          <div className="muted small">Build the {BRAND.short} draw from your sign-up form.</div>
        </div>
        <button
          className="btn btn-sm btn-ghost"
          onClick={() => {
            if (window.confirm('Clear this setup and start again?')) setDraft(emptyDraft());
          }}
        >
          Reset setup
        </button>
      </div>

      <div className="steps">
        {STEPS.map((label, i) => (
          <button
            key={label}
            className={i === step ? 'on' : i < step ? 'done' : ''}
            disabled={i > step}
            onClick={() => i < step && go(i)}
          >
            <div className="bar" />
            <span className="lbl">
              {i + 1}. {label}
            </span>
          </button>
        ))}
      </div>

      {step === 0 && <EventStep draft={draft} patch={patch} next={() => go(1)} />}
      {step === 1 && <SourceStep draft={draft} patch={patch} back={() => go(0)} next={() => go(2)} skip={() => skipImport(setDraft)} />}
      {step === 2 && <ColumnsStep draft={draft} patch={patch} back={() => go(1)} next={runImport} />}
      {step === 3 && <TeamsStep draft={draft} setDraft={setDraft} back={() => go(draft.rows ? 2 : 1)} next={() => go(4)} />}
      {step === 4 && <FormatStep draft={draft} setDraft={setDraft} back={() => go(3)} next={() => go(5)} />}
      {step === 5 && (
        <ReviewStep draft={draft} back={() => go(4)} create={create} replacing={!!t} synced={!!sync} />
      )}
    </>
  );
}

function skipImport(setDraft: Dispatch<SetStateAction<Draft>>) {
  setDraft((d) => ({
    ...d,
    rows: null,
    importKey: null,
    players: {},
    teams: {},
    unmatched: [],
    warnings: [],
    divisions: d.divisions.length
      ? d.divisions
      : BRAND.divisions.map((name) => ({ id: uid('d'), name, teamIds: [], settings: defaultDivisionSettings(0), seeding: 'registration' as const })),
    step: 3,
  }));
}

/* ------------------------------------------------------------------ */

function Foot({ back, next, nextLabel = 'Next', disabled, extra }: { back?: () => void; next: () => void; nextLabel?: string; disabled?: boolean; extra?: ReactNode }) {
  return (
    <div className="wizard-foot">
      {back ? (
        <button className="btn" onClick={back}>
          ← Back
        </button>
      ) : (
        <span />
      )}
      <div className="row">
        {extra}
        <button className="btn btn-primary" disabled={disabled} onClick={next}>
          {nextLabel}
        </button>
      </div>
    </div>
  );
}

function EventStep({ draft, patch, next }: { draft: Draft; patch: (p: Partial<Draft>) => void; next: () => void }) {
  const info = draft.info;
  const set = (p: Partial<Draft['info']>) => patch({ info: { ...info, ...p } });
  return (
    <>
      <div className="card">
        <h2>Event details</h2>
        <div className="form-grid">
          <label className="field">
            Tournament name
            <input className="input" placeholder="Fall Classic 2026" value={info.name} onChange={(e) => set({ name: e.target.value })} />
          </label>
          <label className="field">
            Date
            <input className="input" type="date" value={info.date} onChange={(e) => set({ date: e.target.value })} />
          </label>
          <label className="field">
            Location
            <input className="input" placeholder="Community Park Courts" value={info.location} onChange={(e) => set({ location: e.target.value })} />
          </label>
        </div>
        <div className="form-grid" style={{ marginTop: 12 }}>
          <label className="field">
            Number of courts
            <input
              className="input"
              type="number"
              min={1}
              max={60}
              value={info.courtCount}
              onChange={(e) => set({ courtCount: Math.max(1, Math.min(60, Number(e.target.value) || 1)) })}
            />
          </label>
          <label className="field">
            Hours you have the courts
            <input
              className="input"
              type="number"
              min={0.5}
              max={24}
              step={0.5}
              value={info.hours ?? 4}
              onChange={(e) => set({ hours: Math.max(0.5, Number(e.target.value) || 4) })}
            />
            <span className="hint">We’ll check the draw fits in this time.</span>
          </label>
          <label className="field">
            Minutes for one game to 11
            <input
              className="input"
              type="number"
              min={5}
              max={120}
              value={info.minutesPerMatch}
              onChange={(e) => set({ minutesPerMatch: Math.max(5, Number(e.target.value) || 20) })}
            />
            <span className="hint">Including changeover. Rec play is usually 15–20.</span>
          </label>
          <div className="field">
            Event type
            <Segmented
              value={info.doubles ? 'd' : 's'}
              onChange={(v) => set({ doubles: v === 'd' })}
              options={[
                { value: 'd', label: 'Doubles' },
                { value: 's', label: 'Singles' },
              ]}
            />
          </div>
        </div>
      </div>
      <Foot next={next} />
    </>
  );
}

/* ------------------------------------------------------------------ */

function PreviewTable({ rows }: { rows: string[][] }) {
  const head = rows[0] ?? [];
  return (
    <div className="table-wrap">
      <table className="table preview-table">
        <thead>
          <tr>
            {head.map((h, i) => (
              <th key={i} title={h}>
                {h || `Column ${i + 1}`}
              </th>
            ))}
          </tr>
        </thead>
        <tbody>
          {rows.slice(1, 6).map((r, i) => (
            <tr key={i}>
              {head.map((_, j) => (
                <td key={j} title={r[j]}>
                  {r[j]}
                </td>
              ))}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

function SourceStep({
  draft,
  patch,
  back,
  next,
  skip,
}: {
  draft: Draft;
  patch: (p: Partial<Draft>) => void;
  back: () => void;
  next: () => void;
  skip: () => void;
}) {
  const { sync } = useStore();
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const isScript = classifyGoogleUrl(draft.sheetUrl).kind === 'appsScript';
  const [scriptPass, setScriptPass] = useState(sync?.role === 'admin' ? sync.passcode ?? '' : '');
  // Connected organizers: default to the connected sign-up sheet.
  useEffect(() => {
    if (sync?.role === 'admin' && !draft.sheetUrl) patch({ sheetUrl: sync.url });
  }, []);

  const acceptRows = (rows: string[][]) => {
    if (rows.length < 2) {
      setError('That data has no registration rows (only a header, or nothing at all).');
      return;
    }
    setError(null);
    patch({ rows, mapping: detectColumns(rows[0]), importKey: null });
  };

  const loadSheet = async () => {
    setLoading(true);
    setError(null);
    try {
      acceptRows(await fetchSheetRows(draft.sheetUrl, scriptPass.trim() || undefined));
    } catch (e) {
      setError((e as Error).message);
    } finally {
      setLoading(false);
    }
  };

  return (
    <>
      <div className="card">
        <h2>Where are the sign-ups?</h2>
        <div style={{ marginBottom: 14 }}>
          <Segmented
            value={draft.sourceTab}
            onChange={(v) => patch({ sourceTab: v })}
            options={[
              { value: 'sheet', label: 'Google Sheet link' },
              { value: 'upload', label: 'Upload CSV' },
              { value: 'paste', label: 'Paste' },
              { value: 'sample', label: 'Sample data' },
            ]}
          />
        </div>

        {draft.sourceTab === 'sheet' && (
          <div className="stack">
            <label className="field">
              Google Sheet (form responses) link
              <input
                className="input"
                placeholder="https://docs.google.com/spreadsheets/d/…"
                value={draft.sheetUrl}
                onChange={(e) => patch({ sheetUrl: e.target.value })}
                onKeyDown={(e) => e.key === 'Enter' && draft.sheetUrl && loadSheet()}
              />
              <span className="hint">
                Works with: a sheet shared as “Anyone with the link can view”, a “Publish to web → CSV” link, or your Apps
                Script web-app URL (see the README for the private option).
              </span>
            </label>
            {isScript && (
              <label className="field">
                Admin passcode (from Code.gs)
                <input className="input" type="password" value={scriptPass} onChange={(e) => setScriptPass(e.target.value)} />
              </label>
            )}
            <div className="row">
              <button className="btn btn-primary" disabled={!draft.sheetUrl || loading} onClick={loadSheet}>
                {loading ? 'Loading…' : 'Load responses'}
              </button>
              {sync?.role === 'admin' && sync.passcode && draft.sheetUrl !== sync.url && (
                <button
                  className="btn"
                  onClick={() => {
                    patch({ sheetUrl: sync.url });
                    setScriptPass(sync.passcode ?? '');
                  }}
                >
                  Use the connected Google Sheet
                </button>
              )}
            </div>
            <details className="small muted">
              <summary>How do I get the link?</summary>
              <ol style={{ paddingLeft: 18, marginTop: 6 }}>
                <li>
                  In Google Forms open <b>Responses</b> → <b>Link to Sheets</b> (creates the response spreadsheet).
                </li>
                <li>
                  In that sheet click <b>Share</b> → General access: <b>Anyone with the link</b> → Viewer → Copy link.
                </li>
                <li>Paste it above. New sign-ups show up whenever you load it again.</li>
              </ol>
              Want to keep the sheet private? Use the Apps Script option in the README — it also enables live scores on
              everyone’s phone.
            </details>
          </div>
        )}

        {draft.sourceTab === 'upload' && (
          <label className="field">
            CSV file (Google Sheets → File → Download → .csv)
            <input
              className="input"
              type="file"
              accept=".csv,text/csv"
              onChange={(e) => {
                const file = e.target.files?.[0];
                if (!file) return;
                file.text().then((text) => acceptRows(parseCSV(text)));
              }}
            />
          </label>
        )}

        {draft.sourceTab === 'paste' && (
          <div className="stack">
            <label className="field">
              Paste CSV or rows copied from the spreadsheet (include the header row)
              <textarea
                className="input"
                value={draft.pasted}
                placeholder={'Name,Partner,Skill,Division\nAlex Kim,Jordan Lee,3.5,Intermediate'}
                onChange={(e) => patch({ pasted: e.target.value })}
              />
            </label>
            <div className="row">
              <button
                className="btn btn-primary"
                disabled={!draft.pasted.trim()}
                onClick={() => {
                  const text = draft.pasted.includes('\t') ? draft.pasted.replace(/\t/g, ',') : draft.pasted;
                  acceptRows(parseCSV(text));
                }}
              >
                Use this data
              </button>
            </div>
          </div>
        )}

        {draft.sourceTab === 'sample' && (
          <div className="stack">
            <p className="muted" style={{ margin: 0 }}>
              Try everything out with {sampleRegistrations().length - 1} made-up sign-ups across two divisions, including
              partners who didn’t register and players looking for a partner.
            </p>
            <div>
              <button className="btn btn-primary" onClick={() => acceptRows(sampleRegistrations())}>
                Load sample sign-ups
              </button>
            </div>
          </div>
        )}

        {error && (
          <div className="alert alert-error" style={{ marginTop: 12 }}>
            {error}
          </div>
        )}
      </div>

      {draft.rows && (
        <div className="card section">
          <div className="card-head">
            <h3>
              Loaded {draft.rows.length - 1} response{draft.rows.length === 2 ? '' : 's'}
            </h3>
            <span className="muted small">{draft.rows[0].length} columns</span>
          </div>
          <PreviewTable rows={draft.rows} />
        </div>
      )}
      <Foot
        back={back}
        next={next}
        disabled={!draft.rows}
        extra={
          <button className="btn btn-ghost" onClick={skip}>
            Skip — add teams by hand
          </button>
        }
      />
    </>
  );
}

/* ------------------------------------------------------------------ */

function ColumnsStep({ draft, patch, back, next }: { draft: Draft; patch: (p: Partial<Draft>) => void; back: () => void; next: () => void }) {
  const rows = draft.rows ?? [];
  const headers = rows[0] ?? [];
  const sample = rows[1] ?? [];
  const opts = draft.options;
  const setOpt = (p: Partial<ImportOptions>) => patch({ options: { ...opts, ...p } });
  const setMap = (key: FieldKey, value: string) => {
    const mapping = { ...draft.mapping };
    if (value === '') delete mapping[key];
    else mapping[key] = Number(value);
    patch({ mapping });
  };

  const preview = useMemo(
    () => (rows.length ? importRegistrations(rows, draft.mapping, { ...opts, doubles: draft.info.doubles }) : null),
    [rows, draft.mapping, opts, draft.info.doubles],
  );
  const fields = FIELD_ORDER.filter((f) => draft.info.doubles || !f.startsWith('partner'));
  const divisionValues = draft.mapping.division !== undefined
    ? [...new Set(rows.slice(1).map((r) => r[draft.mapping.division!]).filter(Boolean))]
    : [];
  const hasCommaDivisions = divisionValues.some((v) => /,/.test(v));

  return (
    <>
      <div className="grid grid-2">
        <div className="card">
          <h2>Match your form questions</h2>
          <p className="muted small">We guessed from the column headers — fix anything that looks off.</p>
          <div className="stack">
            {fields.map((key) => (
              <label className="field" key={key}>
                {FIELD_LABELS[key]}
                <select className="input" value={draft.mapping[key] ?? ''} onChange={(e) => setMap(key, e.target.value)}>
                  <option value="">— not in the form —</option>
                  {headers.map((h, i) => (
                    <option key={i} value={i}>
                      {h || `Column ${i + 1}`}
                    </option>
                  ))}
                </select>
                {draft.mapping[key] !== undefined && sample[draft.mapping[key]!] && (
                  <span className="hint">e.g. “{sample[draft.mapping[key]!]}”</span>
                )}
              </label>
            ))}
          </div>
        </div>

        <div className="stack" style={{ gap: 14 }}>
          <div className="card">
            <h2>Options</h2>
            <div className="stack">
              {draft.mapping.division === undefined && (
                <label className="field">
                  Division name (no division question in the form)
                  <input className="input" value={opts.defaultDivision} onChange={(e) => setOpt({ defaultDivision: e.target.value })} />
                </label>
              )}
              {draft.mapping.division !== undefined && (
                <label className="check">
                  <input type="checkbox" checked={opts.splitDivisions} onChange={(e) => setOpt({ splitDivisions: e.target.checked })} />
                  <span>
                    Players can enter several divisions (split “A, B” checkbox answers)
                    {hasCommaDivisions && <span className="badge badge-warn" style={{ marginLeft: 6 }}>detected</span>}
                  </span>
                </label>
              )}
              {draft.info.doubles && (
                <label className="field">
                  Players without a partner
                  <select className="input" value={opts.pairing} onChange={(e) => setOpt({ pairing: e.target.value as PairingStrategy })}>
                    <option value="balanced">Pair for balanced teams (strongest with weakest)</option>
                    <option value="similar">Pair players of similar skill</option>
                    <option value="random">Pair randomly</option>
                  </select>
                </label>
              )}
              <label className="check">
                <input type="checkbox" checked={opts.dedupe} onChange={(e) => setOpt({ dedupe: e.target.checked })} />
                Remove duplicate submissions (keeps the latest)
              </label>
            </div>
          </div>

          {preview && (
            <div className="card">
              <h2>Preview</h2>
              <div className="grid grid-3" style={{ gap: 8 }}>
                <Stat label="Responses" value={preview.rowCount} />
                <Stat label={draft.info.doubles ? 'Teams' : 'Players'} value={Object.keys(preview.teams).length} />
                <Stat label="Divisions" value={preview.divisions.length} />
              </div>
              <div className="stack small" style={{ marginTop: 10, gap: 4 }}>
                {preview.divisions.map((d) => (
                  <div key={d.name} className="row-between">
                    <span className="truncate">{d.name}</span>
                    <span className="muted num">{d.teamIds.length} {draft.info.doubles ? 'teams' : 'players'}</span>
                  </div>
                ))}
              </div>
              {preview.warnings.length > 0 && (
                <div className="alert alert-warn small" style={{ marginTop: 12 }}>
                  <b>Heads up</b>
                  <ul>
                    {preview.warnings.slice(0, 8).map((w, i) => (
                      <li key={i}>{w}</li>
                    ))}
                    {preview.warnings.length > 8 && <li>…and {preview.warnings.length - 8} more</li>}
                  </ul>
                </div>
              )}
              {draft.mapping.name === undefined && (
                <div className="alert alert-error small" style={{ marginTop: 12 }}>
                  Choose which column has the player’s name.
                </div>
              )}
            </div>
          )}
        </div>
      </div>
      <Foot back={back} next={next} nextLabel="Build teams" disabled={draft.mapping.name === undefined} />
    </>
  );
}

function Stat({ label, value }: { label: string; value: ReactNode }) {
  return (
    <div style={{ background: 'var(--surface-2)', borderRadius: 10, padding: '8px 10px' }}>
      <div className="tiny muted bold">{label}</div>
      <div style={{ fontSize: '1.3rem', fontWeight: 800 }} className="num">
        {value}
      </div>
    </div>
  );
}

/* ------------------------------------------------------------------ */

function TeamsStep({
  draft,
  setDraft,
  back,
  next,
}: {
  draft: Draft;
  setDraft: Dispatch<SetStateAction<Draft>>;
  back: () => void;
  next: () => void;
}) {
  const doubles = draft.info.doubles;
  const [selected, setSelected] = useState<string[]>([]);
  const [newTeam, setNewTeam] = useState<Record<string, { p1: string; p2: string }>>({});

  const updateDivision = (id: string, fn: (d: DraftDivision) => DraftDivision) =>
    setDraft((d) => ({ ...d, divisions: d.divisions.map((x) => (x.id === id ? fn(x) : x)) }));

  const renameTeam = (id: string, name: string) =>
    setDraft((d) => ({ ...d, teams: { ...d.teams, [id]: { ...d.teams[id], name } } }));

  const moveTeam = (teamId: string, from: string, to: string) =>
    setDraft((d) => ({
      ...d,
      teams: { ...d.teams, [teamId]: { ...d.teams[teamId], divisionId: to } },
      divisions: d.divisions.map((x) =>
        x.id === from ? { ...x, teamIds: x.teamIds.filter((t) => t !== teamId) } : x.id === to ? { ...x, teamIds: [...x.teamIds, teamId] } : x,
      ),
    }));

  const removeTeam = (teamId: string, divisionId: string) =>
    setDraft((d) => ({
      ...d,
      divisions: d.divisions.map((x) => (x.id === divisionId ? { ...x, teamIds: x.teamIds.filter((t) => t !== teamId) } : x)),
    }));

  const shift = (divisionId: string, index: number, dir: -1 | 1) =>
    updateDivision(divisionId, (x) => {
      const ids = x.teamIds.slice();
      const j = index + dir;
      if (j < 0 || j >= ids.length) return x;
      [ids[index], ids[j]] = [ids[j], ids[index]];
      return { ...x, teamIds: ids, seeding: 'registration' };
    });

  const addTeam = (divisionId: string) => {
    const entry = newTeam[divisionId] ?? { p1: '', p2: '' };
    const names = [entry.p1, entry.p2].map((s) => s.trim()).filter(Boolean);
    if (!names.length) return;
    setDraft((d) => {
      const players = { ...d.players };
      const members: Player[] = names.slice(0, doubles ? 2 : 1).map((name) => {
        const p = { id: uid('pl'), name };
        players[p.id] = p;
        return p;
      });
      const team: Team = {
        id: uid('t'),
        name: teamDisplayName(members),
        playerIds: members.map((m) => m.id),
        divisionId,
        rating: averageRating(members),
      };
      return {
        ...d,
        players,
        teams: { ...d.teams, [team.id]: team },
        divisions: d.divisions.map((x) => (x.id === divisionId ? { ...x, teamIds: [...x.teamIds, team.id] } : x)),
      };
    });
    setNewTeam((s) => ({ ...s, [divisionId]: { p1: '', p2: '' } }));
  };

  const pairSelected = () => {
    if (selected.length !== 2) return;
    setDraft((d) => {
      const [a, b] = selected.map((id) => d.unmatched.find((u) => u.playerId === id)!);
      const members = [d.players[a.playerId], d.players[b.playerId]];
      const team: Team = {
        id: uid('t'),
        name: teamDisplayName(members),
        playerIds: members.map((m) => m.id),
        divisionId: a.divisionId,
        rating: averageRating(members),
      };
      return {
        ...d,
        teams: { ...d.teams, [team.id]: team },
        unmatched: d.unmatched.filter((u) => !selected.includes(u.playerId)),
        divisions: d.divisions.map((x) => (x.id === a.divisionId ? { ...x, teamIds: [...x.teamIds, team.id] } : x)),
      };
    });
    setSelected([]);
  };

  return (
    <>
      {draft.warnings.length > 0 && (
        <details className="alert alert-warn small" style={{ marginBottom: 14 }}>
          <summary className="bold">{draft.warnings.length} import note{draft.warnings.length === 1 ? '' : 's'} — tap to review</summary>
          <ul>
            {draft.warnings.map((w, i) => (
              <li key={i}>{w}</li>
            ))}
          </ul>
        </details>
      )}

      {draft.unmatched.length > 0 && (
        <div className="card" style={{ marginBottom: 14 }}>
          <div className="card-head">
            <h3>Still need a partner</h3>
            <button className="btn btn-sm btn-primary" disabled={selected.length !== 2} onClick={pairSelected}>
              Pair selected
            </button>
          </div>
          <div className="stack" style={{ gap: 6 }}>
            {draft.unmatched.map((u) => {
              const p = draft.players[u.playerId];
              const div = draft.divisions.find((d) => d.id === u.divisionId);
              return (
                <label key={u.playerId} className="check">
                  <input
                    type="checkbox"
                    checked={selected.includes(u.playerId)}
                    onChange={(e) =>
                      setSelected((s) => (e.target.checked ? [...s, u.playerId].slice(-2) : s.filter((x) => x !== u.playerId)))
                    }
                  />
                  <span>
                    <b>{p?.name}</b> <span className="muted small">· {div?.name} {p?.skillLabel ? `· ${p.skillLabel}` : ''}</span>
                  </span>
                </label>
              );
            })}
          </div>
          <p className="tiny muted" style={{ margin: '8px 0 0' }}>
            Tick two players to make them a team, or add their partner below with “Add team”.
          </p>
        </div>
      )}

      <p className="muted small" style={{ marginTop: 0 }}>
        Rename teams, fix partners, move teams between divisions or add walk-ins. Seeding is chosen on the next step (by skill
        rating unless you reorder here with ↑↓).
      </p>
      <div className="stack" style={{ gap: 14 }}>
        {draft.divisions.map((div) => (
          <div className="card" key={div.id}>
            <div className="card-head">
              <h3 style={{ margin: 0 }}>{div.name}</h3>
              <span className="muted small nowrap">
                {div.teamIds.length} {doubles ? 'teams' : 'players'}
              </span>
            </div>
            {div.teamIds.length === 0 && <div className="muted small">No teams yet.</div>}
            {div.teamIds.map((id, i) => {
              const team = draft.teams[id];
              if (!team) return null;
              return (
                <div className="team-row" key={id}>
                  <span className="seed-pill">{i + 1}</span>
                  <div style={{ minWidth: 0 }}>
                    <input className="inline-input" value={team.name} onChange={(e) => renameTeam(id, e.target.value)} />
                    <div className="tiny muted" style={{ paddingLeft: 7 }}>
                      {team.rating !== undefined ? `Rating ${team.rating.toFixed(2)}` : 'No rating'}
                      {team.playerIds.length > 1 &&
                        ' · ' +
                          team.playerIds
                            .map((p) => draft.players[p]?.skillLabel)
                            .filter(Boolean)
                            .join(' / ')}
                    </div>
                  </div>
                  <div className="row" style={{ gap: 2, flexWrap: 'nowrap' }}>
                    <button className="btn btn-ghost btn-sm" onClick={() => shift(div.id, i, -1)} aria-label="Move up" disabled={i === 0}>
                      ↑
                    </button>
                    <button
                      className="btn btn-ghost btn-sm"
                      onClick={() => shift(div.id, i, 1)}
                      aria-label="Move down"
                      disabled={i === div.teamIds.length - 1}
                    >
                      ↓
                    </button>
                  </div>
                  <div className="row" style={{ gap: 2, flexWrap: 'nowrap' }}>
                    {draft.divisions.length > 1 && (
                      <select
                        className="input"
                        style={{ width: 90, padding: '3px 4px', fontSize: '0.78rem' }}
                        value=""
                        onChange={(e) => e.target.value && moveTeam(id, div.id, e.target.value)}
                        aria-label="Move to division"
                      >
                        <option value="">Move…</option>
                        {draft.divisions
                          .filter((x) => x.id !== div.id)
                          .map((x) => (
                            <option key={x.id} value={x.id}>
                              {x.name}
                            </option>
                          ))}
                      </select>
                    )}
                    <button className="btn btn-ghost btn-sm btn-danger" onClick={() => removeTeam(id, div.id)} aria-label="Remove team">
                      ✕
                    </button>
                  </div>
                </div>
              );
            })}
            <div className="row" style={{ marginTop: 10 }}>
              <input
                className="input"
                style={{ flex: '1 1 140px' }}
                placeholder={doubles ? 'Player 1' : 'Player name'}
                value={newTeam[div.id]?.p1 ?? ''}
                onChange={(e) => setNewTeam((s) => ({ ...s, [div.id]: { p1: e.target.value, p2: s[div.id]?.p2 ?? '' } }))}
              />
              {doubles && (
                <input
                  className="input"
                  style={{ flex: '1 1 140px' }}
                  placeholder="Player 2"
                  value={newTeam[div.id]?.p2 ?? ''}
                  onChange={(e) => setNewTeam((s) => ({ ...s, [div.id]: { p1: s[div.id]?.p1 ?? '', p2: e.target.value } }))}
                  onKeyDown={(e) => e.key === 'Enter' && addTeam(div.id)}
                />
              )}
              <button className="btn btn-sm" onClick={() => addTeam(div.id)}>
                + Add {doubles ? 'team' : 'player'}
              </button>
              {div.teamIds.length === 0 && draft.divisions.length > 1 && (
                <button
                  className="btn btn-sm btn-ghost btn-danger"
                  onClick={() => setDraft((d) => ({ ...d, divisions: d.divisions.filter((x) => x.id !== div.id) }))}
                >
                  Delete division
                </button>
              )}
            </div>
          </div>
        ))}
      </div>
      <Foot
        back={back}
        next={next}
        nextLabel="Choose formats"
        disabled={!draft.divisions.some((d) => d.teamIds.length >= 2)}
      />
    </>
  );
}

/* ------------------------------------------------------------------ */

function ScoringEditor({ value, onChange }: { value: ScoringRules; onChange: (v: ScoringRules) => void }) {
  return (
    <div className="form-grid" style={{ gridTemplateColumns: 'repeat(auto-fit, minmax(110px, 1fr))' }}>
      <label className="field">
        Games
        <select className="input" value={value.bestOf} onChange={(e) => onChange({ ...value, bestOf: Number(e.target.value) })}>
          <option value={1}>1 game</option>
          <option value={3}>Best of 3</option>
          <option value={5}>Best of 5</option>
        </select>
      </label>
      <label className="field">
        Play to
        <select className="input" value={value.pointsToWin} onChange={(e) => onChange({ ...value, pointsToWin: Number(e.target.value) })}>
          {[7, 9, 11, 15, 21].map((n) => (
            <option key={n} value={n}>
              {n}
            </option>
          ))}
        </select>
      </label>
      <label className="field">
        Win by
        <select className="input" value={value.winBy} onChange={(e) => onChange({ ...value, winBy: Number(e.target.value) })}>
          <option value={2}>2</option>
          <option value={1}>1</option>
        </select>
      </label>
      <label className="field">
        Cap
        <select
          className="input"
          value={value.cap ?? ''}
          onChange={(e) => onChange({ ...value, cap: e.target.value ? Number(e.target.value) : undefined })}
        >
          <option value="">None</option>
          {[13, 15, 17, 21, 25].filter((n) => n > value.pointsToWin).map((n) => (
            <option key={n} value={n}>
              {n}
            </option>
          ))}
        </select>
      </label>
    </div>
  );
}

function DivisionFormat({
  div,
  doubles,
  onChange,
}: {
  div: DraftDivision;
  doubles: boolean;
  onChange: (fn: (d: DraftDivision) => DraftDivision) => void;
}) {
  const s = div.settings;
  const n = div.teamIds.length;
  const set = (p: Partial<DivisionSettings>) => onChange((d) => ({ ...d, settings: { ...d.settings, ...p } }));
  const poolCount = clampPoolCount(n, s.poolCount);
  const minPool = Math.floor(n / poolCount);
  const est = estimateDivision(div.teamIds, s);
  const maxPools = Math.max(1, Math.floor(n / 3));
  const differentFinals = !!s.finalsScoring && JSON.stringify(s.finalsScoring) !== JSON.stringify(s.scoring);
  const hasPlayoffs = s.format !== 'round_robin';

  return (
    <div className="card">
      <div className="card-head">
        <h3>{div.name}</h3>
        <span className="muted small">
          {n} {doubles ? 'teams' : 'players'}
        </span>
      </div>
      <div className="form-grid">
        <label className="field">
          Format
          <select className="input" value={s.format} onChange={(e) => set({ format: e.target.value as FormatType })}>
            {(Object.keys(FORMAT_LABELS) as FormatType[]).map((f) => (
              <option key={f} value={f} disabled={f === 'pools_playoff' && n < 4}>
                {FORMAT_LABELS[f]}
              </option>
            ))}
          </select>
        </label>
        <label className="field">
          Seeding
          <select className="input" value={div.seeding} onChange={(e) => onChange((d) => ({ ...d, seeding: e.target.value as SeedingMethod }))}>
            <option value="rating">By skill rating</option>
            <option value="random">Random draw</option>
            <option value="registration">As listed on the Teams step</option>
          </select>
        </label>
        {(s.format === 'round_robin' || s.format === 'pools_playoff') && (
          <label className="field">
            {s.format === 'round_robin' ? 'Play each team' : 'In pools, play each team'}
            <select className="input" value={s.roundRobinCycles} onChange={(e) => set({ roundRobinCycles: Number(e.target.value) })}>
              <option value={1}>Once</option>
              <option value={2}>Twice</option>
            </select>
          </label>
        )}
      </div>

      {s.format === 'pools_playoff' && (
        <div className="form-grid" style={{ marginTop: 12 }}>
          <label className="field">
            Pools
            <select className="input" value={poolCount} onChange={(e) => set({ poolCount: Number(e.target.value) })}>
              {Array.from({ length: maxPools }, (_, i) => i + 1).map((p) => (
                <option key={p} value={p}>
                  {p} pool{p > 1 ? 's' : ''} ({Math.floor(n / p)}
                  {n % p ? `–${Math.ceil(n / p)}` : ''} each)
                </option>
              ))}
            </select>
          </label>
          <label className="field">
            Advance from each pool
            <select className="input" value={Math.min(s.advancePerPool, minPool)} onChange={(e) => set({ advancePerPool: Number(e.target.value) })}>
              {Array.from({ length: Math.max(1, minPool) }, (_, i) => i + 1).map((a) => (
                <option key={a} value={a}>
                  Top {a} ({a * poolCount} in playoffs)
                </option>
              ))}
            </select>
          </label>
          <label className="field">
            Playoff bracket
            <select className="input" value={s.playoffFormat} onChange={(e) => set({ playoffFormat: e.target.value as 'single_elim' | 'double_elim' })}>
              <option value="single_elim">Single elimination</option>
              <option value="double_elim">Double elimination</option>
            </select>
          </label>
        </div>
      )}

      {hasPlayoffs && (
        <div className="row" style={{ marginTop: 12, gap: 18 }}>
          {(s.format === 'single_elim' || (s.format === 'pools_playoff' && s.playoffFormat === 'single_elim')) && (
            <label className="check">
              <input type="checkbox" checked={s.thirdPlaceMatch} onChange={(e) => set({ thirdPlaceMatch: e.target.checked })} />
              3rd-place match
            </label>
          )}
          {(s.format === 'double_elim' || (s.format === 'pools_playoff' && s.playoffFormat === 'double_elim')) && (
            <label className="check" title="If the losers-bracket team wins the grand final, play one more deciding match">
              <input type="checkbox" checked={s.grandFinalReset} onChange={(e) => set({ grandFinalReset: e.target.checked })} />
              Grand-final reset (true double elimination)
            </label>
          )}
        </div>
      )}

      <div style={{ marginTop: 14 }}>
        <div className="small bold muted" style={{ marginBottom: 6 }}>
          Scoring {hasPlayoffs ? '(pool play & early rounds)' : ''}
        </div>
        <ScoringEditor
          value={s.scoring}
          onChange={(v) => set({ scoring: v, finalsScoring: differentFinals ? s.finalsScoring : v })}
        />
        {hasPlayoffs && (
          <>
            <label className="check" style={{ marginTop: 10 }}>
              <input
                type="checkbox"
                checked={differentFinals}
                onChange={(e) =>
                  set({
                    finalsScoring: e.target.checked ? { ...s.scoring, bestOf: Math.max(3, s.scoring.bestOf) } : { ...s.scoring },
                  })
                }
              />
              Different scoring for semifinals & finals
            </label>
            {differentFinals && s.finalsScoring && (
              <div style={{ marginTop: 8 }}>
                <ScoringEditor value={s.finalsScoring} onChange={(v) => set({ finalsScoring: v })} />
              </div>
            )}
          </>
        )}
      </div>

      <div className="alert small" style={{ marginTop: 14 }}>
        <b className="num">{est.matches}</b> matches · {describeRules(s.scoring)}
        {differentFinals && s.finalsScoring ? `; finals ${describeRules(s.finalsScoring).toLowerCase()}` : ''}
      </div>
    </div>
  );
}


function FormatStep({
  draft,
  setDraft,
  back,
  next,
}: {
  draft: Draft;
  setDraft: Dispatch<SetStateAction<Draft>>;
  back: () => void;
  next: () => void;
}) {
  const divisions = draft.divisions.filter((d) => d.teamIds.length >= 2);
  const courts = Math.max(1, draft.info.courtCount);
  const hours = draft.info.hours ?? 4;
  const projection = useMemo(() => {
    if (!divisions.length) return null;
    const preview = buildTournament(
      {
        name: 'preview',
        courts: courtNames(courts),
        minutesPerMatch: draft.info.minutesPerMatch,
        doubles: draft.info.doubles,
      },
      draft.players,
      draft.teams,
      divisions.map((d) => ({ name: d.name, teamIds: d.teamIds, settings: d.settings })),
    );
    return projectSchedule(preview);
  }, [divisions, courts, draft.info.minutesPerMatch, draft.info.doubles, draft.players, draft.teams]);
  const budget = hours * 60;
  const over = projection ? projection.minutes - budget : 0;
  return (
    <>
      {projection && (
        <div className={`time-budget ${over > 0 ? 'over' : 'fits'}`}>
          <div className="tb-main">
            <div className="eyebrow">{over > 0 ? 'Over your time' : 'Fits your time'}</div>
            <div className="tb-big">
              {formatDuration(projection.minutes)} <span>of {formatDuration(budget)}</span>
            </div>
            <div className="small">
              {projection.matches} matches on {courts} court{courts === 1 ? '' : 's'} at ~{draft.info.minutesPerMatch} min per
              game to 11.{' '}
              {over > 0
                ? `About ${formatDuration(over)} too long.`
                : `About ${formatDuration(-over)} to spare for warm-ups, delays and awards.`}
            </div>
          </div>
          <div className="tb-bar" aria-hidden="true">
            <div style={{ width: `${Math.min(100, (projection.minutes / Math.max(1, budget)) * 100)}%` }} />
          </div>
          {over > 0 && (
            <ul className="small tb-tips">
              <li>Play pool games to 9 (or add a cap) instead of 11.</li>
              <li>Use one game instead of best of 3, at least until the semifinals.</li>
              <li>Send fewer teams from each pool to the playoffs, or use single instead of double elimination.</li>
              <li>Use bigger pools, or a single round robin for small divisions.</li>
            </ul>
          )}
        </div>
      )}
      <div className="stack" style={{ gap: 14 }}>
        {divisions.map((div) => (
          <DivisionFormat
            key={div.id}
            div={div}
            doubles={draft.info.doubles}
            onChange={(fn) => setDraft((d) => ({ ...d, divisions: d.divisions.map((x) => (x.id === div.id ? fn(x) : x)) }))}
          />
        ))}
      </div>
      <Foot back={back} next={next} nextLabel="Review" />
    </>
  );
}

function ReviewStep({
  draft,
  back,
  create,
  replacing,
  synced,
}: {
  draft: Draft;
  back: () => void;
  create: () => void;
  replacing: boolean;
  synced: boolean;
}) {
  const divisions = draft.divisions.filter((d) => d.teamIds.length >= 2);
  const skipped = draft.divisions.filter((d) => d.teamIds.length < 2);
  return (
    <>
      <div className="card">
        <h2>{draft.info.name || BRAND.eventName}</h2>
        <div className="muted" style={{ marginBottom: 12 }}>
          {[draft.info.date, draft.info.location, `${draft.info.courtCount} courts`, `${draft.info.hours ?? 4} hours`]
            .filter(Boolean)
            .join(' · ')}
        </div>
        <div className="table-wrap">
          <table className="table">
            <thead>
              <tr>
                <th>Division</th>
                <th className="num">{draft.info.doubles ? 'Teams' : 'Players'}</th>
                <th>Format</th>
                <th>Scoring</th>
                <th className="num">Matches</th>
              </tr>
            </thead>
            <tbody>
              {divisions.map((d) => (
                <tr key={d.id}>
                  <td className="bold">{d.name}</td>
                  <td className="num">{d.teamIds.length}</td>
                  <td>
                    {FORMAT_LABELS[d.settings.format]}
                    {d.settings.format === 'pools_playoff' &&
                      ` (${clampPoolCount(d.teamIds.length, d.settings.poolCount)} pools, top ${d.settings.advancePerPool})`}
                  </td>
                  <td className="small">{describeRules(d.settings.scoring)}</td>
                  <td className="num">{estimateDivision(d.teamIds, d.settings).matches}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
        {skipped.length > 0 && (
          <div className="alert alert-warn small" style={{ marginTop: 12 }}>
            Skipping {skipped.map((d) => d.name).join(', ')} — a division needs at least 2 {draft.info.doubles ? 'teams' : 'players'}.
          </div>
        )}
        {draft.unmatched.length > 0 && (
          <div className="alert alert-warn small" style={{ marginTop: 12 }}>
            {draft.unmatched.length} player{draft.unmatched.length === 1 ? ' is' : 's are'} still without a partner and won’t be in
            the draw.
          </div>
        )}
        <div className="alert alert-ok small" style={{ marginTop: 12 }}>
          This creates a <b>draft</b>. Players can’t see it yet: check the courts, matchups and teams, change anything you
          like, then press <b>Publish to players</b> when you’re ready.
        </div>
        {replacing && (
          <div className="alert alert-warn small" style={{ marginTop: 12 }}>
            This replaces the current tournament{synced ? ' for everyone connected to the Google Sheet' : ' on this device'}.
            Export it from Settings first if you want a copy.
          </div>
        )}
      </div>
      <Foot back={back} next={create} nextLabel="Create draft" disabled={!divisions.length} />
    </>
  );
}
