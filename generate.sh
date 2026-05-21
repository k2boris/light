#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PYTHON_BIN="${PYTHON_BIN:-python}"
PROJECT="${PROJECT:-}"
PROJECT_YAML=""
SOURCE_DDL_ENTRIES=()

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
  - Validates and generates IR for the selected project.
  - Reads inputs from projects/<project>/project.yaml.
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

current = None
vals = {}
sources = {}
for raw in path.read_text(encoding="utf-8").splitlines():
    line = raw.rstrip()
    if not line.strip() or line.lstrip().startswith("#"):
        continue
    if not line.startswith(" ") and line.endswith(":"):
        current = line[:-1].strip()
        continue
    if ":" not in line:
        continue
    k, v = line.split(":", 1)
    k = k.strip()
    v = v.strip()
    if (v.startswith('"') and v.endswith('"')) or (v.startswith("'") and v.endswith("'")):
        v = v[1:-1]
    if current == "source_ddls" and raw.startswith(" "):
        sources[k] = v
    else:
        current = None
        vals[k] = v

if key.startswith("source_ddls."):
    print(sources.get(key.split(".", 1)[1], ""))
else:
    print(vals.get(key, ""))
PY
}

yaml_source_ddls() {
  "$PYTHON_BIN" - "$PROJECT_YAML" <<'PY'
import sys
from pathlib import Path

path = Path(sys.argv[1])
in_sources = False
for raw in path.read_text(encoding="utf-8").splitlines():
    line = raw.rstrip()
    if not line.strip() or line.lstrip().startswith("#"):
        continue
    if not line.startswith(" ") and line.endswith(":"):
        in_sources = (line[:-1].strip() == "source_ddls")
        continue
    if not in_sources:
        continue
    if not raw.startswith("  "):
        in_sources = False
        continue
    if ":" not in line:
        continue
    k, v = line.split(":", 1)
    k = k.strip()
    v = v.strip()
    if (v.startswith('"') and v.endswith('"')) or (v.startswith("'") and v.endswith("'")):
        v = v[1:-1]
    if k and v:
        print(f"{k}|{v}")
PY
}

while [[ $# -gt 0 ]]; do
  case "$1" in
    -p|--project)
      [[ $# -ge 2 ]] || { echo "generate.sh: Missing value for $1" >&2; exit 1; }
      PROJECT="$2"
      shift 2
      ;;
    -h|--help)
      usage
      exit 0
      ;;
    *)
      usage
      echo "generate.sh: Unknown argument: $1" >&2
      exit 1
      ;;
  esac
done

if [[ -z "$PROJECT" ]]; then
  echo "generate.sh: PROJECT is required. Example: ./generate.sh -p tmf" >&2
  exit 1
fi

PROJECT_DIR="$ROOT_DIR/projects/$PROJECT"
PROJECT_YAML="$PROJECT_DIR/project.yaml"

if [[ ! -d "$PROJECT_DIR" ]]; then
  echo "generate.sh: Project not found: $PROJECT_DIR" >&2
  exit 1
fi
if [[ ! -f "$PROJECT_YAML" ]]; then
  echo "generate.sh: Project config not found: $PROJECT_YAML" >&2
  exit 1
fi

FULL_SPEC="$PROJECT_DIR/$(yaml_get spec)"
CANONICAL_DDL="$PROJECT_DIR/$(yaml_get canonical_ddl)"
OUT_IR="$PROJECT_DIR/$(yaml_get out_ir)"
OUT_REPORT="$PROJECT_DIR/$(yaml_get out_report)"

while IFS='|' read -r src_name src_rel; do
  [[ -n "$src_name" ]] || continue
  [[ -n "$src_rel" ]] || continue
  SOURCE_DDL_ENTRIES+=("$src_name=$PROJECT_DIR/$src_rel")
done < <(yaml_source_ddls)

if [[ ${#SOURCE_DDL_ENTRIES[@]} -eq 0 ]]; then
  echo "generate.sh: No source_ddls entries found in $PROJECT_YAML" >&2
  exit 1
fi

mkdir -p "$PROJECT_DIR/tmp" "$PROJECT_DIR/reports"

CLI_ARGS=(
  --spec "$FULL_SPEC"
  --canonical-ddl "$CANONICAL_DDL"
  --out-ir "$OUT_IR"
  --out-report "$OUT_REPORT"
  --log-level DEBUG
)

for ddl_entry in "${SOURCE_DDL_ENTRIES[@]}"; do
  CLI_ARGS+=(--source-ddl "$ddl_entry")
done

"$PYTHON_BIN" -m generator.cli "${CLI_ARGS[@]}"
