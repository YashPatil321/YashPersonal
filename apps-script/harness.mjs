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
  deleteRow(r) {
    this.cells.splice(r - 1, 1);
  }
  appendRow(row) {
    this.cells.push(row.map((v) => (typeof v === 'string' && v.startsWith('=') ? (() => { throw new Error('formula'); })() : v)));
  }
  setFrozenRows() {}
}

class FakeSpreadsheet {
  constructor(id, name, sheets) {
    this.id = id;
    this.name = name;
    this.sheets = sheets;
    this.formUrl = null;
  }
  getId() {
    return this.id;
  }
  getName() {
    return this.name;
  }
  getUrl() {
    return `https://docs.google.com/spreadsheets/d/${this.id}/edit`;
  }
  getFormUrl() {
    return this.formUrl;
  }
  getSheets() {
    return this.sheets.slice();
  }
  getSheetByName(n) {
    return this.sheets.find((s) => s.name === n) ?? null;
  }
  insertSheet(n) {
    const s = new FakeSheet(n);
    this.sheets.push(s);
    return s;
  }
  deleteSheet(sheet) {
    this.sheets = this.sheets.filter((s) => s !== sheet);
  }
}

class FakeItem {
  constructor(form, type) {
    this.form = form;
    this.type = type;
    this.title = '';
    this.required = false;
    this.choices = [];
  }
  setTitle(t) {
    this.title = t;
    return this;
  }
  setRequired(r) {
    this.required = r;
    return this;
  }
  setHelpText() {
    return this;
  }
  setChoiceValues(c) {
    this.choices = c;
    return this;
  }
  setValidation() {
    return this;
  }
}

class FakeForm {
  constructor(id, title) {
    this.id = id;
    this.title = title;
    this.items = [];
    this.destination = null;
  }
  getId() {
    return this.id;
  }
  getPublishedUrl() {
    return `https://docs.google.com/forms/d/e/${this.id}/viewform`;
  }
  getEditUrl() {
    return `https://docs.google.com/forms/d/${this.id}/edit`;
  }
  setDescription(d) {
    this.description = d;
    return this;
  }
  setConfirmationMessage(m) {
    this.confirmation = m;
    return this;
  }
  setProgressBar() {
    return this;
  }
  add(type) {
    const item = new FakeItem(this, type);
    this.items.push(item);
    return item;
  }
  addTextItem() {
    return this.add('text');
  }
  addParagraphTextItem() {
    return this.add('paragraph');
  }
  addMultipleChoiceItem() {
    return this.add('choice');
  }
  addSectionHeaderItem() {
    return this.add('section');
  }
}

/**
 * @param {{ registrations?: string[][], adminPasscode?: string, scorerPasscode?: string, standalone?: boolean }} opts
 *   standalone: simulate a project made at script.new (not attached to a sheet) — run setup() first.
 */
export function createAppsScript(opts = {}) {
  let nextId = 1;
  const books = new Map();
  const forms = new Map();
  const bound = opts.standalone
    ? null
    : new FakeSpreadsheet('bound', 'Test Tournament Sign-ups', [
        new FakeSheet('Form Responses 1', opts.registrations ?? [['Timestamp', 'Name']]),
      ]);
  if (bound) books.set(bound.id, bound);
  const props = new Map();
  if (opts.adminPasscode) props.set('ADMIN_PASSCODE', opts.adminPasscode);
  if (opts.scorerPasscode) props.set('SCORER_PASSCODE', opts.scorerPasscode);
  const cache = new Map();
  const logs = [];

  const context = {
    SpreadsheetApp: {
      getActive: () => bound,
      openById: (id) => {
        const b = books.get(id);
        if (!b) throw new Error('No spreadsheet ' + id);
        return b;
      },
      create: (name) => {
        const b = new FakeSpreadsheet(`sheet${nextId++}`, name, [new FakeSheet('Sheet1')]);
        books.set(b.id, b);
        return b;
      },
      flush: () => {},
    },
    FormApp: {
      DestinationType: { SPREADSHEET: 'SPREADSHEET' },
      create: (title) => {
        const f = new FakeForm(`form${nextId++}`, title);
        forms.set(f.id, f);
        return f;
      },
      openById: (id) => forms.get(id),
      openByUrl: (url) => [...forms.values()].find((f) => url.includes(f.id)),
      createTextValidation: () => ({ requireTextIsEmail() { return this; }, build() { return {}; } }),
    },
    Utilities: { getUuid: () => `${Math.random().toString(16).slice(2)}${Math.random().toString(16).slice(2)}`.slice(0, 32) },
    Logger: { log: (m) => logs.push(String(m)) },
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
    Math,
  };
  vm.createContext(context);
  vm.runInContext(readFileSync(join(here, 'Code.gs'), 'utf8'), context);

  // FakeForm.setDestination: link the form to a spreadsheet tab whose header row is the question titles.
  FakeForm.prototype.setDestination = function (_type, id) {
    const b = books.get(id);
    const headers = ['Timestamp', ...this.items.filter((i) => i.type !== 'section').map((i) => i.title)];
    const sheet = new FakeSheet('Form Responses 1', [headers]);
    sheet.getFormUrl = () => this.getPublishedUrl();
    b.sheets.push(sheet);
    b.formUrl = this.getPublishedUrl();
    this.destination = id;
    return this;
  };

  return {
    get sheets() {
      return (bound ?? [...books.values()][0])?.sheets ?? [];
    },
    books,
    forms,
    props,
    logs,
    setup: () => context.setup(),
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
