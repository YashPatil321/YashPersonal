/**
 * Minimal RFC 4180 CSV parser. Handles quoted fields, escaped quotes ("")
 * and newlines inside quotes — all of which show up in Google Form exports.
 */
export function parseCSV(text) {
    const rows = [];
    let row = [];
    let field = '';
    let inQuotes = false;
    let i = 0;
    // Strip UTF-8 BOM
    if (text.charCodeAt(0) === 0xfeff)
        i = 1;
    for (; i < text.length; i++) {
        const c = text[i];
        if (inQuotes) {
            if (c === '"') {
                if (text[i + 1] === '"') {
                    field += '"';
                    i++;
                }
                else {
                    inQuotes = false;
                }
            }
            else {
                field += c;
            }
            continue;
        }
        if (c === '"') {
            inQuotes = true;
        }
        else if (c === ',') {
            row.push(field);
            field = '';
        }
        else if (c === '\n' || c === '\r') {
            if (c === '\r' && text[i + 1] === '\n')
                i++;
            row.push(field);
            rows.push(row);
            row = [];
            field = '';
        }
        else {
            field += c;
        }
    }
    if (field !== '' || row.length > 0) {
        row.push(field);
        rows.push(row);
    }
    // Drop fully empty rows
    return rows.filter((r) => r.some((cell) => cell.trim() !== ''));
}
function escapeCell(value) {
    const s = value == null ? '' : String(value);
    return /[",\n\r]/.test(s) ? `"${s.replace(/"/g, '""')}"` : s;
}
export function toCSV(rows) {
    return rows.map((r) => r.map(escapeCell).join(',')).join('\n');
}
