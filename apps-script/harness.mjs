// Runs apps-script/Code.gs locally with in-memory fakes of the Google services
// it uses, so the backend can be tested without deploying it.
import { readFileSync } from 'node:fs';
import { dirname, join } from 'node:path';
import { fileURLToPath } from 'node:url';
import vm from 'node:vm';

const here = dirname(fileURLToPath(import.meta.url));

class FakeRange {
  constructor(sheet, row, col, rows, cols) {
    Object.assign(this, { sheet, row, col, rows, cols });
  }
  getValues() {
    const out = [];
    for (let r = 0; r < this.rows; r++) {
      const line = [];
      for (let c = 0; c < this.cols; c++) line.push(this.sheet.cells[this.row - 1 + r]?.[this.col - 1 + c] ?? '');
      out.push(line);
    }
    return out;
  }
  getDisplayValues() {
    return this.getValues().map((r) => r.map((v) => String(v)));
  }
  setValues(values) {
    values.forEach((line, r) => {
      const idx = this.row - 1 + r;
      this.sheet.cells[idx] = this.sheet.cells[idx] ?? [];
      line.forEach((v, c) => {
        if (typeof v === 'string' && v.startsWith('=')) throw new Error('Formula parse error (string starting with =)');
        this.sheet.cells[idx][this.col - 1 + c] = v;
      });
    });
    return this;
  }
  setNumberFormat() {
    return this;
  }
  setFontWeight() {
    return this;
  }
}

class FakeSheet {
  constructor(name, cells = []) {
    this.name = name;
    this.cells = cells;
    this.hidden = false;
  }
  getName() {
    return this.name;
  }
  hideSheet() {
    this.hidden = true;
  }
  getLastRow() {
    return this.cells.length;
  }
  getRange(row, col, rows = 1, cols = 1) {
    return new FakeRange(this, row, col, rows, cols);
  }
  getDataRange() {
    const cols = Math.max(0, ...this.cells.map((r) => r.length));
    return new FakeRange(this, 1, 1, this.cells.length, cols);
  }
  clearContents() {
    this.cells = [];
  }
  setFrozenRows() {}
}

/**
 * @param {{ registrations?: string[][], adminPasscode?: string, scorerPasscode?: string }} opts
 */
export function createAppsScript(opts = {}) {
  const sheets = [new FakeSheet('Form Responses 1', opts.registrations ?? [['Timestamp', 'Name']])];
  const props = new Map();
  if (opts.adminPasscode) props.set('ADMIN_PASSCODE', opts.adminPasscode);
  if (opts.scorerPasscode) props.set('SCORER_PASSCODE', opts.scorerPasscode);
  const cache = new Map();

  const context = {
    SpreadsheetApp: {
      getActive: () => ({
        getName: () => 'Test Tournament Sign-ups',
        getSheets: () => sheets,
        getSheetByName: (n) => sheets.find((s) => s.name === n) ?? null,
        insertSheet: (n) => {
          const s = new FakeSheet(n);
          sheets.push(s);
          return s;
        },
      }),
    },
    PropertiesService: {
      getScriptProperties: () => ({
        getProperty: (k) => (props.has(k) ? props.get(k) : null),
        setProperty: (k, v) => props.set(k, String(v)),
      }),
    },
    CacheService: {
      getScriptCache: () => ({
        get: (k) => cache.get(k) ?? null,
        put: (k, v) => cache.set(k, v),
      }),
    },
    LockService: { getScriptLock: () => ({ tryLock: () => true, waitLock: () => {}, releaseLock: () => {} }) },
    ContentService: {
      MimeType: { JSON: 'application/json' },
      createTextOutput: (text) => ({ text, setMimeType() { return this; } }),
    },
    JSON,
    Date,
    String,
    Number,
    Object,
  };
  vm.createContext(context);
  vm.runInContext(readFileSync(join(here, 'Code.gs'), 'utf8'), context);

  return {
    sheets,
    get: (params) => JSON.parse(context.doGet({ parameter: params }).text),
    post: (body) => JSON.parse(context.doPost({ postData: { contents: JSON.stringify(body) } }).text),
    /** Handle a raw HTTP-ish request (used by the browser tests). */
    handle(method, url, body) {
      const u = new URL(url);
      if (method === 'GET') return context.doGet({ parameter: Object.fromEntries(u.searchParams) }).text;
      return context.doPost({ postData: { contents: body ?? '' } }).text;
    },
  };
}
