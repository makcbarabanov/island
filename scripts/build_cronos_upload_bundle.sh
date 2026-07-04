#!/usr/bin/env bash
# Собирает один файл для загрузки в Google AI Studio (у CRONOS нет доступа к диску).
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
OUT="$ROOT/Readme/CRONOS-upload-bundle.md"
BLOOM_TAIL_LINES="${BLOOM_TAIL_LINES:-180}"

{
  cat <<'HEADER'
# CRONOS — upload bundle (Google AI Studio)

> **Для Макса:** прикрепи этот файл к первому сообщению в чате CRONOS (кнопка «+» / Insert files).
> Пересобирай после крупных изменений: `bash scripts/build_cronos_upload_bundle.sh`

HEADER
  echo "Собрано: $(date -Iseconds)"
  echo
  echo "---"
  echo
  echo "# Раздел 1. Handoff"
  echo
  cat "$ROOT/Readme/CRONOS-handoff.md"
  echo
  echo "---"
  echo
  echo "# Раздел 2. DECISIONS (ADR)"
  echo
  cat "$ROOT/Readme/DECISIONS.md"
  echo
  echo "---"
  echo
  echo "# Раздел 3. RUNBOOK (выдержка: песок + прод)"
  echo
  sed -n '1,122p' "$ROOT/Readme/RUNBOOK.md"
  echo
  echo "---"
  echo
  echo "# Раздел 4. AGENTS (роли ИИ)"
  echo
  cat "$ROOT/Readme/AGENTS.md"
  echo
  echo "---"
  echo
  echo "# Раздел 5. Bloom.txt (хвост, последние ${BLOOM_TAIL_LINES} строк)"
  echo
  if [[ -f "$ROOT/chat/Bloom.txt" ]]; then
    tail -n "$BLOOM_TAIL_LINES" "$ROOT/chat/Bloom.txt"
  else
    echo "(chat/Bloom.txt не найден)"
  fi
} >"$OUT"

echo "Wrote $OUT ($(wc -c <"$OUT") bytes)"
