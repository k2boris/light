"""DDL parsing (minimal but deterministic).

This parser is designed for *common* CREATE TABLE statements and PRIMARY KEY constraints.
It is not a full SQL grammar. The intent is to provide enough structure to validate
and compile the mapping workbook reliably.

If you have vendor-specific DDL (Oracle, SQL Server), you may extend the parser or
plug in a proper SQL parser library. The rest of the package stays unchanged.
"""

from __future__ import annotations

import logging
import re
from pathlib import Path
from typing import Dict, List, Tuple

from .schema_model import Schema, Table, Column, PrimaryKey, ForeignKey

logger = logging.getLogger(__name__)

# Very conservative regex-based parsing for:
# - CREATE TABLE <name> ( ... );
# - column lines: <col> <type> [NOT NULL]
# - PK constraints: PRIMARY KEY (a,b,c)
#
# NOTE: This will not handle every dialect. It's a baseline.

CREATE_TABLE_RE = re.compile(
    r"CREATE\s+TABLE\s+(?:IF\s+NOT\s+EXISTS\s+)?([\w\.\"]+)\s*\((.*?)\)\s*;",
    re.IGNORECASE | re.DOTALL,
)
PK_INLINE_RE = re.compile(r"PRIMARY\s+KEY\s*\(([^\)]+)\)", re.IGNORECASE)
COL_DEF_RE = re.compile(r'^\s*([\w\"]+)\s+(.+?)\s*$', re.IGNORECASE)
REF_RE = re.compile(r"REFERENCES\s+([\w\.\"]+)\s*\(\s*([\w\"]+)\s*\)", re.IGNORECASE)

def _clean_ident(s: str) -> str:
    s = s.strip()
    if s.startswith('"') and s.endswith('"'):
        s = s[1:-1]
    # remove schema prefix if present, keep table name only for now
    if '.' in s:
        s = s.split('.')[-1]
    return s

def _strip_sql_line_comments(s: str) -> str:
    """Remove -- comments from SQL text line-by-line."""
    return re.sub(r"--.*?$", "", s, flags=re.MULTILINE)

def _split_top_level_commas(s: str) -> List[str]:
    """Split SQL fragment by commas that are not nested in parentheses."""
    parts: List[str] = []
    buf: List[str] = []
    depth = 0
    for ch in s:
        if ch == "(":
            depth += 1
            buf.append(ch)
            continue
        if ch == ")":
            depth = max(0, depth - 1)
            buf.append(ch)
            continue
        if ch == "," and depth == 0:
            part = "".join(buf).strip()
            if part:
                parts.append(part)
            buf = []
            continue
        buf.append(ch)
    tail = "".join(buf).strip()
    if tail:
        parts.append(tail)
    return parts

def parse_ddl_file(path: Path, schema_name: str) -> Schema:
    """Parse a DDL file into a Schema model.

    Raises ValueError on total parse failure.
    """
    text = path.read_text(encoding="utf-8", errors="ignore")
    schema = Schema(name=schema_name)

    matches = list(CREATE_TABLE_RE.finditer(text))
    if not matches:
        raise ValueError(f"No CREATE TABLE statements found in {path}")

    for m in matches:
        raw_name = m.group(1)
        body = m.group(2)
        body_no_comments = _strip_sql_line_comments(body)

        table_name = _clean_ident(raw_name)
        table = Table(name=table_name)

        joined = _split_top_level_commas(body_no_comments)

        # Extract PK (table-level constraint)
        pk_cols = None
        pk_match = PK_INLINE_RE.search(body_no_comments)
        if pk_match:
            pk_cols = [ _clean_ident(x) for x in pk_match.group(1).split(',') ]
        inline_pk_cols: List[str] = []

        for ln in joined:
            # Skip constraints lines
            ln_u = ln.upper()
            if ln_u.startswith("CONSTRAINT") or ln_u.startswith("PRIMARY KEY") or ln_u.startswith("FOREIGN KEY") or ln_u.startswith("UNIQUE") or ln_u.startswith("CHECK"):
                continue

            cm = COL_DEF_RE.match(ln)
            if not cm:
                continue
            col_name = _clean_ident(cm.group(1))
            col_type = cm.group(2).strip()
            col_type_u = col_type.upper()
            is_inline_pk = bool(re.search(r"\bPRIMARY\s+KEY\b", col_type_u))
            nullable = (not ("NOT NULL" in col_type_u)) and (not is_inline_pk)
            # Remove trailing constraint phrases for type normalization
            col_type_clean = re.sub(r"\s+NOT\s+NULL\b", "", col_type, flags=re.IGNORECASE).strip()
            col_type_clean = re.sub(r"\s+PRIMARY\s+KEY\b", "", col_type_clean, flags=re.IGNORECASE).strip()
            table.columns[col_name] = Column(name=col_name, datatype=col_type_clean, nullable=nullable)
            if is_inline_pk:
                inline_pk_cols.append(col_name)
            ref = REF_RE.search(col_type)
            if ref:
                ref_table = _clean_ident(ref.group(1))
                ref_col = _clean_ident(ref.group(2))
                table.foreign_keys.append(ForeignKey(from_column=col_name, to_table=ref_table, to_column=ref_col))

        if pk_cols:
            table.primary_key = PrimaryKey(columns=pk_cols)
        elif inline_pk_cols:
            table.primary_key = PrimaryKey(columns=inline_pk_cols)

        schema.tables[table.name] = table

    logger.info(f"Parsed {len(schema.tables)} tables from {path}", extra={"phase":"DDL"})
    return schema
