#!/bin/sh
# .env.example'dan guclu, rastgele parolalarla doldurulmus bir .env uretir.
#
#   make init               (veya: ./ops/init-env.sh)
#   FORCE=1 make init       mevcut .env'in uzerine yazar (eski parolalar kaybolur!)
#
# Uretilen degerler: POSTGRES_PASSWORD (+ DATABASE_URL), ADMIN_API_TOKEN,
# WEB_ADMIN_PASSWORD. Yonetim girisi bilgileri sonda bir kez ekrana yazilir.
set -eu

target=${ENV_FILE:-.env}
cd "$(dirname "$0")/.."

if [ -e "$target" ] && [ "${FORCE:-0}" != 1 ]; then
  echo "$target zaten var; dokunulmadi. Yeniden uretmek icin: FORCE=1 make init" >&2
  echo "(Dikkat: mevcut PostgreSQL volume'u eski parolayla olusturulduysa yeni parola calismaz.)" >&2
  exit 1
fi

rand_hex() {
  if command -v openssl >/dev/null 2>&1; then
    openssl rand -hex "$1"
  else
    python3 -c 'import secrets, sys; print(secrets.token_hex(int(sys.argv[1])))' "$1"
  fi
}

value_of() {
  awk -v wanted="$1" 'index($0, wanted "=") == 1 {sub(/^[^=]*=/, ""); print; exit}' .env.example
}

# Hex parolalar URL icinde kacis gerektirmez (DATABASE_URL guvenli kalir).
pg_password=$(rand_hex 24)
admin_token=$(rand_hex 32)
web_password=$(rand_hex 16)
pg_user=$(value_of POSTGRES_USER)
pg_db=$(value_of POSTGRES_DB)
web_user=$(value_of WEB_ADMIN_USERNAME)

umask 077
sed \
  -e "s|^POSTGRES_PASSWORD=.*|POSTGRES_PASSWORD=$pg_password|" \
  -e "s|^DATABASE_URL=.*|DATABASE_URL=postgresql+asyncpg://$pg_user:$pg_password@postgres:5432/$pg_db|" \
  -e "s|^ADMIN_API_TOKEN=.*|ADMIN_API_TOKEN=$admin_token|" \
  -e "s|^WEB_ADMIN_PASSWORD=.*|WEB_ADMIN_PASSWORD=$web_password|" \
  .env.example > "$target"

echo "$target olusturuldu (izinler: 600)."
echo
echo "Yonetim ekranlari (/sistem, /backtest) icin giris bilgileri:"
echo "  Kullanici adi: ${web_user:-admin}"
echo "  Parola:        $web_password"
echo
echo "Bu bilgiler $target icinde de duruyor. Ayrinti: docs/ADMIN.md"
