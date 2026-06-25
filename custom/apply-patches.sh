#!/bin/bash
# apply-patches.sh — Re-applies custom changes after upstream update
# Run this after: git pull upstream && git merge upstream/main
# Or after copying fresh upstream files into your fork

set -e
cd "$(dirname "$0")/.."

echo "=== Applying custom patches for SEO Command Center ==="

# 1. Create client_health table if not exists
echo "→ Ensuring client_health table exists..."
python3 -c "
import sqlite3
conn = sqlite3.connect('data/seo-os.sqlite')
conn.execute('''CREATE TABLE IF NOT EXISTS client_health (
  id TEXT PRIMARY KEY,
  client_id TEXT NOT NULL UNIQUE,
  score INTEGER NOT NULL DEFAULT 50,
  status TEXT NOT NULL DEFAULT 'yellow',
  components_json TEXT NOT NULL DEFAULT '{}',
  pages_ranking INTEGER NOT NULL DEFAULT 0,
  high_priority_opps INTEGER NOT NULL DEFAULT 0,
  total_opportunities INTEGER NOT NULL DEFAULT 0,
  updated_at TEXT NOT NULL
)''')
conn.commit()
print('  ✓ client_health table ready')
"

# 2. Verify custom files are in place
echo "→ Checking custom files..."
for f in scripts/ga4_data_pull.py scripts/gsc_data_pull.py prospects.py; do
  if [ -f "$f" ]; then
    echo "  ✓ $f exists"
  else
    echo "  ⚠ MISSING: $f — you need to restore this file"
  fi
done

# 3. Restart server
echo "→ Restarting server..."
kill $(lsof -t -i :8787) 2>/dev/null || true
sleep 1
nohup python3 server.py --host 0.0.0.0 --port 8787 > /tmp/server.log 2>&1 &
sleep 2

# 4. Verify health
echo "→ Health check..."
curl -s http://127.0.0.1:8787/api/health | python3 -c "import sys,json; d=json.load(sys.stdin); print(f'  ✓ Server OK — {d[\"clients\"]} clients')"

echo ""
echo "=== Patches applied. Dashboard: http://$(curl -s ifconfig.me):8787 ==="
