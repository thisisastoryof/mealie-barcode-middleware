#!/usr/bin/env bash
# Download Tabler v1.4.0 CSS/JS from jsDelivr for offline vendoring.
# Also downloads Inter variable font.
# Run from repo root: ./scripts/download-tabler.sh

set -euo pipefail

VERSION="1.4.0"
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
OUT_DIR="$SCRIPT_DIR/../app/static/vendor/tabler"
INTER_DIR="$SCRIPT_DIR/../app/static/vendor/inter"

echo "Downloading Tabler @tabler/core@$VERSION from jsDelivr..."

mkdir -p "$OUT_DIR/css" "$OUT_DIR/js" "$INTER_DIR"

CSS_URL="https://cdn.jsdelivr.net/npm/@tabler/core@$VERSION/dist/css/tabler.min.css"
JS_URL="https://cdn.jsdelivr.net/npm/@tabler/core@$VERSION/dist/js/tabler.min.js"

curl -fsSL "$CSS_URL" -o "$OUT_DIR/css/tabler.min.css"
echo "  -> css/tabler.min.css"

curl -fsSL "$JS_URL" -o "$OUT_DIR/js/tabler.min.js"
echo "  -> js/tabler.min.js"

# Download Inter variable font
INTER_URL="https://github.com/rsms/inter/releases/download/v4.1/Inter-4.1.zip"
INTER_ZIP="$(mktemp)"
EXTRACT_DIR="$(mktemp -d)"

echo "Downloading Inter font..."
curl -fsSL -L "$INTER_URL" -o "$INTER_ZIP"
unzip -q -o "$INTER_ZIP" -d "$EXTRACT_DIR"
WOFF2="$(find "$EXTRACT_DIR" -name 'InterVariable.woff2' -print -quit)"
cp "$WOFF2" "$INTER_DIR/InterVariable.woff2"
rm -f "$INTER_ZIP"
rm -rf "$EXTRACT_DIR"
echo "  -> inter/InterVariable.woff2"

echo "Done! Tabler $VERSION + Inter font files are in: app/static/vendor/"
