import { useEffect, useState } from 'react';
import QRCode from 'qrcode';
import { toCSV } from '../lib/csv';
import { download, matchesTable, placementsTable, slug, standingsTable, teamsTable } from '../lib/exporters';
import { regenerateDivision } from '../lib/generate';
import { uid } from '../lib/ids';
import { averageRating, teamDisplayName } from '../lib/registrations';
import { remote } from '../lib/sync';
import { FORMAT_LABELS } from '../lib/tournament';
import type { FormatType, Player, Team, Tournament } from '../lib/types';
import { timeAgo } from '../components/ui';
import { navigate } from '../state/router';
import { useStore } from '../state/store';

export function Settings() {
  const { t, isAdmin } = useStore();
  return (
    <>
      <div className="page-head">
        <h1>Settings</h1>
      </div>
      <div className="stack" style={{ gap: 14 }}>
        <SyncCard />
        {t && <ShareCard />}
        {t && isAdmin && <EventCard />}
        {t && isAdmin && <DivisionsCard />}
        <DataCard />
      </div>
    </>
  );
}

/* ------------------------------------------------------------------ */

function SyncCard() {
  const { sync, syncState, connect, t, refresh } = useStore();
  const [url, setUrl] = useState(sync?.url ?? '');
  const [passcode, setPasscode] = useState(sync?.passcode ?? '');
  const [busy, setBusy] = useState(false);
  const [message, setMessage] = useState<{ ok: boolean; text: string } | null>(null);

  const doConnect = async (publishLocal = false) => {
    setBusy(true);
    setMessage(null);
    try {
      const text = await connect({ url: url.trim(), passcode: passcode.trim() || undefined, role: 'viewer' }, { publishLocal });
      setMessage({ ok: true, text });
    } catch (e) {
      setMessage({ ok: false, text: (e as Error).message });
    } finally {
      setBusy(false);
    }
  };

  return (
    <div className="card">
      <div className="card-head">
        <h2>Live sync with Google Sheets</h2>
        {sync && (
          <span className={`badge ${syncState.status === 'synced' ? 'badge-final' : syncState.status === 'error' || syncState.status === 'offline' ? 'badge-warn' : ''}`}>
            {syncState.status} {syncState.lastSync ? `· ${timeAgo(syncState.lastSync)}` : ''}
          </span>
        )}
      </div>
      <p className="muted small">
        Optional. Connect the Apps Script that lives in your form’s Google Sheet and every phone, laptop and TV sees the same
        live scores. Without it, the tournament is saved on this device only. Setup takes about 3 minutes — see{' '}
        <b>apps-script/Code.gs</b> and the README.
      </p>
      {sync && (
        <div className="alert alert-ok small" style={{ marginBottom: 12 }}>
          Connected as <b>{sync.role}</b>
          {sync.role === 'viewer' && ' (read-only — enter the passcode to keep score)'}.
          {syncState.message && <div>{syncState.message}</div>}
        </div>
      )}
      <div className="form-grid">
        <label className="field">
          Apps Script web-app URL
          <input
            className="input"
            placeholder="https://script.google.com/macros/s/…/exec"
            value={url}
            onChange={(e) => setUrl(e.target.value)}
          />
        </label>
        <label className="field">
          Passcode (admin or scorer)
          <input
            className="input"
            type="password"
            placeholder="Leave blank to just watch"
            value={passcode}
            onChange={(e) => setPasscode(e.target.value)}
          />
        </label>
      </div>
      <div className="row" style={{ marginTop: 12 }}>
        <button className="btn btn-primary" disabled={!url.trim() || busy} onClick={() => doConnect(false)}>
          {busy ? 'Connecting…' : sync ? 'Reconnect' : 'Connect'}
        </button>
        {t && !!passcode && (
          <button
            className="btn"
            disabled={!url.trim() || busy}
            onClick={() => {
              if (window.confirm('Upload this device’s tournament to the sheet, replacing whatever is there?')) void doConnect(true);
            }}
          >
            Connect & publish this device’s tournament
          </button>
        )}
        {sync && (
          <>
            <button className="btn btn-ghost" onClick={() => void refresh()}>
              Refresh now
            </button>
            <button
              className="btn btn-ghost btn-danger"
              onClick={async () => setMessage({ ok: true, text: await connect(null) })}
            >
              Disconnect
            </button>
          </>
        )}
      </div>
      {message && (
        <div className={`alert ${message.ok ? 'alert-ok' : 'alert-error'} small`} style={{ marginTop: 12 }}>
          {message.text}
        </div>
      )}
    </div>
  );
}

/* ------------------------------------------------------------------ */

function ShareCard() {
  const { sync } = useStore();
  const base = `${window.location.origin}${window.location.pathname}`;
  const link = sync ? `${base}?live=${encodeURIComponent(sync.url)}#/` : '';
  const [qr, setQr] = useState('');
  const [copied, setCopied] = useState(false);
  useEffect(() => {
    if (!link) return;
    QRCode.toDataURL(link, { margin: 1, width: 360 }).then(setQr).catch(() => setQr(''));
  }, [link]);

  return (
    <div className="card">
      <h2>Share with players</h2>
      {!sync ? (
        <p className="muted small" style={{ margin: 0 }}>
          Connect live sync above to get a link and QR code players can open on their phones. Without sync you can still put{' '}
          <a href="#/tv">TV mode</a> on a screen connected to this device — it updates as you enter scores.
        </p>
      ) : (
        <div className="row" style={{ alignItems: 'flex-start', gap: 16 }}>
          {qr && <img className="qr" src={qr} alt="QR code for the live tournament page" />}
          <div className="stack" style={{ flex: '1 1 240px', minWidth: 0 }}>
            <div className="small muted">Read-only live page — print the QR code or text the link:</div>
            <input className="input" readOnly value={link} onFocus={(e) => e.target.select()} />
            <div className="row">
              <button
                className="btn btn-sm"
                onClick={() => {
                  void navigator.clipboard?.writeText(link);
                  setCopied(true);
                  setTimeout(() => setCopied(false), 1500);
                }}
              >
                {copied ? 'Copied!' : 'Copy link'}
              </button>
              <a className="btn btn-sm" href="#/tv">
                Open TV mode
              </a>
            </div>
            <div className="tiny muted">
              Court volunteers: open the same link, then enter the scorer passcode under Settings to keep score.
            </div>
          </div>
        </div>
      )}
    </div>
  );
}

/* ------------------------------------------------------------------ */

function EventCard() {
  const { t, update } = useStore();
  if (!t) return null;
  const set = (p: Partial<Tournament>) => update((tt) => ({ ...tt, ...p, updatedAt: Date.now() }));
  const setCourts = (courts: string[]) => set({ courts });
  return (
    <div className="card">
      <h2>Event</h2>
      <div className="form-grid">
        <label className="field">
          Name
          <input className="input" defaultValue={t.name} onBlur={(e) => e.target.value.trim() && set({ name: e.target.value.trim() })} />
        </label>
        <label className="field">
          Date
          <input className="input" type="date" defaultValue={t.date} onBlur={(e) => set({ date: e.target.value || undefined })} />
        </label>
        <label className="field">
          Location
          <input className="input" defaultValue={t.location} onBlur={(e) => set({ location: e.target.value.trim() || undefined })} />
        </label>
        <label className="field">
          Minutes per match (for wait estimates)
          <input
            className="input"
            type="number"
            min={5}
            defaultValue={t.settings.minutesPerMatch}
            onBlur={(e) => set({ settings: { ...t.settings, minutesPerMatch: Math.max(5, Number(e.target.value) || 20) } })}
          />
        </label>
      </div>
      <h3 style={{ marginTop: 16 }}>Courts</h3>
      <div className="row">
        {t.courts.map((c, i) => (
          <div key={`${c}-${i}`} className="row" style={{ gap: 2, background: 'var(--surface-2)', borderRadius: 10, padding: '2px 4px 2px 2px' }}>
            <input
              className="inline-input"
              style={{ width: 110 }}
              defaultValue={c}
              onBlur={(e) => {
                const name = e.target.value.trim();
                if (!name || name === c || t.courts.includes(name)) return;
                update((tt) => ({
                  ...tt,
                  courts: tt.courts.map((x) => (x === c ? name : x)),
                  matches: Object.fromEntries(
                    Object.entries(tt.matches).map(([id, m]) => [id, m.court === c ? { ...m, court: name, updatedAt: Date.now() } : m]),
                  ),
                  updatedAt: Date.now(),
                }));
              }}
            />
            <button
              className="btn btn-ghost btn-sm"
              aria-label={`Remove ${c}`}
              disabled={t.courts.length <= 1}
              onClick={() => setCourts(t.courts.filter((x) => x !== c))}
            >
              ✕
            </button>
          </div>
        ))}
        <button
          className="btn btn-sm"
          onClick={() => {
            let n = t.courts.length + 1;
            while (t.courts.includes(`Court ${n}`)) n++;
            setCourts([...t.courts, `Court ${n}`]);
          }}
        >
          + Add court
        </button>
      </div>
    </div>
  );
}

/* ------------------------------------------------------------------ */

function DivisionsCard() {
  const { t, resolved, update } = useStore();
  const [adding, setAdding] = useState<Record<string, { p1: string; p2: string }>>({});
  if (!t || !resolved) return null;

  const addTeam = (divisionId: string) => {
    const entry = adding[divisionId];
    const names = [entry?.p1, entry?.p2].map((s) => s?.trim()).filter((s): s is string => !!s).slice(0, t.settings.doubles ? 2 : 1);
    if (!names.length) return;
    update((tt) => {
      const players = { ...tt.players };
      const members: Player[] = names.map((name) => {
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
        ...tt,
        players,
        teams: { ...tt.teams, [team.id]: team },
        divisions: tt.divisions.map((d) => (d.id === divisionId ? { ...d, teamIds: [...d.teamIds, team.id] } : d)),
        updatedAt: Date.now(),
      };
    });
    setAdding((s) => ({ ...s, [divisionId]: { p1: '', p2: '' } }));
  };

  return (
    <div className="card">
      <h2>Divisions & schedule</h2>
      <p className="muted small">
        Late sign-up or withdrawal? Add or remove teams here, then rebuild that division’s schedule. Rebuilding clears that
        division’s scores, so do it before play starts.
      </p>
      <div className="stack" style={{ gap: 16 }}>
        {t.divisions.map((d) => {
          const rd = resolved.divisions[d.id];
          const played = rd.matches.filter((r) => r.m.status !== 'pending').length;
          const scheduled = new Set(rd.matches.flatMap((r) => [r.m.a, r.m.b]).flatMap((s) => (s.kind === 'team' ? [s.teamId] : [])));
          const outOfDate =
            d.settings.format !== 'pools_playoff'
              ? d.teamIds.some((id) => !scheduled.has(id)) || [...scheduled].some((id) => !d.teamIds.includes(id))
              : d.teamIds.length !== d.pools.reduce((n, p) => n + p.teamIds.length, 0);
          return (
            <div key={d.id} style={{ borderTop: '1px solid var(--line)', paddingTop: 12 }}>
              <div className="row-between" style={{ flexWrap: 'wrap' }}>
                <input
                  className="inline-input"
                  style={{ fontWeight: 750, maxWidth: 260 }}
                  defaultValue={d.name}
                  onBlur={(e) => {
                    const name = e.target.value.trim();
                    if (name && name !== d.name)
                      update((tt) => ({ ...tt, divisions: tt.divisions.map((x) => (x.id === d.id ? { ...x, name } : x)), updatedAt: Date.now() }));
                  }}
                />
                <span className="small muted">
                  {d.teamIds.length} {t.settings.doubles ? 'teams' : 'players'} · {played} matches started
                </span>
              </div>
              <div className="form-grid" style={{ marginTop: 8 }}>
                <label className="field">
                  Format
                  <select
                    className="input"
                    value={d.settings.format}
                    onChange={(e) =>
                      update((tt) => ({
                        ...tt,
                        divisions: tt.divisions.map((x) =>
                          x.id === d.id ? { ...x, settings: { ...x.settings, format: e.target.value as FormatType } } : x,
                        ),
                        updatedAt: Date.now(),
                      }))
                    }
                  >
                    {(Object.keys(FORMAT_LABELS) as FormatType[]).map((f) => (
                      <option key={f} value={f}>
                        {FORMAT_LABELS[f]}
                      </option>
                    ))}
                  </select>
                </label>
                <label className="field">
                  Remove a {t.settings.doubles ? 'team' : 'player'}
                  <select
                    className="input"
                    value=""
                    onChange={(e) => {
                      const id = e.target.value;
                      if (!id || !window.confirm(`Remove ${t.teams[id]?.name} from ${d.name}?`)) return;
                      update((tt) => ({
                        ...tt,
                        divisions: tt.divisions.map((x) => (x.id === d.id ? { ...x, teamIds: x.teamIds.filter((y) => y !== id) } : x)),
                        updatedAt: Date.now(),
                      }));
                    }}
                  >
                    <option value="">Choose…</option>
                    {d.teamIds.map((id) => (
                      <option key={id} value={id}>
                        {t.teams[id]?.name}
                      </option>
                    ))}
                  </select>
                </label>
              </div>
              <div className="row" style={{ marginTop: 8 }}>
                <input
                  className="input"
                  style={{ flex: '1 1 130px' }}
                  placeholder={t.settings.doubles ? 'Player 1' : 'Player name'}
                  value={adding[d.id]?.p1 ?? ''}
                  onChange={(e) => setAdding((s) => ({ ...s, [d.id]: { p1: e.target.value, p2: s[d.id]?.p2 ?? '' } }))}
                />
                {t.settings.doubles && (
                  <input
                    className="input"
                    style={{ flex: '1 1 130px' }}
                    placeholder="Player 2"
                    value={adding[d.id]?.p2 ?? ''}
                    onChange={(e) => setAdding((s) => ({ ...s, [d.id]: { p1: s[d.id]?.p1 ?? '', p2: e.target.value } }))}
                  />
                )}
                <button className="btn btn-sm" onClick={() => addTeam(d.id)}>
                  + Add
                </button>
              </div>
              <div className="row" style={{ marginTop: 8 }}>
                {outOfDate && <span className="badge badge-warn">Teams changed — rebuild to update the schedule</span>}
                <button
                  className={`btn btn-sm ${outOfDate ? 'btn-primary' : ''}`}
                  onClick={() => {
                    if (played && !window.confirm(`Rebuild ${d.name}? This clears ${played} started/finished match(es) in this division.`)) return;
                    update((tt) => regenerateDivision(tt, d.id));
                  }}
                >
                  Rebuild schedule
                </button>
              </div>
            </div>
          );
        })}
      </div>
      <div className="row" style={{ marginTop: 14 }}>
        <a className="btn btn-sm" href="#/setup">
          Start a new tournament from the form…
        </a>
      </div>
    </div>
  );
}

/* ------------------------------------------------------------------ */

function DataCard() {
  const { t, resolved, isAdmin, replace, sync } = useStore();
  const [msg, setMsg] = useState<string | null>(null);
  const name = slug(t?.name ?? 'tournament');

  const exportTables = async () => {
    if (!t || !resolved || !sync?.passcode) return;
    setMsg('Writing to Google Sheet…');
    try {
      await remote.writeTables(sync.url, sync.passcode, {
        Matches: matchesTable(t, resolved),
        Standings: standingsTable(t, resolved),
        Results: placementsTable(t, resolved),
        Teams: teamsTable(t),
      });
      setMsg('Done — look for the “TM Matches”, “TM Standings”, “TM Results” and “TM Teams” tabs in your sheet.');
    } catch (e) {
      setMsg(`Couldn't write to the sheet: ${(e as Error).message}`);
    }
  };

  return (
    <div className="card">
      <h2>Data</h2>
      {t && resolved && (
        <>
          <div className="small bold muted" style={{ marginBottom: 6 }}>
            Download
          </div>
          <div className="row">
            <button className="btn btn-sm" onClick={() => download(`${name}-matches.csv`, toCSV(matchesTable(t, resolved)), 'text/csv')}>
              Matches CSV
            </button>
            <button className="btn btn-sm" onClick={() => download(`${name}-standings.csv`, toCSV(standingsTable(t, resolved)), 'text/csv')}>
              Standings CSV
            </button>
            <button className="btn btn-sm" onClick={() => download(`${name}-results.csv`, toCSV(placementsTable(t, resolved)), 'text/csv')}>
              Final results CSV
            </button>
            <button className="btn btn-sm" onClick={() => download(`${name}-teams.csv`, toCSV(teamsTable(t)), 'text/csv')}>
              Teams CSV
            </button>
            <button
              className="btn btn-sm"
              onClick={() => download(`${name}-backup.json`, JSON.stringify(t, null, 1), 'application/json')}
            >
              Full backup (.json)
            </button>
          </div>
          {sync?.role === 'admin' && (
            <div className="row" style={{ marginTop: 10 }}>
              <button className="btn btn-sm btn-primary" onClick={exportTables}>
                Write results into the Google Sheet
              </button>
            </div>
          )}
        </>
      )}
      {isAdmin && (
        <>
          <div className="small bold muted" style={{ margin: '14px 0 6px' }}>
            Restore
          </div>
          <label className="field">
            Load a backup (.json)
            <input
              className="input"
              type="file"
              accept="application/json,.json"
              onChange={async (e) => {
                const file = e.target.files?.[0];
                if (!file) return;
                try {
                  const data = JSON.parse(await file.text()) as Tournament;
                  if (!data.matches || !data.divisions || !data.teams) throw new Error('Not a tournament backup');
                  if (t && !window.confirm('Replace the current tournament with this backup?')) return;
                  replace({ ...data, id: data.id ?? uid('tour') });
                  setMsg('Backup loaded.');
                  navigate('/');
                } catch (err) {
                  setMsg(`Couldn't load that file: ${(err as Error).message}`);
                }
              }}
            />
          </label>
        </>
      )}
      {t && isAdmin && (
        <div className="row" style={{ marginTop: 14 }}>
          <button
            className="btn btn-sm btn-danger"
            onClick={() => {
              if (!window.confirm(`Delete “${t.name}”${sync ? ' for everyone connected' : ''}? Download a backup first if you might need it.`)) return;
              replace(null);
              navigate('/');
            }}
          >
            Delete tournament
          </button>
        </div>
      )}
      {msg && (
        <div className="alert small" style={{ marginTop: 12 }}>
          {msg}
        </div>
      )}
    </div>
  );
}
