#!/usr/bin/env python3
"""Google Business Profile health monitor for SEO OS Dashboard.

Tracks GBP metrics for local businesses: views, searches, actions (calls,
directions, website clicks), review score, and posting activity.

Requires: Google Business Profile API enabled + OAuth with
https://www.googleapis.com/auth/business.manage scope.
"""

import json
import os
import sqlite3
import sys
from datetime import datetime, timezone, timedelta
from pathlib import Path

DB_PATH = os.environ.get("SEO_OS_DB_PATH", str(Path(__file__).resolve().parent / "data" / "seo-os.sqlite"))

# ─── Schema ──────────────────────────────────────────────────────────────────

SCHEMA_SQL = """
CREATE TABLE IF NOT EXISTS gbp_health (
    id TEXT PRIMARY KEY,
    client_id TEXT NOT NULL,
    date TEXT NOT NULL,
    views_search INTEGER DEFAULT 0,
    views_maps INTEGER DEFAULT 0,
    searches_direct INTEGER DEFAULT 0,
    searches_discovery INTEGER DEFAULT 0,
    actions_website INTEGER DEFAULT 0,
    actions_directions INTEGER DEFAULT 0,
    actions_call INTEGER DEFAULT 0,
    actions_message INTEGER DEFAULT 0,
    review_average REAL DEFAULT 0,
    review_count INTEGER DEFAULT 0,
    posts_published INTEGER DEFAULT 0,
    photos_count INTEGER DEFAULT 0,
    fetched_at TEXT NOT NULL,
    status TEXT NOT NULL DEFAULT 'ok',
    FOREIGN KEY (client_id) REFERENCES clients(id)
);

CREATE INDEX IF NOT EXISTS idx_gbp_client_date ON gbp_health(client_id, date);
CREATE INDEX IF NOT EXISTS idx_gbp_status ON gbp_health(status);
"""


def init_gbp():
    """Create GBP health table if it doesn't exist."""
    conn = sqlite3.connect(DB_PATH)
    conn.executescript(SCHEMA_SQL)
    conn.commit()
    conn.close()


def now_iso():
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def uid(prefix="gbp"):
    import uuid
    return f"{prefix}_{uuid.uuid4().hex[:10]}"


# ─── Local client detection ──────────────────────────────────────────────────

def get_local_clients(conn):
    """Get clients marked as 'local' type — these have GBP profiles."""
    rows = conn.execute(
        "SELECT id, name, domain FROM clients WHERE client_type='local' AND status IN ('active','setup')"
    ).fetchall()
    return [dict(r) for r in rows]


# ─── GBP API fetch ────────────────────────────────────────────────────────────

def fetch_gbp_metrics(client_id, days=28):
    """Fetch GBP metrics for a client.
    
    Returns dict with metrics or None if API not configured.
    Tries: 1) Existing OAuth token, 2) API key, 3) Service account.
    """
    try:
        import googleapiclient.discovery
    except ImportError:
        print(f"  GBP library not installed — run: pip install google-api-python-client google-auth-httplib2 google-auth-oauthlib")
        return None

    # ─── Try 1: Use existing OAuth token ───────────────────────────────────
    token_path = Path("/root/.hermes/google_token.json")
    if token_path.exists():
        try:
            with open(token_path) as f:
                token_data = json.load(f)

            from google.oauth2.credentials import Credentials
            creds = Credentials(
                token=token_data["token"],
                refresh_token=token_data.get("refresh_token"),
                token_uri=token_data.get("token_uri", "https://oauth2.googleapis.com/token"),
                client_id=token_data.get("client_id"),
                client_secret=token_data.get("client_secret"),
                scopes=token_data.get("scopes", []) + ["https://www.googleapis.com/auth/business.manage"]
            )
            client = googleapiclient.discovery.build(
                "mybusinessbusinessinformation", "v1", credentials=creds
            )
            print("  Using existing OAuth token")
            return _fetch_metrics(client, client_id, days)
        except Exception as e:
            print(f"  OAuth token failed: {e}")

    # ─── Try 2: Use API key ────────────────────────────────────────────────
    api_key_path = Path("/root/.hermes/google_token.json")
    try:
        # Try to find API key in environment or hermes config
        import os
        api_key = os.environ.get("GOOGLE_API_KEY", "")
        if not api_key:
            # Try to extract from hermes config
            hermes_config = Path(os.path.expanduser("~/.hermes/config.yaml"))
            if hermes_config.exists():
                content = hermes_config.read_text()
                import re
                m = re.search(r'api_key:\s*["\']?(AIza[^\s"\']+)', content)
                if m:
                    api_key = m.group(1)
        if api_key:
            client = googleapiclient.discovery.build(
                "mybusinessbusinessinformation", "v1", developerKey=api_key
            )
            print("  Using API key")
            return _fetch_metrics(client, client_id, days)
    except Exception as e:
        print(f"  API key failed: {e}")

    # ─── Try 3: Service account ────────────────────────────────────────────
    cred_path = Path("data/gbp_credentials.json")
    if cred_path.exists():
        try:
            from google.oauth2 import service_account
            credentials = service_account.Credentials.from_service_account_file(
                str(cred_path),
                scopes=["https://www.googleapis.com/auth/business.manage"]
            )
            client = googleapiclient.discovery.build(
                "mybusinessbusinessinformation", "v1", credentials=credentials
            )
            print("  Using service account")
            return _fetch_metrics(client, client_id, days)
        except Exception as e:
            print(f"  Service account failed: {e}")

    print("  No valid credentials found for GBP API")
    return None


def _fetch_metrics(client, client_id, days):
    """Execute the actual GBP API calls using a built client."""

    # Fetch metrics
    try:
        # Get location
        account_name = f"accounts/{client_id}"
        locations = client.accounts().locations().list(parent=account_name).execute()
        location_names = [loc["name"] for loc in locations.get("locations", [])]

        if not location_names:
            return None

        end_date = datetime.now(timezone.utc)
        start_date = end_date - timedelta(days=days)

        metrics = {
            "views_search": 0,
            "views_maps": 0,
            "searches_direct": 0,
            "searches_discovery": 0,
            "actions_website": 0,
            "actions_directions": 0,
            "actions_call": 0,
            "actions_message": 0,
            "review_average": 0,
            "review_count": 0,
            "posts_published": 0,
            "photos_count": 0,
        }

        for loc in location_names:
            # Get metric time series
            request = client.accounts().locations().reportInsights(
                name=loc,
                body={
                    "metricRequests": [
                        {"metric": "QUERIES_DIRECT"},
                        {"metric": "QUERIES_DISCOVERY"},
                        {"metric": "VIEWS_SEARCH"},
                        {"metric": "VIEWS_MAPS"},
                        {"metric": "ACTIONS_WEBSITE"},
                        {"metric": "ACTIONS_DIRECTIONS"},
                        {"metric": "ACTIONS_PHONE"},
                        {"metric": "ACTIONS_MESSAGE"},
                    ],
                    "timeRange": {
                        "startTime": start_date.strftime("%Y-%m-%dT%H:%M:%S") + "Z",
                        "endTime": end_date.strftime("%Y-%m-%dT%H:%M:%S") + "Z",
                    }
                }
            )
            response = request.execute()

            for series in response.get("locationMetricValues", []):
                metric = series.get("metric", "")
                values = series.get("totalValue", {})
                val = float(values.get("value", 0) or 0)

                if metric == "QUERIES_DIRECT":
                    metrics["searches_direct"] += int(val)
                elif metric == "QUERIES_DISCOVERY":
                    metrics["searches_discovery"] += int(val)
                elif metric == "VIEWS_SEARCH":
                    metrics["views_search"] += int(val)
                elif metric == "VIEWS_MAPS":
                    metrics["views_maps"] += int(val)
                elif metric == "ACTIONS_WEBSITE":
                    metrics["actions_website"] += int(val)
                elif metric == "ACTIONS_DIRECTIONS":
                    metrics["actions_directions"] += int(val)
                elif metric == "ACTIONS_PHONE":
                    metrics["actions_call"] += int(val)
                elif metric == "ACTIONS_MESSAGE":
                    metrics["actions_message"] += int(val)

            # Get reviews
            reviews_resp = client.accounts().locations().reviews().list(
                parent=loc, pageSize=100
            ).execute()
            reviews = reviews_resp.get("reviews", [])
            if reviews:
                total_score = sum(r.get("starRating", 0) for r in reviews)
                metrics["review_average"] = int(round(total_score / len(reviews), 1) * 10) / 10.0
                metrics["review_count"] = len(reviews)

        return metrics

    except Exception as e:
        print(f"  GBP API fetch failed for {client_id}: {e}")
        return None


# ─── Fallback: generate demo GBP data for testing ────────────────────────────

def generate_demo_gbp_data(client_id, days=28):
    """Generate realistic demo GBP data when API is not connected.
    Used for development/testing without live API credentials."""
    import random
    random.seed(hash(client_id) % 2**32)

    base_views = random.randint(50, 300)
    base_searches = random.randint(20, 120)

    return {
        "views_search": base_views,
        "views_maps": int(base_views * 0.6),
        "searches_direct": int(base_searches * 0.4),
        "searches_discovery": int(base_searches * 0.6),
        "actions_website": random.randint(5, 40),
        "actions_directions": random.randint(10, 60),
        "actions_call": random.randint(3, 25),
        "actions_message": random.randint(0, 10),
        "review_average": round(random.uniform(3.5, 5.0), 1),
        "review_count": random.randint(5, 80),
        "posts_published": random.randint(0, 8),
        "photos_count": random.randint(5, 45),
    }


# ─── Store metrics ────────────────────────────────────────────────────────────

def store_gbp_metrics(conn, client_id, metrics, demo=False):
    """Store GBP metrics for a client."""
    t = now_iso()
    conn.execute(
        """INSERT INTO gbp_health
           (id, client_id, date, views_search, views_maps,
            searches_direct, searches_discovery,
            actions_website, actions_directions, actions_call, actions_message,
            review_average, review_count, posts_published, photos_count,
            fetched_at, status)
           VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
        (
            uid(), client_id,
            datetime.now(timezone.utc).strftime("%Y-%m-%d"),
            metrics["views_search"], metrics["views_maps"],
            metrics["searches_direct"], metrics["searches_discovery"],
            metrics["actions_website"], metrics["actions_directions"],
            metrics["actions_call"], metrics["actions_message"],
            metrics["review_average"], metrics["review_count"],
            metrics["posts_published"], metrics["photos_count"],
            t, "demo" if demo else "ok"
        )
    )
    conn.commit()


# ─── Health score calculation ─────────────────────────────────────────────────

def calculate_gbp_health_score(metrics):
    """Calculate a 0-100 GBP health score based on metrics.
    
    Scoring weights:
    - Actions (calls + website + directions): 30%
    - Views growth potential: 20%
    - Review score: 25%
    - Content freshness (posts + photos): 25%
    """
    if not metrics:
        return 50  # neutral

    # Actions score (0-100): more actions = better, capped at 100
    total_actions = (
        metrics["actions_call"] * 3 +
        metrics["actions_website"] * 2 +
        metrics["actions_directions"] * 1.5 +
        metrics["actions_message"] * 1
    )
    actions_score = min(100, total_actions * 2)

    # Views score: logarithmic scale
    total_views = metrics["views_search"] + metrics["views_maps"]
    import math
    views_score = min(100, int(math.log1p(total_views) * 15))

    # Review score: direct mapping (1-5 → 20-100)
    review_score = min(100, max(0, (metrics["review_average"] / 5.0) * 100))

    # Content score
    content_score = min(100, metrics["posts_published"] * 10 + metrics["photos_count"] * 1)

    # Weighted total
    total = int(
        actions_score * 0.30 +
        views_score * 0.20 +
        review_score * 0.25 +
        content_score * 0.25
    )
    return max(0, min(100, total))


# ─── Status determination ────────────────────────────────────────────────────

def determine_status(metrics, score):
    """Determine GBP health status."""
    if not metrics:
        return "not_connected"
    if score >= 70:
        return "green"
    elif score >= 40:
        return "yellow"
    else:
        return "red"


# ─── Main run ─────────────────────────────────────────────────────────────────

def run_gbp_monitor(demo=True):
    """Run GBP health check for all local clients."""
    init_gbp()
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row

    clients = get_local_clients(conn)
    if not clients:
        print("No local clients found. Add clients with client_type='local' first.")
        conn.close()
        return

    print(f"Checking GBP health for {len(clients)} local client(s)...")

    for client in clients:
        print(f"\n  {client['name']} ({client['id']}):")

        # Try live API first
        metrics = fetch_gbp_metrics(client["id"])
        is_demo = False

        if metrics is None:
            # Fall back to demo data
            metrics = generate_demo_gbp_data(client["id"])
            is_demo = True
            print(f"    Using demo data (API not connected)")

        # Calculate score
        score = calculate_gbp_health_score(metrics)
        status = determine_status(metrics, score)

        # Store
        store_gbp_metrics(conn, client["id"], metrics, demo=is_demo)

        print(f"    Views: {metrics['views_search'] + metrics['views_maps']}")
        print(f"    Searches: {metrics['searches_direct'] + metrics['searches_discovery']}")
        print(f"    Calls: {metrics['actions_call']} | Website: {metrics['actions_website']}")
        print(f"    Reviews: {metrics['review_average']}⭐ ({metrics['review_count']})")
        print(f"    Health Score: {score}/100 ({status})")

    conn.close()
    print(f"\nGBP health check complete.")


def get_latest_gbp_metrics(conn, client_id):
    """Get the most recent GBP metrics for a client."""
    row = conn.execute(
        "SELECT * FROM gbp_health WHERE client_id=? ORDER BY date DESC LIMIT 1",
        (client_id,)
    ).fetchone()
    return dict(row) if row else None


def get_gbp_trend(conn, client_id, days=28):
    """Get GBP metric trend over time."""
    rows = conn.execute(
        """SELECT date, views_search + views_maps as total_views,
                  actions_call + actions_website + actions_directions as total_actions,
                  review_average, review_count
           FROM gbp_health
           WHERE client_id=?
           ORDER BY date DESC
           LIMIT ?""",
        (client_id, days)
    ).fetchall()
    return [dict(r) for r in rows]


if __name__ == "__main__":
    live_mode = "--live" in sys.argv
    run_gbp_monitor(demo=not live_mode)
