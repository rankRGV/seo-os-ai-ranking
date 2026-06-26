#!/usr/bin/env python3
"""SEO OS template dashboard server.

Stdlib-only on purpose: easy to run on a VPS without npm, Docker, or a hosted
DB. The first run creates a local SQLite database with fake demo data only.
Do not commit generated data/ databases from real installs.
"""
from __future__ import annotations

import argparse
import datetime as dt
import json
import os
import re
import sqlite3
import sys
import uuid
from http import HTTPStatus
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.request import Request, urlopen
from urllib.error import HTTPError as _HTTPError, URLError as _URLError
from urllib.parse import parse_qs, urlparse, urlencode

ROOT = Path(__file__).resolve().parent
STATIC = ROOT / "static"
DB_PATH = Path(os.environ.get("SEO_OS_DB_PATH", str(ROOT / "data" / "seo-os.sqlite")))
UTC = dt.timezone.utc

SCHEMA = """
PRAGMA journal_mode=WAL;
CREATE TABLE IF NOT EXISTS clients (
  id TEXT PRIMARY KEY,
  name TEXT NOT NULL,
  domain TEXT NOT NULL,
  role TEXT NOT NULL,
  client_type TEXT NOT NULL DEFAULT 'local',
  status TEXT NOT NULL,
  health_score INTEGER NOT NULL,
  hermes_profile TEXT NOT NULL,
  channel_target TEXT NOT NULL,
  discord_thread_id TEXT NOT NULL DEFAULT '',
  gsc_status TEXT NOT NULL,
  ga4_status TEXT NOT NULL,
  repo_status TEXT NOT NULL,
  zernio_status TEXT NOT NULL DEFAULT 'not_connected',
  workspace TEXT NOT NULL,
  created_at TEXT NOT NULL,
  updated_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS metrics_snapshots (
  id TEXT PRIMARY KEY,
  client_id TEXT NOT NULL,
  period_label TEXT NOT NULL,
  clicks INTEGER NOT NULL,
  clicks_delta INTEGER NOT NULL,
  impressions INTEGER NOT NULL,
  impressions_delta INTEGER NOT NULL,
  ctr REAL NOT NULL,
  ctr_delta REAL NOT NULL,
  avg_rank REAL NOT NULL,
  avg_rank_delta REAL NOT NULL,
  conversions INTEGER NOT NULL DEFAULT 0,
  created_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS opportunities (
  id TEXT PRIMARY KEY,
  client_id TEXT NOT NULL,
  page TEXT NOT NULL,
  problem TEXT NOT NULL,
  opportunity_type TEXT NOT NULL,
  priority TEXT NOT NULL,
  impact TEXT NOT NULL,
  confidence TEXT NOT NULL,
  effort TEXT NOT NULL,
  impressions INTEGER NOT NULL,
  clicks INTEGER NOT NULL,
  ctr REAL NOT NULL,
  position REAL NOT NULL,
  recommended_workflow TEXT NOT NULL,
  status TEXT NOT NULL,
  evidence_json TEXT NOT NULL DEFAULT '{}',
  created_at TEXT NOT NULL,
  updated_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS approval_requests (
  id TEXT PRIMARY KEY,
  client_id TEXT NOT NULL,
  title TEXT NOT NULL,
  type TEXT NOT NULL,
  risk TEXT NOT NULL,
  status TEXT NOT NULL,
  requested_action TEXT NOT NULL,
  evidence TEXT NOT NULL,
  source_url TEXT NOT NULL,
  agent_confidence TEXT NOT NULL,
  production_gate TEXT NOT NULL,
  created_at TEXT NOT NULL,
  updated_at TEXT NOT NULL,
  decision_note TEXT NOT NULL DEFAULT ''
);
CREATE TABLE IF NOT EXISTS agent_tasks (
  id TEXT PRIMARY KEY,
  client_id TEXT NOT NULL,
  title TEXT NOT NULL,
  priority TEXT NOT NULL,
  status TEXT NOT NULL,
  source TEXT NOT NULL,
  owner_profile TEXT NOT NULL,
  page_asset TEXT NOT NULL,
  next_action TEXT NOT NULL,
  notes TEXT NOT NULL DEFAULT '',
  created_at TEXT NOT NULL,
  updated_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS managed_jobs (
  id TEXT PRIMARY KEY,
  client_id TEXT NOT NULL,
  name TEXT NOT NULL,
  job_type TEXT NOT NULL,
  cadence TEXT NOT NULL,
  next_run TEXT NOT NULL,
  last_run TEXT NOT NULL,
  status TEXT NOT NULL,
  model_policy TEXT NOT NULL,
  data_sources TEXT NOT NULL,
  latest_result TEXT NOT NULL,
  managed_by TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS activity_events (
  id TEXT PRIMARY KEY,
  client_id TEXT NOT NULL,
  source TEXT NOT NULL,
  event_type TEXT NOT NULL,
  status TEXT NOT NULL,
  summary TEXT NOT NULL,
  next_action TEXT NOT NULL,
  artifact TEXT NOT NULL DEFAULT '',
  created_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS artifacts (
  id TEXT PRIMARY KEY,
  client_id TEXT NOT NULL,
  title TEXT NOT NULL,
  artifact_type TEXT NOT NULL,
  status TEXT NOT NULL,
  summary TEXT NOT NULL,
  path_or_url TEXT NOT NULL,
  updated_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS settings (
  key TEXT PRIMARY KEY,
  value TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS gsc_performance (
  id TEXT PRIMARY KEY,
  client_id TEXT NOT NULL,
  site_url TEXT NOT NULL DEFAULT '',
  query TEXT NOT NULL DEFAULT '',
  page TEXT NOT NULL DEFAULT '',
  clicks INTEGER NOT NULL DEFAULT 0,
  impressions INTEGER NOT NULL DEFAULT 0,
  ctr REAL NOT NULL DEFAULT 0,
  position REAL NOT NULL DEFAULT 0,
  date TEXT NOT NULL,
  created_at TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_gsc_client ON gsc_performance(client_id);
CREATE INDEX IF NOT EXISTS idx_gsc_date ON gsc_performance(client_id, date);
CREATE INDEX IF NOT EXISTS idx_gsc_created ON gsc_performance(created_at);
CREATE TABLE IF NOT EXISTS health_snapshots (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  client_id TEXT NOT NULL,
  score INTEGER NOT NULL,
  status TEXT NOT NULL,
  components_json TEXT NOT NULL DEFAULT '{}',
  created_at TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_health_snap_client ON health_snapshots(client_id, created_at);
CREATE TABLE IF NOT EXISTS client_health (
  id TEXT PRIMARY KEY,
  client_id TEXT NOT NULL UNIQUE,
  score INTEGER NOT NULL DEFAULT 50,
  status TEXT NOT NULL DEFAULT 'yellow',
  components_json TEXT NOT NULL DEFAULT '{}',
  pages_ranking INTEGER NOT NULL DEFAULT 0,
  high_priority_opps INTEGER NOT NULL DEFAULT 0,
  total_opportunities INTEGER NOT NULL DEFAULT 0,
  updated_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS notification_queue (
  id TEXT PRIMARY KEY,
  client_id TEXT NOT NULL,
  thread_id TEXT NOT NULL DEFAULT '',
  message TEXT NOT NULL,
  created_at TEXT NOT NULL,
  sent_at TEXT NOT NULL DEFAULT '',
  retries INTEGER NOT NULL DEFAULT 0
);
"""


def now() -> str:
    return dt.datetime.now(UTC).replace(microsecond=0).isoformat()


def uid(prefix: str) -> str:
    return f"{prefix}_{uuid.uuid4().hex[:10]}"


def backup_db() -> str | None:
    """Create a timestamped backup of the SQLite DB. Returns backup path or None."""
    import shutil
    db = Path(DB_PATH)
    if not db.exists():
        return None
    backup_dir = Path("backups")
    backup_dir.mkdir(exist_ok=True)
    ts = dt.datetime.now(dt.timezone.utc).strftime("%Y%m%d_%H%M%S")
    backup_path = backup_dir / f"seo-os_{ts}.sqlite"
    shutil.copy2(db, backup_path)
    # Keep only last 7 backups
    backups = sorted(backup_dir.glob("seo-os_*.sqlite"), key=lambda p: p.stat().st_mtime)
    for old in backups[:-7]:
        old.unlink()
    return str(backup_path)


def ensure_schema(conn: sqlite3.Connection) -> None:
    """Create all required tables/indexes if missing. Safe to call repeatedly."""
    conn.executescript(SCHEMA)
    # Plugin tables not in upstream SCHEMA
    conn.executescript("""
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
        CREATE TABLE IF NOT EXISTS health_snapshots (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            client_id TEXT NOT NULL,
            score INTEGER NOT NULL,
            status TEXT NOT NULL,
            components_json TEXT NOT NULL DEFAULT '{}',
            created_at TEXT NOT NULL
        );
        CREATE INDEX IF NOT EXISTS idx_health_snap_client ON health_snapshots(client_id, created_at);
    """)
    conn.commit()


def connect() -> sqlite3.Connection:
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def rows(conn: sqlite3.Connection, sql: str, params=()):
    return [dict(r) for r in conn.execute(sql, params).fetchall()]


def one(conn: sqlite3.Connection, sql: str, params: tuple = ()) -> dict | None:
    r = conn.execute(sql, params).fetchone()
    return dict(r) if r else None


def init_db(seed: bool = True) -> None:
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    with connect() as conn:
        ensure_schema(conn)
        if seed and one(conn, "SELECT id FROM clients LIMIT 1") is None:
            seed_db(conn)


def seed_db(conn: sqlite3.Connection) -> None:
    """Seed minimal starter data for real installs. Demo clients removed — add clients via onboarding."""
    t = now()
    settings = {
        "scheduler_mode": "SEO OS managed scheduler",
        "model_policy": "Data pulls use no model. Summaries and labeling use a cheap configured model. Strategic plans use a stronger model only after approval.",
        "safe_actions": "Dashboard approvals update state and create bounded tasks. Production actions need separate explicit approval.",
        "onboarding_goal": "Add clients via the Add Client form. Connect GSC, GA4 for each client. SEO OS handles managed refresh jobs and approval loops.",
    }
    conn.executemany("INSERT INTO settings VALUES (?,?)", settings.items())

    # System event for fresh start
    conn.execute(
        "INSERT INTO activity_events VALUES (?,?,?,?,?,?,?,?,?)",
        ("ev_1", "all", "dashboard", "system", "complete", "Dashboard initialized — add clients via the onboarding form to begin.", "", "", t)
    )


def generate_content_briefs(conn: sqlite3.Connection, client_id: str, days: int = 28) -> list:
    """Generate prioritized content briefs from GSC data for a client."""
    rows_data = conn.execute("""
        SELECT query,
               SUM(clicks) as total_clicks,
               SUM(impressions) as total_impressions,
               CASE WHEN SUM(impressions) > 0 THEN ROUND(CAST(SUM(clicks) AS REAL) / SUM(impressions), 4) ELSE 0 END as real_ctr,
               AVG(position) as avg_position,
               COUNT(DISTINCT page) as pages
        FROM gsc_performance
        WHERE client_id=?
        GROUP BY query
        HAVING total_impressions >= 5
        ORDER BY total_impressions DESC
    """, (client_id,)).fetchall()

    if not rows_data:
        return []

    briefs = []
    seen_queries = set()

    for row in rows_data:
        query = row["query"]
        clicks = row["total_clicks"]
        impressions = row["total_impressions"]
        avg_ctr = row["real_ctr"] or 0
        avg_pos = row["avg_position"] or 0

        # Skip if already has an opportunity
        existing = conn.execute(
            "SELECT id FROM opportunities WHERE client_id=? AND evidence_json LIKE '%gsc_pull%' AND problem LIKE ?",
            (client_id, f"%{query}%")
        ).fetchone()
        if existing:
            continue

        if avg_pos <= 10 and avg_ctr < 0.03 and impressions >= 10:
            priority = "high"
            opp_type = "Low CTR"
            suggestion = f"Title/meta optimization for '{query}' — you're on page 1 but not getting clicks"
            title_hint = f"Best {query.title()} [2026 Guide]"
        elif avg_pos > 10 and avg_pos <= 20 and impressions >= 10:
            priority = "medium"
            opp_type = "SERP gap"
            suggestion = f"Push '{query}' to page 1 — currently #{avg_pos:.0f}, content refresh or internal links could help"
            title_hint = f"Complete Guide to {query.title()}"
        elif avg_ctr < 0.01 and impressions >= 5:
            priority = "medium"
            opp_type = "SERP gap"
            suggestion = f"High impressions ({impressions}) near-zero CTR — SERP feature may be stealing clicks"
            title_hint = f"{query.title()} — What You Need to Know"
        elif clicks == 0 and impressions >= 3:
            priority = "low"
            opp_type = "Striking distance"
            suggestion = f"Impressions but no clicks — improve title tag appeal for '{query}'"
            title_hint = f"{query.title()}: Expert Tips & Guide"
        else:
            continue

        if query in seen_queries:
            continue
        seen_queries.add(query)

        # Get the top page for this query
        top_page_row = conn.execute(
            "SELECT page FROM gsc_performance WHERE client_id=? AND query=? ORDER BY impressions DESC LIMIT 1",
            (client_id, query)
        ).fetchone()
        top_page = top_page_row["page"] if top_page_row else ""

        briefs.append({
            "client_id": client_id,
            "query": query,
            "priority": priority,
            "opportunity_type": opp_type,
            "impressions": impressions,
            "clicks": clicks,
            "avg_ctr": round(avg_ctr, 4),
            "avg_position": round(avg_pos, 1),
            "suggested_title": title_hint,
            "brief": suggestion,
            "page": top_page,
        })

    priority_order = {"high": 0, "medium": 1, "low": 2}
    briefs.sort(key=lambda x: (priority_order[x["priority"]], -x["impressions"]))
    return briefs


def summary(conn: sqlite3.Connection, client_id: str = "all", days: int = 0, metric_days: int = 0) -> dict:
    clients = rows(conn, "SELECT * FROM clients ORDER BY CASE status WHEN 'active' THEN 0 ELSE 1 END, name")
    metrics = rows(conn, "SELECT * FROM metrics_snapshots")
    # Filter metrics by requested period if specified
    if metric_days > 0:
        period_label = f"Last {metric_days} days"
        filtered = [m for m in metrics if m.get("period_label") == period_label]
        metrics = filtered  # return empty if no data for this period yet
    elif days > 0:
        period_label = f"Last {days} days"
        filtered = [m for m in metrics if m.get("period_label") == period_label]
        metrics = filtered  # return empty if no data for this period yet
    approvals = rows(conn, "SELECT * FROM approval_requests ORDER BY CASE status WHEN 'needs_review' THEN 0 WHEN 'approved' THEN 1 ELSE 2 END, updated_at DESC")
    # Filter opportunities by date range if days specified
    if days > 0:
        from datetime import datetime, timezone, timedelta
        cutoff = (datetime.now(timezone.utc) - timedelta(days=days)).strftime("%Y-%m-%dT%H:%M:%S")
        opps = rows(conn, "SELECT * FROM opportunities WHERE created_at >= ? ORDER BY CASE priority WHEN 'high' THEN 0 WHEN 'medium' THEN 1 ELSE 2 END, impressions DESC", (cutoff,))
    else:
        opps = rows(conn, "SELECT * FROM opportunities ORDER BY CASE priority WHEN 'high' THEN 0 WHEN 'medium' THEN 1 ELSE 2 END, impressions DESC")
    tasks = rows(conn, "SELECT * FROM agent_tasks ORDER BY CASE priority WHEN 'high' THEN 0 WHEN 'medium' THEN 1 ELSE 2 END, updated_at DESC")
    jobs = rows(conn, "SELECT * FROM managed_jobs ORDER BY CASE status WHEN 'setup_needed' THEN 0 WHEN 'failed' THEN 1 ELSE 2 END, next_run")
    events = rows(conn, "SELECT * FROM activity_events ORDER BY created_at DESC LIMIT 30")
    artifacts = rows(conn, "SELECT * FROM artifacts ORDER BY updated_at DESC")
    gsc_rows = rows(conn, "SELECT client_id, query, page, SUM(clicks) as clicks, SUM(impressions) as impressions, AVG(ctr) as ctr, AVG(position) as position FROM gsc_performance GROUP BY client_id, query, page ORDER BY impressions DESC LIMIT 50")
    gsc_total = one(conn, "SELECT COUNT(DISTINCT query) as q, COALESCE(SUM(clicks),0) as c, COALESCE(SUM(impressions),0) as i FROM gsc_performance")
    settings = {r["key"]: r["value"] for r in conn.execute("SELECT * FROM settings")}

    def match(row: dict) -> bool:
        return client_id == "all" or row.get("client_id") == client_id

    visible_clients = clients if client_id == "all" else [c for c in clients if c["id"] == client_id]
    data = {
        "generated_at": now(),
        "active_client": client_id,
        "clients": clients,
        "visible_clients": visible_clients,
        "metrics": [m for m in metrics if client_id == "all" or m["client_id"] == client_id],
        "approvals": [a for a in approvals if match(a)],
        "opportunities": [o for o in opps if match(o)],
        "tasks": [t for t in tasks if match(t)],
        "jobs": [j for j in jobs if match(j)],
        "events": [e for e in events if match(e)],
        "artifacts": [a for a in artifacts if match(a)],
        "gsc": [g for g in gsc_rows if match(g)],
        "gsc_total": {"queries": gsc_total["q"], "clicks": gsc_total["c"], "impressions": gsc_total["i"]},
        "settings": settings,
    }
    # Client health scores
    health_rows = rows(conn, "SELECT client_id, score, status, pages_ranking, high_priority_opps, total_opportunities, updated_at FROM client_health ORDER BY score DESC")
    data["client_health"] = [dict(h) for h in health_rows]

    # Content briefs (top 50 per client, high priority first)
    brief_rows = []
    for c in clients:
        cbriefs = generate_content_briefs(conn, c["id"])
        brief_rows.extend(cbriefs[:50])  # cap at 50 per client
    data["content_briefs"] = brief_rows

    data["kpis"] = {
        "pending_approvals": sum(1 for a in approvals if a["status"] == "needs_review" and match(a)),
        "open_tasks": sum(1 for t in tasks if t["status"] not in ("done", "cancelled") and match(t)),
        "high_impact_opportunities": sum(1 for o in opps if o["priority"] == "high" and match(o)),
        "active_jobs": sum(1 for j in jobs if j["status"] in ("ok", "running", "setup_needed") and match(j)),
        "sites_monitored": len(visible_clients),
        "system_health": "OK" if not any(j["status"] == "failed" for j in jobs if match(j)) else "Issue",
    }

    # GBP health for local clients
    try:
        from gbp_monitor import init_gbp, get_latest_gbp_metrics, calculate_gbp_health_score
        init_gbp()
        gbp_data = []
        for c in visible_clients:
            if c.get("client_type") == "local":
                m = get_latest_gbp_metrics(conn, c["id"])
                if m:
                    score = calculate_gbp_health_score(m)
                    gbp_data.append({
                        "client_id": c["id"],
                        "name": c["name"],
                        "score": score,
                        "status": m.get("status", "ok"),
                        "views": m.get("views_search", 0) + m.get("views_maps", 0),
                        "calls": m.get("actions_call", 0),
                        "website": m.get("actions_website", 0),
                        "directions": m.get("actions_directions", 0),
                        "review_avg": m.get("review_average", 0),
                        "review_count": m.get("review_count", 0),
                    })
        data["gbp_health"] = gbp_data
    except (ImportError, Exception):
        data["gbp_health"] = []

    # Opportunity Command Queue
    try:
        data["opportunity_queue"] = build_opportunity_queue(conn, client_id)
    except Exception:
        data["opportunity_queue"] = []

    # Opportunity scores for each client
    try:
        opp_scores = []
        for c in clients:
            try:
                opp = calculate_opportunity_score(conn, c["id"])
                opp_scores.append({
                    "client_id": c["id"],
                    "name": c["name"],
                    "score": opp["score"],
                    "status": opp["status"],
                    "next_best_action": opp["next_best_action"],
                })
            except Exception:
                pass
        data["opportunity_scores"] = sorted(opp_scores, key=lambda x: x["score"], reverse=True)
    except Exception:
        data["opportunity_scores"] = []

    return data


def queue_notification(conn: sqlite3.Connection, client_id: str, message: str) -> str:
    """Add a notification to the queue for the next notifier tick."""
    t = now()
    nid = uid("notif")
    thread_id = ""
    row = one(conn, "SELECT discord_thread_id FROM clients WHERE id=?", (client_id,))
    if row and row.get("discord_thread_id"):
        thread_id = row["discord_thread_id"]
    conn.execute(
        "INSERT INTO notification_queue (id, client_id, thread_id, message, created_at) VALUES (?,?,?,?,?)",
        (nid, client_id, thread_id, message, t),
    )
    conn.commit()
    return nid


def send_discord_notification(thread_id: str, message: str, bot_token: str) -> bool:
    """Send a message to a Discord thread via the Bot token API. Returns True on success."""
    if not thread_id:
        return False
    try:
        import urllib.request as _req
        url = f"https://discord.com/api/v10/channels/{thread_id}/messages"
        payload = json.dumps({"content": message[:2000]}).encode()
        headers = {
            "Authorization": f"Bot {bot_token}",
            "Content-Type": "application/json",
            "User-Agent": "SEO-OS-Dashboard/1.0",
        }
        req_obj = _req.Request(url, data=payload, headers=headers, method="POST")
        _req.urlopen(req_obj, timeout=10)
        return True
    except Exception as e:
        print(f"Discord notification error: {e}", file=sys.stderr)
        return False


def get_bot_token(conn: sqlite3.Connection) -> str:
    """Get the Discord bot token — from env, .env file, or DB settings."""
    import os as _os
    # Check environment first
    token = _os.environ.get("DISCORD_BOT_TOKEN", "")
    if token:
        return token
    # Check .env file
    env_path = ROOT / ".env"
    if env_path.exists():
        for _line in env_path.read_text().splitlines():
            _line = _line.strip()
            if _line.startswith("DISCORD_BOT_TOKEN="):
                return _line.split("=", 1)[1].strip().strip('"').strip("'")
    # Check DB settings
    row = one(conn, "SELECT value FROM settings WHERE key='discord_bot_token'")
    return row["value"] if row else ""


def notifier_loop() -> None:
    """Background thread: drain notification_queue every 5 seconds."""
    import time
    while True:
        try:
            with connect() as conn:
                bot_token = get_bot_token(conn)
                if not bot_token:
                    time.sleep(5)
                    continue
                pending = rows(conn, "SELECT * FROM notification_queue WHERE sent_at='' ORDER BY created_at LIMIT 10")
                for n in pending:
                    ok = send_discord_notification(n["thread_id"], n["message"], bot_token)
                    t = now()
                    if ok:
                        conn.execute("UPDATE notification_queue SET sent_at=? WHERE id=?", (t, n["id"]))
                    else:
                        conn.execute("UPDATE notification_queue SET retries=retries+1 WHERE id=?", (n["id"]))
                if pending:
                    conn.commit()
        except Exception as e:
            print(f"Notifier loop error: {e}", file=sys.stderr)
        time.sleep(5)


class Handler(SimpleHTTPRequestHandler):
    server_version = "SEOOSTemplate/0.1"

    def translate_path(self, path: str) -> str:
        parsed = urlparse(path).path
        if parsed == "/":
            return str(STATIC / "index.html")
        return str(STATIC / parsed.lstrip("/"))

    def end_headers(self):
        self.send_header("Cache-Control", "no-store")
        super().end_headers()

    def json_response(self, payload: dict, status: int = 200) -> None:
        body = json.dumps(payload, indent=2).encode()
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def read_json(self) -> dict:
        length = int(self.headers.get("Content-Length", "0"))
        if not length:
            return {}
        try:
            return json.loads(self.rfile.read(length).decode())
        except (json.JSONDecodeError, UnicodeDecodeError):
            return {}

    def do_GET(self):
        parsed = urlparse(self.path)
        if parsed.path == "/api/summary":
            client = parse_qs(parsed.query).get("client", ["all"])[0]
            days_str = parse_qs(parsed.query).get("days", ["0"])[0]
            metric_days_str = parse_qs(parsed.query).get("metric_days", ["0"])[0]
            try:
                days = int(days_str)
            except (ValueError, TypeError):
                days = 0
            try:
                metric_days = int(metric_days_str)
            except (ValueError, TypeError):
                metric_days = 0
            with connect() as conn:
                self.json_response(summary(conn, client, days=days, metric_days=metric_days))
            return
        if parsed.path == "/api/health":
            with connect() as conn:
                count = one(conn, "SELECT COUNT(*) AS n FROM clients")
            self.json_response({"ok": True, "clients": count["n"], "db": str(DB_PATH)})
            return
        if parsed.path == "/api/notification-queue/status":
            with connect() as conn:
                pending = one(conn, "SELECT COUNT(*) as n FROM notification_queue WHERE sent_at=''")["n"]
                sent = one(conn, "SELECT COUNT(*) as n FROM notification_queue WHERE sent_at!=''")["n"]
                recent = rows(conn, "SELECT * FROM notification_queue ORDER BY created_at DESC LIMIT 5")
            self.json_response({"ok": True, "pending": pending, "sent": sent, "recent": recent})
            return
        if parsed.path == "/api/gsc/summary":
            client = parse_qs(parsed.query).get("client", ["all"])[0]
            with connect() as conn:
                query = """
                    SELECT client_id, query, page, SUM(clicks) as clicks, SUM(impressions) as impressions,
                           AVG(ctr) as ctr, AVG(position) as position
                    FROM gsc_performance
                """
                params = []
                if client != "all":
                    query += " WHERE client_id=?"
                    params.append(client)
                query += " GROUP BY client_id, query, page ORDER BY impressions DESC LIMIT 100"
                rows_data = rows(conn, query, tuple(params))
                total_queries = one(conn, "SELECT COUNT(DISTINCT query) as n FROM gsc_performance")
                total_clicks = one(conn, "SELECT COALESCE(SUM(clicks),0) as n FROM gsc_performance")
                total_impressions = one(conn, "SELECT COALESCE(SUM(impressions),0) as n FROM gsc_performance")
            self.json_response({
                "ok": True,
                "queries": total_queries["n"] if total_queries else 0,
                "clicks": total_clicks["n"] if total_clicks else 0,
                "impressions": total_impressions["n"] if total_impressions else 0,
                "rows": rows_data
            })
            return
        return super().do_GET()

    def do_POST(self):
        parsed = urlparse(self.path)
        body = self.read_json()
        if parsed.path == "/api/gsc/pull":
            # Trigger GSC pull (runs synchronously for small datasets)
            try:
                import subprocess
                result = subprocess.run(
                    [sys.executable, "scripts/gsc_data_pull.py", "--days", "28"],
                    capture_output=True, text=True, cwd=str(ROOT), timeout=120
                )
                # Audit the pull
                with connect() as conn:
                    t = now()
                    conn.execute("INSERT INTO activity_events VALUES (?,?,?,?,?,?,?,?,?)", (
                        uid("ev"), "all", "gsc_pull", "data_refresh", "complete",
                        f"GSC data pull completed (exit {result.returncode})",
                        result.stdout.strip()[:200] or result.stderr.strip()[:200] or "No output",
                        "", t,
                    ))
                    conn.commit()
                self.json_response({
                    "ok": result.returncode == 0,
                    "stdout": result.stdout.strip(),
                    "stderr": result.stderr.strip()
                })
            except Exception as e:
                self.json_response({"ok": False, "error": str(e)}, 500)
            return
        if parsed.path.startswith("/api/approvals/") and parsed.path.endswith("/decision"):
            approval_id = parsed.path.split("/")[3]
            decision = body.get("decision", "").strip()
            note = body.get("note", "").strip()
            allowed = {"approved", "needs_changes", "rejected", "needs_review"}
            if decision not in allowed:
                self.json_response({"ok": False, "error": "Invalid decision"}, 400)
                return
            with connect() as conn:
                appr = one(conn, "SELECT * FROM approval_requests WHERE id=?", (approval_id,))
                if not appr:
                    self.json_response({"ok": False, "error": "Approval not found"}, 404)
                    return
                t = now()
                conn.execute("UPDATE approval_requests SET status=?, decision_note=?, updated_at=? WHERE id=?", (decision, note, t, approval_id))
                conn.execute("INSERT INTO activity_events VALUES (?,?,?,?,?,?,?,?,?)", (
                    uid("ev"), appr["client_id"], "dashboard", "approval_decision", "complete",
                    f"Approval {decision.replace('_', ' ')}: {appr['title']}",
                    "SEO OS watcher can create/update the bounded agent task." if decision == "approved" else "Agent will wait for the next human instruction.",
                    appr["source_url"], t,
                ))
                # Auto-notify Discord thread
                emoji_map = {"approved": "✅", "rejected": "❌", "needs_review": "📋", "needs_changes": "🔄"}
                emoji = emoji_map.get(decision, "📣")
                decision_label = decision.replace("_", " ").title()
                notify_msg = (
                    f"{emoji} **Approval {decision_label}**\n"
                    f"**{appr['title']}**\n"
                    f"Client: {appr['client_id']}\n"
                )
                if appr.get("source_url"):
                    notify_msg += f"Page: {appr['source_url']}\n"
                if note:
                    notify_msg += f"Note: {note}\n"
                queue_notification(conn, appr["client_id"], notify_msg)
                if decision == "approved" and appr["type"] != "policy":
                    existing = one(conn, "SELECT id FROM agent_tasks WHERE page_asset=?", (appr["source_url"],))
                    if not existing:
                        client = one(conn, "SELECT hermes_profile FROM clients WHERE id=?", (appr["client_id"],)) or {"hermes_profile": "seo-agent"}
                        conn.execute("INSERT INTO agent_tasks VALUES (?,?,?,?,?,?,?,?,?,?,?,?)", (
                            uid("task"), appr["client_id"], f"Run approved workflow: {appr['title']}", "high", "ready", "Approval request",
                            client["hermes_profile"], appr["source_url"], appr["requested_action"], "Created from dashboard approval. Production remains separately gated.", t, t,
                        ))
                    else:
                        conn.execute(
                            "UPDATE agent_tasks SET status=?, source=?, next_action=?, notes=?, updated_at=? WHERE id=?",
                            ("ready", "Dashboard approval", appr["requested_action"], "Approved in SEO OS dashboard. Production remains separately gated.", t, existing["id"]),
                        )
                conn.commit()
                self.json_response({"ok": True, "summary": summary(conn, "all")})
            return
        if parsed.path == "/api/notification-queue/mark-sent":
            nid = body.get("id", "").strip()
            if not nid:
                self.json_response({"ok": False, "error": "id required"}, 400)
                return
            with connect() as conn:
                t = now()
                conn.execute("UPDATE notification_queue SET sent_at=? WHERE id=?", (t, nid))
                conn.commit()
            self.json_response({"ok": True})
            return
        if parsed.path == "/api/refresh":
            client_id = body.get("client_id", "all")
            # Run the actual GA4 + GSC pull script
            import subprocess
            script = str(ROOT / "scripts" / "ga4_data_pull.py")
            cmd = ["python3", script, "--days", "28", "--json"]
            if client_id and client_id != "all":
                cmd.extend(["--client", client_id])
            try:
                result = subprocess.run(cmd, capture_output=True, text=True, timeout=120)
                output = result.stdout.strip()
                try:
                    pull_data = json.loads(output) if output else []
                except json.JSONDecodeError:
                    pull_data = []
                errors = result.stderr.strip() if result.stderr.strip() else None
                # Log the pull event
                with connect() as conn:
                    t = now()
                    total_opps = sum(r.get("opportunities_stored", 0) for r in pull_data if "error" not in r)
                    total_sessions = 0
                    for r in pull_data:
                        if "error" not in r and r.get("sessions_data"):
                            for row in r["sessions_data"]:
                                total_sessions += int(row.get("sessions", 0) or 0)
                    summary_text = f"GA4 pull: {total_sessions} sessions, {total_opps} opportunities."
                    if errors:
                        summary_text += f" Warnings: {errors[:200]}"
                    conn.execute("INSERT INTO activity_events VALUES (?,?,?,?,?,?,?,?,?)", (
                        uid("ev"), client_id if client_id != "all" else "all", "ga4_pull", "data_refresh", "complete",
                        summary_text, "Review updated opportunities and approvals.", "", t,
                    ))
                    conn.commit()
                    self.json_response({"ok": True, "pull_results": pull_data, "summary": summary(conn, client_id)})
            except subprocess.TimeoutExpired:
                self.json_response({"ok": False, "error": "GA4 pull timed out (120s)"}, 500)
            except Exception as e:
                self.json_response({"ok": False, "error": str(e)}, 500)
            return
        if parsed.path == "/api/discord/notify":
            message = body.get("message", "").strip()
            client_id = body.get("client_id", "all")
            if not message:
                self.json_response({"ok": False, "error": "message is required"}, 400)
                return
            with connect() as conn:
                webhook_row = one(conn, "SELECT value FROM settings WHERE key='discord_webhook_url'")
                thread_row = None
                if client_id != "all":
                    thread_row = one(conn, "SELECT discord_thread_id, name FROM clients WHERE id=?", (client_id,))
            webhook_url = webhook_row["value"] if webhook_row else ""
            if not webhook_url:
                self.json_response({"ok": False, "error": "Discord webhook URL not configured in Settings"}, 500)
                return
            payload = {"content": message}
            if thread_row and thread_row.get("discord_thread_id"):
                payload["thread_name"] = f"{thread_row['name']} — Updates"
            try:
                import urllib.request as _req
                data = json.dumps(payload).encode()
                headers = {"Content-Type": "application/json", "User-Agent": "SEO-OS-Dashboard/1.0"}
                req_obj = _req.Request(webhook_url, data=data, headers=headers, method="POST")
                _req.urlopen(req_obj, timeout=10)
                with connect() as conn:
                    t = now()
                    conn.execute("INSERT INTO activity_events VALUES (?,?,?,?,?,?,?,?,?)", (
                        uid("ev"), client_id, "dashboard", "discord_notification", "complete",
                        message[:200], "Sent to Discord webhook.", "", t,
                    ))
                    conn.commit()
                self.json_response({"ok": True})
            except Exception as e:
                self.json_response({"ok": False, "error": str(e)}, 500)
            return
        if parsed.path == "/api/discord/thread":
            client_id = body.get("client_id", "").strip()
            if not client_id or client_id == "all":
                self.json_response({"ok": False, "error": "client_id is required"}, 400)
                return
            with connect() as conn:
                client = one(conn, "SELECT * FROM clients WHERE id=?", (client_id,))
                if not client:
                    self.json_response({"ok": False, "error": "Client not found"}, 404)
                    return
                if client.get("discord_thread_id"):
                    self.json_response({"ok": True, "thread_id": client["discord_thread_id"], "message": "Thread already exists"})
                    return
                bot_token_row = one(conn, "SELECT value FROM settings WHERE key='discord_bot_token'")
                channel_row = one(conn, "SELECT value FROM settings WHERE key='discord_channel_id'")
            if not bot_token_row or not channel_row:
                self.json_response({"ok": False, "error": "Discord bot token or channel not configured"}, 500)
                return
            try:
                import urllib.request as _req
                payload = json.dumps({"name": f"📋 {client['name']}", "type": 11, "auto_archive_duration": 1440}).encode()
                th_headers = {"Authorization": f"Bot {bot_token_row['value']}", "Content-Type": "application/json", "User-Agent": "SEO-OS-Dashboard/1.0"}
                req_obj = _req.Request(f"https://discord.com/api/v10/channels/{channel_row['value']}/threads", data=payload, headers=th_headers, method="POST")
                resp = _req.urlopen(req_obj, timeout=10)
                thread_data = json.loads(resp.read())
                thread_id = thread_data["id"]
                with connect() as conn:
                    conn.execute("UPDATE clients SET discord_thread_id=? WHERE id=?", (thread_id, client_id))
                    conn.commit()
                self.json_response({"ok": True, "thread_id": thread_id, "thread_name": thread_data.get("name", "")})
            except Exception as e:
                self.json_response({"ok": False, "error": str(e)}, 500)
            return
        if parsed.path.startswith("/api/clients/") and parsed.path.endswith("/delete"):
            client_id = parsed.path.split("/")[3]
            confirm = body.get("confirm", "").strip()
            if client_id in ("", "all") or confirm != "DELETE":
                self.json_response({"ok": False, "error": "Client delete requires confirm=DELETE and a real client id"}, 400)
                return
            with connect() as conn:
                client = one(conn, "SELECT * FROM clients WHERE id=?", (client_id,))
                if not client:
                    self.json_response({"ok": False, "error": "Client not found"}, 404)
                    return
                t = now()
                # Backup before destructive delete
                backup_path = backup_db()
                deleted_counts = {}
                for table in ("metrics_snapshots", "opportunities", "approval_requests", "agent_tasks", "managed_jobs", "artifacts"):
                    cur = conn.execute(f"DELETE FROM {table} WHERE client_id=?", (client_id,))
                    deleted_counts[table] = cur.rowcount
                conn.execute("INSERT INTO activity_events VALUES (?,?,?,?,?,?,?,?,?)", (
                    uid("ev"), "all", "dashboard", "client_deleted", "complete",
                    f"Deleted client from SEO OS dashboard: {client['name']}",
                    f"All client-scoped rows removed. Backup: {backup_path}", "", t,
                ))
                cur = conn.execute("DELETE FROM activity_events WHERE client_id=?", (client_id,))
                deleted_counts["activity_events"] = cur.rowcount
                conn.execute("DELETE FROM clients WHERE id=?", (client_id,))
                conn.commit()
                self.json_response({"ok": True, "deleted_client": client_id, "deleted_counts": deleted_counts, "summary": summary(conn, "all")})
            return
        # ─── Create Client ───────────────────────────────────────────────────
        m = re.match(r"^/api/clients/([^/]+)/create$", parsed.path)
        if m:
            client_id = m.group(1)
            data = body
            name = (data.get("name") or "").strip()
            domain = (data.get("domain") or "").strip()
            role = (data.get("role") or "").strip() or "SEO client"
            client_type = (data.get("client_type") or "local").strip()
            if not name or not domain:
                self.json_response({"ok": False, "error": "name and domain are required"}, 400)
                return
            if client_id in ("", "all"):
                self.json_response({"ok": False, "error": "Invalid client id"}, 400)
                return
            t = now()
            slug = data.get("hermes_profile") or f"{client_id}-seo"
            workspace = f"/opt/seo-os/workspaces/{client_id}"
            with connect() as conn:
                existing = one(conn, "SELECT id FROM clients WHERE id=?", (client_id,))
                if existing:
                    self.json_response({"ok": False, "error": "Client already exists"}, 409)
                    return
                conn.execute(
                    """INSERT INTO clients (id, name, domain, role, status, health_score,
                       hermes_profile, channel_target, discord_thread_id,
                       gsc_status, ga4_status, repo_status, zernio_status, client_type,
                       workspace, created_at, updated_at)
                       VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
                    (client_id, name, domain, role, "setup", 50, slug,
                     "not_bound", "", "not_connected", "not_connected", "not_connected",
                     "not_connected", client_type, workspace, t, t)
                )
                conn.execute(
                    "INSERT INTO activity_events VALUES (?,?,?,?,?,?,?,?,?)",
                    (uid("ev"), client_id, "dashboard", "client_created", "complete",
                     f"Client added: {name}", "Connect GSC, GA4, and review source to begin.", "", t)
                )
                conn.commit()
            self.json_response({"ok": True, "client_id": client_id, "summary": summary(conn, "all")})
            return
        if parsed.path == "/api/gbp/health":
            client_id = body.get("client_id", "")
            demo = body.get("demo", True)
            from gbp_monitor import init_gbp, get_latest_gbp_metrics, get_gbp_trend, run_gbp_monitor, calculate_gbp_health_score
            init_gbp()
            if demo:
                run_gbp_monitor(demo=True)
            metrics = get_latest_gbp_metrics(conn, client_id) if client_id else None
            trend = get_gbp_trend(conn, client_id) if client_id else []
            score = calculate_gbp_health_score(metrics) if metrics else 0
            self.json_response({
                "ok": True,
                "metrics": metrics,
                "trend": trend,
                "score": score,
                "summary": summary(conn, "all")
            })
            return
        self.json_response({"ok": False, "error": "Not found"}, HTTPStatus.NOT_FOUND)


    def do_GET(self):
        parsed = urlparse(self.path)
        if parsed.path == "/api/summary":
            client = parse_qs(parsed.query).get("client", ["all"])[0]
            days_str = parse_qs(parsed.query).get("days", ["0"])[0]
            metric_days_str = parse_qs(parsed.query).get("metric_days", ["0"])[0]
            try:
                days = int(days_str)
            except (ValueError, TypeError):
                days = 0
            try:
                metric_days = int(metric_days_str)
            except (ValueError, TypeError):
                metric_days = 0
            with connect() as conn:
                s = summary(conn, client, days=days, metric_days=metric_days)
            self.json_response({"ok": True, "summary": s, **s})
            return
        if parsed.path == "/api/prospects/card":
            qs = parse_qs(parsed.query)
            prospect_id = qs.get("id", [""])[0]
            if prospect_id:
                with connect() as conn:
                    card = generate_outreach_card(conn, prospect_id)
                if card:
                    self.json_response({"ok": True, **card})
                else:
                    self.json_response({"ok": False, "error": "Prospect not found"}, 404)
            else:
                self.json_response({"ok": False, "error": "id required"}, 400)
            return
        if parsed.path == "/api/clients/health_trend":
            qs = parse_qs(parsed.query)
            client_id = qs.get("id", [""])[0]
            days = int(qs.get("days", ["90"])[0])
            with connect() as conn:
                trend = get_health_trend(conn, client_id, days)
            self.json_response({"ok": True, "trend": trend})
            return
        if parsed.path == "/api/google/discover":
            try:
                from scripts.google_discovery import discover_all
                result = discover_all()
                self.json_response({"ok": True, **result})
            except Exception as e:
                self.json_response({"ok": False, "error": str(e)}, 500)
            return
        super().do_GET()


def calculate_client_health(conn: sqlite3.Connection, client_id: str) -> dict:
    """Calculate a 0-100 health score for a client based on multiple signals.

    Returns dict with score, status (green/yellow/red), and component breakdown.
    """
    import json

    # 1. Traffic trend (30%) — compare last two metrics_snapshots
    snapshots = conn.execute(
        """SELECT * FROM metrics_snapshots
        WHERE client_id=? ORDER BY created_at DESC LIMIT 2""",
        (client_id,)
    ).fetchall()
    traffic_score = 50  # neutral default
    if len(snapshots) >= 2:
        curr = dict(snapshots[0])
        prev = dict(snapshots[1])
        if prev["clicks"] > 0:
            change = (curr["clicks"] - prev["clicks"]) / prev["clicks"]
            traffic_score = max(0, min(100, 50 + int(change * 100)))

    # 2. Position improvement (25%) — lower avg_position is better
    gsc_pos = conn.execute(
        "SELECT AVG(position) as avg_pos FROM gsc_performance WHERE client_id=?",
        (client_id,)
    ).fetchone()
    position_score = 50  # neutral default
    if gsc_pos and gsc_pos["avg_pos"]:
        avg_pos = gsc_pos["avg_pos"]
        # Score: position 1 = 100, position 50 = 0
        position_score = max(0, min(100, int(100 - (avg_pos - 1) * 2)))

    # 3. Content velocity (20%) — number of distinct pages ranking
    pages_row = conn.execute(
        "SELECT COUNT(DISTINCT page) as n FROM gsc_performance WHERE client_id=?",
        (client_id,)
    ).fetchone()
    pages_ranking = pages_row["n"] if pages_row else 0
    # 30+ pages = 100, 0 pages = 0
    content_score = min(100, int(pages_ranking * 3.3))

    # 4. Opportunity signal (25%) — ratio of high-priority opps
    total_opps = conn.execute(
        "SELECT COUNT(*) as n FROM opportunities WHERE client_id=?",
        (client_id,)
    ).fetchone()["n"]
    high_opps = conn.execute(
        "SELECT COUNT(*) as n FROM opportunities WHERE client_id=? AND priority='high'",
        (client_id,)
    ).fetchone()["n"]
    if total_opps > 0:
        # More high-priority opps = more room for improvement = lower score
        # But also having opps means we're detecting things. Balance:
        # 0% high = 70 (stable), 10-20% = 50 (needs work), >30% = 30 (urgent)
        high_ratio = high_opps / total_opps
        if high_ratio == 0:
            signal_score = 80  # No high-priority issues = healthy
        elif high_ratio <= 0.1:
            signal_score = 60
        elif high_ratio <= 0.25:
            signal_score = 40
        else:
            signal_score = 20
    else:
        signal_score = 50  # no data

    # Weighted composite
    score = int(
        traffic_score * 0.30 +
        position_score * 0.25 +
        content_score * 0.20 +
        signal_score * 0.25
    )
    score = max(0, min(100, score))

    # Status
    if score >= 70:
        status = "green"
    elif score >= 40:
        status = "yellow"
    else:
        status = "red"

    return {
        "client_id": client_id,
        "score": score,
        "status": status,
        "components": {
            "traffic_trend": traffic_score,
            "avg_position": position_score,
            "content_velocity": content_score,
            "opportunity_signal": signal_score,
        },
        "pages_ranking": pages_ranking,
        "high_priority_opps": high_opps,
        "total_opportunities": total_opps,
    }


def calculate_opportunity_score(conn: sqlite3.Connection, client_id: str) -> dict:
    """Calculate a 0-100 opportunity score for a client/prospect.
    
    Higher score = more opportunity (more room to grow, more value).
    Combines: search position, GBP metrics, traffic, content coverage, opportunity gaps.
    Returns dict with score, status, components, and next_best_action.
    """
    import json

    score_components = {
        "search_position": 0,
        "gbp_strength": 0,
        "traffic": 0,
        "content_coverage": 0,
        "opportunity_gap": 0,
        "gbp_activity": 0,
    }

    # 1. Search position (25%) — higher position = more opportunity
    gsc_pos = conn.execute(
        "SELECT AVG(position) as avg_pos FROM gsc_performance WHERE client_id=?",
        (client_id,)
    ).fetchone()
    if gsc_pos and gsc_pos["avg_pos"]:
        avg_pos = gsc_pos["avg_pos"]
        if avg_pos <= 3:
            score_components["search_position"] = 15
        elif avg_pos <= 6:
            score_components["search_position"] = 35
        elif avg_pos <= 10:
            score_components["search_position"] = 55
        elif avg_pos <= 20:
            score_components["search_position"] = 75
        else:
            score_components["search_position"] = 90
    else:
        score_components["search_position"] = 50

    # 2. GBP strength (20%) — lower reviews/activity = more opportunity
    gbp = conn.execute(
        "SELECT review_average, review_count, views_search, views_maps, actions_call, actions_website, actions_directions, posts_published FROM gbp_health WHERE client_id=? ORDER BY date DESC LIMIT 1",
        (client_id,)
    ).fetchone()
    if gbp:
        rev_count = gbp["review_count"] or 0
        reviews_avg = gbp["review_average"] or 0
        rev_opportunity = max(0, 100 - rev_count * 2)
        rating_gap = max(0, int((5.0 - (reviews_avg or 0)) * 20))
        score_components["gbp_strength"] = min(100, (rev_opportunity + rating_gap) // 2)
        total_actions = (gbp["actions_call"] or 0) + (gbp["actions_website"] or 0) + (gbp["actions_directions"] or 0)
        if total_actions < 5:
            score_components["gbp_activity"] = 80
        elif total_actions < 20:
            score_components["gbp_activity"] = 50
        elif total_actions < 50:
            score_components["gbp_activity"] = 30
        else:
            score_components["gbp_activity"] = 10
    else:
        score_components["gbp_strength"] = 50
        score_components["gbp_activity"] = 50

    # 3. Traffic (20%) — less traffic = more opportunity for growth
    snap = conn.execute(
        "SELECT clicks, impressions FROM metrics_snapshots WHERE client_id=? ORDER BY created_at DESC LIMIT 1",
        (client_id,)
    ).fetchone()
    if snap:
        impressions = snap["impressions"] or 0
        if impressions < 50:
            score_components["traffic"] = 80
        elif impressions < 200:
            score_components["traffic"] = 60
        elif impressions < 1000:
            score_components["traffic"] = 40
        else:
            score_components["traffic"] = 20
    else:
        score_components["traffic"] = 50

    # 4. Content coverage (15%) — fewer pages = more opportunity
    pages_row = conn.execute(
        "SELECT COUNT(DISTINCT page) as n FROM gsc_performance WHERE client_id=?",
        (client_id,)
    ).fetchone()
    pages = pages_row["n"] if pages_row else 0
    if pages < 10:
        score_components["content_coverage"] = 80
    elif pages < 30:
        score_components["content_coverage"] = 55
    elif pages < 60:
        score_components["content_coverage"] = 35
    else:
        score_components["content_coverage"] = 15

    # 5. Opportunity gap (10%) — more high-priority opps = more to do
    total_opps = conn.execute(
        "SELECT COUNT(*) as n FROM opportunities WHERE client_id=?", (client_id,)
    ).fetchone()["n"]
    high_opps = conn.execute(
        "SELECT COUNT(*) as n FROM opportunities WHERE client_id=? AND priority='high'",
        (client_id,)
    ).fetchone()["n"]
    if total_opps > 0 and high_opps / total_opps > 0.25:
        score_components["opportunity_gap"] = 80
    elif high_opps > 0:
        score_components["opportunity_gap"] = 50
    else:
        score_components["opportunity_gap"] = 20

    # Weighted composite (higher = more opportunity)
    score = int(
        score_components["search_position"] * 0.25 +
        score_components["gbp_strength"] * 0.20 +
        score_components["traffic"] * 0.20 +
        score_components["content_coverage"] * 0.15 +
        score_components["opportunity_gap"] * 0.10 +
        score_components["gbp_activity"] * 0.10
    )
    score = max(0, min(100, score))

    # Determine next best action
    next_action = _determine_next_best_action(score_components, gbp, snap, pages, total_opps, high_opps)

    if score >= 65:
        status = "high_opportunity"
    elif score >= 35:
        status = "medium_opportunity"
    else:
        status = "low_opportunity"

    return {
        "client_id": client_id,
        "score": score,
        "status": status,
        "components": score_components,
        "next_best_action": next_action,
    }


def _determine_next_best_action(components, gbp, snap, pages, total_opps, high_opps):
    """Generate one clear next action based on weakest signals."""
    weakest = min(components, key=components.get)

    if weakest == "search_position":
        return "Improve SERP visibility — optimize title/meta for top queries"
    elif weakest == "gbp_strength":
        if gbp and (gbp["review_count"] or 0) < 10:
            return "Request reviews (currently {})".format(gbp["review_count"] or 0)
        return "Complete GBP profile — add services, hours, Q&A"
    elif weakest == "gbp_activity":
        return "Post weekly GBP update + add photos"
    elif weakest == "traffic":
        return "Create content for high-impression low-CTR queries"
    elif weakest == "content_coverage":
        return f"Build {max(5, 30 - pages)} new service/location pages"
    elif weakest == "opportunity_gap":
        return f"Address {high_opps} high-priority opportunity(ies)"
    else:
        return "Run full audit — identify quick wins"


def build_opportunity_queue(conn: sqlite3.Connection, client_id: str = "all") -> list:
    """Build a unified opportunity queue combining:
    - Existing opportunities (with evidence)
    - GBP gaps (low reviews, no posts, missing services)
    - Top GSC opportunities (high impressions, low CTR, position 4-10)
    
    Returns list of queue items sorted by impact (high first).
    """
    import json
    queue = []
    clients_filter = "" if client_id == "all" else "AND client_id=?"
    params = () if client_id == "all" else (client_id,)

    # ─── 1. Existing opportunities ──────────────────────────────────────────
    opp_rows = conn.execute(
        f"""SELECT o.*, c.name as client_name FROM opportunities o
            JOIN clients c ON o.client_id = c.id
            WHERE 1=1 {clients_filter}
            ORDER BY CASE o.priority WHEN 'high' THEN 0 WHEN 'medium' THEN 1 ELSE 2 END,
                     o.impressions DESC LIMIT 50""",
        params
    ).fetchall()
    for o in opp_rows:
        o = dict(o)
        evidence = json.loads(o.get("evidence_json") or "{}")
        impact_map = {"high": "High", "medium": "Medium", "low": "Low"}
        queue.append({
            "id": f"opp_{o['id']}",
            "business": o.get("client_name", o["client_id"]),
            "client_id": o["client_id"],
            "type": "Opportunity",
            "type_label": o.get("opportunity_type", "SEO"),
            "opportunity": o.get("problem", ""),
            "evidence": f"Position {o.get('position', 0):.0f}, {o.get('impressions', 0):,} impressions, {o.get('ctr', 0):.2%} CTR",
            "impact": impact_map.get(o.get("priority", "low"), "Low"),
            "effort": o.get("effort", "Medium").title(),
            "next_action": o.get("recommended_workflow", "Review"),
            "status": o.get("status", "new"),
            "source": evidence.get("source", "gsc_pull"),
        })

    # ─── 2. GBP gaps ────────────────────────────────────────────────────────
    gbp_rows = conn.execute(
        f"""SELECT g.client_id, c.name as client_name, g.review_count, g.review_average,
                   g.posts_published, g.actions_call, g.actions_website, g.actions_directions,
                   g.views_search, g.views_maps
            FROM gbp_health g
            JOIN clients c ON g.client_id = c.id
            WHERE g.client_id IN (SELECT id FROM clients {'WHERE client_id=?' if client_id != 'all' else ''})
            AND g.date = (SELECT MAX(g2.date) FROM gbp_health g2 WHERE g2.client_id = g.client_id)
            ORDER BY g.date DESC""",
        params if client_id != "all" else ()
    ).fetchall()
    for g in gbp_rows:
        g = dict(g)
        total_actions = (g.get("actions_call") or 0) + (g.get("actions_website") or 0) + (g.get("actions_directions") or 0)
        rev_count = g.get("review_count") or 0
        posts = g.get("posts_published") or 0

        if rev_count < 10:
            queue.append({
                "id": f"gbp_reviews_{g['client_id']}",
                "business": g.get("client_name", g["client_id"]),
                "client_id": g["client_id"],
                "type": "GBP",
                "type_label": "Reviews",
                "opportunity": f"Low reviews vs competitors ({rev_count} reviews)",
                "evidence": f"Current: {rev_count} reviews, {g.get('review_average', 0):.1f}⭐. Top competitors average 50-150+",
                "impact": "High" if rev_count < 5 else "Medium",
                "effort": "Low",
                "next_action": "Pitch review growth campaign",
                "status": "new",
                "source": "gbp_monitor",
            })

        if posts < 2:
            queue.append({
                "id": f"gbp_posts_{g['client_id']}",
                "business": g.get("client_name", g["client_id"]),
                "client_id": g["client_id"],
                "type": "GBP",
                "type_label": "Engagement",
                "opportunity": "Stale GBP — no recent posts",
                "evidence": f"Only {posts} posts published. Active businesses post 2-4x/month",
                "impact": "Medium",
                "effort": "Low",
                "next_action": "Create 4-week content calendar",
                "status": "new",
                "source": "gbp_monitor",
            })

        if total_actions < 5:
            queue.append({
                "id": f"gbp_actions_{g['client_id']}",
                "business": g.get("client_name", g["client_id"]),
                "client_id": g["client_id"],
                "type": "GBP",
                "type_label": "Visibility",
                "opportunity": "Low GBP engagement (calls, website clicks, directions)",
                "evidence": f"Total actions: {total_actions} (calls: {g.get('actions_call', 0)}, web: {g.get('actions_website', 0)}, directions: {g.get('actions_directions', 0)})",
                "impact": "Medium",
                "effort": "Medium",
                "next_action": "Optimize GBP categories + add Q&A",
                "status": "new",
                "source": "gbp_monitor",
            })

    # ─── 3. Top GSC opportunities (position 4-10, high impressions, low CTR) ─
    gsc_top = conn.execute(
        f"""SELECT client_id, query, page, SUM(impressions) as total_impr,
                   AVG(position) as avg_pos, AVG(ctr) as avg_ctr, SUM(clicks) as total_clicks
            FROM gsc_performance
            WHERE 1=1 {clients_filter}
            GROUP BY client_id, query
            HAVING avg_pos BETWEEN 4 AND 15 AND total_impr > 100 AND avg_ctr < 0.03
            ORDER BY total_impr DESC LIMIT 20""",
        params
    ).fetchall()
    for g in gsc_top:
        g = dict(g)
        queue.append({
            "id": f"gsc_{g['client_id']}_{g['query'][:20]}",
            "business": g["client_id"],
            "client_id": g["client_id"],
            "type": "GSC",
            "type_label": "SERP Gap",
            "opportunity": f"'{g['query'][:40]}' — position {g['avg_pos']:.1f}, {g['total_impr']:,} impressions",
            "evidence": f"Position {g['avg_pos']:.1f}, {g['total_impr']:,} impr, {g['avg_ctr']:.2%} CTR, {g['total_clicks']} clicks",
            "impact": "High" if g['avg_pos'] <= 10 else "Medium",
            "effort": "Medium",
            "next_action": f"Optimize title/meta for '{g['query'][:30]}'",
            "status": "new",
            "source": "gsc_pull",
        })

    # Sort: High impact first
    impact_order = {"High": 0, "Medium": 1, "Low": 2}
    queue.sort(key=lambda x: (impact_order.get(x["impact"], 2), x["source"]))

    return queue[:50]


def generate_outreach_card(conn: sqlite3.Connection, prospect_id: str) -> dict | None:
    """Generate an outreach-ready pitch card for a prospect.
    
    Combines prospect data + client data (if linked) into a concise pitch.
    Returns dict with pitch, evidence, and recommended channel.
    """
    try:
        from prospects import get_prospect
        prospect = get_prospect(prospect_id)
    except ImportError:
        prospect = None
    if not prospect:
        return None

    name = prospect.get("name", "Business")
    keyword = prospect.get("keyword", "your main service")
    city = prospect.get("city", "your city")
    rank = prospect.get("rank", 0)
    niche = prospect.get("niche", "your industry")
    website = prospect.get("website", "")
    score = prospect.get("score", 0)

    # Build evidence snippets
    evidence_parts = []
    if rank and rank > 3:
        evidence_parts.append(f"ranks #{rank} for '{keyword}' in {city}")
    elif rank:
        evidence_parts.append(f"ranks #{rank} for '{keyword}' in {city} (close to top 3)")

    # If prospect has a linked client_id, pull client data
    client_data = prospect.get("client_id", "")
    if client_data:
        client = one(conn, "SELECT * FROM clients WHERE id=?", (client_data,))
        if client:
            gbp = conn.execute(
                "SELECT review_count, review_average FROM gbp_health WHERE client_id=? ORDER BY date DESC LIMIT 1",
                (client_data,)
            ).fetchone()
            if gbp and (gbp["review_count"] or 0) < 10:
                evidence_parts.append(f"GBP has only {gbp['review_count'] or 0} reviews (competitors have 50+)")
            gsc = conn.execute(
                "SELECT COUNT(DISTINCT page) as n FROM gsc_performance WHERE client_id=?",
                (client_data,)
            ).fetchone()
            if gsc and gsc["n"] < 15:
                evidence_parts.append(f"site has only {gsc['n']} ranking pages (competitors have 30+)")

    if score and score >= 70:
        evidence_parts.append(f"opportunity score: {score}/100 (high potential)")
    elif score and score >= 40:
        evidence_parts.append(f"opportunity score: {score}/100 (solid potential)")

    # Determine recommended channel
    channel = prospect.get("channel", "fb_dm")
    channel_map = {
        "fb_dm": "Facebook DM",
        "email": "Email",
        "phone": "Phone call",
        "linkedin": "LinkedIn",
        "in_person": "In person",
    }
    recommended_channel = channel_map.get(channel, "Facebook DM")

    # Generate pitch paragraph
    pitch_parts = [f"Hey {name.split()[0] if name else 'there'}!"]
    if rank and rank <= 3:
        pitch_parts.append(f"Congrats on ranking #{rank} for '{keyword}' in {city} — you're close to the top!")
    elif rank:
        pitch_parts.append(f"I noticed {name} ranks #{rank} for '{keyword}' in {city} on Google.")
    else:
        pitch_parts.append(f"I came across {name} while researching {keyword} in {city}.")

    if evidence_parts:
        pitch_parts.append("Here's what I see: " + "; ".join(evidence_parts) + ".")

    pitch_parts.append(
        f"I help {niche} businesses in the RGV get found on Google and generate more calls. "
        "Would it be worth a quick 10-min chat to show you how you could get to the top 3? No pressure either way."
    )
    pitch_parts.append("")
    pitch_parts.append("— Eddie / RankRGV | rankrgv.com | (956) 391-5991 / Helping RGV {} get found on Google".format(niche))

    pitch = "\n".join(pitch_parts)

    return {
        "prospect_id": prospect_id,
        "name": name,
        "channel": recommended_channel,
        "pitch": pitch,
        "evidence": evidence_parts,
        "score": score,
        "rank": rank,
        "keyword": keyword,
        "city": city,
    }


def store_health_score(conn: sqlite3.Connection, health: dict) -> None:
    """Store or update client health score."""
    import uuid
    t = dt.datetime.now(dt.timezone.utc).replace(microsecond=0).isoformat()

    existing = conn.execute(
        "SELECT id FROM client_health WHERE client_id=?",
        (health["client_id"],)
    ).fetchone()

    if existing:
        conn.execute(
            """UPDATE client_health SET
                score=?, status=?, components_json=?,
                pages_ranking=?, high_priority_opps=?, total_opportunities=?, updated_at=?
            WHERE client_id=?""",
            (health["score"], health["status"], json.dumps(health["components"]),
             health["pages_ranking"], health["high_priority_opps"],
             health["total_opportunities"], t, health["client_id"])
        )
    else:
        hid = f"health_{uuid.uuid4().hex[:10]}"
        conn.execute(
            "INSERT INTO client_health VALUES (?,?,?,?,?,?,?,?,?)",
            (hid, health["client_id"], health["score"], health["status"],
             json.dumps(health["components"]), health["pages_ranking"],
             health["high_priority_opps"], health["total_opportunities"], t)
        )
    conn.commit()


def refresh_ga4_token() -> bool:
    """Refresh the GA4 OAuth token on startup if refresh_token is available. Returns True if token is valid."""
    try:
        token_path = Path("/root/.hermes/google_token.json")
        if not token_path.exists():
            return False
        with open(token_path) as f:
            token = json.load(f)
        if "refresh_token" not in token:
            return True  # token exists but can't refresh; assume valid
        data = urlencode({
            "client_id": token["client_id"],
            "client_secret": token["client_secret"],
            "refresh_token": token["refresh_token"],
            "grant_type": "refresh_token",
        }).encode()
        req = Request(
            "https://oauth2.googleapis.com/token", data=data,
            headers={"Content-Type": "application/x-www-form-urlencoded"}, method="POST"
        )
        resp = urlopen(req, timeout=10)
        result = json.loads(resp.read())
        token["token"] = result["access_token"]
        from datetime import datetime, timezone, timedelta
        token["expiry"] = (datetime.now(timezone.utc) + timedelta(seconds=result.get("expires_in", 3600))).isoformat()
        with open(token_path, "w") as f:
            json.dump(token, f)
        print("  ✓ GA4 token refreshed on startup")
        return True
    except Exception as e:
        print(f"  ⚠ Token refresh failed: {e}", file=sys.stderr)
        return False


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8787)
    parser.add_argument("--reset", action="store_true", help="Delete and reseed SQLite database")
    args = parser.parse_args()
    if args.reset and DB_PATH.exists():
        DB_PATH.unlink()
    init_db(seed=True)
    refresh_ga4_token()
    # Start background notifier thread
    import threading as _threading
    _notifier = _threading.Thread(target=notifier_loop, daemon=True)
    _notifier.start()
    httpd = ThreadingHTTPServer((args.host, args.port), Handler)
    print(f"SEO OS dashboard running at http://{args.host}:{args.port}")
    print(f"SQLite: {DB_PATH}")
    print(f"Notifier: background notification thread started")
    httpd.serve_forever()



try:
    import prospects as _prospects
    _prospects.register_routes(Handler)
except (ImportError, AttributeError):
    pass


if __name__ == "__main__":
    try:
        import prospects
        prospects.init_prospects()
    except ImportError:
        pass


def get_health_trend(conn: sqlite3.Connection, client_id: str, days: int = 90) -> list:
    """Get health score trend for a client over time."""
    rows = conn.execute(
        """SELECT score, status, components_json, created_at FROM health_snapshots
           WHERE client_id=? AND created_at >= ?
           ORDER BY created_at ASC""",
        (client_id, (dt.datetime.now(dt.timezone.utc) - dt.timedelta(days=days)).isoformat())
    ).fetchall()
    return [dict(r) for r in rows]


def snapshot_all_health_scores(conn: sqlite3.Connection) -> int:
    """Snapshot current health scores for all active clients. Returns count."""
    import json as _json
    clients = conn.execute(
        "SELECT id FROM clients WHERE status IN ('active', 'setup')"
    ).fetchall()
    t = now()
    count = 0
    for c in clients:
        health = calculate_client_health(conn, c["id"])
        conn.execute(
            "INSERT INTO health_snapshots (client_id, score, status, components_json, created_at) VALUES (?,?,?,?,?)",
            (c["id"], health["score"], health["status"], _json.dumps(health.get("components", {})), t)
        )
        count += 1
    conn.commit()
    return count


if __name__ == "__main__":
    try:
        import prospects
        prospects.init_prospects()
    except ImportError:
        pass
    main()
