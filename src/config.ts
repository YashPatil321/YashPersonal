/**
 * Optional: bake your Apps Script web-app URL into the site so competitors who
 * open the plain website address land straight on the live, read-only
 * tournament. Set VITE_LIVE_URL in your hosting provider (e.g. Vercel →
 * Settings → Environment Variables) or in a local `.env` file.
 */
export const DEFAULT_LIVE_URL: string = (import.meta.env.VITE_LIVE_URL as string | undefined)?.trim() ?? '';
