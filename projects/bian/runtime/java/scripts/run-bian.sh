#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/../../../../.." && pwd)"
RUNTIME_DIR="$ROOT_DIR/projects/bian/runtime/java"
LOG_DIR="$ROOT_DIR/projects/bian/tmp/java-runtime/logs"
mkdir -p "$LOG_DIR"

cd "$RUNTIME_DIR"
mvn -q compile exec:java \
  -Dexec.mainClass=com.blackbox.bian.BianPartyRuntimeApp \
  -Dexec.args=config/bian-runtime.properties \
  > "$LOG_DIR/bian-forward.log" 2>&1

echo "BIAN forward runtime complete. Log: $LOG_DIR/bian-forward.log"
