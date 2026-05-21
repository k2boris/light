"""CLI entrypoint.

This module wires together:
- DDL parsing
- Excel spec loading
- Validation phases
- IR generation
- Report writing

The goal is determinism + debuggability. We log phase boundaries and row-level context.
"""

from __future__ import annotations

import argparse
import logging
from pathlib import Path
from typing import Dict, List, Tuple

from .logging_config import configure_logging
from .ddl.ddl_parser import parse_ddl_file
from .spec.excel_loader import load_v4_1_workbook
from .validate.validator import validate_all
from .ir.ir_builder import build_ir_bundle
from .reports.report_writer import write_json_report

logger = logging.getLogger(__name__)

def _parse_source_ddl_args(items: List[str]) -> Dict[str, Path]:
    """Parse --source-ddl args of the form System=/path/file.sql."""
    out: Dict[str, Path] = {}
    for item in items:
        if "=" not in item:
            raise ValueError(f"Invalid --source-ddl '{item}'. Expected NAME=/path/to/file.sql")
        name, path = item.split("=", 1)
        out[name.strip()] = Path(path).expanduser().resolve()
    return out

def build_arg_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="spec-to-ir", description="Validate V4.1 mapping spec and generate IR JSON")
    p.add_argument("--spec", required=True, help="Path to V4.1 Excel mapping spec" )
    p.add_argument("--canonical-ddl", required=True, help="Path to canonical DDL (e.g., tmf.sql)" )
    p.add_argument("--source-ddl", action="append", default=[], help="Source DDL mapping: Name=/path/file.sql" )
    p.add_argument("--out-ir", required=True, help="Output IR JSON path" )
    p.add_argument("--out-report", required=False, help="Optional validation report JSON path" )
    p.add_argument("--log-level", default="INFO", choices=["DEBUG","INFO","WARNING","ERROR"], help="Logging level" )
    p.add_argument("--dry-run", action="store_true", help="Validate only; do not emit IR" )
    p.add_argument("--strict", action="store_true", help="Enable strict mode (default)." )
    p.add_argument("--permissive", action="store_true", help="Relax certain validations." )
    return p

def main(argv: List[str] | None = None) -> None:
    args = build_arg_parser().parse_args(argv)
    configure_logging(args.log_level)

    strict = True
    if args.permissive:
        strict = False
    if args.strict:
        strict = True

    spec_path = Path(args.spec).expanduser().resolve()
    canonical_path = Path(args.canonical_ddl).expanduser().resolve()
    source_ddls = _parse_source_ddl_args(args.source_ddl)

    logger.info("Starting spec-to-ir", extra={"phase":"START"})

    # 1) Parse DDLs
    logger.info("Parsing canonical DDL", extra={"phase":"DDL"})
    canonical_schema = parse_ddl_file(canonical_path, schema_name="CANONICAL")

    source_schemas = {}
    for sys_name, ddl_path in source_ddls.items():
        logger.info(f"Parsing source DDL for {sys_name}", extra={"phase":"DDL"})
        source_schemas[sys_name] = parse_ddl_file(ddl_path, schema_name=sys_name)

    # 2) Load workbook
    logger.info("Loading V4.1 workbook", extra={"phase":"SPEC"})
    spec = load_v4_1_workbook(spec_path)

    # 3) Validate
    logger.info("Validating spec against schemas", extra={"phase":"VALIDATE"})
    report = validate_all(spec=spec, canonical=canonical_schema, sources=source_schemas, strict=strict)

    if args.out_report:
        write_json_report(Path(args.out_report).expanduser().resolve(), report)

    if report.has_errors:
        logger.error("Validation failed; IR will not be generated", extra={"phase":"VALIDATE"})
        raise SystemExit(2)

    if args.dry_run:
        logger.info("Dry-run complete (validation passed)", extra={"phase":"DONE"})
        return

    # 4) Build IR
    logger.info("Building IR bundle", extra={"phase":"IR"})
    ir = build_ir_bundle(spec=spec, canonical=canonical_schema, sources=source_schemas, report=report, strict=strict)

    out_ir = Path(args.out_ir).expanduser().resolve()
    out_ir.parent.mkdir(parents=True, exist_ok=True)
    out_ir.write_text(ir.to_json(indent=2), encoding="utf-8")

    logger.info(f"Wrote IR to {out_ir}", extra={"phase":"DONE"})


if __name__ == "__main__":
    main()
