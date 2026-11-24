# Yash HQ

A wall dashboard for Yash. One self contained HTML file (index.html). It lives as a
claude.ai artifact at https://claude.ai/artifact/9ZQx1xYZwPMRDhDuoT5oVE and runs on an
iPad on a stand and a 49 inch OLED.

## How it gets data (do not break this)

Inside claude.ai the page gets `window.claude.use(name)`:

- `mcp`: live connector calls with Yash's own login, no API keys.
  - `watchTool("Google Calendar", "list_events", {orderBy:"startTime", pageSize:60}, handler, {refetchInterval: 300000})`
    payload: `{events:[{id, summary, start:{dateTime|date}, end:{...}, htmlLink, transparency}]}`
  - `watchTool("Gmail", "search_threads", {query, view:"THREAD_VIEW_SUMMARY", pageSize}, ...)` twice:
    unread mail (last 3 days) and GitHub notifications (last 7 days).
    payload: `{threads:[{id, viewUrl, messages:[{sender, subject, snippet, date, labelIds, addressDisplayNames}]}]}`
  - `watchTool("Solidhauz", "business_overview", {days:30}, ...)` every 15 min and `watchTool("Solidhauz", "today", {limit:20}, ...)` every 5 min
    for the SolidHauz panel (cash, production stages, overdue, customers waiting on a reply).
    payload: the tool's JSON (`{kpis, money, production:{active, stages, stuck}, attention}` and `{awaitingReply, pendingReview, consultsToday}`).
    The page accepts `result.payload`, `result.structuredContent` or JSON in `result.content[0].text`.
- `sample`: asks Claude on Yash's own account. `sample.json(prompt)` builds the AI brief
  (headline, tasks, which mail matters, per project build summary, ticker lines). Cached 30 min.
- `db`: tiny document store. `brief/latest` (last AI brief), `done/<taskId>` (checked tasks),
  `agents/<id>` `{name, status: working|done|blocked, note, updated}` (status board other Claude sessions write to).

Allowed capabilities are in capabilities.json. If you add a connector tool, it must be added there too.

## Design: Ember Cockpit

Dot matrix hardware with a flight deck layer. True black, one warm ember hue, cream ink.
Status strip on top (active, armed, free time, SolidHauz, caution), a dot ring countdown,
a nav display of the next 6 hours over dot terrain, sun arc and live moon phase for San Diego
(computed locally, no network), today in 64 quarter hour dots, week grid, checklist, mail,
SolidHauz production pipeline, builds and agents. Night mode runs 11 PM to 6 AM (N toggles).
The layout drifts 1px every 3 minutes to protect the OLED. On the iPad two slots rotate.
Keys: R rescan, N night, F full screen.
Standby: after 20 idle minutes HQ dims to a dot clock. A tap wakes it, and so does any other HQ
opening (the `room` capability): Jarvis opens HQ on the PC after a clap, which wakes the iPad.
iPad setup: Settings, Display, Auto-Lock Never, keep it plugged in, Guided Access to pin Safari. `direction-a/b/c.html` are the earlier explorations.

## Preview mode

Opened as a plain file (no window.claude), the page fills itself with realistic sample data
(`mockFeeds()`), so you can design in a normal browser. Keep that working.

## Page rules (claude.ai artifact sandbox)

- One HTML file. Scripts inline or from cdnjs, cdn.jsdelivr.net, unpkg. Fonts from Google Fonts only.
- No fetch to other hosts, no remote images, no alert/confirm, no localStorage reliance.
- Fullscreen and wake lock only from a click.

## Publishing changes

Edit index.html, then in a claude.ai chat with Claude say:
"Republish this file to my Yash HQ artifact" and attach index.html.
(Or, if your Claude Code has the claude-artifacts connector, publish_files to slug
454fab32-dad1-420d-9cb5-ac334dac44dd with as: index.html.)
