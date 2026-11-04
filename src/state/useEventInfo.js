import { useCallback, useEffect, useState } from 'react';
import { remote } from '../lib/sync';
import { useStore } from './store';
/** Public details from the connected Apps Script: whether sign-ups are open and how many there are. */
export function useEventInfo() {
    const { sync } = useStore();
    const url = sync?.url;
    const [info, setInfo] = useState(null);
    const [loading, setLoading] = useState(!!url);
    const [tick, setTick] = useState(0);
    useEffect(() => {
        if (!url) {
            setInfo(null);
            setLoading(false);
            return;
        }
        let alive = true;
        setLoading(true);
        remote
            .ping(url)
            .then((d) => {
            if (!alive)
                return;
            setInfo({
                spreadsheet: d.spreadsheet,
                scorerEnabled: d.scorerEnabled,
                registrationOpen: d.registrationOpen !== false,
                registrations: d.registrations ?? 0,
                fundraising: d.fundraising ?? { donations: 0, donors: 0, players: 0, goal: 0, extra: 0 },
                waiting: d.waiting ?? [],
            });
        })
            .catch(() => alive && setInfo(null))
            .finally(() => alive && setLoading(false));
        return () => {
            alive = false;
        };
    }, [url, tick]);
    const refresh = useCallback(() => setTick((n) => n + 1), []);
    return { info, loading, refresh };
}
