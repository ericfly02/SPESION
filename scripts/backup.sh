#!/usr/bin/env bash
# =============================================================================
# SPESION 2.0 — Backup Script
# =============================================================================
# Usage:  chmod +x scripts/backup.sh && ./scripts/backup.sh
# Recommended: add to crontab:  0 3 * * * /opt/spesion/scripts/backup.sh
# =============================================================================

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
PROJECT_DIR="$(dirname "$SCRIPT_DIR")"
BACKUP_DIR="$PROJECT_DIR/data/backups"
TIMESTAMP=$(date +%Y%m%d_%H%M%S)

mkdir -p "$BACKUP_DIR"

echo "🗂️  SPESION Backup — $TIMESTAMP"

# Backup SQLite (hot copy)
if [ -f "$PROJECT_DIR/data/sessions.db" ]; then
    sqlite3 "$PROJECT_DIR/data/sessions.db" ".backup '$BACKUP_DIR/sessions_$TIMESTAMP.db'"
    echo "  ✅ sessions.db backed up"
fi

# Backup ChromaDB directory
if [ -d "$PROJECT_DIR/data/chroma" ]; then
    tar -czf "$BACKUP_DIR/chroma_$TIMESTAMP.tar.gz" -C "$PROJECT_DIR/data" chroma
    echo "  ✅ chroma/ backed up"
fi

# Backup user profile
if [ -f "$PROJECT_DIR/data/user_profile.md" ]; then
    cp "$PROJECT_DIR/data/user_profile.md" "$BACKUP_DIR/user_profile_$TIMESTAMP.md"
    echo "  ✅ user_profile.md backed up"
fi

# Backup .env (encrypted would be better, but at least it's local)
if [ -f "$PROJECT_DIR/.env" ]; then
    cp "$PROJECT_DIR/.env" "$BACKUP_DIR/env_$TIMESTAMP.bak"
    chmod 600 "$BACKUP_DIR/env_$TIMESTAMP.bak"
    echo "  ✅ .env backed up (chmod 600)"
fi

# Prune old backups (keep last 14 days)
find "$BACKUP_DIR" -name "*.db" -mtime +14 -delete 2>/dev/null || true
find "$BACKUP_DIR" -name "*.tar.gz" -mtime +14 -delete 2>/dev/null || true
find "$BACKUP_DIR" -name "*.md" -mtime +14 -delete 2>/dev/null || true
find "$BACKUP_DIR" -name "*.bak" -mtime +14 -delete 2>/dev/null || true

echo "  🧹 Pruned backups older than 14 days"
echo "  📁 Backup location: $BACKUP_DIR"
echo "  ✅ Done!"
