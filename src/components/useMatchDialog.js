import { jsx as _jsx } from "react/jsx-runtime";
import { useCallback, useState } from 'react';
import { ScoreDialog } from './ScoreDialog';
export function useMatchDialog() {
    const [id, setId] = useState(null);
    const open = useCallback((r) => setId(r.m.id), []);
    const close = useCallback(() => setId(null), []);
    const dialog = id ? _jsx(ScoreDialog, { matchId: id, onClose: close }, id) : null;
    return { open, dialog };
}
