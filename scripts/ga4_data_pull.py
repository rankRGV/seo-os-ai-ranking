#!/usr/bin/env python3
"""GA4 Data API pull — fetches search performance data for client properties.

Pulls: sessions, engaged sessions, engagement rate, average session duration,
conversions, and search landing page data from GA4 Data API.

Usage:
    python3 scripts/ga4_data_pull.py                  # Pull all configured clients
    python3 scripts/ga4_data_pull.py --client rankrgv  # Pull specific client
    python3 scripts/ga4_data_pull.py --days 28         # Lookback window (default: 28)
"""

import argparse
import json
import os
import sqlite3
import sys
import urllib.request
import urllib.error
import uuid
from datetime import datetime, timezone, timedelta
from pathlib import Path

# Import health score functions from server (reuses same DB)
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from server import calculate_client_health, store_health_score

# ── Config ───────────────────────────────────────────────────────────────────

DB_PATH = Path(os.environ.get("SEO_OS_DB_PATH", Path(__file__).resolve().parent.parent / "data" / "seo-os.sqlite"))
TOKEN_PATH = Path("/root/.hermes/google_token.json")
ROOT = Path(__file__).resolve().parent.parent

# GA4 Data API scope
GA4_READONLY_SCOPE = "https://www.googleapis.com/auth/analytics.readonly"
GA4_API_BASE = "https://analyticsdata.googleapis.com/v1beta"

UTC = datetime.now(timezone.utc).tzinfo


# ── Token management ─────────────────────────────────────────────────────────

def load_token() -> dict:
    """Load OAuth token from file."""
    if not TOKEN_PATH.exists():
        print(f"ERROR: Token file not found at {TOKEN_PATH}", file=sys.stderr)
        sys.exit(1)
    with open(TOKEN_PATH) as f:
        return json.load(f)


def get_access_token() -> str:
    """Load OAuth access token from file."""
    data = load_token()
    token = data.get("token", "")
    if not token:
        print("ERROR: No token in token file", file=sys.stderr)
        sys.exit(1)
    return token


# ── GA4 API helpers ──────────────────────────────────────────────────────────

def ga4_run_report(property_id: str, payload: dict) -> list:
    """Run a GA4 Data API report and return rows."""
    access_token = get_access_token()
    url = f"{GA4_API_BASE}/properties/{property_id}:runReport"

    data = json.dumps(payload).encode()
    headers = {
        "Authorization": f"Bearer {access_token}",
        "Content-Type": "application/json",
        "User-Agent": "SEO-OS-Dashboard/1.0",
    }

    req = urllib.request.Request(url, data=data, headers=headers, method="POST")
    try:
        resp = urllib.request.urlopen(req, timeout=30)
        result = json.loads(resp.read())
    except urllib.error.HTTPError as e:
        body = e.read().decode()
        print(f"GA4 API error {e.code}: {body[:500]}", file=sys.stderr)
        return []
    except Exception as e:
        print(f"GA4 API request failed: {e}", file=sys.stderr)
        return []

    rows = []
    dimension_headers = [h.get("name", "") for h in result.get("dimensionHeaders", [])]
    metric_headers = [h.get("name", "") for h in result.get("metricHeaders", [])]
    raw_rows = result.get("rows", [])

    for raw in raw_rows:
        row = {}
        for i, val in enumerate(raw.get("dimensionValues", [])):
            row[dimension_headers[i]] = val.get("value", "")
        for i, val in enumerate(raw.get("metricValues", [])):
            row[metric_headers[i]] = val.get("value", "")
        rows.append(row)

    return rows


# ── Data pull functions ──────────────────────────────────────────────────────

def pull_sessions_and_engagement(property_id: str, days: int = 28) -> list:
    """Pull sessions, engaged sessions, engagement rate, avg session duration by landing page."""
    payload = {
        "dateRanges": [{"startDate": f"{days}daysAgo", "endDate": "today"}],
        "dimensions": [{"name": "sessionDefaultChannelGroup"}],
        "metrics": [
            {"name": "sessions"},
            {"name": "engagedSessions"},
            {"name": "engagementRate"},
            {"name": "averageSessionDuration"},
            {"name": "conversions"},
        ],
        "orderBys": [{"metric": {"metricName": "sessions"}, "desc": True}],
        "limit": 20,
    }
    return ga4_run_report(property_id, payload)


def pull_landing_pages(property_id: str, days: int = 28) -> list:
    """Pull landing page performance data."""
    payload = {
        "dateRanges": [{"startDate": f"{days}daysAgo", "endDate": "today"}],
        "dimensions": [{"name": "landingPagePlusQueryString"}],
        "metrics": [
            {"name": "sessions"},
            {"name": "engagedSessions"},
            {"name": "engagementRate"},
            {"name": "averageSessionDuration"},
            {"name": "conversions"},
            {"name": "newUsers"},
            {"name": "bounceRate"},
        ],
        "orderBys": [{"metric": {"metricName": "sessions"}, "desc": True}],
        "limit": 50,
    }
    return ga4_run_report(property_id, payload)


def pull_search_queries(property_id: str, days: int = 28) -> list:
    """Pull search query data (organic search only)."""
    payload = {
        "dateRanges": [{"startDate": f"{days}daysAgo", "endDate": "today"}],
        "dimensions": [
            {"name": "sessionSa360Query"},
            {"name": "sessionDefaultChannelGroup"},
        ],
        "metrics": [
            {"name": "sessions"},
            {"name": "engagedSessions"},
            {"name": "conversions"},
        ],
        "dimensionFilter": {
            "filter": {
                "fieldName": "sessionDefaultChannelGroup",
                "stringFilter": {
                    "value": "Organic Search",
                    "matchType": "EXACT",
                },
            }
        },
        "orderBys": [{"metric": {"metricName": "sessions"}, "desc": True}],
        "limit": 25,
    }
    return ga4_run_report(property_id, payload)


def pull_daily_trend(property_id: str, days: int = 28) -> list:
    """Pull daily sessions trend."""
    payload = {
        "dateRanges": [{"startDate": f"{days}daysAgo", "endDate": "today"}],
        "dimensions": [{"name": "date"}],
        "metrics": [
            {"name": "sessions"},
            {"name": "engagedSessions"},
            {"name": "conversions"},
        ],
        "orderBys": [{"dimension": {"dimensionName": "date"}}],
    }
    return ga4_run_report(property_id, payload)


# ── Database operations ──────────────────────────────────────────────────────

def connect() -> sqlite3.Connection:
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def get_clients_with_ga4(conn: sqlite3.Connection) -> list:
    """Get all clients that have GA4 connected, with their per-client property ID."""
    clients = conn.execute(
        "SELECT * FROM clients WHERE ga4_status='connected'"
    ).fetchall()
    result = []
    for c in clients:
        c = dict(c)
        # Use per-client property ID if set, fallback to global setting
        if c.get("ga4_property_id"):
            c["property_id"] = c["ga4_property_id"]
        else:
            ga4_setting = conn.execute(
                "SELECT value FROM settings WHERE key='ga4_property_id'"
            ).fetchone()
            c["property_id"] = ga4_setting["value"] if ga4_setting else ""
        result.append(c)
    return result


def store_metrics_snapshot(conn: sqlite3.Connection, client_id: str, data: dict, period_label: str) -> str:
    """Store a metrics snapshot row."""
    import uuid
    t = datetime.now(timezone.utc).replace(microsecond=0).isoformat()
    mid = f"metric_{uuid.uuid4().hex[:10]}"

    # Deduplicate: remove existing snapshot for same client+period, then insert fresh
    conn.execute(
        "DELETE FROM metrics_snapshots WHERE client_id=? AND period_label=?",
        (client_id, period_label)
    )
    conn.execute(
        "INSERT INTO metrics_snapshots VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)",
        (
            mid, client_id, period_label,
            data.get("sessions", 0), data.get("sessions_delta", 0),
            data.get("engaged_sessions", 0), data.get("engaged_sessions_delta", 0),
            data.get("engagement_rate", 0), data.get("engagement_rate_delta", 0),
            data.get("avg_session_duration", 0), data.get("avg_session_duration_delta", 0),
            data.get("conversions", 0),
            t,
        )
    )
    return mid


def store_opportunity(conn: sqlite3.Connection, client_id: str, page_data: dict, total_client_sessions: int = 0) -> str | None:
    """Store or update an opportunity from GA4 landing page data.

    Creates opportunities for any page with measurable traffic (>= 1 session).
    Priority is relative to the client's own traffic distribution:
    - High: top 20% of pages by traffic + problem signal, OR any page with bounce > 80%
    - Medium: top 50% by traffic, OR strong performer worth scaling
    - Low: has traffic but no strong signal
    """
    import uuid
    t = datetime.now(timezone.utc).replace(microsecond=0).isoformat()
    page = page_data.get("landingPagePlusQueryString", "")

    # Skip pages with no traffic
    sessions = int(page_data.get("sessions", 0) or 0)
    if sessions < 1:
        return None

    new_users = int(page_data.get("newUsers", 0) or 0)
    engagement_rate = float(page_data.get("engagementRate", 0) or 0)
    bounce_rate = float(page_data.get("bounceRate", 0) or 0)
    avg_duration = float(page_data.get("averageSessionDuration", 0) or 0)

    # Check if opportunity already exists for this page
    existing = conn.execute(
        "SELECT * FROM opportunities WHERE client_id=? AND page=?",
        (client_id, page)
    ).fetchone()

    # Look up baseline from previous pull for this page (specific to metric)
    baseline_clicks_row = conn.execute(
        "SELECT * FROM baselines WHERE client_id=? AND page=? AND metric='clicks' ORDER BY created_at DESC LIMIT 1",
        (client_id, page)
    ).fetchone()
    baseline_imp_row = conn.execute(
        "SELECT * FROM baselines WHERE client_id=? AND page=? AND metric='impressions' ORDER BY created_at DESC LIMIT 1",
        (client_id, page)
    ).fetchone()

    baseline_clicks = baseline_clicks_row["value"] if baseline_clicks_row else None
    baseline_impressions = baseline_imp_row["value"] if baseline_imp_row else None

    # Calculate trend
    trend = "stable"
    trend_direction = "→"
    if baseline_clicks is not None:
        if sessions > baseline_clicks * 1.1:
            trend = "clicks_up"
            trend_direction = "↑"
        elif sessions < baseline_clicks * 0.9:
            trend = "clicks_down"
            trend_direction = "↓"

    # Store current data as new baseline for next comparison
    import uuid as _uuid
    bid = f"bl_{_uuid.uuid4().hex[:10]}"
    now_t = datetime.now(timezone.utc).replace(microsecond=0).isoformat()
    conn.execute(
        "INSERT INTO baselines VALUES (?,?,?,?,?,?,?)",
        (bid, client_id, page, "clicks", float(sessions), "previous_pull", now_t)
    )
    bid2 = f"bl_{_uuid.uuid4().hex[:10]}"
    conn.execute(
        "INSERT INTO baselines VALUES (?,?,?,?,?,?,?)",
        (bid2, client_id, page, "impressions", float(new_users), "previous_pull", now_t)
    )

    # Relative thresholds based on client's total traffic
    # Top page gets ~20% of sessions, second gets ~10%, etc.
    # For low-traffic sites, even 5 sessions can be "high" if it's a top page
    is_top_page = total_client_sessions > 0 and (sessions / total_client_sessions) >= 0.15
    is_strong_page = total_client_sessions > 0 and (sessions / total_client_sessions) >= 0.08

    # Priority logic — relative to client's own baseline
    if bounce_rate > 0.8 and sessions >= 3:
        priority = "high"
        problem = f"High bounce ({bounce_rate:.0%}) — visitors leaving immediately"
        opp_type = "UX Issue"
    elif is_top_page and engagement_rate < 0.3:
        priority = "high"
        problem = f"Top page ({sessions} sessions, {sessions/total_client_sessions:.0%} of traffic) but low engagement ({engagement_rate:.0%})"
        opp_type = "Low Engagement"
    elif is_top_page and bounce_rate > 0.6:
        priority = "high"
        problem = f"Top page ({sessions} sessions) with high bounce ({bounce_rate:.0%})"
        opp_type = "High Bounce Rate"
    elif engagement_rate >= 0.5 and is_strong_page:
        priority = "medium"
        problem = f"Strong engagement ({engagement_rate:.0%}) on {sessions} sessions — scale this page"
        opp_type = "High Performer"
    elif avg_duration < 30 and sessions >= 3:
        priority = "medium"
        problem = f"Short sessions ({avg_duration:.0f}s avg) — possible content mismatch"
        opp_type = "Content Gap"
    elif is_strong_page:
        priority = "medium"
        problem = f"Decent traffic ({sessions} sessions, {engagement_rate:.0%} engaged) — optimize"
        opp_type = "Optimization"
    else:
        priority = "low"
        problem = f"{sessions} sessions, {engagement_rate:.0%} engaged, {bounce_rate:.0%} bounce"
        opp_type = "Optimization"

    if existing:
        conn.execute(
            """UPDATE opportunities SET
                problem=?, opportunity_type=?, priority=?,
                impressions=?, clicks=?, ctr=?,
                baseline_clicks=?, baseline_impressions=?, trend=?, trend_direction=?,
                updated_at=?
            WHERE id=?""",
            (
                problem, opp_type, priority,
                sessions, new_users, engagement_rate,
                baseline_clicks, baseline_impressions, trend, trend_direction,
                t, existing["id"],
            )
        )
        return existing["id"]
    else:
        oid = f"opp_{uuid.uuid4().hex[:10]}"
        conn.execute(
            """INSERT INTO opportunities VALUES (
                ?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?
            )""",
            (
                oid, client_id, page, problem, opp_type, priority,
                "GA4 data pull", "medium", "low",
                sessions, new_users, engagement_rate, 0.0,
                "Review GA4 data and identify improvement actions.",
                "new",
                json.dumps({"source": "ga4_pull", "new_users": new_users, "bounce_rate": bounce_rate, "avg_duration": avg_duration}),
                t, t,
                baseline_clicks, baseline_impressions, trend, trend_direction,
            )
        )
        return oid


def generate_gsc_opportunities(conn: sqlite3.Connection, client_id: str, days: int = 28) -> int:
    """Generate opportunities from GSC search performance data.

    Creates opportunities for pages with:
    - High impressions but weak CTR (under 3% for top-10 positions)
    - Position 4-20 range (striking distance for page 1)
    - High impressions with zero clicks (SERP gap)
    """
    import uuid
    t = datetime.now(timezone.utc).replace(microsecond=0).isoformat()

    # Get aggregated GSC data for this client over the period
    cutoff = (datetime.now(timezone.utc) - timedelta(days=days)).strftime("%Y-%m-%dT%H:%M:%S")
    gsc_agg = conn.execute("""
        SELECT page,
               SUM(clicks) as total_clicks,
               SUM(impressions) as total_impressions,
               AVG(ctr) as avg_ctr,
               AVG(position) as avg_position,
               COUNT(DISTINCT query) as query_count
        FROM gsc_performance
        WHERE client_id=? AND created_at >= ?
        GROUP BY page
        HAVING total_impressions > 0
        ORDER BY total_impressions DESC
    """, (client_id, cutoff)).fetchall()

    if not gsc_agg:
        return 0

    stored = 0
    for row in gsc_agg:
        page = row["page"]
        clicks = row["total_clicks"]
        impressions = row["total_impressions"]
        avg_ctr = row["avg_ctr"] or 0
        avg_position = row["avg_position"] or 0
        query_count = row["query_count"]

        # Skip very low impression pages
        if impressions < 3:
            continue

        # Check if opportunity already exists for this page (from GSC source)
        existing = conn.execute(
            "SELECT * FROM opportunities WHERE client_id=? AND page=? AND evidence_json LIKE '%gsc_pull%'",
            (client_id, page)
        ).fetchone()

        # Determine priority based on GSC signals
        if avg_position <= 10 and avg_ctr < 0.03 and impressions >= 10:
            priority = "high"
            problem = f"Top 10 position ({avg_position:.1f}) but low CTR ({avg_ctr:.1%}) — title/meta mismatch for {query_count} queries"
            opp_type = "Low CTR"
        elif avg_position > 10 and avg_position <= 20 and impressions >= 10:
            priority = "medium"
            problem = f"Striking distance: position {avg_position:.1f} with {impressions} impressions — optimize to reach page 1"
            opp_type = "SERP gap"
        elif avg_ctr < 0.01 and impressions >= 5:
            priority = "medium"
            problem = f"High impressions ({impressions}) but near-zero CTR ({avg_ctr:.1%}) — SERP feature stealing clicks?"
            opp_type = "SERP gap"
        elif clicks == 0 and impressions >= 5:
            priority = "low"
            problem = f"{impressions} impressions, 0 clicks — check title/description appeal"
            opp_type = "SERP gap"
        else:
            continue  # No actionable signal

        evidence = json.dumps({
            "source": "gsc_pull",
            "total_clicks": clicks,
            "total_impressions": impressions,
            "avg_ctr": round(avg_ctr, 4),
            "avg_position": round(avg_position, 1),
            "query_count": query_count,
        })

        if existing:
            conn.execute(
                """UPDATE opportunities SET
                    problem=?, opportunity_type=?, priority=?,
                    impressions=?, clicks=?, ctr=?,
                    evidence_json=?, updated_at=?
                WHERE id=?""",
                (problem, opp_type, priority,
                 impressions, clicks, avg_ctr,
                 evidence, t, existing["id"])
            )
        else:
            oid = f"opp_{uuid.uuid4().hex[:10]}"
            conn.execute(
                """INSERT INTO opportunities VALUES (
                    ?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?
                )""",
                (oid, client_id, page, problem, opp_type, priority,
                 "GSC search data", "medium", "low",
                 impressions, clicks, avg_ctr, avg_position,
                 "Review search queries and optimize title/meta for better CTR.",
                 "new", evidence, t, t, None, None, "stable", "→")
            )
        stored += 1

    conn.commit()
    return stored


def store_activity_event(conn: sqlite3.Connection, client_id: str, summary: str, next_action: str) -> str:
    """Store an activity event."""
    import uuid
    t = datetime.now(timezone.utc).replace(microsecond=0).isoformat()
    eid = f"ev_{uuid.uuid4().hex[:10]}"
    conn.execute(
        "INSERT INTO activity_events VALUES (?,?,?,?,?,?,?,?,?)",
        (eid, client_id, "ga4_pull", "data_refresh", "complete", summary, next_action, "", t)
    )
    return eid


# ── Main pull logic ──────────────────────────────────────────────────────────

# ── GSC integration ──────────────────────────────────────────────────────────

def get_gsc_site_for_client(client_id: str, domain: str) -> str:
    """Derive GSC site URL from client domain."""
    if domain.startswith("http"):
        return "sc-domain:" + domain.split("//")[1].rstrip("/")
    return "sc-domain:" + domain.rstrip("/")


def pull_gsc_data(token: str, site_url: str, days: int = 28) -> dict:
    """Pull search analytics data from GSC.

    Returns query×page breakdown and daily totals.
    """
    from datetime import datetime as _dt
    end_date = _dt.now(timezone.utc).date()
    start_date = end_date - timedelta(days=days)

    # 1. Pull daily totals
    daily_payload = {
        "startDate": start_date.isoformat(),
        "endDate": end_date.isoformat(),
        "dimensions": ["date"],
        "rowLimit": 250,
        "startRow": 0,
        "dataState": "final",
    }
    daily_clicks = 0
    daily_impressions = 0
    try:
        daily_result = gsc_request(token, site_url, daily_payload)
        if daily_result and "rows" in daily_result:
            for row in daily_result["rows"]:
                daily_clicks += int(row.get("clicks", 0))
                daily_impressions += int(row.get("impressions", 0))
    except Exception:
        pass

    # 2. Pull query×page breakdown
    all_rows = []
    start_row = 0
    while True:
        qp_payload = {
            "startDate": start_date.isoformat(),
            "endDate": end_date.isoformat(),
            "dimensions": ["query", "page"],
            "rowLimit": 250,
            "startRow": start_row,
            "dataState": "final",
        }
        try:
            result = gsc_request(token, site_url, qp_payload)
        except Exception:
            break
        if not result or "rows" not in result:
            break
        rows = result["rows"]
        all_rows.extend(rows)
        start_row += len(rows)
        if len(rows) < 250:
            break

    return {
        "query_page_rows": all_rows,
        "total_clicks": daily_clicks,
        "total_impressions": daily_impressions,
    }


def gsc_request(token: str, site_url: str, payload: dict) -> dict | None:
    """Make a GSC searchAnalytics.query request."""
    url = f"https://www.googleapis.com/webmasters/v3/sites/{site_url}/searchAnalytics/query"
    data = json.dumps(payload).encode()
    req = urllib.request.Request(url, data=data, method="POST", headers={
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json",
    })
    try:
        resp = urllib.request.urlopen(req, timeout=30)
        return json.loads(resp.read())
    except Exception as e:
        code = getattr(e, "code", "?")
        if code == 401:
            # Try refreshing token once
            try:
                token = _refresh_token_inline()
                req2 = urllib.request.Request(url, data=data, method="POST", headers={
                    "Authorization": f"Bearer {token}",
                    "Content-Type": "application/json",
                })
                resp2 = urllib.request.urlopen(req2, timeout=30)
                return json.loads(resp2.read())
            except Exception:
                pass
        print(f"  GSC API error ({code}): {str(e)[:100]}", file=sys.stderr)
        return None


def _refresh_token_inline() -> str:
    """Refresh OAuth token inline for GSC requests."""
    with open("/root/.hermes/google_token.json") as f:
        token = json.load(f)
    if "refresh_token" not in token:
        return token["token"]
    import urllib.parse as _up
    data = _up.urlencode({
        "client_id": token["client_id"],
        "client_secret": token["client_secret"],
        "refresh_token": token["refresh_token"],
        "grant_type": "refresh_token",
    }).encode()
    req = urllib.request.Request(
        "https://oauth2.googleapis.com/token", data=data,
        headers={"Content-Type": "application/x-www-form-urlencoded"}, method="POST"
    )
    resp = urllib.request.urlopen(req, timeout=10)
    result = json.loads(resp.read())
    token["token"] = result["access_token"]
    with open("/root/.hermes/google_token.json", "w") as f:
        json.dump(token, f)
    return token["token"]


def store_gsc_data(conn: sqlite3.Connection, client_id: str, site_url: str, rows: list) -> int:
    """Store GSC data in gsc_performance table."""
    now = datetime.now(timezone.utc).replace(microsecond=0).isoformat()
    today = datetime.now(timezone.utc).date().isoformat()

    conn.execute(
        "DELETE FROM gsc_performance WHERE client_id=? AND date=?",
        (client_id, today)
    )

    stored = 0
    for row in rows:
        keys = row.get("keys", [])
        if len(keys) < 2:
            continue
        query = keys[0]
        page = keys[1]
        clicks = int(row.get("clicks", 0))
        impressions = int(row.get("impressions", 0))
        ctr = float(row.get("ctr", 0))
        position = float(row.get("position", 0))

        rid = f"gsc_{uuid.uuid4().hex[:10]}"
        conn.execute(
            "INSERT INTO gsc_performance VALUES (?,?,?,?,?,?,?,?,?,?,?)",
            (rid, client_id, site_url, query, page, clicks, impressions, ctr, position, today, now)
        )
        stored += 1

    conn.commit()
    return stored


def find_max_available_days(property_id: str, preferred_days: int = 28) -> int:
    """Find the maximum number of days GA4 has data for, down to preferred_days.

    Tries preferred_days first, then falls back to shorter windows.
    Returns the largest window that returns data.
    """
    token = get_access_token()
    candidates = [preferred_days, 28, 14, 7, 3, 1]
    for d in candidates:
        if d > preferred_days:
            continue
        payload = {
            "dateRanges": [{"startDate": f"{d}daysAgo", "endDate": "today"}],
            "metrics": [{"name": "sessions"}],
            "limit": 1,
        }
        try:
            rows = ga4_run_report(property_id, payload)
            if rows:
                total = sum(int(r.get("sessions", 0) or 0) for r in rows)
                if total > 0:
                    return d
        except Exception:
            continue
    return 0


def pull_client_data(client_id: str, property_id: str, days: int = 28, gsc_site_url: str = "") -> dict:
    """Pull all GA4 data + GSC data for a client and store in database."""
    results = {
        "client_id": client_id,
        "property_id": property_id,
        "period": f"Last {days} days",
        "sessions_data": [],
        "landing_pages": [],
        "search_queries": [],
        "daily_trend": [],
        "gsc_rows": 0,
        "metrics_stored": 0,
        "opportunities_stored": 0,
        "errors": [],
    }

    print(f"  Pulling sessions by channel group...")
    sessions_data = pull_sessions_and_engagement(property_id, days)
    results["sessions_data"] = sessions_data

    print(f"  Pulling landing pages...")
    landing_pages = pull_landing_pages(property_id, days)
    results["landing_pages"] = landing_pages

    print(f"  Pulling search queries...")
    search_queries = pull_search_queries(property_id, days)
    results["search_queries"] = search_queries

    print(f"  Pulling daily trend...")
    daily_trend = pull_daily_trend(property_id, days)
    results["daily_trend"] = daily_trend

    # Pull GSC data if client has a site URL
    gsc_rows = 0
    if gsc_site_url:
        print(f"  Pulling GSC data for {gsc_site_url}...")
        try:
            token = get_access_token()
            gsc_result = pull_gsc_data(token, gsc_site_url, days=days)
            if gsc_result and gsc_result["query_page_rows"]:
                with connect() as conn:
                    gsc_rows = store_gsc_data(conn, client_id, gsc_site_url, gsc_result["query_page_rows"])
                    results["gsc_rows"] = gsc_rows
                    print(f"  ✓ {gsc_rows} GSC query×page rows stored")
            else:
                print(f"  ℹ No GSC data returned for {gsc_site_url}")
        except Exception as e:
            print(f"  ⚠ GSC pull failed: {e}", file=sys.stderr)
            results["errors"].append(f"GSC: {str(e)}")

    # Store in database
    with connect() as conn:
        # Calculate aggregate metrics from channel data
        total_sessions = 0
        total_engaged = 0
        total_conversions = 0

        for row in sessions_data:
            s = int(row.get("sessions", 0) or 0)
            e = int(row.get("engagedSessions", 0) or 0)
            c = int(row.get("conversions", 0) or 0)
            total_sessions += s
            total_engaged += e
            total_conversions += c

        engagement_rate = total_engaged / total_sessions if total_sessions > 0 else 0

        # Get previous snapshot for delta calculation
        prev = conn.execute(
            """SELECT * FROM metrics_snapshots
            WHERE client_id=? AND period_label=?
            ORDER BY created_at DESC LIMIT 1""",
            (client_id, f"Last {days} days")
        ).fetchone()

        prev_clicks = prev["clicks"] if prev else 0
        prev_impressions = prev["impressions"] if prev else 0
        prev_ctr = prev["ctr"] if prev else 0
        prev_rank = prev["avg_rank"] if prev else 0

        # Store metrics snapshot
        metrics = {
            "sessions": total_sessions,
            "sessions_delta": total_sessions - prev_clicks,
            "engaged_sessions": total_engaged,
            "engaged_sessions_delta": total_engaged - prev_impressions,
            "engagement_rate": round(engagement_rate, 4),
            "engagement_rate_delta": round(engagement_rate - prev_ctr, 4),
            "avg_session_duration": 0,
            "avg_session_duration_delta": 0,
            "conversions": total_conversions,
        }

        mid = store_metrics_snapshot(conn, client_id, metrics, f"Last {days} days")
        results["metrics_stored"] = 1

        # Store opportunities from landing pages
        for page_row in landing_pages:
            page_url = page_row.get("landingPagePlusQueryString", "")
            if not page_url or page_url == "(not set)":
                continue
            # Only include pages with any traffic
            if int(page_row.get("sessions", 0) or 0) >= 1:
                oid = store_opportunity(conn, client_id, page_row, total_sessions)
                results["opportunities_stored"] += 1

        # Generate opportunities from GSC data
        print(f"  Generating GSC opportunities...")
        gsc_opps = generate_gsc_opportunities(conn, client_id, days)
        if gsc_opps:
            print(f"  ✓ {gsc_opps} GSC opportunities created/updated")
        results["opportunities_stored"] += gsc_opps

        # Calculate and store health score
        print(f"  Calculating health score...")
        try:
            health = calculate_client_health(conn, client_id)
            store_health_score(conn, health)
            print(f"  ✓ Health score: {health['score']}/100 ({health['status']})")
            results["health_score"] = health["score"]
            results["health_status"] = health["status"]
        except Exception as e:
            print(f"  ⚠ Health score calc failed: {e}", file=sys.stderr)

        # Store activity event
        summary = (
            f"Data pull complete: {total_sessions} sessions (GA4), "
            f"{total_conversions} conversions, {gsc_opps} GSC opps. "
            f"{results['opportunities_stored']} total opportunities updated."
        )
        next_action = "Review updated opportunities and metrics in dashboard."
        store_activity_event(conn, client_id, summary, next_action)

        conn.commit()

    return results


# ── Entry point ──────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(description="GA4 Data Pull for SEO OS Dashboard")
    parser.add_argument("--client", help="Specific client ID to pull (default: all connected)")
    parser.add_argument("--days", type=int, default=28, help="Lookback window in days (default: 28)")
    parser.add_argument("--json", action="store_true", help="Output JSON instead of human-readable")
    args = parser.parse_args()

    print(f"GA4 Data Pull — {args.days} day window")
    print(f"{'=' * 50}")

    with connect() as conn:
        clients = get_clients_with_ga4(conn)

        if args.client:
            clients = [c for c in clients if c["id"] == args.client]
            if not clients:
                print(f"ERROR: Client '{args.client}' not found or not GA4-connected", file=sys.stderr)
                sys.exit(1)

        if not clients:
            print("No clients with GA4 connected found.", file=sys.stderr)
            sys.exit(1)

    print(f"Clients: {[c['id'] for c in clients]}")
    print()

    all_results = []
    for client in clients:
        property_id = client["property_id"]
        if not property_id:
            print(f"SKIP: {client['id']} has no GA4 property ID", file=sys.stderr)
            continue
        print(f"Processing: {client['name']} ({client['id']}) — Property: {property_id}")
        try:
            # Find best available window (falls back if no data for requested days)
            actual_days = find_max_available_days(property_id, args.days)
            if actual_days == 0:
                print(f"  ✗ No GA4 data available for property {property_id}", file=sys.stderr)
                continue
            if actual_days < args.days:
                print(f"  ℹ Only {actual_days} days of data available (requested {args.days})")
            gsc_site = get_gsc_site_for_client(client["id"], client.get("domain", ""))
            results = pull_client_data(client["id"], property_id, actual_days, gsc_site_url=gsc_site)
            all_results.append(results)
            print(f"  ✓ {results['metrics_stored']} metrics snapshot stored")
            print(f"  ✓ {results['opportunities_stored']} opportunities updated")
            print(f"  ✓ {len(results['landing_pages'])} landing pages analyzed")
            print(f"  ✓ {len(results['search_queries'])} search queries pulled")
            if results.get("gsc_rows"):
                print(f"  ✓ {results['gsc_rows']} GSC query×page rows stored")
        except Exception as e:
            print(f"  ✗ Error: {e}", file=sys.stderr)
            all_results.append({
                "client_id": client["id"],
                "error": str(e),
            })

    if args.json:
        print(json.dumps(all_results, indent=2, default=str))
    else:
        print(f"\n{'=' * 50}")
        print("GA4 Data Pull complete.")
        for r in all_results:
            if "error" in r:
                print(f"  {r['client_id']}: ERROR — {r['error']}")
            else:
                print(
                    f"  {r['client_id']}: "
                    f"{r.get('sessions_data', [{}])[0].get('sessions', 0) if r.get('sessions_data') else 0} sessions, "
                    f"{r['opportunities_stored']} opportunities"
                )


if __name__ == "__main__":
    main()
