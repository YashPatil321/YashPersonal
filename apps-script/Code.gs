/**
 * SACS Pickleball Tournament: Google Apps Script backend
 * ======================================================
 *
 * ONE-TIME SETUP (about 3 minutes, no coding)
 *   1. Open https://script.new while signed in to the Google account that should
 *      own the sign-up sheet (e.g. the SACS exec account).
 *   2. Delete what's in the editor, paste this whole file, and click Save.
 *   3. In the toolbar pick the function "setup" and click Run. Approve the
 *      permissions (it creates one Google Sheet in your Drive).
 *      The Execution log prints the sheet link and your passcodes.
 *   4. Deploy → New deployment → gear icon → Web app
 *        Execute as:      Me
 *        Who has access:  Anyone
 *      Click Deploy and copy the Web app URL (ends in /exec).
 *   5. Open the tournament site's Organizer page (…/#/admin), paste that URL and
 *      the admin passcode, and click Connect.
 *
 * Re-run "setup" any time to print the links and passcodes again (it never
 * creates a second sheet). To change a passcode: Project Settings → Script
 * properties → ADMIN_PASSCODE / SCORER_PASSCODE.
 *
 * What it does
 *   - Saves sign-ups from the website's Register tab into the "Registrations"
 *     tab of your sheet. Only the ADMIN passcode can read them back.
 *     Registration closes automatically once you publish the draw.
 *   - Stores the tournament (teams, schedule, scores) in a hidden tab so every
 *     phone/laptop/TV sees the same live scores.
 *   - Competitors can READ the tournament (without emails/phone numbers).
 *     Only passcode holders can change anything:
 *       admin  – build the tournament, edit teams, enter scores
 *       scorer – enter scores / call matches to courts only
 *   - Optionally writes readable "Results" / "Standings" tabs back to the sheet.
 */

// ---- Settings ---------------------------------------------------------------

/** Leave as 'change-me': "setup" generates a random admin passcode for you. */
var ADMIN_PASSCODE = 'change-me';

/** Leave '': "setup" generates a scorer passcode for court volunteers. */
var SCORER_PASSCODE = '';

/** Tab that collects sign-ups from the website's Register tab. */
var REGISTRATION_SHEET = 'Registrations';

/** Columns of the Registrations tab, in order (the website reads these titles). */
var REG_HEADERS = [
  'Timestamp',
  'Full name',
  'Email',
  'Phone number',
  'School',
  'Skill level',
  'Bracket',
  "Partner's full name",
  "Partner's email",
  "Partner's skill level",
  'Team name (optional)',
  'Anything else we should know?',
];
/** Matching keys sent by the website's form. */
var REG_FIELDS = ['name', 'email', 'phone', 'school', 'skill', 'bracket', 'partnerName', 'partnerEmail', 'partnerSkill', 'teamName', 'notes'];
var MAX_REGISTRATIONS = 1000;

/** Public tournament site, shown to people after they register. */
var SITE_URL = 'https://pickleball-tournament-jet.vercel.app';

var EVENT_NAME = 'SACS Pickleball Tournament';
var CHARITY = 'Akshaya Patra Foundation';

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
        spreadsheet: book().getName(),
        version: getVersion(),
        scorerEnabled: !!getScorerPasscode(),
        registrationOpen: registrationOpen(),
        registrations: registrationCount(),
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
  if (body.action === 'register') return json(register(body.entry || {}, body.website));

  if (getAdminPasscode() === 'change-me') {
    return json({ ok: false, error: 'No admin passcode yet: run "setup" in the Apps Script editor first.', auth: false });
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
  if (body.action === 'setRegistration') {
    if (role !== 'admin') return json({ ok: false, error: 'Admin passcode required', auth: false });
    props().setProperty('REG_OPEN', body.open ? 'true' : 'false');
    return json({ ok: true, registrationOpen: registrationOpen() });
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
  // Read from the cache first: PropertiesService has a daily read quota and
  // every phone polls this every few seconds on tournament day.
  var cache = CacheService.getScriptCache();
  var cached = cache.get('STATE_VERSION');
  if (cached !== null && cached !== undefined) return Number(cached);
  var v = Number(props().getProperty('STATE_VERSION') || 0);
  cache.put('STATE_VERSION', String(v), 21600);
  return v;
}

/** The spreadsheet holding responses + tournament state (bound sheet or the one "setup" created). */
function book() {
  var id = props().getProperty('SHEET_ID');
  if (id) return SpreadsheetApp.openById(id);
  var active = SpreadsheetApp.getActive();
  if (active) return active;
  throw new Error('Run "setup" in the Apps Script editor first.');
}

function registrationRows(sheetName) {
  var ss = book();
  var sheet = sheetName ? ss.getSheetByName(sheetName) : REGISTRATION_SHEET ? ss.getSheetByName(REGISTRATION_SHEET) : null;
  if (sheet && sheet.getLastRow() < 2 && !sheetName) {
    // Empty Registrations tab: fall back to a linked Google Form tab if there is one
    var linked = ss.getSheets().filter(function (s) {
      return typeof s.getFormUrl === 'function' && s.getFormUrl() && s.getLastRow() > 1;
    })[0];
    if (linked) sheet = linked;
  }
  var candidates = ss.getSheets().filter(function (s) {
    return s.getName() !== STATE_SHEET && s.getName().indexOf('TM ') !== 0;
  });
  if (!sheet) {
    // Prefer the tab linked to the Google Form
    sheet = candidates.filter(function (s) {
      return typeof s.getFormUrl === 'function' && s.getFormUrl();
    })[0];
  }
  if (!sheet) sheet = candidates[0];
  if (!sheet) throw new Error('No registration sheet found');
  return sheet.getDataRange().getDisplayValues();
}

function stateSheet() {
  var ss = book();
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
  CacheService.getScriptCache().put('STATE_VERSION', String(version), 21600);
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
  var ss = book();
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

// ---- Registration -------------------------------------------------------------

function registrationSheet() {
  var ss = book();
  var sheet = ss.getSheetByName(REGISTRATION_SHEET);
  if (!sheet) {
    sheet = ss.insertSheet(REGISTRATION_SHEET);
    sheet.getRange(1, 1, 1, REG_HEADERS.length).setValues([REG_HEADERS]);
    sheet.getRange(1, 1, 1, REG_HEADERS.length).setFontWeight('bold');
    sheet.setFrozenRows(1);
  }
  return sheet;
}

function registrationCount() {
  try {
    var sheet = book().getSheetByName(REGISTRATION_SHEET);
    return sheet ? Math.max(0, sheet.getLastRow() - 1) : 0;
  } catch (err) {
    return 0;
  }
}

/** Open unless the organizer closed it, and always closed once a draw is published. */
function registrationOpen() {
  if (props().getProperty('REG_OPEN') === 'false') return false;
  try {
    return !readState().state;
  } catch (err) {
    return true;
  }
}

function clean(value, max) {
  return String(value == null ? '' : value)
    .replace(/[\u0000-\u001f]/g, ' ')
    .replace(/^[=+\-@]+/, '') // never let a sign-up become a spreadsheet formula
    .trim()
    .slice(0, max);
}

/** Save one sign-up from the website's Register tab. Public: no passcode. */
function register(entry, honeypot) {
  if (honeypot) return { ok: true }; // bots fill the hidden field; pretend it worked
  if (!registrationOpen()) return { ok: false, error: 'Registration is closed.' };
  var values = {};
  REG_FIELDS.forEach(function (f) {
    values[f] = clean(entry[f], f === 'notes' ? 500 : 120);
  });
  if (!values.name) return { ok: false, error: 'Please enter your full name.' };
  var emailRe = /^[^\s@]+@[^\s@]+\.[^\s@]+$/;
  if (!emailRe.test(values.email)) return { ok: false, error: 'Please enter a valid email.' };
  if (values.partnerEmail && !emailRe.test(values.partnerEmail)) return { ok: false, error: "Please check your partner's email." };
  if (!values.skill) return { ok: false, error: 'Please choose your skill level.' };

  var lock = LockService.getScriptLock();
  if (!lock.tryLock(20000)) return { ok: false, error: 'Busy, please try again.' };
  try {
    var sheet = registrationSheet();
    if (sheet.getLastRow() - 1 >= MAX_REGISTRATIONS) return { ok: false, error: 'Registration is full.' };
    var row = [new Date().toLocaleString('en-US')].concat(
      REG_FIELDS.map(function (f) {
        return values[f];
      })
    );
    sheet.appendRow(row);
    return { ok: true, count: sheet.getLastRow() - 1 };
  } finally {
    lock.releaseLock();
  }
}

// ---- One-time setup -----------------------------------------------------------

/**
 * Run this once from the editor. Creates the sign-up sheet (unless it already
 * exists) and passcodes, then logs everything you need.
 */
function setup() {
  var p = props();
  if (!p.getProperty('ADMIN_PASSCODE') && ADMIN_PASSCODE === 'change-me') {
    p.setProperty('ADMIN_PASSCODE', 'sacs-' + randomCode(6));
  }
  if (!p.getProperty('SCORER_PASSCODE') && !SCORER_PASSCODE) {
    p.setProperty('SCORER_PASSCODE', 'court-' + randomCode(4));
  }

  // Spreadsheet: one "setup" made before, the sheet this script is attached to, or a new one.
  var ss = null;
  if (p.getProperty('SHEET_ID')) ss = SpreadsheetApp.openById(p.getProperty('SHEET_ID'));
  if (!ss) ss = SpreadsheetApp.getActive();
  var created = false;
  if (!ss) {
    ss = SpreadsheetApp.create(EVENT_NAME + ' (Sign-ups)');
    created = true;
  }
  p.setProperty('SHEET_ID', ss.getId());
  registrationSheet();
  if (created) {
    // Drop the empty default tab so "Registrations" is the obvious one.
    ss.getSheets().forEach(function (sh) {
      if (ss.getSheets().length > 1 && sh.getName() !== REGISTRATION_SHEET && sh.getLastRow() === 0) ss.deleteSheet(sh);
    });
  }

  var lines = [
    '',
    '=== ' + EVENT_NAME + ' is set up ===',
    'Sign-ups spreadsheet:                   ' + ss.getUrl(),
    'Players register on the website:        ' + SITE_URL + '/#/register',
    '',
    'ADMIN passcode (keep private):          ' + getAdminPasscode(),
    'SCORER passcode (court volunteers):     ' + getScorerPasscode(),
    '',
    'Next: Deploy → New deployment → Web app (Execute as: Me, Who has access: Anyone).',
    'Then open ' + SITE_URL + '/#/admin and paste the Web app URL + admin passcode.',
  ];
  Logger.log(lines.join('\n'));
  return lines.join('\n');
}

function randomCode(length) {
  return Utilities.getUuid().replace(/-/g, '').slice(0, length);
}
