#!/bin/sh
set -eu

backup_file=${1:-}
if [ -z "$backup_file" ] || [ ! -f "$backup_file" ]; then
  echo "Kullanim: CONFIRM_RESTORE=trade-ai $0 backups/trade-ai-....dump" >&2
  exit 2
fi
if [ "${CONFIRM_RESTORE:-}" != "trade-ai" ]; then
  echo "Geri yukleme mevcut veritabanini degistirir. CONFIRM_RESTORE=trade-ai gerekli." >&2
  exit 2
fi

docker compose exec -T postgres sh -c \
  'pg_restore -U "$POSTGRES_USER" -d "$POSTGRES_DB" --clean --if-exists --no-owner --no-privileges' \
  < "$backup_file"
echo "Geri yukleme tamamlandi: $backup_file"
