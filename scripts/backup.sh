#!/bin/bash
# SEO OS Dashboard — backup before destructive operations
# Creates a timestamped copy of the SQLite database

set -e

DB_PATH="${SEO_OS_DB_PATH:-/root/seo-os-dashboard/data/seo-os.sqlite}"
BACKUP_DIR="/root/seo-os-dashboard/backups"

backup() {
    mkdir -p "$BACKUP_DIR"
    local timestamp=$(date +%Y%m%d_%H%M%S)
    local backup_file="${BACKUP_DIR}/seo-os_${timestamp}.sqlite"
    
    if [ -f "$DB_PATH" ]; then
        cp "$DB_PATH" "$backup_file"
        echo "Backup created: $backup_file"
        
        # Keep only last 7 backups
        ls -t "${BACKUP_DIR}"/seo-os_*.sqlite 2>/dev/null | tail -n +8 | xargs rm -f 2>/dev/null || true
    fi
}

backup
