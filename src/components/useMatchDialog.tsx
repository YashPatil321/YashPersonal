import { useCallback, useState } from 'react';
import type { ResolvedMatch } from '../lib/resolve';
import { ScoreDialog } from './ScoreDialog';

export function useMatchDialog() {
  const [id, setId] = useState<string | null>(null);
  const open = useCallback((r: ResolvedMatch) => setId(r.m.id), []);
  const close = useCallback(() => setId(null), []);
  const dialog = id ? <ScoreDialog key={id} matchId={id} onClose={close} /> : null;
  return { open, dialog };
}
