# Incident Desk

**A full-stack incident reporting platform for security teams — structured intake, lifecycle tracking, and a self-documenting audit trail.**

![Python](https://img.shields.io/badge/Python-3.10+-3776AB?logo=python&logoColor=white)
![Flask](https://img.shields.io/badge/Flask-3.1-000000?logo=flask&logoColor=white)
![SQLite](https://img.shields.io/badge/SQLite-file--based-003B57?logo=sqlite&logoColor=white)
![JavaScript](https://img.shields.io/badge/JavaScript-vanilla-F7DF1E?logo=javascript&logoColor=black)
![License](https://img.shields.io/badge/license-MIT-informational)

---

## Table of contents

- [The problem](#the-problem)
- [Preview](#preview)
- [Tech stack](#tech-stack)
- [Getting started](#getting-started)
- [What's built](#whats-built-mvp-scope)
- [Business rules](#business-rules-worth-knowing)
- [API reference](#api-reference)
- [Known limitations](#known-limitations-honest-not-hidden)
- [Project structure](#project-structure)
- [Skills demonstrated](#skills-demonstrated)
- [Challenges and decisions](#challenges-and-how-they-were-resolved)
- [License](#license)

---

## The problem

Security incidents at a digital payments company get reported wherever is convenient in the moment: an email, a Slack thread, a spreadsheet someone half-remembers to update. When a support agent, fraud analyst, or infra engineer needs to know *"is this actually new, who's on it, what's already been tried,"* the answer is scattered across tools nobody agrees is the source of truth. That slows down response and makes the after-the-fact learning — why did this happen, what do we change — even harder, because the record is incomplete by the time anyone goes looking for it.

**Incident Desk** replaces that with one place to file a report, track it through its lifecycle, and log a timestamped, attributable trail of what was done — so the record exists whether or not anyone remembers to write a postmortem later.

## Preview

> Run it locally and drop in your own screenshots here — intake form, dashboard, incident drawer with timeline, and trends view all make for a strong at-a-glance preview.

```
[ dashboard.png ]   [ intake-form.png ]
[ drawer.png ]      [ trends.png ]
```

## Tech stack

| Layer      | Choice                          | Why |
|------------|----------------------------------|-----|
| Backend    | Python + Flask, raw `sqlite3`    | No ORM — the schema is three tables; an ORM would add abstraction without solving a real problem here. |
| Database   | SQLite, file-based (`incidents.db`) | Trivial to set up, which matters for something meant to be run and demoed in one sitting. |
| Frontend   | Vanilla HTML/CSS/JS, no build step | [Chart.js](https://www.chartjs.org/) via CDN for the trends chart — the one place a charting library actually earns its weight over hand-rolled SVG. |

No React/Node here on purpose: the surface area (a form, a table, a drawer, a chart) doesn't need a component framework, and skipping the build step means `python app.py` is the entire setup.

## Getting started

```bash
git clone https://github.com/<your-username>/incident-desk.git
cd incident-desk
pip install -r requirements.txt --break-system-packages   # or use a venv
python app.py
```

Then open **http://127.0.0.1:5050**.

The database ships pre-seeded with 9 realistic mock incidents spanning all four statuses. To reset it to that clean state at any point:

```bash
python seed_data.py
```

## What's built (MVP scope)

1. **Structured intake form** — required fields (type, discovery time, description, initial severity, reporter), validated on both the client and the server. The server is the actual source of truth for valid values; the frontend dropdowns are populated from `/api/meta` rather than hardcoded, so they can't drift out of sync.
2. **Status & severity tracking** — every incident carries a current status (`Open` / `Investigating` / `Resolved` / `Closed`) and severity (`Low` / `Medium` / `High` / `Critical`), filterable and sortable from the dashboard.
3. **Timeline log** — an append-only, timestamped log per incident. Status and severity changes write themselves into the timeline automatically, so the audit trail can't fall out of sync with the actual record.

### Advanced features (both shipped)

- **Post-incident report auto-fill** — pulls the incident's fields and full timeline into a read-only context block, then gives the user three editable fields (root cause, remediation, lessons learned) to complete and save. It doesn't try to auto-write the analysis — that's the part that requires a human — but it removes all the re-typing.
- **Trend view** — a stacked bar chart of incident volume by type over a selectable range (7 / 30 / 90 / 365 days), plus a ranked total-by-type list beside it. Bucketing scales with the range — daily for short windows, weekly and monthly for longer ones — so the chart shows a real shape instead of a field of single-incident bars.

## Business rules worth knowing

These came up directly from edge-case testing and were resolved as explicit product decisions, not left ambiguous:

- **Closed incidents are locked.** No status/severity change and no new timeline entries once an incident is `Closed`. This is deliberate — a closed incident is supposed to be the finished record. Reopening is a separate, explicit action (`POST /api/incidents/<id>/reopen`) that logs *why* it was reopened, rather than a silent field edit.
- **Discovery time can't be blank or in the future.** Basic bad-data guard; discovery is a fact about the past by definition.
- **Status/severity changes are self-documenting.** Changing either one writes a system-authored timeline entry, so you can't change an incident's state without it showing up in the log.
- **Timeline entries are immutable and ordered by timestamp**, with insertion order as a tiebreaker for same-timestamp entries.

## API reference

| Method | Endpoint                              | Description |
|--------|----------------------------------------|--------------|
| GET    | `/api/meta`                            | Valid types, statuses, and severities (drives the form dropdowns). |
| GET    | `/api/incidents`                       | List incidents, filterable/sortable via query params. |
| POST   | `/api/incidents`                       | File a new incident report. |
| GET    | `/api/incidents/<id>`                  | Fetch one incident with its full timeline. |
| PATCH  | `/api/incidents/<id>`                  | Update status and/or severity (writes a timeline entry). |
| POST   | `/api/incidents/<id>/reopen`           | Reopen a closed incident with a logged reason. |
| POST   | `/api/incidents/<id>/timeline`         | Add a note to the timeline. |
| GET/POST | `/api/incidents/<id>/report`         | Fetch or save the post-incident report. |
| GET    | `/api/trends`                          | Incident volume by type, bucketed over a date range. |

## Known limitations (honest, not hidden)

- No authentication — anyone with network access to the server can file and edit incidents. The "author" field on edits is self-reported, not verified. Fine for a local MVP demo; not fine for production without an auth layer.
- Single SQLite file — works for one instance, not for concurrent writers at scale. A real deployment would move to Postgres.
- Discovery-time validation compares against the server's local clock; if the browser and server are in different timezones with clocks out of sync, the "not in the future" check could be slightly off. Not an issue running everything locally.

## Project structure

```
incident-desk/
├── app.py            # Flask app: routes, validation, DB access
├── seed_data.py       # Wipes and repopulates incidents.db with mock data
├── requirements.txt
├── incidents.db        # SQLite database (gitignored in practice; ships seeded)
├── templates/
│   └── index.html
└── static/
    ├── app.js         # All frontend logic — views, drawer, chart, forms
    └── style.css      # Design tokens + component styles
```

## Skills demonstrated

- **Full-stack design and implementation** — REST API design, relational schema design, and a dependency-free frontend built to match a specific operational (not marketing) use case.
- **Domain-aware UX thinking** — a table-first, ops-console layout chosen because the actual users triage lists all day, not because it's a default template.
- **Security/incident-management domain literacy** — severity/status taxonomy, audit-trail integrity (self-documenting state changes, locked-closed records), and realistic fintech incident scenarios used for testing.

## Challenges and how they were resolved

- **Deciding what happens to a Closed incident.** The brief asked the question but didn't answer it. I resolved it as a product decision (locked + explicit reopen with a logged reason) rather than leaving the behavior undefined, because an ambiguous answer here would have meant an inconsistent audit trail — the actual thing this tool exists to fix.
- **Keeping the timeline trustworthy.** It would have been easy to let the frontend freely edit status/severity with the timeline as an afterthought. Instead every state change is written server-side as a timeline entry in the same transaction as the update, so the two can never fall out of sync.
- **Avoiding generic dashboard-template design.** The default "AI dashboard" look (rounded cards, one accent color, uniform shadows) doesn't fit how someone actually triages a queue of incidents. Went with a dense, table-first layout with severity encoded on the row itself, closer to how an ops console actually gets used.
- **Making the trends chart actually informative.** At low incident volume, daily bucketing produced a chart where every bar had height 1 — technically correct, visually meaningless. Bucket granularity now scales with the selected range (day / week / month), so the chart shows an actual distribution instead of noise.

## License

[MIT](LICENSE) — free to use, modify, and learn from.
