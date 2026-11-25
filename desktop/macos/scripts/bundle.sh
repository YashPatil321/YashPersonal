#!/usr/bin/env bash
# Builds Halo.app and Lyra.app into build/ (universal: Apple silicon + Intel), ad-hoc signed.
set -euo pipefail
cd "$(dirname "$0")/.."

ARCHS=${ARCHS:-"arm64 x86_64"}
ARCH_FLAGS=()
for a in $ARCHS; do ARCH_FLAGS+=(--arch "$a"); done

swift build -c release "${ARCH_FLAGS[@]}"
BIN_DIR=$(swift build -c release "${ARCH_FLAGS[@]}" --show-bin-path)

rm -rf build && mkdir -p build
for APP in Halo Lyra; do
  DEST="build/$APP.app/Contents"
  mkdir -p "$DEST/MacOS" "$DEST/Resources"
  cp "$BIN_DIR/$APP" "$DEST/MacOS/$APP"
  cp "Resources/$APP-Info.plist" "$DEST/Info.plist"
  ./scripts/make-icon.sh "$APP" "$DEST/Resources/AppIcon.icns" || echo "warning: icon not generated for $APP"
  codesign --force --deep --sign - "build/$APP.app"
  echo "Built build/$APP.app"
done
