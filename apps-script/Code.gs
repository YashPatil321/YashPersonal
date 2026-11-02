/** @OnlyCurrentDoc  (limits permissions to this one spreadsheet) */

/**
 * Pickleball Tournament — Google Apps Script backend
 * ===================================================
 * Paste this into the Apps Script editor of the Google Sheet that collects your
 * Google Form responses (Extensions → Apps Script), set the passcodes below,
 * then Deploy → New deployment → Web app:
 *     Execute as: Me
 *     Who has access: Anyone
 * Copy the web app URL (ends in /exec) into the website's Settings → Live sync.
 *
 * What it does
 *   - Serves your form responses to the website (no need to publish the sheet).
 *     Only someone with the ADMIN passcode can read them.
 *   - Stores the tournament (teams, schedule, scores) in a hidden tab so every
 *     phone/laptop sees the same live scores.
 *   - Competitors can READ the tournament (without emails/phone numbers).
 *     Only passcode holders can change anything:
 *       admin  – build the tournament, edit teams, enter scores
 *       scorer – enter scores / call matches to courts only
 *   - Optionally writes readable "Results" / "Standings" tabs back to the sheet.
 */

// ---- Settings ---------------------------------------------------------------

/** Full control: build the tournament, edit teams, enter scores. CHANGE THIS. */
var ADMIN_PASSCODE = 'change-me';

/** Optional: court volunteers who can only enter scores / call matches. Leave '' to disable. */
var SCORER_PASSCODE = '';

/** Tab with the form responses. Leave '' to use the first tab. */
var REGISTRATION_SHEET = '';

// -----------------------------------------------------------------------------

var STATE_SHEET = '_tournament_state';
var CHUNK_SIZE = 40000; // a single cell holds max 50,000 characters
var CACHE_KEY = 'tournament_state_v1';
var RESULT_FIELDS = ['status', 'games', 'court', 'forfeit', 'resultTeams', 'serve', 'calledAt', 'finishedAt', 'updatedAt'];

function doGet(e) {
  var p = (e && e.parameter) || {};
  var action = p.action || 'state';
  try {
    if (action === 'ping') {
      return json({
        ok: true,
        spreadsheet: SpreadsheetApp.getActive().getName(),
        version: getVersion(),
        scorerEnabled: !!getScorerPasscode(),
      });
    }
    if (action === 'version') return json({ ok: true, version: getVersion() });
    if (action === 'state') {
      var s = readState();
      return json({ ok: true, version: s.version, state: publicState(s.state) });
    }
    if (action === 'registrations') {
      return json({ ok: false, error: 'Registrations need the admin passcode', auth: false });
    }
    return json({ ok: false, error: 'Unknown action: ' + action });
  } catch (err) {
    return json({ ok: false, error: String(err && err.message ? err.message : err) });
  }
}

function doPost(e) {
  var body;
  try {
    body = JSON.parse(e.postData.contents);
  } catch (err) {
    return json({ ok: false, error: 'Invalid JSON body' });
  }
  if (getAdminPasscode() === 'change-me' && body.passcode === 'change-me') {
    return json({ ok: false, error: 'Set ADMIN_PASSCODE at the top of Code.gs (it can\'t stay "change-me") and redeploy.', auth: false });
  }
  var role = roleFor(body.passcode);
  if (!role) return json({ ok: false, error: 'Wrong passcode', auth: false });
  if (body.action === 'verify') return json({ ok: true, role: role });
  if (body.action === 'state') {
    var st = readState();
    return json({ ok: true, version: st.version, state: role === 'admin' ? st.state : publicState(st.state) });
  }
  if (body.action === 'registrations') {
    if (role !== 'admin') return json({ ok: false, error: 'Admin passcode required', auth: false });
    return json({ ok: true, rows: registrationRows(body.sheet) });
  }

  var lock = LockService.getScriptLock();
  if (!lock.tryLock(25000)) return json({ ok: false, error: 'Server busy, try again' });
  try {
    var current = readState();
    var state = current.state;

    if (body.action === 'saveState') {
      if (role !== 'admin') return json({ ok: false, error: 'Admin passcode required', auth: false });
      state = mergeState(state, body.state);
    } else if (body.action === 'patchMatches') {
      if (!state) return json({ ok: false, error: 'No tournament has been published yet' });
      (body.matches || []).forEach(function (incoming) {
        var existing = state.matches[incoming.id];
        if (!existing) return;
        if ((existing.updatedAt || 0) > (incoming.updatedAt || 0)) return; // newer result already stored
        if (role === 'admin') {
          state.matches[incoming.id] = incoming;
        } else {
          RESULT_FIELDS.forEach(function (f) {
            if (incoming.hasOwnProperty(f)) existing[f] = incoming[f];
            else delete existing[f];
          });
        }
      });
      state.updatedAt = Date.now();
    } else if (body.action === 'writeTables') {
      if (role !== 'admin') return json({ ok: false, error: 'Admin passcode required', auth: false });
      writeTables(body.tables || {});
      return json({ ok: true, version: current.version });
    } else if (body.action === 'clearState') {
      if (role !== 'admin') return json({ ok: false, error: 'Admin passcode required', auth: false });
      state = null;
    } else {
      return json({ ok: false, error: 'Unknown action: ' + body.action });
    }

    var version = writeState(state, current.version + 1);
    return json({ ok: true, version: version, state: role === 'admin' ? state : publicState(state) });
  } catch (err) {
    return json({ ok: false, error: String(err && err.message ? err.message : err) });
  } finally {
    lock.releaseLock();
  }
}

// ---- helpers ----------------------------------------------------------------

function json(obj) {
  return ContentService.createTextOutput(JSON.stringify(obj)).setMimeType(ContentService.MimeType.JSON);
}

/** What competitors see: everything except players' contact details. */
function publicState(state) {
  if (!state || !state.players) return state;
  var copy = JSON.parse(JSON.stringify(state));
  Object.keys(copy.players).forEach(function (id) {
    delete copy.players[id].email;
    delete copy.players[id].phone;
  });
  return copy;
}

function props() {
  return PropertiesService.getScriptProperties();
}

function getAdminPasscode() {
  return props().getProperty('ADMIN_PASSCODE') || ADMIN_PASSCODE;
}

function getScorerPasscode() {
  return props().getProperty('SCORER_PASSCODE') || SCORER_PASSCODE;
}

function roleFor(passcode) {
  if (!passcode) return null;
  if (passcode === getAdminPasscode() && getAdminPasscode() !== 'change-me') return 'admin';
  var scorer = getScorerPasscode();
  if (scorer && passcode === scorer) return 'scorer';
  return null;
}

function getVersion() {
  return Number(props().getProperty('STATE_VERSION') || 0);
}

function registrationRows(sheetName) {
  var ss = SpreadsheetApp.getActive();
  var sheet = sheetName ? ss.getSheetByName(sheetName) : REGISTRATION_SHEET ? ss.getSheetByName(REGISTRATION_SHEET) : null;
  if (!sheet) {
    sheet = ss.getSheets().filter(function (s) {
      return s.getName() !== STATE_SHEET && s.getName().indexOf('TM ') !== 0;
    })[0];
  }
  if (!sheet) throw new Error('No registration sheet found');
  return sheet.getDataRange().getDisplayValues();
}

function stateSheet() {
  var ss = SpreadsheetApp.getActive();
  var sheet = ss.getSheetByName(STATE_SHEET);
  if (!sheet) {
    sheet = ss.insertSheet(STATE_SHEET);
    sheet.hideSheet();
  }
  return sheet;
}

function readState() {
  var version = getVersion();
  var cache = CacheService.getScriptCache();
  var cached = cache.get(CACHE_KEY + ':' + version);
  if (cached) return { version: version, state: JSON.parse(cached) };

  var sheet = stateSheet();
  var last = sheet.getLastRow();
  var text = '';
  if (last > 0) {
    text = sheet
      .getRange(1, 1, last, 1)
      .getValues()
      .map(function (r) {
        var v = String(r[0]);
        return v.charAt(0) === '~' ? v.substr(1) : v; // '~' stops Sheets treating chunks as formulas
      })
      .join('');
  }
  var state = text ? JSON.parse(text) : null;
  if (text && text.length < 90000) cache.put(CACHE_KEY + ':' + version, text, 21600);
  return { version: version, state: state };
}

function writeState(state, version) {
  var sheet = stateSheet();
  var text = state ? JSON.stringify(state) : '';
  var chunks = [];
  for (var i = 0; i < text.length; i += CHUNK_SIZE) chunks.push(['~' + text.substr(i, CHUNK_SIZE)]);
  sheet.clearContents();
  if (chunks.length) {
    var range = sheet.getRange(1, 1, chunks.length, 1);
    range.setNumberFormat('@');
    range.setValues(chunks);
  }
  props().setProperty('STATE_VERSION', String(version));
  if (text && text.length < 90000) CacheService.getScriptCache().put(CACHE_KEY + ':' + version, text, 21600);
  return version;
}

/** Admin saves replace the structure, but never overwrite a newer score from a court device. */
function mergeState(current, incoming) {
  if (!incoming) return incoming;
  if (!current || !current.matches || current.id !== incoming.id) return incoming;
  Object.keys(incoming.matches || {}).forEach(function (id) {
    var mine = current.matches[id];
    var theirs = incoming.matches[id];
    if (mine && (mine.updatedAt || 0) > (theirs.updatedAt || 0)) {
      RESULT_FIELDS.forEach(function (f) {
        if (mine.hasOwnProperty(f)) theirs[f] = mine[f];
        else delete theirs[f];
      });
    }
  });
  return incoming;
}

/** Write human-readable tables (sent by the website) to tabs prefixed "TM ". */
function writeTables(tables) {
  var ss = SpreadsheetApp.getActive();
  Object.keys(tables).forEach(function (name) {
    var rows = tables[name];
    var tabName = 'TM ' + name;
    var sheet = ss.getSheetByName(tabName) || ss.insertSheet(tabName);
    sheet.clearContents();
    if (!rows.length) return;
    var width = rows.reduce(function (w, r) {
      return Math.max(w, r.length);
    }, 0);
    var padded = rows.map(function (r) {
      var out = r.slice();
      while (out.length < width) out.push('');
      return out;
    });
    sheet.getRange(1, 1, padded.length, width).setValues(padded);
    sheet.getRange(1, 1, 1, width).setFontWeight('bold');
    sheet.setFrozenRows(1);
  });
}
