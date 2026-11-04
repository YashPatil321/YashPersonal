/**
 * The tournament's backend: a Supabase project with one public function, `pb`,
 * that takes sign-ups, checks the organizer/court passcodes and stores the draw.
 * The publishable key is meant to be public; everything private sits behind passcodes.
 */
export const SUPABASE_URL = 'https://kjxyojpjwgimspgupksv.supabase.co';
export const SUPABASE_KEY = 'sb_publishable_oDEIgYdzUZC243q88DIh3A_5KOlKIuB';
/** Where every visitor's site connects. VITE_LIVE_URL can point it somewhere else (e.g. an Apps Script). */
export const DEFAULT_LIVE_URL = import.meta.env.VITE_LIVE_URL?.trim() || SUPABASE_URL;
