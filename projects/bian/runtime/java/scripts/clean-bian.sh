#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/../../../../.." && pwd)"
RUNTIME_DIR="$ROOT_DIR/projects/bian/runtime/java"
OUT_DIR="$ROOT_DIR/projects/bian/tmp/java-runtime"

rm -rf "$OUT_DIR"
mkdir -p "$OUT_DIR/data" "$OUT_DIR/logs" "$OUT_DIR/reverse-sources"
rm -rf "$RUNTIME_DIR/target"

echo "Cleaned BIAN Java runtime outputs under $OUT_DIR"
