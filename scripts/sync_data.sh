#!/usr/bin/env bash
# Синхронизация песочницы с прод-БД: дамп → restore в Docker → снимок /stat/.
#
# Использование (из корня репо):
#   bash scripts/sync_data.sh        # с подтверждением
#   bash scripts/sync_data.sh -y   # без вопросов
#
# Требует: .env (DB_USER, DB_PASS, DB_NAME), docker compose, доступ к прод-БД.
# Опционально в .env, если прод-БД ≠ локальный Docker:
#   SYNC_DB_HOST=83.217.220.97  SYNC_DB_USER=…  SYNC_DB_PASS=…

set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"

COMPOSE=(docker compose -f docker-compose.yml -f docker-compose.dev.yml)
BACKUP_DIR="${BACKUP_DIR:-$HOME/Backups/island}"
PG_IMAGE="${PG_IMAGE:-postgres:17}"
STAT_URL="${STAT_URL:-http://127.0.0.1:8001/stat/}"
AUTO_YES=false

docker_network() {
  local cid
  cid="$("${COMPOSE[@]}" ps -q db 2>/dev/null | head -1)" || return 1
  [[ -n "$cid" ]] || return 1
  docker inspect "$cid" --format '{{range $k,$v := .NetworkSettings.Networks}}{{$k}}{{end}}' | head -1
}

for arg in "$@"; do
  case "$arg" in
    -y|--yes) AUTO_YES=true ;;
    -h|--help)
      echo "Usage: bash scripts/sync_data.sh [-y]"
      echo "  Скачивает дамп с прод-БД, разворачивает в island-db-1, строит marathon_snapshot.json"
      exit 0
      ;;
    *)
      echo "Неизвестный аргумент: $arg (см. --help)" >&2
      exit 2
      ;;
  esac
done

if [[ ! -f .env ]]; then
  echo "Ошибка: нет .env в $ROOT" >&2
  exit 1
fi

read_env() {
  local key="$1"
  local line
  line="$(grep -E "^${key}=" .env | head -1 | tr -d '\r')" || true
  if [[ -z "$line" ]]; then
    return 1
  fi
  printf '%s' "${line#*=}" | sed -e 's/^["'\'']//' -e 's/["'\'']$//' -e 's/^[[:space:]]*//' -e 's/[[:space:]]*$//'
}

DB_USER="$(read_env DB_USER 2>/dev/null || echo marabot)"
DB_NAME="$(read_env DB_NAME 2>/dev/null || echo default_db)"
DB_PORT="$(read_env DB_PORT 2>/dev/null || echo 5432)"
DB_PASS="$(read_env DB_PASS)" || { echo "Ошибка: в .env нет DB_PASS" >&2; exit 1; }
DB_SSLMODE="$(read_env DB_SSLMODE 2>/dev/null || echo prefer)"

# Для дампа с прода (если креды/хост отличаются от локального Docker):
SYNC_DB_HOST="${SYNC_DB_HOST:-$(read_env SYNC_DB_HOST 2>/dev/null || echo 83.217.220.97)}"
SYNC_DB_USER="${SYNC_DB_USER:-$(read_env SYNC_DB_USER 2>/dev/null || echo "$DB_USER")}"
SYNC_DB_PASS="${SYNC_DB_PASS:-$(read_env SYNC_DB_PASS 2>/dev/null || echo "$DB_PASS")}"
SYNC_DB_PORT="${SYNC_DB_PORT:-$(read_env SYNC_DB_PORT 2>/dev/null || echo "$DB_PORT")}"
SYNC_DB_NAME="${SYNC_DB_NAME:-$(read_env SYNC_DB_NAME 2>/dev/null || echo "$DB_NAME")}"

mkdir -p "$BACKUP_DIR"
TS="$(date +%Y%m%d_%H%M%S)"
PROD_DUMP="$BACKUP_DIR/prod_${SYNC_DB_NAME}_${TS}.dump"
SANDBOX_DUMP="$BACKUP_DIR/sandbox_${DB_NAME}_before_sync_${TS}.dump"

echo "=== ОСТРОВ: sync_data (песок ← прод-БД) ==="
echo "Прод-БД:  ${SYNC_DB_HOST}:${SYNC_DB_PORT}/${SYNC_DB_NAME}"
echo "Локально: Docker db (${COMPOSE[*]})"
echo "Дамп:     $PROD_DUMP"
echo ""

if [[ "$AUTO_YES" != true ]]; then
  read -r -p "Локальная БД в Docker будет ПЕРЕЗАПИСАНА. Прод не трогаем. Продолжить? [y/N] " ans
  case "$ans" in
    y|Y|yes|YES|д|Д) ;;
    *) echo "Отменено."; exit 0 ;;
  esac
fi

echo "==> Поднимаем db (если нужно)"
"${COMPOSE[@]}" up -d db
"${COMPOSE[@]}" up -d app 2>/dev/null || true

echo "==> Ждём healthy db"
for i in $(seq 1 40); do
  if "${COMPOSE[@]}" ps db 2>/dev/null | grep -q '(healthy)'; then
    break
  fi
  sleep 1
  if [[ "$i" -eq 40 ]]; then
    echo "Ошибка: контейнер db не стал healthy" >&2
    exit 1
  fi
done

echo "==> Бэкап текущей песочной БД"
if "${COMPOSE[@]}" exec -T db pg_isready -U "$DB_USER" -d "$DB_NAME" >/dev/null 2>&1; then
  "${COMPOSE[@]}" exec -T db pg_dump -U "$DB_USER" -d "$DB_NAME" -F c >"$SANDBOX_DUMP"
  echo "    Сохранён: $SANDBOX_DUMP"
else
  echo "    Песочная БД пуста или недоступна — бэкап пропущен"
fi

echo "==> Скачиваем свежий дамп с прода"
export PGPASSWORD="$SYNC_DB_PASS"
export PGSSLMODE="$DB_SSLMODE"
if ! docker run --rm \
  -e PGPASSWORD \
  -e PGSSLMODE \
  "$PG_IMAGE" \
  pg_dump -h "$SYNC_DB_HOST" -p "$SYNC_DB_PORT" -U "$SYNC_DB_USER" -d "$SYNC_DB_NAME" -F c \
  >"$PROD_DUMP"; then
  unset PGPASSWORD
  echo "Ошибка pg_dump. Проверь:" >&2
  echo "  • SYNC_DB_PASS в .env — если пароль прода ≠ локального DB_PASS" >&2
  echo "  • PG_IMAGE=postgres:17 — клиент не ниже сервера (прод сейчас PG 17)" >&2
  exit 1
fi
unset PGPASSWORD
echo "    Сохранён: $PROD_DUMP ($(du -h "$PROD_DUMP" | cut -f1))"

echo "==> Restore в локальный Docker"
"${COMPOSE[@]}" exec -T db psql -U "$DB_USER" -d postgres -v ON_ERROR_STOP=1 <<SQL
SELECT pg_terminate_backend(pid)
FROM pg_stat_activity
WHERE datname = '$DB_NAME' AND pid <> pg_backend_pid();
SQL

"${COMPOSE[@]}" exec -T db dropdb -U "$DB_USER" --if-exists "$DB_NAME"
"${COMPOSE[@]}" exec -T db createdb -U "$DB_USER" "$DB_NAME"

NET="$(docker_network)" || { echo "Ошибка: не найдена docker-сеть db" >&2; exit 1; }

# pg_restore из PG 17 (формат 1.16) — клиент в контейнере, сервер в island-db-1 (может быть PG 15)
set +e
export PGPASSWORD="$DB_PASS"
pg_restore_out="$(
  docker run --rm \
    --network "$NET" \
    -e PGPASSWORD \
    -v "$PROD_DUMP:/dump.dump:ro" \
    "$PG_IMAGE" \
    pg_restore -h db -p 5432 -U "$DB_USER" -d "$DB_NAME" --no-owner --no-privileges /dump.dump 2>&1
)"
pg_restore_rc=$?
unset PGPASSWORD
set -e
if [[ "$pg_restore_rc" -ne 0 ]]; then
  echo "$pg_restore_out" | tail -20
  if ! "${COMPOSE[@]}" exec -T db psql -U "$DB_USER" -d "$DB_NAME" -tAc "SELECT 1 FROM users LIMIT 1" | grep -q 1; then
    echo "Ошибка: restore не удался (users пуста)" >&2
    exit 1
  fi
  echo "    pg_restore вернул $pg_restore_rc, но данные на месте — продолжаем"
fi

echo "==> Снимок марафона для /stat/"
"${COMPOSE[@]}" up -d app
sleep 2
"${COMPOSE[@]}" exec -T app python3 scripts/build_marathon_snapshot.py

USERS="$("${COMPOSE[@]}" exec -T db psql -U "$DB_USER" -d "$DB_NAME" -tAc 'SELECT COUNT(*) FROM users')"
DREAMS="$("${COMPOSE[@]}" exec -T db psql -U "$DB_USER" -d "$DB_NAME" -tAc 'SELECT COUNT(*) FROM dreams')"

echo ""
echo "=== Готово ==="
echo "users:  $USERS"
echo "dreams: $DREAMS"
echo "stat:   $STAT_URL"
echo "дамп:   $PROD_DUMP"
if [[ -f "$SANDBOX_DUMP" ]]; then
  echo "откат:  cat $SANDBOX_DUMP | ${COMPOSE[*]} exec -T db pg_restore -U $DB_USER -d $DB_NAME --clean --if-exists"
fi
