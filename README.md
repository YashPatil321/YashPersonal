# Pickleball Tournament Manager

A website that turns your **Google Form sign-ups** into a complete pickleball tournament: teams, pools, brackets, a court schedule, live scoring, standings and final results.

- **Competitors** open one link (or scan a QR code) to see live scores, find their team, check when they play next, and follow standings and brackets. No login needed, and nothing they can change.
- **You (the organizer)** sign in with an admin passcode to build the draw, run the courts and enter or fix scores.
- **Court volunteers** (optional) get a separate *scorer* passcode. They can keep score and call matches, nothing else.

## What it does

| | |
|---|---|
| **Import from Google Forms / Sheets** | Auto-detects your form's questions (name, partner, email, skill/DUPR, division…). Matches partners who registered separately, adds partners who didn't, pairs players who need a partner (balanced, similar-skill or random), removes duplicate submissions, and handles "check all that apply" division questions. |
| **Formats (per division)** | Round robin (once or twice), pool play → playoffs, single elimination (optional 3rd-place match), double elimination (optional grand-final reset). Byes, snake-seeded pools and standard bracket seeding are handled for you. The first playoff round avoids rematches between teams from the same pool. |
| **Seeding** | By skill rating, random draw, or your own order. |
| **Scoring rules** | 1 game / best of 3 / best of 5, to 7–21 points, win by 1 or 2, optional point cap. Semis and finals can use different scoring. |
| **Court desk** | Calls the next match to each open court automatically, never double-books a team, and shows a queue with wait estimates. |
| **Live scorekeeper** | Phone-friendly tap scoring. Traditional side-out mode tracks the server and calls the score ("4-2-1") for you. Rally scoring and a simple +/− mode are also available, with undo. |
| **Standings** | Wins, then head-to-head, then point differential, then points scored. Pool qualifiers fill the bracket automatically. If an earlier score is corrected, everything downstream updates, and any later match that is now wrong is flagged. |
| **For players** | "Find my team" (with "#3 in line, ~20 min"), live courts, results, brackets, and a **TV mode** for a screen at the venue. |
| **Exports** | CSVs (matches, standings, final results, teams), a full JSON backup, and a one-click "write results into the Google Sheet". |

---

## 1. Make the Google Form

Any form works. These questions are detected automatically:

| Question | Type | Notes |
|---|---|---|
| Full name | Short answer | Or separate *First name* / *Last name* questions. |
| Email | Short answer | Or turn on "Collect email addresses". |
| Phone number | Short answer | Optional. Only the organizer ever sees it. |
| Skill level | Short answer or dropdown | "3.5", "3.0-3.5", "DUPR 4.12", "Beginner / Intermediate / Advanced" all work. Used for seeding and partner pairing. |
| Division | Multiple choice or checkboxes | e.g. *Intermediate (3.0-3.5)*, *Advanced (4.0+)*. With checkboxes, players can enter several divisions. |
| Partner's name | Short answer | "Leave blank if you need a partner." Answers like "need one", "n/a" or "TBD" are treated as no partner. |
| Partner's email | Short answer | Optional; makes partner matching exact. |

Then in the form go to **Responses → Link to Sheets** to create the response spreadsheet.

## 2. Put the website online

The site is a static app (Vite + React + TypeScript). Pick any host:

- **Vercel** (easiest): import this GitHub repo at vercel.com → *Add New Project*. It detects Vite on its own: build `npm run build`, output `dist`.
- **Netlify / Cloudflare Pages**: build command `npm run build`, publish directory `dist`.
- **Run it locally**: `npm install` then `npm run dev`.

## 3. Choose how you'll run it

### Option A: Live for everyone (recommended)

This is what lets competitors follow along on their own phones. It uses a free Google Apps Script that lives inside **your** response spreadsheet, so there are no servers or accounts to manage.

1. Open the response spreadsheet → **Extensions → Apps Script**.
2. Delete the sample code and paste in everything from [`apps-script/Code.gs`](apps-script/Code.gs).
3. At the top of that file, set your passcodes:
   ```js
   var ADMIN_PASSCODE = 'pick-something-long';   // you
   var SCORER_PASSCODE = 'court-volunteers';     // optional, '' to disable
   ```
4. Click **Deploy → New deployment**, choose type **Web app**, and set:
   - *Execute as*: **Me**
   - *Who has access*: **Anyone**

   Click **Deploy** and approve the permissions prompt (it only touches this spreadsheet).
5. Copy the **Web app URL** (it ends in `/exec`).
6. On the website: **Settings → Live sync** → paste the URL and your admin passcode → **Connect**.
7. Click **Create** and choose **Google Sheet link → Use the connected Google Sheet** to load the sign-ups. Your spreadsheet can stay private.
8. Share the link or QR code from **Settings → Share with players**.

**Optional, but nice:** in Vercel go to **Settings → Environment Variables** and add `VITE_LIVE_URL` = your web app URL, then redeploy. Now the plain website address opens straight into the live tournament for everyone, and you use **Organizer login** at the top to get your admin controls.

> If you edit `Code.gs` later, use **Deploy → Manage deployments → Edit → New version**. That keeps the same URL.

### Option B: One device only (zero setup)

Skip Apps Script. In the Create wizard, paste your spreadsheet link (Share → *Anyone with the link → Viewer*), upload a CSV, or paste rows. The tournament is saved in that browser. Open **TV mode** in a second window on a big screen and it updates as you enter scores. You can switch to Option A at any time with **Settings → Live sync → Connect & publish this device's tournament**.

## 4. Tournament day

1. **Home → Start tournament** sends the first matches to every court.
2. **Courts** shows what's on each court. When a score is saved, the next match is called to that court automatically (toggle *Auto-call*).
3. Score from the court with **Keep score** (on the volunteer's phone), or type the final score with **Enter final**.
4. Players use **Find my team** to see their queue position and estimated wait time.
5. Late changes: **Settings → Divisions & schedule** lets you add or remove a team and rebuild a division (best done before it starts). Forfeits are in each match's score dialog.
6. Afterwards: **Settings → Data** to download results or write them into the Google Sheet (as `TM …` tabs).

## Who can do what

| | Competitor | Scorer passcode | Admin passcode |
|---|:-:|:-:|:-:|
| See live courts, matches, standings, brackets, TV mode | ✅ | ✅ | ✅ |
| Find my team / queue position | ✅ | ✅ | ✅ |
| Keep score, enter results, call matches to courts | | ✅ | ✅ |
| Create the tournament, edit teams, divisions, courts, settings | | | ✅ |
| See players' emails and phone numbers | | | ✅ |
| Read the raw form responses | | | ✅ |

Passcodes are checked by your Apps Script, not just hidden in the website. The public feed has emails and phone numbers stripped out. If two devices save at nearly the same moment, the newer score always wins, and an admin save never overwrites a score that a court volunteer entered after it.

## Development

```bash
npm install
npm run dev        # local dev server
npm test           # engine, importer and Apps Script backend tests
npm run build      # typecheck + production build into dist/
```

```
src/lib/          tournament engine (no UI)
  registrations.ts  Google Form → players / teams / divisions
  generate.ts       round robin, pools, single & double elimination
  resolve.ts        derives brackets, standings, placements from results
  actions.ts        scoring, court queue, auto-call
  sync.ts           Apps Script client
src/pages/        Setup wizard, Overview, Courts, Matches, Standings/Brackets, Teams, Scorekeeper, TV, Settings
apps-script/      Code.gs (backend) + harness.mjs (runs Code.gs locally for tests)
```

The engine only stores structure plus raw results. Who advances, standings and placements are recomputed from scores every time, so correcting any score keeps the whole tournament consistent.
