async function getJSON(url, action) {
    const res = await fetch(`${url}?action=${action}&t=${Date.now()}`, { redirect: 'follow' });
    if (!res.ok)
        throw new Error(`HTTP ${res.status}`);
    const data = await res.json();
    if (!data.ok)
        throw new Error(data.error || 'Request failed');
    return data;
}
async function postJSON(url, body) {
    // text/plain keeps this a "simple" CORS request (Apps Script can't answer preflights)
    const res = await fetch(url, {
        method: 'POST',
        redirect: 'follow',
        headers: { 'Content-Type': 'text/plain;charset=utf-8' },
        body: JSON.stringify(body),
    });
    if (!res.ok)
        throw new Error(`HTTP ${res.status}`);
    const data = await res.json();
    if (!data.ok) {
        const err = new Error(data.error || 'Request failed');
        if (data.auth === false)
            err.auth = true;
        throw err;
    }
    return data;
}
export const remote = {
    ping: (url) => getJSON(url, 'ping'),
    /** Public: save one sign-up from the Register tab. `website` is a honeypot that must stay empty. */
    register: (url, entry, website = '') => postJSON(url, { action: 'register', entry, website }),
    /** Admin: add a sign-up by hand (walk-ups, phone sign-ups). Works while registration is closed. */
    addRegistration: (url, passcode, entry) => postJSON(url, { action: 'addRegistration', passcode, entry }),
    /** Admin: change sign-up number `row` (1 = first). `stamp` is its timestamp as loaded. */
    editRegistration: (url, passcode, row, stamp, entry) => postJSON(url, { action: 'editRegistration', passcode, row, stamp, entry }),
    deleteRegistration: (url, passcode, row, stamp) => postJSON(url, { action: 'deleteRegistration', passcode, row, stamp }),
    setRegistration: (url, passcode, open) => postJSON(url, { action: 'setRegistration', passcode, open }),
    setFundraising: (url, passcode, goal, extra) => postJSON(url, { action: 'setFundraising', passcode, goal, extra }),
    registrations: async (url, passcode) => (await postJSON(url, { action: 'registrations', passcode })).rows,
    version: async (url) => (await getJSON(url, 'version')).version,
    /** Public read (no contact details), or the full state when an admin passcode is given. */
    state: async (url, passcode) => {
        const d = passcode ? await postJSON(url, { action: 'state', passcode }) : await getJSON(url, 'state');
        return { version: d.version, state: d.state };
    },
    verify: async (url, passcode) => (await postJSON(url, { action: 'verify', passcode })).role,
    saveState: (url, passcode, state) => postJSON(url, { action: state ? 'saveState' : 'clearState', passcode, state }),
    patchMatches: (url, passcode, matches) => postJSON(url, { action: 'patchMatches', passcode, matches }),
    writeTables: (url, passcode, tables) => postJSON(url, { action: 'writeTables', passcode, tables }),
};
/**
 * Work out what changed between two tournament snapshots.
 * Score-only changes are sent as small match patches; anything else
 * (teams, divisions, settings) is sent as a full save.
 */
export function diffTournament(prev, next) {
    if (!prev || !next || prev.id !== next.id)
        return { full: true, matchIds: [] };
    const keys = new Set([...Object.keys(prev), ...Object.keys(next)]);
    for (const k of keys) {
        if (k === 'matches' || k === 'updatedAt')
            continue;
        if (prev[k] !== next[k])
            return { full: true, matchIds: [] };
    }
    const prevIds = Object.keys(prev.matches);
    const nextIds = Object.keys(next.matches);
    if (prevIds.length !== nextIds.length || nextIds.some((id) => !prev.matches[id]))
        return { full: true, matchIds: [] };
    return { full: false, matchIds: nextIds.filter((id) => prev.matches[id] !== next.matches[id]) };
}
