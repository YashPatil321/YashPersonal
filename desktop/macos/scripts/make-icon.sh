#!/usr/bin/env bash
# make-icon.sh <App> <output.icns>: builds an .icns from desktop/icons/<App>.png with sips and iconutil.
set -euo pipefail
cd "$(dirname "$0")/.."
SRC="../icons/$1.png"
OUT="$2"
SET=$(mktemp -d)/AppIcon.iconset
mkdir -p "$SET"
for s in 16 32 128 256 512; do
  sips -z $s $s "$SRC" --out "$SET/icon_${s}x${s}.png" >/dev/null
  sips -z $((s*2)) $((s*2)) "$SRC" --out "$SET/icon_${s}x${s}@2x.png" >/dev/null
done
iconutil -c icns "$SET" -o "$OUT"
