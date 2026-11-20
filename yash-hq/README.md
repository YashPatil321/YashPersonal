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
- `sample`: asks Claude on Yash's own account. `sample.json(prompt)` builds the AI brief
  (headline, tasks, which mail matters, per project build summary, ticker lines). Cached 30 min.
- `db`: tiny document store. `brief/latest` (last AI brief), `done/<taskId>` (checked tasks),
  `agents/<id>` `{name, status: working|done|blocked, note, updated}` (status board other Claude sessions write to).

Allowed capabilities are in capabilities.json. If you add a connector tool, it must be added there too.

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
