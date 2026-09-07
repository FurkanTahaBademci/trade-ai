#!/bin/sh
set -eu

web_url=${WEB_URL:-http://localhost:3000}
api_url=${API_URL:-http://localhost:8000}

check() {
  label=$1
  url=$2
  curl --fail --silent --show-error --max-time 20 "$url" >/dev/null
  printf 'OK  %s  %s\n' "$label" "$url"
}

check "API process" "$api_url/health"
check "API dependencies" "$api_url/health/detailed"
check "Schedules" "$api_url/api/schedules"
check "Web process" "$web_url/health"
check "Dashboard" "$web_url/"
check "System UI" "$web_url/sistem"
check "Macro UI" "$web_url/makro"
echo "Production smoke kontrolleri tamamlandi."
