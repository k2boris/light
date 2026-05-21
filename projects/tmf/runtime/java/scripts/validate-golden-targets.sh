#!/usr/bin/env bash
set -euo pipefail

PROJECT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/../../.." && pwd)"
REPO_DIR="$(cd "$PROJECT_DIR/../.." && pwd)"
RUN_DIR="$PROJECT_DIR/tmp/java-runtime"

python3 "$PROJECT_DIR/tests/golden/validate_targets.py" \
  --golden-dir "$PROJECT_DIR/tests/golden/targets" \
  --data-dir "$RUN_DIR/data" \
  --report "$RUN_DIR/golden-target-compare.json"
