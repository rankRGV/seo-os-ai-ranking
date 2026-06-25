#!/usr/bin/env python3
"""SEO OS Discord bot — listens for commands in client threads and updates the dashboard database."""

import json
import os
import sqlite3
import sys
from pathlib import Path

# ── Config ───────────────────────────────────────────────────────────────────

DB_PATH = Path(os.environ.get("SEO_OS_DB_PATH", Path(__file__).resolve().parent.parent / "data" / "seo-os.sqlite"))

BOT_TOKEN = os.environ.get("DISCORD_BOT_TOKEN", "")
if not BOT_TOKEN:
    try:
        _conn = sqlite3.connect(DB_PATH)
        _conn.row_factory = sqlite3.Row
        _row = _conn.execute("SELECT value FROM settings WHERE key='discord_bot_token'").fetchone()
        if _row:
            BOT_TOKEN = _row["value"]
        _conn.close()
    except Exception:
        pass

CHANNEL_ID = os.environ.get("DISCORD_CHANNEL_ID", "")

# ── Database helpers ─────────────────────────────────────────────────────────

def db():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn

def get_client_by_thread(thread_id):
    with db() as conn:
        row = conn.execute("SELECT * FROM clients WHERE discord_thread_id=?", (thread_id,)).fetchone()
        return dict(row) if row else None

def get_client_by_id(client_id):
    with db() as conn:
        row = conn.execute("SELECT * FROM clients WHERE id=?", (client_id,)).fetchone()
        return dict(row) if row else None

def get_pending_approvals(client_id=None):
    with db() as conn:
        if client_id:
            rows = conn.execute(
                "SELECT * FROM approval_requests WHERE client_id=? AND status='needs_review'",
                (client_id,)
            ).fetchall()
        else:
            rows = conn.execute(
                "SELECT * FROM approval_requests WHERE status='needs_review'"
            ).fetchall()
        return [dict(r) for r in rows]

def decide_approval(approval_id, decision, note=""):
    from datetime import datetime, timezone
    t = datetime.now(timezone.utc).replace(microsecond=0).isoformat()
    with db() as conn:
        # Get approval details before updating
        appr = conn.execute("SELECT * FROM approval_requests WHERE id=?", (approval_id,)).fetchone()
        conn.execute(
            "UPDATE approval_requests SET status=?, decision_note=?, updated_at=? WHERE id=?",
            (decision, note, t, approval_id)
        )
        conn.commit()
        # Auto-notify (best-effort, same pattern as server.py)
        if appr:
            emoji_map = {"approved": "✅", "rejected": "❌", "needs_review": "📋", "needs_changes": "🔄"}
            emoji = emoji_map.get(decision, "📣")
            decision_label = decision.replace("_", " ").title()
            appr_d = dict(appr)
            notify_msg = (
                f"{emoji} **Approval {decision_label}**\n"
                f"**{appr_d['title']}**\n"
                f"Client: {appr_d['client_id']}\n"
            )
            if appr_d.get("source_url"):
                notify_msg += f"Page: {appr_d['source_url']}\n"
            if note:
                notify_msg += f"Note: {note}\n"
            # Queue via notification_queue table (server.py notifier picks it up)
            try:
                import uuid as _uuid
                nid = f"notif_{_uuid.uuid4().hex[:10]}"
                thread_row = conn.execute(
                    "SELECT discord_thread_id FROM clients WHERE id=?", (appr_d["client_id"],)
                ).fetchone()
                thread_id = thread_row["discord_thread_id"] if thread_row else ""
                conn.execute(
                    "INSERT INTO notification_queue (id, client_id, thread_id, message, created_at) VALUES (?,?,?,?,?)",
                    (nid, appr_d["client_id"], thread_id, notify_msg, t),
                )
                conn.commit()
            except Exception as e:
                import sys as _sys
                print(f"Notification queue error: {e}", file=_sys.stderr)
    return True

def get_opportunities(client_id=None, limit=5):
    with db() as conn:
        if client_id:
            rows = conn.execute(
                "SELECT * FROM opportunities WHERE client_id=? ORDER BY impressions DESC LIMIT ?",
                (client_id, limit)
            ).fetchall()
        else:
            rows = conn.execute(
                "SELECT * FROM opportunities ORDER BY impressions DESC LIMIT ?",
                (limit,)
            ).fetchall()
        return [dict(r) for r in rows]

def get_status(client_id):
    with db() as conn:
        client = conn.execute("SELECT * FROM clients WHERE id=?", (client_id,)).fetchone()
        if not client:
            return None
        pending = conn.execute(
            "SELECT COUNT(*) as n FROM approval_requests WHERE client_id=? AND status='needs_review'",
            (client_id,)
        ).fetchone()["n"]
        tasks = conn.execute(
            "SELECT COUNT(*) as n FROM agent_tasks WHERE client_id=? AND status NOT IN ('done','cancelled')",
            (client_id,)
        ).fetchone()["n"]
        opps = conn.execute(
            "SELECT COUNT(*) as n FROM opportunities WHERE client_id=?",
            (client_id,)
        ).fetchone()["n"]
        return {
            "name": client["name"],
            "domain": client["domain"],
            "status": client["status"],
            "health_score": client["health_score"],
            "pending_approvals": pending,
            "open_tasks": tasks,
            "opportunities": opps,
        }

# ── Discord API helpers ──────────────────────────────────────────────────────

import urllib.request

DISCORD_API = "https://discord.com/api/v10"
HEADERS = {
    "Authorization": f"Bot {BOT_TOKEN}",
    "Content-Type": "application/json",
    "User-Agent": "SEO-OS-Bot/1.0"
}

def discord_request(method, path, data=None):
    url = f"{DISCORD_API}{path}"
    payload = json.dumps(data).encode() if data else None
    req = urllib.request.Request(url, data=payload, headers=HEADERS, method=method)
    try:
        resp = urllib.request.urlopen(req, timeout=10)
        if resp.status == 204:
            return {}
        return json.loads(resp.read())
    except urllib.error.HTTPError as e:
        body = e.read().decode()
        print(f"Discord API error {e.code}: {body[:200]}", file=sys.stderr)
        return None

def send_message(channel_id, content, thread_id=None):
    path = f"/channels/{channel_id}/messages" if not thread_id else f"/channels/{thread_id}/messages"
    return discord_request("POST", path, {"content": content})

def send_thread_message(thread_id, content):
    return discord_request("POST", f"/channels/{thread_id}/messages", {"content": content})

# ── Command handlers ─────────────────────────────────────────────────────────

def handle_status(thread_id, client_id=None):
    if not client_id:
        # Try to find client by thread
        client = get_client_by_thread(thread_id)
        if not client:
            return "⚠️ No client linked to this thread. Use `!status <client_id>` or create a thread from the dashboard first."
        client_id = client["id"]
    status = get_status(client_id)
    if not status:
        return f"⚠️ Client `{client_id}` not found."
    return (
        f"📊 **{status['name']}** Status\n"
        f"Domain: {status['domain']}\n"
        f"Health: {status['health_score']}% | Status: {status['status']}\n"
        f"Pending approvals: {status['pending_approvals']}\n"
        f"Open tasks: {status['open_tasks']}\n"
        f"Opportunities: {status['opportunities']}"
    )

def handle_approve(thread_id, approval_id=None):
    if approval_id:
        decide_approval(approval_id, "approved")
        return f"✅ Approval `{approval_id}` approved."
    # Show pending approvals
    client = get_client_by_thread(thread_id)
    if not client:
        # Show all pending
        pending = get_pending_approvals()
    else:
        pending = get_pending_approvals(client["id"])
    if not pending:
        return "No pending approvals."
    lines = ["📋 **Pending Approvals**\n"]
    for p in pending:
        lines.append(f"`{p['id']}` — {p['title']}")
    lines.append("\nUse `!approve <id>` to approve.")
    return "\n".join(lines)

def handle_reject(thread_id, approval_id=None, note=""):
    if approval_id:
        decide_approval(approval_id, "rejected", note)
        return f"❌ Approval `{approval_id}` rejected."
    return "⚠️ Specify an approval ID: `!reject <id> [note]`"

def handle_opps(thread_id, client_id=None):
    if not client_id:
        client = get_client_by_thread(thread_id)
        if client:
            client_id = client["id"]
    opps = get_opportunities(client_id)
    if not opps:
        return "No opportunities found."
    lines = ["📈 **Top Opportunities**\n"]
    for o in opps:
        lines.append(
            f"• {o['page']} — {o['problem']}\n"
            f"  Priority: {o['priority']} | Impr: {o['impressions']} | CTR: {o['ctr']}%"
        )
    return "\n".join(lines)

def handle_help():
    return (
        "🤖 **SEO OS Bot Commands**\n\n"
        "`!status [client_id]` — Show client status\n"
        "`!approve [id]` — Approve a pending request\n"
        "`!reject <id> [note]` — Reject a pending request\n"
        "`!opps [client_id]` — List top opportunities\n"
        "`!help` — Show this message\n\n"
        "When in a client thread, commands auto-target that client."
    )

# ── Main loop (Discord Gateway / polling) ────────────────────────────────────

def poll_messages():
    """Simple polling approach — checks for new messages in threads."""
    # Get active threads in the channel
    threads = discord_request("GET", f"/channels/{CHANNEL_ID}/threads/archived/public") or {}
    active = discord_request("GET", f"/channels/{CHANNEL_ID}/threads/active") or {}
    
    all_threads = threads.get("threads", []) + active.get("threads", [])
    
    for thread in all_threads:
        thread_id = thread["id"]
        # Get recent messages
        msgs = discord_request("GET", f"/channels/{thread_id}/messages?limit=10)") or []
        for msg in msgs.get("messages", []):
            content = msg.get("content", "").strip()
            if content.startswith("!"):
                author = msg.get("author", {})
                if author.get("bot"):
                    continue  # Skip bot messages
                process_command(thread_id, content)

def process_command(thread_id, content):
    parts = content.strip().split()
    if not parts:
        return
    cmd = parts[0].lower()
    args = parts[1:]

    # Find client linked to this thread
    client = get_client_by_thread(thread_id)
    client_id = client["id"] if client else None

    if cmd == "!help":
        response = handle_help()
    elif cmd == "!status":
        response = handle_status(thread_id, args[0] if args else client_id)
    elif cmd == "!approve":
        response = handle_approve(thread_id, args[0] if args else None)
    elif cmd == "!reject":
        note = " ".join(args[1:]) if len(args) > 1 else ""
        approval_id = args[0] if args else None
        response = handle_reject(thread_id, approval_id, note)
    elif cmd == "!opps":
        response = handle_opps(thread_id, args[0] if args else client_id)
    else:
        response = f"Unknown command: `{cmd}`. Type `!help` for available commands."

    if response:
        send_thread_message(thread_id, response)

# ── Entry point ──────────────────────────────────────────────────────────────

if __name__ == "__main__":
    print("SEO OS Discord bot starting...", file=sys.stderr)
    
    # Check DB exists
    if not DB_PATH.exists():
        print(f"ERROR: Database not found at {DB_PATH}", file=sys.stderr)
        sys.exit(1)
    
    # Check bot token works
    me = discord_request("GET", "/users/@me")
    if me:
        print(f"Bot connected: {me.get('username', '?')}#{me.get('discriminator', '0')}", file=sys.stderr)
    else:
        print("ERROR: Could not authenticate with Discord. Check bot token.", file=sys.stderr)
        sys.exit(1)
    
    print("Bot ready. Monitoring threads for commands...", file=sys.stderr)
    
    # Simple polling loop
    import time
    while True:
        try:
            poll_messages()
        except Exception as e:
            print(f"Error in poll loop: {e}", file=sys.stderr)
        time.sleep(10)  # Poll every 10 seconds
