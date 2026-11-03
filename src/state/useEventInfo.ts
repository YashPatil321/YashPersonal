import { useCallback, useEffect, useState } from 'react';
import { remote } from '../lib/sync';
import { useStore } from './store';

export interface EventInfo {
  spreadsheet: string;
  scorerEnabled: boolean;
  registrationOpen: boolean;
  registrations: number;
}

/** Public details from the connected Apps Script: whether sign-ups are open and how many there are. */
export function useEventInfo(): { info: EventInfo | null; loading: boolean; refresh: () => void } {
  const { sync } = useStore();
  const url = sync?.url;
  const [info, setInfo] = useState<EventInfo | null>(null);
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
        if (!alive) return;
        setInfo({
          spreadsheet: d.spreadsheet,
          scorerEnabled: d.scorerEnabled,
          registrationOpen: d.registrationOpen !== false,
          registrations: d.registrations ?? 0,
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
