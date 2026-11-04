import { parseCSV } from './csv';
/** Work out what kind of Google link the organizer pasted. */
export function classifyGoogleUrl(input) {
    const url = input.trim();
    if (/script\.google(usercontent)?\.com\/macros\//.test(url))
        return { kind: 'appsScript', url: url.split('?')[0] };
    if (/docs\.google\.com\/forms\//.test(url))
        return { kind: 'form', url };
    if (/docs\.google\.com\/spreadsheets\/d\/e\//.test(url)) {
        // Published-to-web link: make sure it returns CSV
        let u = url.replace(/\/pubhtml.*$/, '/pub').replace(/#.*$/, '');
        if (!/\/pub/.test(u))
            u = u.replace(/\/?$/, '/pub');
        const gid = url.match(/[#&?]gid=(\d+)/)?.[1];
        const base = u.split('?')[0];
        return { kind: 'published', url: `${base}?output=csv${gid ? `&gid=${gid}` : ''}&single=true` };
    }
    const m = url.match(/docs\.google\.com\/spreadsheets\/d\/([a-zA-Z0-9_-]+)/);
    if (m) {
        const gid = url.match(/[#&?]gid=(\d+)/)?.[1];
        return { kind: 'sheet', id: m[1], gid };
    }
    if (/output=csv|\.csv(\?|$)/.test(url))
        return { kind: 'published', url };
    return { kind: 'unknown', url };
}
async function fetchText(url) {
    const res = await fetch(url, { redirect: 'follow' });
    if (!res.ok)
        throw new Error(`HTTP ${res.status}`);
    const text = await res.text();
    if (/^\s*<(!doctype|html)/i.test(text)) {
        throw new Error('Google returned a web page instead of data (the sheet is probably not shared publicly).');
    }
    return text;
}
/** Fetch rows (including header) from any supported Google link. */
export async function fetchSheetRows(input, passcode) {
    const src = classifyGoogleUrl(input);
    switch (src.kind) {
        case 'form':
            throw new Error('That is a Google Form link. Open the form → Responses → "Link to Sheets", then paste the Google Sheet link here.');
        case 'appsScript': {
            if (!passcode)
                throw new Error('Enter your admin passcode to read registrations through Apps Script.');
            const res = await fetch(src.url, {
                method: 'POST',
                redirect: 'follow',
                headers: { 'Content-Type': 'text/plain;charset=utf-8' },
                body: JSON.stringify({ action: 'registrations', passcode }),
            });
            const data = await res.json();
            if (!data.ok)
                throw new Error(data.error || 'Apps Script returned an error');
            return data.rows;
        }
        case 'published':
        case 'unknown':
            return parseCSV(await fetchText(src.url));
        case 'sheet': {
            const gid = src.gid ? `&gid=${src.gid}` : '';
            const attempts = [
                `https://docs.google.com/spreadsheets/d/${src.id}/export?format=csv${gid}`,
                `https://docs.google.com/spreadsheets/d/${src.id}/gviz/tq?tqx=out:csv&headers=1${gid}`,
            ];
            let lastError;
            for (const url of attempts) {
                try {
                    return parseCSV(await fetchText(url));
                }
                catch (err) {
                    lastError = err;
                }
            }
            throw new Error(`Couldn't read that sheet (${String(lastError?.message ?? lastError)}). In Google Sheets use Share → "Anyone with the link: Viewer", or File → Share → Publish to web → CSV and paste that link.`);
        }
    }
}
