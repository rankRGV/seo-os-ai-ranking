# SEO OS Onboarding Sequence

This is the recommended onboarding flow for the dashboard-first SEO OS starter kit.

## Fast checklist

1. Create or choose the client workspace.
2. Add the client in the dashboard.
3. Connect read-only data sources first: GSC, GA4, sitemap/crawl, and review source where relevant.
4. Bind the client to a Hermes profile and operator notification route.
5. Run the first safe workflow: opportunity detection, title/meta planning, content refresh planning, or review-response drafting.
6. Route recommendations to Approvals.
7. Only after explicit approval, create bounded tasks for staging or drafting.
8. Keep production publishing, deploys, redirects, canonicals/noindex, deletions, DNS/WAF, and external outreach behind a separate explicit approval.

## Core principle

A Telegram topic and website URL are enough to start the conversation, but not enough to operate safely.

If setup starts in Telegram, SEO OS must still complete the visible setup loop before replying:

```text
Telegram setup message
  -> create/update dashboard client row
  -> create per-client Hermes profile
  -> create per-client workspace
  -> queue setup tasks and setup-needed jobs
  -> bind the Telegram topic target
  -> send confirmation back to the same Telegram topic
```

The confirmation should tell the operator that the dashboard was updated, which profile/workspace was created, and what the next setup step is.

## Minimum client facts

| Field | Required | Notes |
|---|---:|---|
| Client name | yes | Human-readable name |
| Domain/site URL | yes | Canonical public site |
| Business type | yes | Local SEO, SaaS, agency, content site, ecommerce, etc. |
| Main offer | yes | What the site sells or converts for |
| Target audience/location | yes | Needed for SERP intent and content relevance |
| Primary conversion goal | yes | Calls, bookings, trials, paid signups, leads, purchases |
| GSC property | yes for real SEO | URL-prefix or domain property |
| GA4 property | recommended | Needed for landing-page quality and conversions |
| Telegram topic target | yes for Telegram flow | Must be explicit `telegram:<chat_id>:<thread_id>` |
| Approval policy | yes | Defines what can happen without approval |
| CMS/platform | recommended | Astro/Cloudflare, WordPress, Webflow, Shopify, Wix, custom, etc. |
| Content delivery mode | yes | Default to `google_doc` unless repo/CMS automation is intentionally connected |
| Image style guide | optional but recommended | Keeps future feature images visually consistent |
| Competitors | recommended | Useful after first baseline |
| Repo/hosting | optional | Required only for code/content changes or staging previews |
| Staging URL | optional | Required for Git/static-site staging workflows |
| Zernio/GBP | optional | For local SEO review workflows |

If the operator only provides the website URL, create a setup draft but mark the client as `setup_needed` until the required fields are complete.

## Recommended first message from the operator

```text
New SEO OS client setup

Client name:
Website URL:
Business type:
Main offer:
Target audience/location:
Primary conversion goal:
GSC property:
GA4 property:
Competitors:
Approval policy:
CMS/platform:
Content delivery mode:
Generate image style guide? yes/no
Repo/hosting access:
Staging URL:
Reviews/Zernio/GBP:
Notes:
```

## Stage 1: Create local system records

Create or update:

```text
/root/seo-sites/<domain>/
  AGENTS.md
  site-profile.md
  approval-policy.md
  analytics-access.md
  marketing-boundaries.md
  onboarding-checklist.md
  content-writing-guidelines.md
  image-style-guide.md
  client-config.json
  client-knowledge/
  data/
  reports/
  drafts/
  plans/
  logs/
  repo/
```

Create or update the SEO OS registry and dashboard immediately:

```text
clients.yaml or SQLite clients table
telegram_bindings table or config section
approval policy row
managed jobs rows, initially disabled or setup_needed
client-scoped dashboard rows for every visible tab
```

Before inserting a client, search existing clients by exact domain and common variants. Use the canonical existing `client_id` when found. Do not create duplicate clients because of slug differences such as `my-inclusion` vs `myinclusion`.

## Stage 2: Verify routing

Topic names are not enough. Verify the actual topic binding.

1. Send an outbound test message to `telegram:<chat_id>:<thread_id>`.
2. Operator confirms it appears in the intended topic.
3. Operator sends a normal standalone message in that same topic.
4. Confirm Hermes receives the inbound message with the same thread ID.
5. Save the verified target and timestamp.

If inbound does not work, check Telegram allowed chats, free response chats, `require_mention: false`, BotFather privacy mode, and bot permissions in the group/topic.

## Stage 3: Verify data access

Run read-only checks only:

- GSC property can be queried.
- GA4 property can be queried, if provided.
- sitemap URL is reachable.
- robots.txt is reachable.
- homepage and top pages can be fetched.
- repo/hosting boundaries are documented, if provided.
- content delivery mode is documented, defaulting to Google Doc drafts when no safe publishing integration exists.
- image style guide is created or explicitly skipped.

Do not create content, push branches, publish, redirect, noindex, canonicalize, delete, or send outreach during onboarding verification.

## Stage 4: Generate baseline

Create a short baseline report:

- current indexed/public pages from sitemap
- GSC 28-day page/query snapshot
- GA4 landing-page snapshot, if available
- obvious technical blockers
- top 3 to 5 opportunities
- recommended first safe workflow

## Stage 5: Ask for first approval

The first approval should be bounded and low risk. Recommended options:

1. Low-CTR title/meta planning for high-impression pages.
2. SERP gap analysis for one existing page.
3. Indexing recovery plan for pages that deserve indexing.
4. Internal-link suggestions only.
5. Google Doc content draft for one approved topic.

Approval copy should be explicit:

```text
Approve this planning/staging task only?

This allows Hermes to create a bounded task and draft recommendations.
It does not allow publishing, deploying, redirects, noindex/canonical changes, deletions, or outreach.
```

## Hard rule: client-scoped views

Every tab and dashboard section must apply the active client filter before rendering rows. If the user selects one client, show only rows where `client_id` exactly equals that client.

Do not leak another client's CTR tests, content queue, jobs, tasks, approvals, reports, activity, performance, or opportunities into the selected client view. Global policy rows belong in the All Clients view only unless deliberately duplicated for the selected client.

## Stage 6: Execute through approvals

When the dashboard approval button is clicked:

```text
Dashboard decision
  -> update approval_requests.status
  -> log activity_events
  -> create/update agent_tasks row
  -> send Telegram confirmation to the bound topic
  -> worker/dispatcher picks up ready task with the correct profile
```

The confirmation should tell the user:

- what they approved
- what Hermes will do next
- what is still gated
- whether anything else is needed from them

## Do not promise

Avoid claiming:

- fully autonomous SEO
- guaranteed rankings
- no human input required
- safe automatic publishing

Better framing:

> SEO OS helps you connect your SEO data, find opportunities, draft improvements, and route work through human approval.
