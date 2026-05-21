#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/../../../../.." && pwd)"
"$ROOT_DIR/projects/bian/runtime/java/scripts/clean-bian.sh"
"$ROOT_DIR/projects/bian/runtime/java/scripts/run-bian.sh"
"$ROOT_DIR/projects/bian/runtime/java/scripts/reverse-bian.sh"

DATA_DIR="$ROOT_DIR/projects/bian/tmp/java-runtime/data"
COUNT="$(find "$DATA_DIR" -name '*.db' -maxdepth 1 | wc -l | tr -d ' ')"
echo "Generated target DBs: $COUNT"
test "$COUNT" -gt 0
