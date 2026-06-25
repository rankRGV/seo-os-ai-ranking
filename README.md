# SEO OS AI Ranking — RankRGV Fork

A reusable starter kit for running an SEO operating system with Hermes Agent and a VPS-local custom dashboard.

This fork (`rankRGV/seo-os-ai-ranking`) extends the upstream NicoSKOOL/seo-os-ai-ranking with agency-specific features for local SEO clients.

## What's live

- **Dashboard** at port 8787 (teal theme #1c4642)
- **Daily 9am cron** pulls GA4 + GSC data for all active clients
- **Health score widget** per client (rank-based scoring)
- **Content Briefs tab** (100 briefs, filterable by priority)
- **Opportunities** from both GA4 and GSC with source badges (GA4 blue / GSC green)
- **Date-range filter** (7/28/90 days)
- **Token refresh** on startup + background daemon every 50 min
- **Patch script** at `custom/apply-patches.sh` for upstream updates

## New in this fork

### Prospecting Module (`prospects.py`)
Full CRM pipeline for local business prospecting:
- Add/search/filter prospects
- Pipeline stages: New → Contacted → Pitched → Negotiation → Closed-Won
- FB DM opener generator (auto-personalized with rank, city, niche)
- Activity logging per prospect
- Prospects tab in navigation

### Client Onboarding Flow
Settings page includes an active "Add Client" form:
- Client ID, name, domain, role/niche
- Client type selector (local vs national)
- Auto-creates Hermes profile, workspace, and dashboard row
- Activity event logged on creation

### Google Business Profile Health Monitor (`gbp_monitor.py`)
Tracks GBP metrics for local businesses:
- Views (search + maps), searches (direct + discovery)
- Actions (calls, website clicks, directions, messages)
- Review average + count, posts, photos
- Health score 0-100 (weighted: actions 30%, views 20%, reviews 25%, content 25%)
- Green/yellow/red status cards in Command Center widget
- Daily 10am cron auto-runs
- Demo data fallback when API not connected

**To enable live GBP data:**
1. Enable "Business Profile Performance API" in Google Cloud Console
2. Add scope `https://www.googleapis.com/auth/business.manage` to OAuth token
3. Request quota increase (default is 0/min for new projects)
4. Run `python3 gbp_monitor.py --live`

### Local vs National client types
- `local` — GBP health monitor applies, map pack tracking
- `national` — GBP monitor skipped, e-commerce/wide-reach focus

## Quick start

```bash
cd seo-os-dashboard
python3 server.py --port 8787
```

Then open `http://127.0.0.1:8787` (use SSH tunnel for VPS).

## Architecture

```text
Custom SEO OS Dashboard = operating board (port 8787)
SQLite = local operational state (data/seo-os.sqlite)
Hermes = worker
Discord = operator notification layer
Hermes profiles = client separation
VPS file system = internal workspace and data store
Google Docs / clean HTML = polished reports
Google Sheets = outreach tracker (optional export layer)
```

## Data sources

| Source | API | Auth |
|--------|-----|------|
| Google Search Console | webmasters.readonly | OAuth |
| GA4 | analytics.readonly | OAuth |
| Google Business Profile | business.manage | OAuth (pending quota approval) |
| Google Sheets | spreadsheets | OAuth |
| Google Drive | drive | OAuth |

## Client sites

Custom Astro on Vercel (NOT WordPress). No GA4 conversion tracking set up yet — needs GTM container snippet on Astro sites.

## Safety defaults

Dashboard approvals update state and create bounded tasks. They do not publish, deploy, redirect, noindex, canonicalize, delete pages, or send outreach. Those actions need separate explicit approval.

## Never commit

- `data/` SQLite databases, WAL files
- `logs/` files
- Real client data or credentials
- API tokens, Discord IDs, OAuth secrets
- Generated reports or local workspace files

## Upstream

- Upstream: github.com/NicoSKOOL/seo-os-ai-ranking
- Fork: github.com/rankRGV/SEO-OS-AI-ranking
- Sync: `git fetch upstream && git merge main && git rebase discord-adaptation`
