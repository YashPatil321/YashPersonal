/**
 * SACS Pickleball Tournament: Google Apps Script backend + sign-up form builder
 * ===========================================================================
 *
 * ONE-TIME SETUP (about 3 minutes, no coding)
 *   1. Open https://script.new while signed in to the Google account that should
 *      own the form (e.g. the SACS exec account).
 *   2. Delete what's in the editor, paste this whole file, and click Save.
 *   3. In the toolbar pick the function "setup" and click Run. Approve the
 *      permissions (it creates one Google Form and one Google Sheet).
 *      The Execution log prints the sign-up form link and your passcodes.
 *   4. Deploy → New deployment → gear icon → Web app
 *        Execute as:      Me
 *        Who has access:  Anyone
 *      Click Deploy and copy the Web app URL (ends in /exec).
 *   5. Open the tournament site's Organizer page (…/#/admin), paste that URL and
 *      the admin passcode, and click Connect.
 *
 * Re-run "setup" any time to print the links and passcodes again (it never
 * creates a second form). To change a passcode: Project Settings → Script
 * properties → ADMIN_PASSCODE / SCORER_PASSCODE.
 *
 * What it does
 *   - Builds the SACS registration Google Form and collects responses in a Sheet.
 *   - Serves those responses to the website. Only the ADMIN passcode can read them.
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

/** Tab with the form responses. Leave '' to find it automatically. */
var REGISTRATION_SHEET = '';

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
        formUrl: props().getProperty('FORM_URL') || '',
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

// ---- One-time setup -----------------------------------------------------------

/**
 * Run this once from the editor. Creates the SACS sign-up form + response sheet
 * (unless they already exist) and passcodes, then logs everything you need.
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

  // Form: one "setup" made before, the form already feeding this sheet, or a new one.
  var form = null;
  if (p.getProperty('FORM_ID')) form = FormApp.openById(p.getProperty('FORM_ID'));
  if (!form && ss.getFormUrl()) form = FormApp.openByUrl(ss.getFormUrl());
  if (!form) {
    form = buildSignupForm();
    form.setDestination(FormApp.DestinationType.SPREADSHEET, ss.getId());
    SpreadsheetApp.flush();
    if (created) {
      // Drop the empty default tab so the responses tab is the obvious one.
      ss.getSheets().forEach(function (sh) {
        if (ss.getSheets().length > 1 && sh.getLastRow() === 0 && !(sh.getFormUrl && sh.getFormUrl())) ss.deleteSheet(sh);
      });
    }
  }
  p.setProperty('FORM_ID', form.getId());
  p.setProperty('FORM_URL', form.getPublishedUrl());

  var lines = [
    '',
    '=== ' + EVENT_NAME + ' is set up ===',
    'Share this sign-up form with players:  ' + form.getPublishedUrl(),
    'Edit the form:                          ' + form.getEditUrl(),
    'Responses spreadsheet:                  ' + ss.getUrl(),
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

/** The SACS registration form. Question titles match what the website auto-detects. */
function buildSignupForm() {
  var skill = ['Beginner (new to pickleball)', 'Intermediate (2.5 - 3.5)', 'Advanced (4.0+)'];
  var form = FormApp.create(EVENT_NAME + ' Registration');
  form.setDescription(
    'Hosted by the South Asian Culture Show (SACS). A portion of every entry fee is donated to the ' +
      CHARITY +
      ', which serves free school lunches to children across India.\n\n' +
      'This is a doubles tournament. Signing up as a pair? Only one of you needs to fill this out: add your partner below. ' +
      "Need a partner? Leave the partner questions blank and we'll match you with someone."
  );
  form.setConfirmationMessage(
    "You're in! Thanks for playing for the " + CHARITY + '. Follow the draw and live scores at ' + SITE_URL
  );
  form.setProgressBar(false);

  form.addTextItem().setTitle('Full name').setRequired(true);
  form
    .addTextItem()
    .setTitle('Email')
    .setRequired(true)
    .setValidation(FormApp.createTextValidation().requireTextIsEmail().build());
  form.addTextItem().setTitle('Phone number').setHelpText('In case we need to reach you on tournament day.');
  form.addTextItem().setTitle('School');
  form.addMultipleChoiceItem().setTitle('Skill level').setChoiceValues(skill).setRequired(true);
  form
    .addMultipleChoiceItem()
    .setTitle('Bracket')
    .setHelpText("Pick the one that fits your team. We'll seed by skill within each bracket.")
    .setChoiceValues(['Competitive', 'Just for fun'])
    .setRequired(true);

  form
    .addSectionHeaderItem()
    .setTitle('Your partner')
    .setHelpText("Leave these blank if you need a partner and we'll pair you up.");
  form.addTextItem().setTitle("Partner's full name");
  form
    .addTextItem()
    .setTitle("Partner's email")
    .setValidation(FormApp.createTextValidation().requireTextIsEmail().build());
  form.addMultipleChoiceItem().setTitle("Partner's skill level").setChoiceValues(skill);
  form.addTextItem().setTitle('Team name (optional)');
  form.addParagraphTextItem().setTitle('Anything else we should know?');
  return form;
}

function randomCode(length) {
  return Utilities.getUuid().replace(/-/g, '').slice(0, length);
}
