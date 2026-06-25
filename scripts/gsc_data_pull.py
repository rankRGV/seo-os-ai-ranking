#!/usr/bin/env python3
"""Google Search Console data pull for SEO OS Dashboard."""

import json
import os
import sys
import uuid
import sqlite3
import urllib.request
import urllib.parse
from datetime import datetime, timezone, timedelta
from pathlib import Path

DB_PATH = os.environ.get("SEO_OS_DB_PATH", str(Path(__file__).resolve().parent.parent / "data" / "seo-os.sqlite"))
GSC_API_BASE = "https://www.googleapis.com/webmasters/v3/sites"

# Client ID → GSC site URL mapping (from clients table)
def get_gsc_site_for_client(client_id, domain):
    """Derive GSC site URL from client domain."""
    if domain.startswith("http"):
        # Convert https://example.com to sc-domain:example.com
        return "sc-domain:" + domain.split("//")[1].rstrip("/")
    return "sc-domain:" + domain.rstrip("/")


def gsc_request(token, site_url, payload):
    """Make a GSC searchAnalytics.query request with auto token refresh."""
    # URL-encode site_url (e.g. "https://rankrgv.com/" → "https%3A%2F%2Frankrgv.com%2F")
    encoded_site = urllib.parse.quote(site_url, safe="")
    url = f"{GSC_API_BASE}/{encoded_site}/searchAnalytics/query"
    data = json.dumps(payload).encode()
    req = urllib.request.Request(url, data=data, method="POST", headers={
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json"
    })
    try:
        resp = urllib.request.urlopen(req, timeout=30)
        return json.loads(resp.read())
    except Exception as e:
        err_body = ""
        if hasattr(e, 'read'):
            try:
                err_body = e.read().decode()[:200]
            except:
                pass
        code = getattr(e, 'code', '?')
        # If 401, try refreshing token once
        if code == 401:
            token = refresh_token()
            req2 = urllib.request.Request(url, data=data, method="POST", headers={
                "Authorization": f"Bearer {token}",
                "Content-Type": "application/json"
            })
            try:
                resp2 = urllib.request.urlopen(req2, timeout=30)
                return json.loads(resp2.read())
            except Exception as e2:
                print(f"  GSC API error after refresh ({getattr(e2, 'code', '?')}): {str(e2)[:100]}", file=sys.stderr)
                return None
        print(f"  GSC API error ({code}): {err_body}", file=sys.stderr)
        return None


def pull_gsc_data(token, site_url, days=28, row_limit=250):
    """Pull search analytics data from GSC.
    
    Returns both query×page breakdown AND daily totals.
    The query×page data is subject to API row limits (250 max),
    so we also pull daily totals separately for accurate aggregate metrics.
    """
    end_date = datetime.now(timezone.utc).date()
    start_date = end_date - timedelta(days=days)

    # 1. Pull daily totals (accurate aggregate numbers)
    daily_payload = {
        "startDate": start_date.isoformat(),
        "endDate": end_date.isoformat(),
        "dimensions": ["date"],
        "rowLimit": 250,
        "startRow": 0,
        "dataState": "final"
    }
    daily_result = gsc_request(token, site_url, daily_payload)
    daily_clicks = 0
    daily_impressions = 0
    if daily_result and "rows" in daily_result:
        for row in daily_result["rows"]:
            daily_clicks += int(row.get("clicks", 0))
            daily_impressions += int(row.get("impressions", 0))

    # 2. Pull query×page breakdown (for the opportunities table)
    all_rows = []
    start_row = 0
    while True:
        qp_payload = {
            "startDate": start_date.isoformat(),
            "endDate": end_date.isoformat(),
            "dimensions": ["query", "page"],
            "rowLimit": min(row_limit, 250),
            "startRow": start_row,
            "dataState": "final"
        }
        result = gsc_request(token, site_url, qp_payload)
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


def store_gsc_data(conn, client_id, site_url, rows):
    """Store GSC data in gsc_performance table."""
    now = datetime.now(timezone.utc).replace(microsecond=0).isoformat()
    today = datetime.now(timezone.utc).date().isoformat()

    # Delete old data for this client+date to avoid duplicates
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


def get_clients_with_gsc(conn):
    """Get clients with GSC connected."""
    clients = conn.execute(
        "SELECT * FROM clients WHERE gsc_status='connected'"
    ).fetchall()
    return [dict(c) for c in clients] if clients else []


def refresh_token():
    """Refresh the Google OAuth token if it's close to expiry."""
    with open("/root/.hermes/google_token.json") as f:
        token = json.load(f)
    if "refresh_token" not in token:
        return token
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
    try:
        resp = urllib.request.urlopen(req, timeout=10)
        result = json.loads(resp.read())
        token["token"] = result["access_token"]
        with open("/root/.hermes/google_token.json", "w") as f:
            json.dump(token, f)
    except Exception as e:
        print(f"Token refresh warning: {e}", file=sys.stderr)
    return token


def get_token():
    """Load Google OAuth token, refreshing if possible."""
    return refresh_token()


def main():
    import argparse
    parser = argparse.ArgumentParser(description="GSC Data Pull")
    parser.add_argument("--client", help="Specific client ID")
    parser.add_argument("--days", type=int, default=28, help="Lookback days")
    args = parser.parse_args()

    token = get_token()
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row

    clients = get_clients_with_gsc(conn)
    if args.client:
        clients = [c for c in clients if c["id"] == args.client]
        if not clients:
            print(f"ERROR: Client '{args.client}' not found or GSC not connected", file=sys.stderr)
            sys.exit(1)

    if not clients:
        print("No clients with GSC connected found.")
        return

    print(f"GSC Data Pull — {args.days} day window")
    print("=" * 50)

    total = 0
    for client in clients:
        site_url = get_gsc_site_for_client(client["id"], client["domain"])
        print(f"\nProcessing: {client['name']} ({client['id']}) — {site_url}")

        result = pull_gsc_data(token, site_url, days=args.days)
        if result["query_page_rows"]:
            stored = store_gsc_data(conn, client["id"], site_url, result["query_page_rows"])
            total += stored
            print(f"  ✓ {stored} query×page rows stored")
            print(f"  ✓ Totals: {result['total_clicks']} clicks, {result['total_impressions']} impressions")
            
            # Update metrics_snapshots — aggregate from gsc_performance for accurate totals
            # (The GSC daily-dimension API returns unreliable aggregates, so we sum query×page rows)
            client_id = client["id"]
            agg = conn.execute(
                "SELECT COALESCE(SUM(clicks),0) as total_clicks, COALESCE(SUM(impressions),0) as total_impressions FROM gsc_performance WHERE client_id=?",
                (client_id,)
            ).fetchone()
            total_clicks = agg["total_clicks"]
            total_impressions = agg["total_impressions"]
            avg_pos = conn.execute(
                "SELECT AVG(position) FROM gsc_performance WHERE client_id=? AND position > 0",
                (client_id,)
            ).fetchone()
            avg_rank = round(avg_pos[0], 1) if avg_pos[0] else 0
            ctr = round(total_clicks / total_impressions, 4) if total_impressions > 0 else 0

            existing = conn.execute(
                "SELECT id FROM metrics_snapshots WHERE client_id=? AND period_label='Last 28 days'",
                (client_id,)
            ).fetchone()
            if existing:
                conn.execute(
                    "UPDATE metrics_snapshots SET clicks=?, impressions=?, ctr=?, avg_rank=? WHERE id=?",
                    (total_clicks, total_impressions, ctr, avg_rank, existing["id"])
                )
            else:
                import uuid as _uuid
                mid = f"metric_{_uuid.uuid4().hex[:10]}"
                conn.execute(
                    "INSERT INTO metrics_snapshots VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)",
                    (mid, client_id, "Last 28 days",
                     total_clicks, 0,
                     total_impressions, 0,
                     ctr, 0, avg_rank, 0, 0,
                     datetime.now(timezone.utc).replace(microsecond=0).isoformat())
                )
        else:
            print(f"  ✗ No GSC data returned")

    conn.commit()
    print(f"\n{'=' * 50}")
    print(f"GSC Data Pull complete. Total rows: {total}")
    conn.close()


if __name__ == "__main__":
    main()
