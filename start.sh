#!/bin/bash
# SEO OS Command Center — Start both the dashboard server and Discord bot
# Uses systemd if available, otherwise falls back to direct process management

set -e

cd /root/seo-os-dashboard

# Load environment
if [ -f /root/.hermes/.env ]; then
    set -a
    source /root/.hermes/.env
    set +a
fi
if [ -f .env ]; then
    set -a
    source .env
    set +a
fi

# Check required env
if [ -z "$DISCORD_BOT_TOKEN" ]; then
    echo "ERROR: DISCORD_BOT_TOKEN not set. Add it to /root/.hermes/.env or .env"
    exit 1
fi

HOST="${SEO_OS_HOST:-127.0.0.1}"
PORT="${SEO_OS_PORT:-8787}"

# ─── Use systemd if available ───────────────────────────────────────────────
if command -v systemctl &>/dev/null && [ -f seo-os-dashboard.service ]; then
    echo "Installing systemd service..."
    cp seo-os-dashboard.service /etc/systemd/system/
    cp .env.example /etc/default/seo-os-dashboard 2>/dev/null || true
    systemctl daemon-reload
    systemctl enable seo-os-dashboard
    systemctl restart seo-os-dashboard
    echo "SEO OS Dashboard started via systemd: systemctl status seo-os-dashboard"
    exit 0
fi

# ─── Fallback: direct process management ────────────────────────────────────
echo "systemd not available, using direct process management..."

# Stop existing instances safely (by PID, not by broad pkill)
stop_service() {
    local name="$1"
    local pidfile="/tmp/seo-os-${name}.pid"
    if [ -f "$pidfile" ]; then
        local pid=$(cat "$pidfile")
        if kill -0 "$pid" 2>/dev/null; then
            echo "Stopping $name (PID $pid)..."
            kill "$pid" 2>/dev/null || true
            sleep 1
            kill -9 "$pid" 2>/dev/null || true
        fi
        rm -f "$pidfile"
    fi
    # Fallback: use specific pattern (not broad pkill -f)
    pkill -f "python3 server.py --host.*--port $PORT" 2>/dev/null || true
}

stop_service "dashboard"
stop_service "discord"

# Start dashboard
echo "Starting SEO OS Dashboard..."
python3 server.py --host "$HOST" --port "$PORT" > /tmp/seo-os-dashboard.log 2>&1 &
echo $! > /tmp/seo-os-dashboard.pid
sleep 3

# Verify dashboard started
if ! kill -0 "$(cat /tmp/seo-os-dashboard.pid)" 2>/dev/null; then
    echo "ERROR: Dashboard failed to start. Check /tmp/seo-os-dashboard.log"
    cat /tmp/seo-os-dashboard.log | tail -20
    exit 1
fi

# Start Discord bot
echo "Starting Discord Bot..."
python3 bot/discord_bot.py > /tmp/seo-os-discord.log 2>&1 &
echo $! > /tmp/seo-os-discord.pid

echo ""
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "  SEO OS Command Center is running!"
echo ""
echo "  Dashboard: http://${HOST}:${PORT}"
echo "  (Use SSH tunnel: ssh -L ${PORT}:127.0.0.1:${PORT} root@<vps-ip> -N)"
echo ""
echo "  PID files: /tmp/seo-os-dashboard.pid /tmp/seo-os-discord.pid"
echo "  Logs: /tmp/seo-os-dashboard.log /tmp/seo-os-discord.log"
echo ""
echo "  Commands in Discord threads:"
echo "    !status [client_id]  — Show client status"
echo "    !approve [id]        — Approve a pending request"
echo "    !reject <id> [note]  — Reject a pending request"
echo "    !opps [client_id]    — List top opportunities"
echo "    !help                — Show all commands"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
