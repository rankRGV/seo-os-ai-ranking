# SEO OS Architecture

SEO OS is a reusable Hermes-based operating system for SEO agency work.

## Components

```text
Telegram / CLI
  ↓
Hermes operator profile
  ↓ routes work to
Per-client Hermes profile
  ↓ reads/writes
Per-client VPS workspace
  ↓ summarizes into
SQLite operational state
  ↓ powers
Custom SEO OS dashboard
  ↓ produces
Google Docs / clean HTML reports / optional Sheet exports
```

## Roles

| Component | Role |
|---|---|
| Custom dashboard | Main human-readable operating board |
| SQLite | Local operational state for clients, jobs, approvals, tasks, reports, and activity |
| Hermes | Worker that refreshes data, drafts tasks, writes reports, and requests approval |
| Telegram | Operator notification and conversation layer |
| Hermes profile | Client-specific memory/context/tool routing |
| VPS workspace | Internal data, drafts, logs, reports, scripts, and client knowledge |
| Google Docs / HTML | Polished reports and client-facing deliverables |
| Google Sheets | Optional export layer only |

## Client isolation and filtering

Every operational row must have a `client_id`. Every tab, Sheet update script, dashboard API query, and frontend view must filter by the selected `client_id`. Selecting a client means the user sees only that client's CTR tests, jobs, content items, approvals, opportunities, tasks, reports, activity, and performance. All-client/global rows are shown only in the All Clients view.

Telegram onboarding must be atomic from the operator's perspective:

```text
Telegram setup message
  -> create/update client registry row
  -> create per-client Hermes profile
  -> create per-client workspace
  -> queue setup tasks/jobs
  -> update dashboard
  -> send Telegram confirmation to the same topic
```

Before inserting a client, check existing clients by domain and common variants so `my-inclusion` and `myinclusion` style slug differences do not create duplicates.

## Update model

- Daily refresh updates the operating picture.
- Work-time updates modify approvals, agent tasks, activity, CTR tests, review management, reports, and dashboard KPIs.
- Internal artifacts stay on the VPS unless they become user-reviewable deliverables.
- The dashboard should only display operational summaries and artifacts, not raw private credentials or full conversation logs.

## Client expertise layer

For content quality, SEO OS should gather client expertise by email/form, then distill it into `client-knowledge/`. This is what prevents generic AI SEO content.

## Review management layer

For local SEO, review monitoring can connect to GBP tooling, Zernio, or another review provider. Positive reviews can use approved response templates. Negative/risky reviews require approval before posting.
