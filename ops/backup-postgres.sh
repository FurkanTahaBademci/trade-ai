#!/bin/sh
set -eu

umask 077
backup_dir=${BACKUP_DIR:-./backups}
mkdir -p "$backup_dir"
stamp=$(date -u +%Y%m%dT%H%M%SZ)
target="$backup_dir/trade-ai-$stamp.dump"
temporary="$target.partial"
trap 'rm -f "$temporary"' EXIT INT TERM

docker compose exec -T postgres sh -c \
  'pg_dump -U "$POSTGRES_USER" -d "$POSTGRES_DB" --format=custom --no-owner --no-privileges' \
  > "$temporary"
mv "$temporary" "$target"
trap - EXIT INT TERM
printf '%s\n' "$target"
