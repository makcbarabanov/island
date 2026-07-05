#!/usr/bin/env bash
# Полная синхронизация истории марафона из чата → _educ_* (песочница).
set -euo pipefail
cd "$(dirname "$0")/.."
PY="${PY:-.venv/bin/python3}"
echo "== 1/3 Чат 2025-07 … 2026-05 =="
"$PY" scripts/import_marathon_from_chat.py import
echo "== 2/3 Июнь 2026 (build-june) =="
"$PY" scripts/import_marathon_june_2026.py
echo "== 3/3 Проверка =="
"$PY" scripts/verify_marathon_db_sync.py
