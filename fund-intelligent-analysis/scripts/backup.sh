#!/bin/bash
# 基金智能分析系统 - 数据库备份脚本
DB_PATH="$(dirname "$0")/../data/fund_quant.db"
BACKUP_DIR="$(dirname "$0")/../data/backups"
TIMESTAMP=$(date +%Y%m%d_%H%M%S)
BACKUP_FILE="$BACKUP_DIR/fund_quant_$TIMESTAMP.db"

mkdir -p "$BACKUP_DIR"

python -c "
import sqlite3, shutil
shutil.copy2('$DB_PATH', '$BACKUP_FILE')
print('[OK] Backup created:', '$BACKUP_FILE'.split('/')[-1])
"

if [ -f "$BACKUP_FILE" ]; then
    # Keep only last 7 days
    find "$BACKUP_DIR" -name "fund_quant_*.db" -mtime +7 -delete 2>/dev/null
    echo "[OK] Cleaned up old backups (keeping 7 days)"
else
    echo "[FAIL] Backup failed!"
    exit 1
fi
