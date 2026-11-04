import { jsx as _jsx } from "react/jsx-runtime";
import { createContext, useCallback, useContext, useEffect, useMemo, useRef, useState } from 'react';
import { resolveTournament } from '../lib/resolve';
import { diffTournament, remote } from '../lib/sync';
import { DEFAULT_LIVE_URL } from '../config';
const LS_TOURNAMENT = 'pbt.tournament.v1';
const LS_SYNC = 'pbt.sync.v1';
const POLL_MS = 8000;
const StoreContext = createContext(null);
export function load(key) {
    try {
        const raw = localStorage.getItem(key);
        return raw ? JSON.parse(raw) : null;
    }
    catch {
        return null;
    }
}
export function save(key, value) {
    try {
        if (value === null || value === undefined)
            localStorage.removeItem(key);
        else
            localStorage.setItem(key, JSON.stringify(value));
    }
    catch {
        /* storage full / private mode — ignore */
    }
}
function initialSync() {
    const stored = load(LS_SYNC);
    const live = new URLSearchParams(window.location.search).get('live') || DEFAULT_LIVE_URL;
    if (live) {
        if (stored?.url === live)
            return stored;
        const viewer = { url: live, role: 'viewer' };
        save(LS_SYNC, viewer);
        return viewer;
    }
    return stored;
}
export function StoreProvider({ children }) {
    const [t, setT] = useState(() => load(LS_TOURNAMENT));
    const [sync, setSync] = useState(initialSync);
    const [syncState, setSyncState] = useState({ status: sync ? 'connecting' : 'off' });
    const tRef = useRef(t);
    const syncRef = useRef(sync);
    syncRef.current = sync;
    const engine = useRef({
        inFlight: false,
        pendingFull: false,
        pendingIds: new Set(),
        edits: 0,
        version: -1,
        retry: 0,
    });
    const commit = useCallback((next) => {
        tRef.current = next;
        setT(next);
        save(LS_TOURNAMENT, next);
    }, []);
    const hasPending = () => engine.current.pendingFull || engine.current.pendingIds.size > 0;
    const push = useCallback(async () => {
        const e = engine.current;
        const cfg = syncRef.current;
        if (!cfg || cfg.role === 'viewer' || !cfg.passcode)
            return;
        if (e.inFlight || !hasPending())
            return;
        e.inFlight = true;
        const full = e.pendingFull;
        const ids = [...e.pendingIds];
        e.pendingFull = false;
        e.pendingIds.clear();
        const startEdits = e.edits;
        const snapshot = tRef.current;
        setSyncState((s) => ({ ...s, status: 'saving' }));
        try {
            const res = full || !snapshot
                ? await remote.saveState(cfg.url, cfg.passcode, snapshot)
                : await remote.patchMatches(cfg.url, cfg.passcode, ids.map((id) => snapshot.matches[id]).filter(Boolean));
            e.version = res.version;
            if (e.edits === startEdits && !hasPending())
                commit(res.state);
            setSyncState({ status: 'synced', lastSync: Date.now() });
        }
        catch (err) {
            e.pendingFull = e.pendingFull || full;
            ids.forEach((id) => e.pendingIds.add(id));
            const error = err;
            if (error.auth) {
                setSyncState({ status: 'error', message: 'The passcode was rejected — changes are only saved on this device.' });
            }
            else {
                setSyncState({ status: 'offline', message: `Couldn't reach the Google Sheet (${error.message}). Retrying…` });
                if (e.retry)
                    clearTimeout(e.retry);
                e.retry = setTimeout(() => void push(), 5000);
            }
            e.inFlight = false;
            return;
        }
        e.inFlight = false;
        if (hasPending())
            void push();
    }, [commit]);
    const pull = useCallback(async () => {
        const cfg = syncRef.current;
        if (!cfg)
            return;
        const e = engine.current;
        if (e.inFlight || hasPending())
            return;
        try {
            const v = await remote.version(cfg.url);
            if (v !== e.version) {
                const rs = await remote.state(cfg.url, cfg.role === 'admin' ? cfg.passcode : undefined);
                if (!e.inFlight && !hasPending()) {
                    e.version = rs.version;
                    commit(rs.state);
                }
            }
            setSyncState((s) => (s.status === 'error' ? s : { status: 'synced', lastSync: Date.now() }));
        }
        catch (err) {
            setSyncState({ status: 'offline', message: `Couldn't reach the Google Sheet (${err.message}).` });
        }
    }, [commit]);
    // Polling for live updates
    useEffect(() => {
        if (!sync)
            return;
        void pull();
        const id = setInterval(() => void pull(), POLL_MS);
        const onVisible = () => document.visibilityState === 'visible' && void pull();
        document.addEventListener('visibilitychange', onVisible);
        return () => {
            clearInterval(id);
            document.removeEventListener('visibilitychange', onVisible);
        };
    }, [sync, pull]);
    // Without live sync, keep other tabs on this device (e.g. a TV window) in step.
    useEffect(() => {
        const onStorage = (ev) => {
            if (ev.key !== LS_TOURNAMENT || syncRef.current)
                return;
            const next = ev.newValue ? JSON.parse(ev.newValue) : null;
            tRef.current = next;
            setT(next);
        };
        window.addEventListener('storage', onStorage);
        return () => window.removeEventListener('storage', onStorage);
    }, []);
    const queue = useCallback((prev, next) => {
        const cfg = syncRef.current;
        if (!cfg || cfg.role === 'viewer')
            return;
        const e = engine.current;
        e.edits++;
        const d = diffTournament(prev, next);
        if (d.full)
            e.pendingFull = true;
        else
            d.matchIds.forEach((id) => e.pendingIds.add(id));
        void push();
    }, [push]);
    const update = useCallback((fn) => {
        const prev = tRef.current;
        if (!prev)
            return;
        const next = fn(prev);
        if (next === prev)
            return;
        commit(next);
        queue(prev, next);
    }, [commit, queue]);
    const replace = useCallback((next) => {
        commit(next);
        const cfg = syncRef.current;
        if (cfg && cfg.role === 'admin') {
            engine.current.edits++;
            engine.current.pendingFull = true;
            void push();
        }
    }, [commit, push]);
    const connect = useCallback(async (cfg, opts = {}) => {
        const e = engine.current;
        e.pendingFull = false;
        e.pendingIds.clear();
        e.version = -1;
        if (!cfg) {
            save(LS_SYNC, null);
            syncRef.current = null;
            setSync(null);
            setSyncState({ status: 'off' });
            return 'Live sync turned off. This device keeps its own copy.';
        }
        const previous = syncRef.current;
        setSyncState({ status: 'connecting' });
        let info;
        let role = cfg.role;
        try {
            info = await remote.ping(cfg.url);
            if (cfg.passcode)
                role = await remote.verify(cfg.url, cfg.passcode);
        }
        catch (err) {
            e.version = -1;
            setSyncState(previous ? { status: 'synced', lastSync: Date.now() } : { status: 'off' });
            throw err;
        }
        const final = { ...cfg, role };
        save(LS_SYNC, final);
        syncRef.current = final;
        setSync(final);
        const rs = await remote.state(cfg.url, role === 'admin' ? cfg.passcode : undefined);
        e.version = rs.version;
        let message = `Connected to “${info.spreadsheet}” as ${role}.`;
        const local = tRef.current;
        if ((opts.publishLocal || !rs.state) && local && role === 'admin') {
            e.pendingFull = true;
            e.edits++;
            await push();
            message += ' Published this device’s tournament to the sheet.';
        }
        else if (rs.state) {
            commit(rs.state);
            message += ' Loaded the tournament from the sheet.';
        }
        setSyncState({ status: 'synced', lastSync: Date.now() });
        return message;
    }, [commit, push]);
    const resolved = useMemo(() => (t ? resolveTournament(t) : null), [t]);
    const isAdmin = !sync || sync.role === 'admin';
    const canScore = isAdmin || sync?.role === 'scorer';
    const value = {
        t,
        resolved,
        sync,
        syncState,
        isAdmin,
        canScore,
        update,
        replace,
        connect,
        refresh: pull,
    };
    return _jsx(StoreContext.Provider, { value: value, children: children });
}
export function useStore() {
    const ctx = useContext(StoreContext);
    if (!ctx)
        throw new Error('useStore outside StoreProvider');
    return ctx;
}
/** Store helpers for pages that only render once a tournament exists. */
export function useTournament() {
    const s = useStore();
    if (!s.t || !s.resolved)
        throw new Error('No tournament');
    return { ...s, t: s.t, resolved: s.resolved };
}
