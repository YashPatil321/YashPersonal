import { useEffect, useState } from 'react';
import { remote } from '../lib/sync';
import { useStore } from './store';

export interface EventInfo {
  spreadsheet: string;
  formUrl?: string;
  scorerEnabled: boolean;
}

/** Public details from the connected Apps Script (sign-up form link, sheet name). */
export function useEventInfo(): EventInfo | null {
  const { sync } = useStore();
  const url = sync?.url;
  const [info, setInfo] = useState<EventInfo | null>(null);
  useEffect(() => {
    if (!url) {
      setInfo(null);
      return;
    }
    let alive = true;
    remote
      .ping(url)
      .then((d) => alive && setInfo({ spreadsheet: d.spreadsheet, formUrl: d.formUrl || undefined, scorerEnabled: d.scorerEnabled }))
      .catch(() => alive && setInfo(null));
    return () => {
      alive = false;
    };
  }, [url]);
  return info;
}
