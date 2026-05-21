#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PYTHON_BIN="${PYTHON_BIN:-python}"
PROJECT="${PROJECT:-}"
STEP=0

PROJECT_DIR=""
PROJECT_YAML=""
SPEC_FILE=""
CANONICAL_DDL=""
SIEBEL_DDL=""
BSCS_DDL=""
NCC_DDL=""
OUT_IR=""
OUT_REPORT=""
SOURCE_DDL_ENTRIES=()
SOURCE_DDL_PATHS=()

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

die() {
  echo "validate.sh: $*" >&2
  exit 1
}

log_step() {
  STEP=$((STEP + 1))
  echo "[STEP $STEP] $*"
}

log_ok() {
  echo "[OK] $*"
}

finish() {
  rc=$?
  if [[ $rc -eq 0 ]]; then
    log_ok "Validation script completed successfully."
  else
    echo "[FAIL] Validation script exited with status $rc." >&2
  fi
}
trap finish EXIT

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
  - Runs validation only (--dry-run).
  - Reads inputs from projects/<project>/project.yaml.
EOF
}

if [[ $# -eq 0 ]]; then
  usage
  exit 0
fi

while [[ $# -gt 0 ]]; do
  case "$1" in
    -p|--project)
      [[ $# -ge 2 ]] || die "Missing value for $1"
      PROJECT="$2"
      shift 2
      ;;
    -h|--help)
      usage
      exit 0
      ;;
    *)
      usage
      die "Unknown argument: $1"
      ;;
  esac
done

[[ -n "$PROJECT" ]] || die "PROJECT is required. Example: PROJECT=tmf ./validate.sh"

PROJECT_DIR="$ROOT_DIR/projects/$PROJECT"
PROJECT_YAML="$PROJECT_DIR/project.yaml"

[[ -d "$PROJECT_DIR" ]] || die "Project not found: $PROJECT_DIR"
[[ -f "$PROJECT_YAML" ]] || die "Project config not found: $PROJECT_YAML"

SPEC_FILE="$PROJECT_DIR/$(yaml_get spec)"
CANONICAL_DDL="$PROJECT_DIR/$(yaml_get canonical_ddl)"
OUT_IR="$PROJECT_DIR/$(yaml_get out_ir)"
OUT_REPORT="$PROJECT_DIR/$(yaml_get out_report)"

while IFS='|' read -r src_name src_rel; do
  [[ -n "$src_name" ]] || continue
  [[ -n "$src_rel" ]] || continue
  src_path="$PROJECT_DIR/$src_rel"
  SOURCE_DDL_ENTRIES+=("$src_name=$src_path")
  SOURCE_DDL_PATHS+=("$src_path")
done < <(yaml_source_ddls)

[[ ${#SOURCE_DDL_ENTRIES[@]} -gt 0 ]] || die "No source_ddls entries found in $PROJECT_YAML"

log_step "Checking Python interpreter ($PYTHON_BIN)"
command -v "$PYTHON_BIN" >/dev/null 2>&1 || die "Python not found. Activate your environment (e.g. 'conda activate gen')."
if [[ "${CONDA_DEFAULT_ENV:-}" != "gen" ]]; then
  echo "validate.sh: Warning: active conda env is '${CONDA_DEFAULT_ENV:-none}', expected 'gen'." >&2
fi
log_ok "Python interpreter found."

log_step "Checking required Python dependency (openpyxl)"
"$PYTHON_BIN" -c "import openpyxl" >/dev/null 2>&1 || die "Missing dependency 'openpyxl'. Run: $PYTHON_BIN -m pip install -e ."
log_ok "Dependency check passed."

log_step "Validating required input files"
for file in "$SPEC_FILE" "$CANONICAL_DDL" "${SOURCE_DDL_PATHS[@]}"; do
  [[ -f "$file" ]] || die "Required file not found: $file"
  echo "  - found: $file"
done
log_ok "All required files are present."

log_step "Preparing output directories"
mkdir -p "$PROJECT_DIR/tmp" "$PROJECT_DIR/reports"
log_ok "Output directories ready."

log_step "Running validator CLI"
echo "  - root: $ROOT_DIR"
echo "  - project: $PROJECT"
echo "  - project dir: $PROJECT_DIR"
echo "  - report: $OUT_REPORT"
echo "  - mode: dry-run (validation only)"

CLI_ARGS=(
  --spec "$SPEC_FILE"
  --canonical-ddl "$CANONICAL_DDL"
  --out-ir "$OUT_IR"
  --out-report "$OUT_REPORT"
  --log-level INFO
  --dry-run
)

for ddl_entry in "${SOURCE_DDL_ENTRIES[@]}"; do
  CLI_ARGS+=(--source-ddl "$ddl_entry")
done

PYTHONUNBUFFERED=1 "$PYTHON_BIN" -u -m generator.cli \
  "${CLI_ARGS[@]}"
log_ok "Validator CLI run completed."

log_step "Verifying validation report output"
if [[ -f "$OUT_REPORT" ]]; then
  log_ok "Report generated: $OUT_REPORT"
else
  die "Validator completed but report was not found at: $OUT_REPORT"
fi
