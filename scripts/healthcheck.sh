#!/bin/bash
# SEO OS Dashboard healthcheck
# Returns 0 if healthy, 1 if not

set -e

PORT="${SEO_OS_PORT:-8787}"
HOST="${SEO_OS_HOST:-127.0.0.1}"
DB_PATH="${SEO_OS_DB_PATH:-/root/seo-os-dashboard/data/seo-os.sqlite}"

# 1. Check HTTP responds
if ! curl -sf "http://${HOST}:${PORT}/" > /dev/null 2>&1; then
    echo "UNHEALTHY: HTTP check failed on ${HOST}:${PORT}"
    exit 1
fi

# 2. Check API responds with valid JSON
if ! curl -sf "http://${HOST}:${PORT}/api/summary?client=all" | python3 -c "import sys,json; json.load(sys.stdin)" 2>/dev/null; then
    echo "UNHEALTHY: API summary endpoint not returning JSON"
    exit 1
fi

# 3. Check SQLite DB exists and is writable
if [ ! -f "$DB_PATH" ]; then
    echo "UNHEALTHY: Database not found at ${DB_PATH}"
    exit 1
fi

if ! python3 -c "
import sqlite3, sys
conn = sqlite3.connect('${DB_PATH}')
conn.execute('SELECT 1')
conn.close()
" 2>/dev/null; then
    echo "UNHEALTHY: Database not queryable"
    exit 1
fi

echo "HEALTHY: Dashboard on ${HOST}:${PORT}, DB OK"
exit 0
