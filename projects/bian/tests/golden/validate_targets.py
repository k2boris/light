#!/usr/bin/env python3
"""Validate generated BIAN target SQLite DBs against golden JSON targets."""

from __future__ import annotations

import argparse
import json
import sqlite3
from collections import Counter
from decimal import Decimal, InvalidOperation
from pathlib import Path
from typing import Any


IGNORED_TABLES = {"bi_mapping_audit", "sqlite_sequence"}
IGNORED_COLUMNS = {"created_at", "updated_at"}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--golden-dir", type=Path, required=True)
    parser.add_argument("--data-dir", type=Path, required=True)
    parser.add_argument("--report", type=Path, required=True)
    args = parser.parse_args()

    results = [
        validate_file(golden_file, args.data_dir)
        for golden_file in sorted(args.golden_dir.glob("*.json"))
        if not golden_file.name.startswith(".")
    ]

    report = {
        "passed": all(result["passed"] for result in results),
        "mode": "case-insensitive-table-column-and-string-values",
        "goldenDir": str(args.golden_dir),
        "dataDir": str(args.data_dir),
        "fileCount": len(results),
        "mismatchCount": sum(len(result["mismatches"]) for result in results),
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
    db_path = data_dir / f"BI_PARTY_{party_id}.db"
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
            normalized_table = normalize_name(table_name)
            if normalized_table in IGNORED_TABLES:
                continue

            expected_rows = expected_rows or []
            actual_table = actual_tables.get(normalized_table)
            if actual_table is None:
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

            actual_rows = read_rows(connection, actual_table)
            expected_columns = projected_columns(expected_rows)
            missing_columns = sorted(
                column for column in expected_columns if column not in actual_rows["columns"]
            )
            if missing_columns:
                mismatches.append(
                    {
                        "table": table_name,
                        "reason": "missing_columns",
                        "missingColumns": missing_columns,
                    }
                )
                continue

            expected_counter = Counter(
                row_signature(normalize_row_keys(row), expected_columns)
                for row in expected_rows
            )
            actual_counter = Counter(
                row_signature(row, expected_columns)
                for row in actual_rows["rows"]
            )

            missing = list((expected_counter - actual_counter).elements())
            unexpected = list((actual_counter - expected_counter).elements())
            if missing or unexpected:
                mismatches.append(
                    {
                        "table": table_name,
                        "reason": "row_multiset_mismatch",
                        "expectedCount": sum(expected_counter.values()),
                        "actualCount": sum(actual_counter.values()),
                        "projectedColumns": expected_columns,
                        "missingRows": sorted(missing)[:25],
                        "unexpectedRows": sorted(unexpected)[:25],
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
        if not rows:
            continue
        for key, value in rows[0].items():
            if normalize_name(key) == "party_id" and value:
                return str(value)
    stem = golden_file.stem
    if "_" in stem:
        return stem.rsplit("_", 1)[-1]
    return stem


def table_names(connection: sqlite3.Connection) -> dict[str, str]:
    rows = connection.execute(
        "select name from sqlite_master where type in ('table', 'view')"
    ).fetchall()
    return {normalize_name(str(row[0])): str(row[0]) for row in rows}


def read_rows(connection: sqlite3.Connection, table_name: str) -> dict[str, Any]:
    rows = connection.execute(f"select * from {quote_identifier(table_name)}").fetchall()
    if not rows:
        columns = {
            normalize_name(str(row[1]))
            for row in connection.execute(f"pragma table_info({quote_identifier(table_name)})")
        }
        return {"columns": columns, "rows": []}
    return {
        "columns": {normalize_name(key) for key in rows[0].keys()},
        "rows": [
            {normalize_name(key): row[key] for key in row.keys()}
            for row in rows
        ],
    }


def projected_columns(rows: list[dict[str, Any]]) -> list[str]:
    columns: list[str] = []
    for row in rows:
        for key in row:
            normalized = normalize_name(key)
            if ignored_column(normalized):
                continue
            if normalized not in columns:
                columns.append(normalized)
    return columns


def normalize_row_keys(row: dict[str, Any]) -> dict[str, Any]:
    return {normalize_name(str(key)): value for key, value in row.items()}


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
    numeric = normalize_numeric_text(text)
    if numeric is not None:
        return numeric
    return text.casefold()


def normalize_numeric_text(text: str) -> str | None:
    if not text:
        return None
    try:
        number = Decimal(text)
    except InvalidOperation:
        return None
    normalized = number.normalize()
    if normalized == normalized.to_integral():
        return format(normalized.quantize(Decimal(1)), "f")
    return format(normalized, "f")


def normalize_name(value: str) -> str:
    return value.strip().casefold()


def ignored_column(column: str) -> bool:
    return (
        column in IGNORED_COLUMNS
        or column.endswith("_at")
        or column.endswith("_date")
        or column.endswith("_dt")
    )


def quote_identifier(identifier: str) -> str:
    return '"' + identifier.replace('"', '""') + '"'


if __name__ == "__main__":
    raise SystemExit(main())
