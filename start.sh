#!/bin/bash
# SEO OS Command Center — Start both the dashboard server and Discord bot

# Load bot token from environment or .env file
if [ -f /root/.hermes/.env ]; then
    export $(grep DISCORD_BOT_TOKEN /root/.hermes/.env 2>/dev/null | xargs)
fi

if [ -z "$DISCORD_BOT_TOKEN" ]; then
    echo "ERROR: DISCORD_BOT_TOKEN not set. Add it to /root/.hermes/.env or export it manually."
    exit 1
fi

cd /root/seo-os-dashboard

# Kill any existing instances
kill $(lsof -t -i :8787) 2>/dev/null
pkill -f discord_bot.py 2>/dev/null
sleep 2

echo "Starting SEO OS Dashboard..."
python3 server.py --host 0.0.0.0 --port 8787 &
sleep 3

echo "Starting Discord Bot..."
python3 bot/discord_bot.py &

echo ""
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "  SEO OS Command Center is running!"
echo ""
echo "  Dashboard: http://127.0.0.1:8787"
echo "  (Use SSH tunnel: ssh -L 8787:127.0.0.1:8787 root@<vps-ip> -N)"
echo ""
echo "  Discord Bot: Running (polling threads every 10s)"
echo "  Channel: #seo-clients"
echo ""
echo "  Commands in Discord threads:"
echo "    !status [client_id]  — Show client status"
echo "    !approve [id]        — Approve a pending request"
echo "    !reject <id> [note]  — Reject a pending request"
echo "    !opps [client_id]    — List top opportunities"
echo "    !help                — Show all commands"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
