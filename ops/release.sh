#!/usr/bin/env bash
# Yeni surum hazirlar: surum numarasini her yere yazar, CHANGELOG'u kapatir,
# commit + annotated tag olusturur. Push etmez; son adimi ekrana yazar.
#
#   ops/release.sh 0.2.0        (veya: make release VERSION=0.2.0)
#
# Surumleme: Semantic Versioning (MAJOR.MINOR.PATCH). Tek kaynak VERSION
# dosyasidir; backend/pyproject.toml ve web/package.json(+lock) ona esitlenir.
set -euo pipefail

new=${1:-}
root=$(git rev-parse --show-toplevel)
cd "$root"

if ! printf '%s' "$new" | grep -Eq '^[0-9]+\.[0-9]+\.[0-9]+$'; then
  echo "kullanim: ops/release.sh MAJOR.MINOR.PATCH (or. 0.2.0)" >&2
  exit 1
fi
current=$(tr -d '[:space:]' < VERSION)
if [ "$(printf '%s\n%s\n' "$current" "$new" | sort -V | tail -1)" != "$new" ] || [ "$current" = "$new" ]; then
  echo "Yeni surum ($new) mevcut surumden ($current) buyuk olmali." >&2
  exit 1
fi
if [ -n "$(git status --porcelain)" ]; then
  echo "Calisma agaci temiz degil; once degisiklikleri commit et." >&2
  exit 1
fi
branch=$(git rev-parse --abbrev-ref HEAD)
if [ "$branch" != "main" ]; then
  echo "Surumler main dalindan cikarilir (su an: $branch)." >&2
  exit 1
fi
if git rev-parse -q --verify "refs/tags/v$new" >/dev/null; then
  echo "v$new etiketi zaten var." >&2
  exit 1
fi

python3 - "$new" <<'PY'
import datetime
import json
import pathlib
import re
import sys

new = sys.argv[1]
pathlib.Path("VERSION").write_text(new + "\n")

pyproject = pathlib.Path("backend/pyproject.toml")
text, count = re.subn(r'(?m)^version = "[^"]+"$', f'version = "{new}"', pyproject.read_text(), count=1)
assert count == 1, "pyproject.toml icinde version satiri bulunamadi"
pyproject.write_text(text)

for name in ("web/package.json", "web/package-lock.json"):
    path = pathlib.Path(name)
    data = json.loads(path.read_text())
    data["version"] = new
    if "packages" in data and "" in data["packages"]:
        data["packages"][""]["version"] = new
    path.write_text(json.dumps(data, indent=2, ensure_ascii=False) + "\n")

changelog = pathlib.Path("CHANGELOG.md")
text = changelog.read_text()
marker = "## [Unreleased]"
start = text.index(marker) + len(marker)
nxt = text.find("\n## [", start)
body = text[start: nxt if nxt != -1 else len(text)].strip()
if not body:
    sys.exit("CHANGELOG.md [Unreleased] bolumu bos; once yapilan degisiklikleri yaz.")
today = datetime.date.today().isoformat()
text = text.replace(marker, f"{marker}\n\n## [{new}] - {today}", 1)
changelog.write_text(text)
PY

git add VERSION backend/pyproject.toml web/package.json web/package-lock.json CHANGELOG.md
git commit -q -m "chore(release): v$new"
git tag -a "v$new" -m "v$new"

echo "v$new hazir (commit + etiket olusturuldu)."
echo "Yayinlamak icin:  git push origin main --follow-tags"
echo "Etiket CI'dan gecince GitHub Release otomatik olusur (.github/workflows/release.yml)."
