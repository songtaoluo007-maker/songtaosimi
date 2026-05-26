#!/bin/bash
set -e
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
PROJECT_DIR="$(dirname "$SCRIPT_DIR")"

echo "=== Backend Tests ==="
cd "$PROJECT_DIR"
python -m pytest backend/tests/ -v --tb=short

echo ""
echo "=== All Done ==="
