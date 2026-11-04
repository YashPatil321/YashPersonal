# SACS Pickleball Tournament

The website for the **SACS Pickleball Tournament**, hosted by the South Asian Culture Show. A portion of every entry fee is donated to the [Akshaya Patra Foundation](https://www.akshayapatrausa.org/), which serves free school lunches to children across India.

Organizers build the draw from the Google Form sign-ups. Competitors follow live courts, brackets and scores on their phones.

**Live site:** https://pickleball-tournament-jet.vercel.app

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

## Organizer setup (registration + live scores)

**Admin link:** https://pickleball-tournament-jet.vercel.app/#/admin (or **Organizer** in the footer)

Players sign up on the site's **Register** tab (https://pickleball-tournament-jet.vercel.app/#/register). There's no Google Form. Sign-ups are saved to a private Google Sheet in your account through a small Google Apps Script, which also powers live scores. Set it up once (about 3 minutes, no coding); the admin page walks you through it:

1. **Copy the setup script** from the admin page (it's [`apps-script/Code.gs`](apps-script/Code.gs)) and open [script.new](https://script.new), signed in to the Google account that should own the sign-ups sheet.
2. Paste it over everything, **Save**, choose **setup** in the function menu and press **Run**. Allow access. The **Execution log** prints the sign-ups sheet link, your **admin passcode** (`sacs-…`) and the **scorer passcode** (`court-…`) for court volunteers.
3. **Deploy → New deployment →** gear icon **→ Web app**. Execute as **Me**, Who has access **Anyone**. Copy the **Web app URL** (ends in `/exec`).
4. Back on the admin page, paste the URL and the admin passcode and press **Connect**.

The dashboard then gives you:
- the **registration** count, a list of who signed up, and an **open/close** switch. Registration also closes automatically when you publish the draw.
- a **registration link** to send players, a **players' link** (live, read-only) and an **admin link** that opens the dashboard on any device (passcode required)
- **Build the draw**, which turns the sign-ups into teams and brackets

**Make the plain site address work for everyone:** in Vercel go to **Settings → Environment Variables**, add `VITE_LIVE_URL` = your web app URL, then redeploy. Until then, share the links from the dashboard (they include `?live=…`).

### The Register tab

| Field | Notes |
|---|---|
| Full name, Email | Required |
| Phone number, School | Optional |
| Skill level | Beginner / Intermediate (2.5 - 3.5) / Advanced (4.0+), required. Used for seeding and pairing. |
| Division | Adults / Kids/Teens, required. Each becomes its own division in the draw. |
| Partner's full name, email | Optional. Leave blank to get paired with someone. Only one person per team needs to register. |
| Anything else we should know? | Optional |
| Payment method | Zelle / Venmo / Cash at check-in, required |
| Payment confirmation | Required checkbox: "I've sent the entry fee" (or "I'll bring cash to check-in") |

Set the entry fee and your Zelle/Venmo handles in [`src/brand.ts`](src/brand.ts) (`payment`). Entries land in the **Registrations** tab of the sheet, including how each person paid, so you can match them against your Zelle/Venmo history. You can edit or delete rows. The form has a spam honeypot, and values can't turn into spreadsheet formulas.

> If you edit `Code.gs` later, use **Deploy → Manage deployments → Edit → New version**. That keeps the same URL.

### Without the script (one device only)

The admin page's setup screen also has a link to build a draw on just this device, from a CSV or a shared sheet link. Nobody else will see it. TV mode in a second window still works.

## Hosting

The site is a static app (Vite + React + TypeScript), deployed to the Vercel project **`pickleball-tournament`** and connected to this GitHub repo. Merging into `main` redeploys the live site automatically, and other branches get preview links. To redeploy by hand: `npx vercel deploy --prod`. Run it locally with `npm install` then `npm run dev`.

## Planning for your time

In the Create wizard, enter your courts and how many hours you have. The **Format** step simulates the whole day: courts, match length, who can play when, and bracket rounds that have to wait. It then tells you whether the draw fits, with ideas if it doesn't. On the day, the home page shows a projected finish time and warns the organizer if things are running long.

What fits on **10 courts** with the default format (pools of about 5, top 2 into a single-elimination bracket, one game to 11):

| Teams | Matches | ~20 min per game | ~15 min per game |
|---|---:|---:|---:|
| 24 (1 division) | 55 | 3h 00m | 2h 15m |
| 32 (2 × 16) | 80 | 3h 20m | 2h 30m |
| 40 (2 × 20) | 94 | 3h 40m | 2h 45m |
| 48 (2 × 24) | 110 | 4h 40m | 3h 30m |
| 60 (3 × 20) | 141 | 5h 20m | 4h 00m |

So in about 4 hours, plan for up to roughly 40 teams. Go bigger only with shorter games: to 9, or with a point cap.

## Tournament day

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

Event name, organizer, charity and sign-up link live in [`src/brand.ts`](src/brand.ts). Set `signupUrl` there to show a **Register** button on the home page.

```
src/brand.ts      SACS branding & charity details
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
