#!/usr/bin/env python3
"""Prospecting module for SEO OS Dashboard.

Self-contained module that adds a Prospects tab to the dashboard.
All routes are under /api/prospects/* to avoid conflicts with upstream.

To integrate, add to server.py:
    import prospects
    prospects.register_routes(Handler)
"""

import json
import os
import sqlite3
import uuid
from datetime import datetime, timezone
from pathlib import Path
from http import HTTPStatus

DB_PATH = os.environ.get("SEO_OS_DB_PATH", str(Path(__file__).resolve().parent / "data" / "seo-os.sqlite"))

# ─── Schema ──────────────────────────────────────────────────────────────────

def init_prospects():
    """Create prospecting tables if they don't exist. Safe to call multiple times."""
    conn = sqlite3.connect(DB_PATH)
    conn.executescript("""
        CREATE TABLE IF NOT EXISTS prospects (
            id TEXT PRIMARY KEY,
            name TEXT NOT NULL,
            phone TEXT DEFAULT '',
            keyword TEXT DEFAULT '',
            city TEXT DEFAULT '',
            niche TEXT DEFAULT '',
            score INTEGER DEFAULT 0,
            rank INTEGER DEFAULT 0,
            website TEXT DEFAULT '',
            email TEXT DEFAULT '',
            social TEXT DEFAULT '',
            fb_dm_opener TEXT DEFAULT '',
            channel TEXT DEFAULT 'fb_dm',
            status TEXT DEFAULT 'new',
            notes TEXT DEFAULT '',
            pipeline_stage TEXT DEFAULT 'new',
            last_contacted TEXT DEFAULT '',
            next_action TEXT DEFAULT '',
            created_at TEXT NOT NULL,
            updated_at TEXT NOT NULL
        );

        CREATE INDEX IF NOT EXISTS idx_prospects_status ON prospects(status);
        CREATE INDEX IF NOT EXISTS idx_prospects_city ON prospects(city);
        CREATE INDEX IF NOT EXISTS idx_prospects_niche ON prospects(niche);
        CREATE INDEX IF NOT EXISTS idx_prospects_pipeline ON prospects(pipeline_stage);

        CREATE TABLE IF NOT EXISTS prospect_activities (
            id TEXT PRIMARY KEY,
            prospect_id TEXT NOT NULL,
            activity_type TEXT NOT NULL,
            note TEXT DEFAULT '',
            created_at TEXT NOT NULL,
            FOREIGN KEY (prospect_id) REFERENCES prospects(id)
        );

        CREATE INDEX IF NOT EXISTS idx_activities_prospect ON prospect_activities(prospect_id);
    """)
    conn.commit()
    conn.close()


# ─── Helpers ─────────────────────────────────────────────────────────────────

def now_iso():
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def uid(prefix="prospect"):
    return f"{prefix}_{uuid.uuid4().hex[:10]}"


def row_to_dict(row):
    return dict(row) if row else None


def get_prospect(prospect_id):
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    row = conn.execute("SELECT * FROM prospects WHERE id=?", (prospect_id,)).fetchone()
    conn.close()
    return row_to_dict(row)


# ─── CRUD ────────────────────────────────────────────────────────────────────

def list_prospects(filters=None, limit=200, offset=0):
    """List prospects with optional filters."""
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row

    where = []
    params = []
    if filters:
        if filters.get("status"):
            where.append("status=?")
            params.append(filters["status"])
        if filters.get("city"):
            where.append("city LIKE ?")
            params.append(f"%{filters['city']}%")
        if filters.get("niche"):
            where.append("niche LIKE ?")
            params.append(f"%{filters['niche']}%")
        if filters.get("pipeline_stage"):
            where.append("pipeline_stage=?")
            params.append(filters["pipeline_stage"])
        if filters.get("channel"):
            where.append("channel=?")
            params.append(filters["channel"])
        if filters.get("min_score"):
            where.append("score >= ?")
            params.append(int(filters["min_score"]))
        if filters.get("q"):
            where.append("(name LIKE ? OR keyword LIKE ? OR website LIKE ? OR notes LIKE ?)")
            q = f"%{filters['q']}%"
            params.extend([q, q, q, q])

    sql = "SELECT * FROM prospects"
    if where:
        sql += " WHERE " + " AND ".join(where)
    sql += " ORDER BY score DESC, rank ASC LIMIT ? OFFSET ?"
    params.extend([limit, offset])

    rows = conn.execute(sql, params).fetchall()

    # Get counts for stats
    total = conn.execute("SELECT COUNT(*) as n FROM prospects").fetchone()["n"]
    by_status = {}
    for r in conn.execute("SELECT status, COUNT(*) as n FROM prospects GROUP BY status"):
        by_status[r["status"]] = r["n"]
    by_pipeline = {}
    for r in conn.execute("SELECT pipeline_stage, COUNT(*) as n FROM prospects GROUP BY pipeline_stage"):
        by_pipeline[r["pipeline_stage"]] = r["n"]
    by_city = {}
    for r in conn.execute("SELECT city, COUNT(*) as n FROM prospects WHERE city != '' GROUP BY city ORDER BY n DESC LIMIT 10"):
        by_city[r["city"]] = r["n"]

    conn.close()
    return {
        "prospects": [dict(r) for r in rows],
        "total": total,
        "by_status": by_status,
        "by_pipeline": by_pipeline,
        "by_city": by_city,
    }


def get_prospect_detail(prospect_id):
    """Get a single prospect with its activity history."""
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row

    prospect = conn.execute("SELECT * FROM prospects WHERE id=?", (prospect_id,)).fetchone()
    if not prospect:
        conn.close()
        return None

    activities = conn.execute(
        "SELECT * FROM prospect_activities WHERE prospect_id=? ORDER BY created_at DESC LIMIT 50",
        (prospect_id,)
    ).fetchall()

    conn.close()
    result = dict(prospect)
    result["activities"] = [dict(a) for a in activities]
    return result


def create_prospect(data):
    """Create a new prospect."""
    t = now_iso()
    prospect_id = uid()
    conn = sqlite3.connect(DB_PATH)
    conn.execute(
        """INSERT INTO prospects VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
        (
            prospect_id,
            data.get("name", ""),
            data.get("phone", ""),
            data.get("keyword", ""),
            data.get("city", ""),
            data.get("niche", ""),
            int(data.get("score", 0)),
            int(data.get("rank", 0)),
            data.get("website", ""),
            data.get("email", ""),
            data.get("social", ""),
            data.get("fb_dm_opener", ""),
            data.get("channel", "fb_dm"),
            data.get("status", "new"),
            data.get("notes", ""),
            data.get("pipeline_stage", "new"),
            data.get("last_contacted", ""),
            data.get("next_action", ""),
            t, t,
        )
    )
    conn.commit()
    conn.close()
    return prospect_id


def update_prospect(prospect_id, data):
    """Update a prospect. Only updates provided fields."""
    conn = sqlite3.connect(DB_PATH)
    existing = conn.execute("SELECT * FROM prospects WHERE id=?", (prospect_id,)).fetchone()
    if not existing:
        conn.close()
        return False

    fields = []
    values = []
    for key in ["name", "phone", "keyword", "city", "niche", "score", "rank",
                "website", "email", "social", "fb_dm_opener", "channel", "status",
                "notes", "pipeline_stage", "last_contacted", "next_action"]:
        if key in data:
            fields.append(f"{key}=?")
            values.append(data[key])

    if fields:
        fields.append("updated_at=?")
        values.append(now_iso())
        values.append(prospect_id)
        conn.execute(f"UPDATE prospects SET {','.join(fields)} WHERE id=?", values)
        conn.commit()

    conn.close()

    # Write status change back to Google Sheet (non-blocking)
    if 'status' in data:
        try:
            from scripts.prospects_sync import push_single_status
            push_single_status(existing['name'], data['status'])
        except Exception:
            pass  # Don't fail the update if Sheet write fails

    return True


def delete_prospect(prospect_id):
    """Delete a prospect and its activities."""
    conn = sqlite3.connect(DB_PATH)
    conn.execute("DELETE FROM prospect_activities WHERE prospect_id=?", (prospect_id,))
    conn.execute("DELETE FROM prospects WHERE id=?", (prospect_id,))
    conn.commit()
    conn.close()
    return True


def log_activity(prospect_id, activity_type, note=""):
    """Log an activity for a prospect."""
    t = now_iso()
    conn = sqlite3.connect(DB_PATH)
    aid = uid("activity")
    conn.execute(
        "INSERT INTO prospect_activities VALUES (?,?,?,?,?)",
        (aid, prospect_id, activity_type, note, t)
    )
    # Also update last_contacted if activity is a contact
    if activity_type in ("call", "message", "email", "fb_dm"):
        conn.execute(
            "UPDATE prospects SET last_contacted=?, updated_at=? WHERE id=?",
            (t, t, prospect_id)
        )
    conn.commit()
    conn.close()
    return aid


# ─── Templates ───────────────────────────────────────────────────────────────

FB_DM_TEMPLATE = """Hey {name}! I was looking at your business and noticed you're #{rank} in {city} for "{keyword}" on Google.

I help local businesses in the {niche} space get found on Google — I've been doing it for businesses right here in the RGV.

Would it be worth a quick 10-min chat to show you how you could get to the top 3? No pressure either way.

— Eddie / RankRGV | rankrgv.com | (956) 391-5991 / Helping RGV {niche} get found on Google"""


def generate_dm_opener(prospect):
    """Generate a personalized FB DM opener for a prospect."""
    return FB_DM_TEMPLATE.format(
        name=prospect.get("name", "").split()[0] if prospect.get("name") else "there",
        rank=prospect.get("rank", "?"),
        city=prospect.get("city", "your city"),
        keyword=prospect.get("keyword", "your main service"),
        niche=prospect.get("niche", "your industry"),
    )


# ─── Route Registration ──────────────────────────────────────────────────────

def register_routes(handler_class):
    """Add /api/prospects/* routes to the HTTP handler class.

    Usage in server.py:
        import prospects
        prospects.register_routes(Handler)
    """
    original_do_GET = handler_class.do_GET
    original_do_POST = handler_class.do_POST

    def patched_do_GET(self):
        from urllib.parse import urlparse, parse_qs
        parsed = urlparse(self.path)

        if parsed.path == "/api/prospects/list":
            filters = parse_qs(parsed.query)
            # Flatten single-value lists
            flat_filters = {k: v[0] for k, v in filters.items()}
            result = list_prospects(flat_filters)
            self.json_response({"ok": True, **result})
            return

        if parsed.path == "/api/prospects/detail":
            qs = parse_qs(parsed.query)
            prospect_id = qs.get("id", [""])[0]
            result = get_prospect_detail(prospect_id)
            if result:
                self.json_response({"ok": True, **result})
            else:
                self.json_response({"ok": False, "error": "Not found"}, 404)
            return

        if parsed.path == "/api/prospects/dm_opener":
            qs = parse_qs(parsed.query)
            prospect_id = qs.get("id", [""])[0]
            prospect = get_prospect(prospect_id)
            if prospect:
                opener = generate_dm_opener(prospect)
                self.json_response({"ok": True, "opener": opener})
            else:
                self.json_response({"ok": False, "error": "Not found"}, 404)
            return

        return original_do_GET(self)

    def patched_do_POST(self):
        from urllib.parse import urlparse, parse_qs
        parsed = urlparse(self.path)

        if parsed.path == "/api/prospects/create":
            body = self.read_json()
            prospect_id = create_prospect(body)
            self.json_response({"ok": True, "id": prospect_id})
            return

        if parsed.path == "/api/prospects/update":
            body = self.read_json()
            prospect_id = body.get("id", "")
            success = update_prospect(prospect_id, body)
            self.json_response({"ok": success})
            return

        if parsed.path == "/api/prospects/delete":
            body = self.read_json()
            prospect_id = body.get("id", "")
            delete_prospect(prospect_id)
            self.json_response({"ok": True})
            return

        if parsed.path == "/api/prospects/log_activity":
            body = self.read_json()
            log_activity(body.get("prospect_id", ""), body.get("activity_type", ""), body.get("note", ""))
            self.json_response({"ok": True})
            return

        return original_do_POST(self)

    handler_class.do_GET = patched_do_GET
    handler_class.do_POST = patched_do_POST
