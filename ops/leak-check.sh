#!/usr/bin/env bash
# Repoya girecek dosyalarda secret ve kisisel veri sizintisi arar.
#
#   ops/leak-check.sh            (veya: make leak-check)
#   GITLEAKS_DOCKER=1 make leak-check    gitleaks'i Docker'dan da calistirir
#
# - Taranan kume: git'te izlenen + izlenmeyip .gitignore'a takilmayan dosyalar,
#   yani commit'lenebilecek her sey.
# - Yasakli dosya adlari ve icerik desenleri aranir; bulunursa cikis kodu 1.
#   Kisiye ozel desenler (canli alan adi, sunucu IP'si...) repoya yazilmaz:
#   LEAK_DENY_PATTERNS ortam degiskeni (CI secret'i) veya git disi .leak-deny
#   dosyasi, satir basina bir grep -E deseni.
# - gitleaks kuruluysa (veya GITLEAKS_DOCKER=1 ile) secret taramasi da calisir.
set -euo pipefail

root=$(git rev-parse --show-toplevel)
cd "$root"

work=$(mktemp -d)
trap 'rm -rf "$work"' EXIT
git ls-files -z --cached --others --exclude-standard > "$work/files"

# Silinmis ama henuz commit'lenmemis dosyalari atla.
snapshot="$work/tree"
mkdir -p "$snapshot"
while IFS= read -r -d '' path; do
  [ -f "$path" ] || continue
  mkdir -p "$snapshot/$(dirname "$path")"
  cp -p "$path" "$snapshot/$path"
done < "$work/files"

failures=0

# 1) Asla commit'lenmemesi gereken dosya adlari
bad_files=$(cd "$snapshot" && find . -type f \( -name '.env' -o -name '.env.*' ! -name '.env.example' \
  -o -name '*.pem' -o -name '*.key' -o -name 'id_rsa*' -o -name 'id_ed25519*' -o -name '*.dump' \
  -o -name '.leak-deny' \) -print)
if [ -n "$bad_files" ]; then
  printf 'FAIL  yasakli dosya(lar):\n%s\n' "$bad_files" >&2
  failures=$((failures + 1))
fi

# 2) Icerik desenleri: genel olanlar burada, kisiye ozel olanlar secret/yerel dosyada
patterns="$work/patterns"
cat > "$patterns" <<'EOF'
C:\\Users\\
/home/[a-z][a-z0-9_-]*/
@gmail\.com
AIza[0-9A-Za-z_-]{30,}
-----BEGIN [A-Z ]*PRIVATE KEY-----
EOF
if [ -n "${LEAK_DENY_PATTERNS:-}" ]; then
  printf '%s\n' "$LEAK_DENY_PATTERNS" >> "$patterns"
fi
if [ -f .leak-deny ]; then
  grep -v '^[[:space:]]*\(#\|$\)' .leak-deny >> "$patterns" || true
fi
sed -i '/^[[:space:]]*$/d' "$patterns"
hits=$(cd "$snapshot" && grep -rInE -f "$patterns" . --exclude=package-lock.json --exclude=leak-check.sh || true)
if [ -n "$hits" ]; then
  # Eslesen satirin kendisini degil yalniz konumunu yaz: CI loguna sizinti olmasin.
  printf 'FAIL  yasakli icerik deseni bulundu:\n%s\n' "$(printf '%s\n' "$hits" | cut -d: -f1,2)" >&2
  failures=$((failures + 1))
fi

# 3) gitleaks secret taramasi
if command -v gitleaks >/dev/null 2>&1; then
  gitleaks detect --no-git --source "$snapshot" --redact --no-banner || failures=$((failures + 1))
elif [ "${GITLEAKS_DOCKER:-0}" = 1 ]; then
  docker run --rm -v "$snapshot:/repo:ro" zricethezav/gitleaks:v8.18.4 \
    detect --no-git --source /repo --redact --no-banner || failures=$((failures + 1))
else
  echo "INFO  gitleaks bulunamadi; secret taramasi atlandi (GITLEAKS_DOCKER=1 ile Docker'dan calistir)"
fi

if [ "$failures" -gt 0 ]; then
  echo "Sizinti denetimi BASARISIZ: $failures kontrol." >&2
  exit 1
fi
echo "OK    sizinti denetimi temiz"
