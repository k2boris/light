#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PYTHON_BIN="${PYTHON_BIN:-python}"
PROJECT="${PROJECT:-}"
PROJECT_YAML=""

usage() {
  cat <<EOF
Usage:
  $0 -p <project>
  $0 --project <project>
  PROJECT=<project> $0

Options:
  -p, --project NAME   Project name under projects/ (e.g., tmf, tmf-temp)
  -h, --help           Show this help

Behavior:
  - Materializes Broadway/Python outputs from the project's IR.
  - Materializes the first Java build-output slice for TMF TC_PARTY.
  - Reads paths from projects/<project>/project.yaml.
EOF
}

if [[ $# -eq 0 ]]; then
  usage
  exit 0
fi

yaml_get() {
  local key="$1"
  "$PYTHON_BIN" - "$PROJECT_YAML" "$key" <<'PY'
import sys
from pathlib import Path

path = Path(sys.argv[1])
key = sys.argv[2]

vals = {}
for raw in path.read_text(encoding="utf-8").splitlines():
    line = raw.strip()
    if not line or line.startswith("#"):
        continue
    if ":" not in line:
        continue
    k, v = line.split(":", 1)
    k = k.strip()
    v = v.strip()
    if (v.startswith('"') and v.endswith('"')) or (v.startswith("'") and v.endswith("'")):
        v = v[1:-1]
    vals[k] = v
print(vals.get(key, ""))
PY
}

while [[ $# -gt 0 ]]; do
  case "$1" in
    -p|--project)
      [[ $# -ge 2 ]] || { echo "materialize.sh: Missing value for $1" >&2; exit 1; }
      PROJECT="$2"
      shift 2
      ;;
    -h|--help)
      usage
      exit 0
      ;;
    *)
      usage
      echo "materialize.sh: Unknown argument: $1" >&2
      exit 1
      ;;
  esac
done

if [[ -z "$PROJECT" ]]; then
  echo "materialize.sh: PROJECT is required. Example: ./materialize.sh -p tmf" >&2
  exit 1
fi

PROJECT_DIR="$ROOT_DIR/projects/$PROJECT"
PROJECT_YAML="$PROJECT_DIR/project.yaml"

if [[ ! -d "$PROJECT_DIR" ]]; then
  echo "materialize.sh: Project not found: $PROJECT_DIR" >&2
  exit 1
fi
if [[ ! -f "$PROJECT_YAML" ]]; then
  echo "materialize.sh: Project config not found: $PROJECT_YAML" >&2
  exit 1
fi

IN_IR="$PROJECT_DIR/$(yaml_get out_ir)"
OUT_DIR="$PROJECT_DIR/$(yaml_get out_implementations)"
CANONICAL_DDL="$PROJECT_DIR/$(yaml_get canonical_ddl)"

"$PYTHON_BIN" -m generator.implement_cli \
  --in-ir "$IN_IR" \
  --out-dir "$OUT_DIR" \
  --canonical-ddl "$CANONICAL_DDL"

echo "Materialized implementations written under: $OUT_DIR"
