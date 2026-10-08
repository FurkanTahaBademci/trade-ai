#!/bin/sh
set -eu

env_file=${ENV_FILE:-.env}
failures=0

setting() {
  name=$1
  value=$(printenv "$name" 2>/dev/null || true)
  if [ -n "$value" ]; then
    printf '%s' "$value"
    return
  fi
  if [ -f "$env_file" ]; then
    awk -v wanted="$name" 'index($0, wanted "=") == 1 {sub(/^[^=]*=/, ""); print; exit}' "$env_file"
  fi
}

pass() {
  printf 'OK    %s\n' "$1"
}

fail() {
  printf 'FAIL  %s\n' "$1" >&2
  failures=$((failures + 1))
}

environment=$(setting ENVIRONMENT)
[ "$environment" = "production" ] && pass "ENVIRONMENT=production" || fail "ENVIRONMENT production olmali"

postgres_password=$(setting POSTGRES_PASSWORD)
case "$postgres_password" in
  ""|tradeai|changeme|replace-*) fail "POSTGRES_PASSWORD guclu ve benzersiz olmali" ;;
  *) [ ${#postgres_password} -ge 16 ] && pass "POSTGRES_PASSWORD yapilandirildi" || fail "POSTGRES_PASSWORD en az 16 karakter olmali" ;;
esac

database_url=$(setting DATABASE_URL)
case "$database_url" in
  postgresql+asyncpg://*)
    case "$database_url" in
      *:tradeai@*) fail "DATABASE_URL varsayilan parolayi kullaniyor" ;;
      *) pass "DATABASE_URL async PostgreSQL icin yapilandirildi" ;;
    esac
    ;;
  *) fail "DATABASE_URL postgresql+asyncpg:// ile baslamali" ;;
esac

admin_token=$(setting ADMIN_API_TOKEN)
case "$admin_token" in
  ""|changeme|replace-*) fail "ADMIN_API_TOKEN rastgele bir secret olmali" ;;
  *) [ ${#admin_token} -ge 32 ] && pass "ADMIN_API_TOKEN yapilandirildi" || fail "ADMIN_API_TOKEN en az 32 karakter olmali" ;;
esac

web_admin_password=$(setting WEB_ADMIN_PASSWORD)
if [ -n "$web_admin_password" ]; then
  [ ${#web_admin_password} -ge 16 ] && pass "WEB_ADMIN_PASSWORD yapilandirildi" || fail "WEB_ADMIN_PASSWORD en az 16 karakter olmali"
else
  printf 'WARN  WEB_ADMIN_PASSWORD bos; yonetim girisi ADMIN_API_TOKEN parolasini kullanacak\n'
fi

public_api_url=$(setting NEXT_PUBLIC_API_URL)
case "$public_api_url" in
  "") pass "Public API adresi kapali; web private API agini kullanacak" ;;
  https://*)
    case "$public_api_url" in
      *localhost*|*127.0.0.1*|*example.com*) fail "NEXT_PUBLIC_API_URL gercek production domaini olmali" ;;
      *) pass "NEXT_PUBLIC_API_URL HTTPS kullaniyor" ;;
    esac
    ;;
  *) fail "NEXT_PUBLIC_API_URL tanimliysa HTTPS adresi olmali" ;;
esac

cors_origins=$(setting CORS_ORIGINS)
case "$cors_origins" in
  *https://*)
    case "$cors_origins" in
      *localhost*|*127.0.0.1*|*example.com*|*\**) fail "CORS_ORIGINS yalniz gercek HTTPS originlerini icermeli" ;;
      *) pass "CORS_ORIGINS daraltilmis HTTPS originleri kullaniyor" ;;
    esac
    ;;
  *) fail "CORS_ORIGINS en az bir HTTPS origin icermeli" ;;
esac

allowed_hosts=$(setting ALLOWED_HOSTS)
case "$allowed_hosts" in
  ""|*example.com*|*\**|*://*) fail "ALLOWED_HOSTS guvenilir API hostlarini icermeli" ;;
  *)
    case ",$allowed_hosts," in
      *,api,*) pass "ALLOWED_HOSTS private API hostname'ini iceriyor" ;;
      *) fail "ALLOWED_HOSTS private 'api' hostname'ini icermeli" ;;
    esac
    ;;
esac

if docker compose config --quiet; then
  pass "Docker Compose yapilandirmasi gecerli"
else
  fail "Docker Compose yapilandirmasi gecersiz"
fi

for optional_name in GEMINI_API_KEY N8N_WEBHOOK_URL; do
  if [ -n "$(setting "$optional_name")" ]; then
    pass "$optional_name opsiyonel entegrasyonu yapilandirildi"
  else
    printf 'INFO  %s bos; ilgili opsiyonel ozellik devre disi kalir\n' "$optional_name"
  fi
done

if [ "$failures" -gt 0 ]; then
  printf '\nProduction preflight basarisiz: %s duzeltme gerekli.\n' "$failures" >&2
  exit 1
fi

printf '\nProduction preflight basarili. Deploy sonrasi make production-smoke calistirin.\n'
