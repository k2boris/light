#!/usr/bin/env bash
set -euo pipefail

PROJECT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/../../.." && pwd)"

rm -rf "$PROJECT_DIR/tmp/java-runtime"
rm -f /tmp/blackbox-tmf-java-runtime.log
rm -f /tmp/blackbox-tmf-java-runtime-core.log

echo "Removed TMF Java party runtime outputs:"
echo "  $PROJECT_DIR/tmp/java-runtime"
echo "  legacy /tmp/blackbox-tmf-java-runtime.log"
echo "  legacy /tmp/blackbox-tmf-java-runtime-core.log"
