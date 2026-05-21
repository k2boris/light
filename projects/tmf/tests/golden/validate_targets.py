#!/usr/bin/env python3
"""Validate generated TMF target SQLite DBs against golden JSON targets."""

from __future__ import annotations

import argparse
import json
import sqlite3
from pathlib import Path
from typing import Any


IGNORED_FIELDS = {"__iid", "created_dt", "as_of_dt"}
IGNORED_TABLES = {"v_partyaccounts", "v_partyproducts", "viewtest1"}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--golden-dir", type=Path, required=True)
    parser.add_argument("--data-dir", type=Path, required=True)
    parser.add_argument("--report", type=Path, required=True)
    args = parser.parse_args()

    results: list[dict[str, Any]] = []
    for golden_file in sorted(args.golden_dir.glob("*.json")):
        if golden_file.name.startswith("."):
            continue
        results.append(validate_file(golden_file, args.data_dir))

    report = {
        "passed": all(item["passed"] for item in results),
        "goldenDir": str(args.golden_dir),
        "dataDir": str(args.data_dir),
        "fileCount": len(results),
        "mismatchCount": sum(len(item["mismatches"]) for item in results),
        "results": results,
    }
    args.report.parent.mkdir(parents=True, exist_ok=True)
    args.report.write_text(json.dumps(report, indent=2), encoding="utf-8")

    print(f"golden_passed={report['passed']}")
    print(f"golden_file_count={report['fileCount']}")
    print(f"golden_mismatch_count={report['mismatchCount']}")
    print(f"golden_report={args.report}")
    return 0 if report["passed"] else 1


def validate_file(golden_file: Path, data_dir: Path) -> dict[str, Any]:
    golden = json.loads(golden_file.read_text(encoding="utf-8"))
    party_id = infer_party_id(golden_file, golden)
    db_path = data_dir / f"TC_PARTY_{party_id}.db"
    mismatches: list[dict[str, Any]] = []

    if not db_path.exists():
        return {
            "file": str(golden_file),
            "partyId": party_id,
            "db": str(db_path),
            "passed": False,
            "mismatches": [{"table": None, "reason": "missing_target_db"}],
        }

    with sqlite3.connect(db_path) as connection:
        connection.row_factory = sqlite3.Row
        actual_tables = table_names(connection)
        for table_name, expected_rows in golden.items():
            if table_name.startswith("."):
                continue
            if table_name.casefold() in IGNORED_TABLES:
                continue
            canonical_table = table_name.upper()
            expected_rows = expected_rows or []

            if canonical_table not in actual_tables:
                if expected_rows:
                    mismatches.append(
                        {
                            "table": table_name,
                            "reason": "missing_table",
                            "expectedCount": len(expected_rows),
                            "actualCount": None,
                        }
                    )
                continue

            actual_rows = read_rows(connection, canonical_table)
            expected_columns = projected_columns(expected_rows)
            missing_columns = sorted(col for col in expected_columns if col not in actual_rows["columns"])
            if missing_columns:
                mismatches.append(
                    {
                        "table": table_name,
                        "reason": "missing_columns",
                        "missingColumns": missing_columns,
                    }
                )
                continue

            expected_set = {
                row_signature(normalize_row_keys(row), expected_columns)
                for row in expected_rows
            }
            actual_set = {
                row_signature(row, expected_columns)
                for row in actual_rows["rows"]
            }
            missing = sorted(expected_set - actual_set)
            unexpected = sorted(actual_set - expected_set)
            if missing or unexpected:
                mismatches.append(
                    {
                        "table": table_name,
                        "reason": "row_set_mismatch",
                        "expectedCount": len(expected_set),
                        "actualCount": len(actual_set),
                        "projectedColumns": expected_columns,
                        "missingRows": missing[:25],
                        "unexpectedRows": unexpected[:25],
                        "missingRowCount": len(missing),
                        "unexpectedRowCount": len(unexpected),
                    }
                )

    return {
        "file": str(golden_file),
        "partyId": party_id,
        "db": str(db_path),
        "passed": not mismatches,
        "mismatches": mismatches,
    }


def infer_party_id(golden_file: Path, golden: dict[str, Any]) -> str:
    for rows in golden.values():
        if rows:
            value = rows[0].get("__iid")
            if value:
                return str(value)
    stem = golden_file.stem
    if "_" in stem:
        return stem.rsplit("_", 1)[-1]
    return stem


def table_names(connection: sqlite3.Connection) -> set[str]:
    rows = connection.execute(
        "select name from sqlite_master where type in ('table', 'view')"
    ).fetchall()
    return {str(row[0]).upper() for row in rows}


def read_rows(connection: sqlite3.Connection, table_name: str) -> dict[str, Any]:
    rows = connection.execute(f"select * from {quote_identifier(table_name)}").fetchall()
    if not rows:
        columns = {
            str(row[1]).lower()
            for row in connection.execute(f"pragma table_info({quote_identifier(table_name)})")
        }
        return {"columns": columns, "rows": []}
    return {
        "columns": {key.lower() for key in rows[0].keys()},
        "rows": [{key.lower(): row[key] for key in row.keys()} for row in rows],
    }


def projected_columns(rows: list[dict[str, Any]]) -> list[str]:
    columns: list[str] = []
    for row in rows:
        for key in row:
            normalized = key.lower()
            if normalized in IGNORED_FIELDS:
                continue
            if normalized not in columns:
                columns.append(normalized)
    return columns


def normalize_row_keys(row: dict[str, Any]) -> dict[str, Any]:
    return {str(key).lower(): value for key, value in row.items()}


def row_signature(row: dict[str, Any], columns: list[str]) -> str:
    return "|".join(normalize_value(row.get(column)) for column in columns)


def normalize_value(value: Any) -> str:
    if value is None:
        return "<NULL>"
    if isinstance(value, float):
        return format(value, "g")
    text = str(value).strip()
    while text.startswith("[") and text.endswith("]") and len(text) >= 2:
        text = text[1:-1].strip()
    return text.casefold()


def quote_identifier(identifier: str) -> str:
    return '"' + identifier.replace('"', '""') + '"'


if __name__ == "__main__":
    raise SystemExit(main())
