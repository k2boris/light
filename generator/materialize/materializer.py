"""Execution-plan materializer.

This module turns abstract runtime execution plans into concrete implementation artifacts.
"""

from __future__ import annotations

import json
import re
import shutil
from pathlib import Path
from typing import Dict, Any, Iterable, Optional

from .materialize_k2tables import materialize_k2tables

TEMPLATE_BROADWAY_ACTOR_REFERENCE: Dict[str, Dict[str, Any]] = {
    "TPL_ARRAY_INPUT_TO_EAV_PARENT_SCOPED": {
        "profile": "array_input_to_eav_parent_scoped",
        "summary": "SourceDbQuery filtered by PopulationArgs parent rows, then emit EAV rows.",
        "stages": [
            {"name": "Input", "actors": ["PopulationArgs", "SyncDeleteMode"]},
            {"name": "Source", "actors": ["Query"]},
            {"name": "Stage 1", "actors": ["EmitRows(JavaScript)"]},
            {"name": "LU Table", "actors": ["DbLoad(target_table)"]},
        ],
        "flow": [
            "PopulationArgs.parent_rows -> Query(parent_rows) -> EmitRows/result -> DbLoad",
        ],
    },
    "TPL_ARRAY_INPUT_TO_COLUMNS_PARENT_SCOPED": {
        "profile": "array_input_to_columns_parent_scoped",
        "summary": "SourceDbQuery filtered by PopulationArgs parent rows, then direct load.",
        "stages": [
            {"name": "Input", "actors": ["PopulationArgs", "SyncDeleteMode"]},
            {"name": "Source", "actors": ["Query"]},
            {"name": "Stage 1", "actors": ["Const*|ChangeValue*|Now1"]},
            {"name": "LU Table", "actors": ["DbLoad(target_table)"]},
        ],
        "flow": [
            "PopulationArgs.parent_rows -> Query(parent_rows) -> DbLoad",
        ],
    },
    "TPL_COLUMNS_PARENT_SCOPED": {
        "profile": "snapshot_or_multirow_columns_parent_scoped",
        "summary": "Unified columns template: snapshot (field bindings) or multirow (emit_rows) with row-match policy.",
        "stages": [
            {"name": "Input", "actors": ["PopulationArgs", "SyncDeleteMode"]},
            {"name": "Stage 2", "actors": ["RenameAndChangeValue"]},
            {"name": "Source", "actors": ["Query"]},
            {"name": "Stage 1", "actors": ["EmitRows|Const*|ChangeValue*|Now1"]},
            {"name": "LU Table", "actors": ["DbLoad(target_table)"]},
        ],
        "flow": [
            "PopulationArgs.parent_rows -> RenameAndChangeValue -> Query",
            "Query/result -> projection -> DbLoad",
        ],
    },
    "TPL_COLUMNS_XREF_PARENT_SCOPED": {
        "profile": "xref_columns_parent_scoped",
        "summary": "Resolve source key via MDM XREF from incoming party_id, then query source and load target.",
        "stages": [
            {"name": "Input", "actors": ["PopulationArgs"]},
            {"name": "Stage 3", "actors": ["RenameAndChangeValue(xref seed)"]},
            {"name": "Source", "actors": ["XRefBridge(XREF)"]},
            {"name": "Stage 2", "actors": ["QueryJoin(source query)"]},
            {"name": "Stage 1", "actors": ["ProjectRows(JavaScript)", "Now1(optional)"]},
            {"name": "LU Table", "actors": ["DbLoad(target_table)"]},
        ],
        "flow": [
            "PopulationArgs.party_id -> RenameAndChangeValue(ROWID_OBJECT)",
            "RenameAndChangeValue/result -> XRefBridge(C_XREF_PARTY) -> QueryJoin(parent_rows) -> ProjectRows -> DbLoad",
        ],
    },
    "TPL_XREF_JOIN_PARENT_SCOPED": {
        "profile": "join_to_1_parent_scoped",
        "summary": "Resolve source key via MDM XREF, then execute join-path source query and project/load target.",
        "stages": [
            {"name": "Input", "actors": ["PopulationArgs"]},
            {"name": "Stage 3", "actors": ["RenameAndChangeValue(xref seed)"]},
            {"name": "Source", "actors": ["XRefBridge(XREF)"]},
            {"name": "Stage 2", "actors": ["QueryJoin(join query)"]},
            {"name": "Stage 1", "actors": ["ProjectRows(JavaScript)", "Now1(optional)"]},
            {"name": "LU Table", "actors": ["DbLoad(target_table)"]},
        ],
        "flow": [
            "PopulationArgs.driver -> RenameAndChangeValue(ROWID_OBJECT)",
            "RenameAndChangeValue/result -> XRefBridge -> QueryJoin(parent_rows) -> ProjectRows -> DbLoad",
        ],
    },
    "TPL_EAV_PARENT_SCOPED": {
        "profile": "eav_parent_scoped",
        "summary": "Unified EAV template emitted from EAV rules (possibly multirow source).",
        "stages": [
            {"name": "Input", "actors": ["PopulationArgs", "SyncDeleteMode"]},
            {"name": "Stage 2", "actors": ["RenameAndChangeValue"]},
            {"name": "Source", "actors": ["Query"]},
            {"name": "Stage 1", "actors": ["EmitRows(JavaScript)"]},
            {"name": "LU Table", "actors": ["DbLoad(target_table)"]},
        ],
        "flow": [
            "PopulationArgs.parent_rows -> RenameAndChangeValue -> Query",
            "Query/result -> EmitRows/result -> DbLoad",
        ],
    },
    "TPL_SNAPSHOT_1TO1_PARENT_SCOPED": {
        "profile": "snapshot_1to1_parent_scoped",
        "summary": "Single-row projection per scoped source row.",
        "stages": [
            {"name": "Input", "actors": ["PopulationArgs", "SyncDeleteMode"]},
            {"name": "Stage 2", "actors": ["RenameAndChangeValue"]},
            {"name": "Source", "actors": ["Query"]},
            {"name": "Stage 1", "actors": ["Const*", "ChangeValue*", "Now1"]},
            {"name": "LU Table", "actors": ["DbLoad(target_table)"]},
        ],
        "flow": [
            "PopulationArgs.parent_rows -> RenameAndChangeValue -> Query",
            "Query/result (+ constants/expr) -> DbLoad",
        ],
    },
    "TPL_MULTIROW_FROM_COLUMNS_PARENT_SCOPED": {
        "profile": "multirow_from_columns_parent_scoped",
        "summary": "Emit 0..N rows from source columns using emit_rows rules.",
        "stages": [
            {"name": "Input", "actors": ["PopulationArgs", "SyncDeleteMode"]},
            {"name": "Stage 2", "actors": ["RenameAndChangeValue"]},
            {"name": "Source", "actors": ["Query"]},
            {"name": "Stage 1", "actors": ["EmitRows(JavaScript)"]},
            {"name": "LU Table", "actors": ["DbLoad(target_table)"]},
        ],
        "flow": [
            "PopulationArgs.parent_rows -> RenameAndChangeValue -> Query",
            "Query/result -> EmitRows/result -> DbLoad",
        ],
    },
    "TPL_JOIN_TO_1_PARENT_SCOPED": {
        "profile": "join_to_1_parent_scoped",
        "summary": "Bridge lookup then local join query, followed by projection JS.",
        "stages": [
            {"name": "Input", "actors": ["PopulationArgs"]},
            {"name": "Stage 3", "actors": ["RenameAndChangeValue(bridge seed)"]},
            {"name": "Source", "actors": ["XRefBridge"]},
            {"name": "Stage 2", "actors": ["QueryJoin"]},
            {"name": "Stage 1", "actors": ["ProjectRows(JavaScript)"]},
            {"name": "LU Table", "actors": ["DbLoad(target_table)"]},
        ],
        "flow": [
            "PopulationArgs/driver -> RenameAndChangeValue/result -> XRefBridge(parent_rows)",
            "XRefBridge/result -> QueryJoin(parent_rows) -> ProjectRows -> DbLoad",
        ],
    },
}


def get_template_broadway_actor_reference(template_id: str) -> Dict[str, Any]:
    """Return procedural Broadway actor reference for a template_id.

    This is documentation-in-code only; generation logic lives in renderer
    functions in this module and runtime semantics from ir/broadway_compiler.py.
    """
    return TEMPLATE_BROADWAY_ACTOR_REFERENCE.get(template_id, {})


def _ensure_dir(path: Path) -> None:
    path.mkdir(parents=True, exist_ok=True)


def _safe_name(plan_id: str) -> str:
    return plan_id.replace("/", "_").replace(" ", "_")


def _safe_table_name(table_name: str) -> str:
    return str(table_name or "UNKNOWN_TARGET").replace("/", "_").replace(" ", "_")


def _java_identifier_part(value: str) -> str:
    cleaned = re.sub(r"[^0-9A-Za-z]+", " ", str(value or "")).strip()
    if not cleaned:
        return "Generated"
    return "".join(part[:1].upper() + part[1:].lower() for part in cleaned.split())


def _java_class_name(plan_id: str) -> str:
    return "".join(_java_identifier_part(part) for part in str(plan_id or "GeneratedPlan").split("__")) + "Plan"


JAVA_CLASS_ALIASES: Dict[str, str] = {
    "TC_PTY_CNT_MED__Siebel__SBL_CUSTOMER": "TcPtyCntMedSiebelCustomerContactPlan",
    "TC_PTY_CNT_MED__BSCS__JOINED": "TcPtyCntMedBscsBillingAddressPlan",
}


def _java_string(value: Any) -> str:
    return json.dumps("" if value is None else str(value))


def _java_sql_identifier(value: str) -> str:
    text = str(value or "")
    if not re.fullmatch(r"[A-Za-z_][A-Za-z0-9_]*", text):
        raise ValueError(f"Unsupported SQL identifier for Java materialization: {text!r}")
    return text


def _java_field_name(value: str) -> str:
    field_name = _java_identifier_part(value)
    return field_name[:1].lower() + field_name[1:]


def _target_table_from_runtime_plan(runtime_plan: Dict[str, Any]) -> str:
    spec = runtime_plan.get("spec", {})
    if isinstance(spec, dict):
        load = spec.get("load", {})
        if isinstance(load, dict) and load.get("target_table"):
            return str(load.get("target_table"))
        args = spec.get("args", {})
        if isinstance(args, dict) and args.get("target_table"):
            return str(args.get("target_table"))
    if runtime_plan.get("target_table"):
        return str(runtime_plan.get("target_table"))
    return "UNKNOWN_TARGET"


def _copy_spec_with_load_command(spec: Dict[str, Any], command: str) -> Dict[str, Any]:
    if not isinstance(spec, dict):
        return spec
    copied = dict(spec)
    load = copied.get("load")
    if isinstance(load, dict):
        updated_load = dict(load)
        updated_load["command"] = command
        copied["load"] = updated_load
    return copied


def _inject_dbload_command(load_actor_in: Dict[str, Any], load: Dict[str, Any]) -> None:
    command = load.get("command") if isinstance(load, dict) else None
    if command:
        load_actor_in["command"] = {"const": str(command)}


def _yaml_scalar(value: Any) -> str:
    if value is None:
        return "null"
    if isinstance(value, bool):
        return "true" if value else "false"
    if isinstance(value, (int, float)):
        return str(value)
    if isinstance(value, str):
        if value == "":
            return "''"
        if "\n" in value:
            return value
        # Keep plain scalars readable; quote only when needed.
        unsafe = ["{", "}", "[", "]", "#", "&", "?", "|", ">", "@", "`", "'"]
        if value.strip() != value or any(ch in value for ch in unsafe):
            return "'" + value.replace("'", "''") + "'"
        return value
    return "'" + str(value).replace("'", "''") + "'"


def _yaml_dump(value: Any, indent: int = 0) -> str:
    sp = " " * indent
    if isinstance(value, dict):
        if not value:
            return "{}"
        lines = []
        for k, v in value.items():
            key = str(k)
            if isinstance(v, str) and "\n" in v:
                lines.append(f"{sp}{key}: |-")
                for ln in v.splitlines():
                    lines.append(f"{sp}  {ln}")
                continue
            if isinstance(v, dict):
                if not v:
                    lines.append(f"{sp}{key}: {{}}")
                else:
                    lines.append(f"{sp}{key}:")
                    lines.append(_yaml_dump(v, indent + 2))
                continue
            if isinstance(v, list):
                if not v:
                    lines.append(f"{sp}{key}: []")
                else:
                    lines.append(f"{sp}{key}:")
                    lines.append(_yaml_dump(v, indent + 2))
                continue
            else:
                lines.append(f"{sp}{key}: {_yaml_scalar(v)}")
        return "\n".join(lines)
    if isinstance(value, list):
        if not value:
            return "[]"
        lines = []
        for item in value:
            if isinstance(item, str) and "\n" in item:
                lines.append(f"{sp}- |-")
                for ln in item.splitlines():
                    lines.append(f"{sp}  {ln}")
                continue
            if isinstance(item, dict):
                if not item:
                    lines.append(f"{sp}- {{}}")
                else:
                    lines.append(f"{sp}-")
                    lines.append(_yaml_dump(item, indent + 2))
                continue
            if isinstance(item, list):
                if not item:
                    lines.append(f"{sp}- []")
                else:
                    lines.append(f"{sp}-")
                    lines.append(_yaml_dump(item, indent + 2))
                continue
            else:
                lines.append(f"{sp}- {_yaml_scalar(item)}")
        return "\n".join(lines)
    return f"{sp}{_yaml_scalar(value)}"


def _load_template_text(name: str) -> str:
    tpath = Path(__file__).resolve().parent / "broadway_templates" / name
    return tpath.read_text(encoding="utf-8")


def _load_template_json(name: str) -> Dict[str, Any]:
    tpath = Path(__file__).resolve().parent / "broadway_templates" / name
    return json.loads(tpath.read_text(encoding="utf-8"))


def _build_rename_script(rename_alias: str, strip_prefix: Optional[str] = None) -> str:
    if strip_prefix:
        pfx = json.dumps(str(strip_prefix))
        return (
            "var s = \"\";\n"
            "if (inputs !== null && inputs !== undefined) {\n"
            "  s = \"\" + inputs;\n"
            "}\n\n"
            "s = s.trim().replace(/^\\[/, \"\").replace(/\\]$/, \"\");\n"
            f"var pfx = {pfx};\n\n"
            "self.result = [];\n\n"
            "if (s) {\n"
            "  var parts = s.split(\",\");\n"
            "  for (var i = 0; i < parts.length; i++) {\n"
            "    var v = parts[i].trim().replace(/^\\[/, \"\").replace(/\\]$/, \"\");\n"
            "    if (v && pfx && v.indexOf(pfx) === 0) {\n"
            "      v = v.substring(pfx.length);\n"
            "    }\n"
            "    if (v) self.result.push({ " + rename_alias + ": v });\n"
            "  }\n"
            "}\n\n"
            "self.result;"
        )
    return _load_template_text("rename_from_parent.js").replace("{{rename_alias}}", rename_alias)


def _normalize_row_match_policy(value: Any) -> str:
    p = str(value or "").strip().upper()
    if p in {"ONE_ONLY", "ZERO_OR_ONE", "MULTIPLE", "LATEST"}:
        return p
    if p == "EXPECT_ONE":
        return "ONE_ONLY"
    if p in {"ALLOW_MANY", "EXPECT_MANY"}:
        return "MULTIPLE"
    return "MULTIPLE"


def _sql_with_row_policy(base_sql: str, policy: Any, latest_by: Optional[str] = None) -> str:
    p = _normalize_row_match_policy(policy)
    sql = (base_sql or "").strip()
    if not sql:
        return sql
    if p == "MULTIPLE":
        return sql
    col = (latest_by or "").strip()
    is_ident = bool(re.fullmatch(r"[A-Za-z_][A-Za-z0-9_]*", col))
    if p == "LATEST":
        if is_ident:
            return f"SELECT * FROM ({sql}) __rowmatch ORDER BY {col} DESC LIMIT 1"
        return f"SELECT * FROM ({sql}) __rowmatch LIMIT 1"
    # ONE_ONLY / ZERO_OR_ONE: cap to 1 row.
    return f"SELECT * FROM ({sql}) __rowmatch LIMIT 1"


_IDENT_RE = re.compile(r"\b[A-Za-z_][A-Za-z0-9_]*\b")
_NOW_CALL_RE = re.compile(r"\bnow\s*\(\s*\)", re.IGNORECASE)
_JS_NOW_RE = re.compile(
    r"\(\s*new\s+Date\s*\(\s*\)\s*\)\s*\.toISOString\s*\(\s*\)|new\s+Date\s*\(\s*\)\s*\.toISOString\s*\(\s*\)"
)
_RESERVED_WORDS = {
    "true", "false", "null", "undefined", "NaN", "Infinity",
    "if", "else", "return", "var", "let", "const", "new", "typeof",
}


def _extract_identifiers(expr: Any) -> list[str]:
    if not isinstance(expr, str):
        return []
    out: list[str] = []
    seen = set()
    for m in _IDENT_RE.finditer(expr):
        token = m.group(0)
        if token in _RESERVED_WORDS:
            continue
        start, end = m.span()
        prev_char = expr[start - 1] if start > 0 else ""
        if prev_char == ".":
            continue
        i = end
        while i < len(expr) and expr[i].isspace():
            i += 1
        if i < len(expr) and expr[i] == "(":
            continue
        if end < len(expr) and expr[end] == ".":
            continue
        if token not in seen:
            seen.add(token)
            out.append(token)
    return out


def _rewrite_expr_to_scalar_vars(expr: Any, source_columns: list[str]) -> str:
    if not isinstance(expr, str):
        return str(expr) if expr is not None else "null"
    out = expr
    for col in source_columns:
        if not col:
            continue
        out = re.sub(rf"(?<!['\"])\b{re.escape(col)}\b(?!['\"])", f"s_{col}", out)
    return out


def _rewrite_now_tokens(expr: Any) -> tuple[str, bool]:
    if not isinstance(expr, str):
        return (str(expr) if expr is not None else "null"), False
    out = expr
    used_now = False
    if _NOW_CALL_RE.search(out):
        out = _NOW_CALL_RE.sub("s_now", out)
        used_now = True
    if _JS_NOW_RE.search(out):
        out = _JS_NOW_RE.sub("s_now", out)
        used_now = True
    return out, used_now


def _js_const_literal(value: Any) -> str:
    if value is None:
        return "null"
    if isinstance(value, bool):
        return "true" if value else "false"
    if isinstance(value, (int, float)):
        return str(value)
    s = str(value).strip()
    if re.fullmatch(r"-?\d+", s):
        return s
    if s.lower() in {"true", "false"}:
        return s.lower()
    return json.dumps(str(value))


def _build_emit_rows_js(emit_rows: list[dict[str, Any]]) -> tuple[str, list[str], bool]:
    source_columns: list[str] = []
    context_columns: list[str] = []
    uses_now = False
    for row in emit_rows:
        for token in _extract_identifiers(row.get("emit_when")):
            if token not in source_columns:
                source_columns.append(token)
        fields = row.get("fields")
        if not isinstance(fields, dict):
            continue
        for expr in fields.values():
            if not isinstance(expr, dict):
                continue
            op = expr.get("op")
            if op == "PATH":
                path = str(expr.get("path") or "")
                parts = path.split(".")
                if len(parts) == 3 and parts[2] not in source_columns:
                    source_columns.append(parts[2])
            elif op == "CONTEXT":
                ck = str(expr.get("context_key") or "").strip()
                if ck and ck not in context_columns:
                    context_columns.append(ck)
            elif op == "EXPR":
                for token in _extract_identifiers(expr.get("expr")):
                    if token not in source_columns:
                        source_columns.append(token)

    lines: list[str] = [
        "function scalar(v) {",
        "  if (v === null || v === undefined) return null;",
        "  try {",
        "    if (typeof v !== 'string' && v[0] !== undefined) v = v[0];",
        "  } catch (e) {}",
        "  return '' + v;",
        "}",
        "",
    ]
    for c in source_columns:
        lines.append(f"var s_{c} = scalar({c});")
    if uses_now:
        lines.append("var s_now = scalar(now);")
    for c in context_columns:
        lines.append(f"var s_parent_{c} = scalar(parent_{c});")
    lines.extend(["", "self.result = [];", ""])

    for row in emit_rows:
        row_id = row.get("row_id", "ROW")
        emit_when = row.get("emit_when") or "true"
        fields = row.get("fields")
        if not isinstance(fields, dict):
            fields = {}
        lines.append(f"if ({emit_when}) {{")
        lines.append(f"  // {row_id}")
        lines.append("  self.result.push({")
        field_lines: list[str] = []
        for k, expr in fields.items():
            if not isinstance(expr, dict):
                field_lines.append(f"    {k}: null")
                continue
            op = expr.get("op")
            if op == "PATH":
                path = str(expr.get("path") or "")
                parts = path.split(".")
                col = parts[2] if len(parts) == 3 else ""
                field_lines.append(f"    {k}: s_{col}" if col else f"    {k}: null")
            elif op == "CONST":
                field_lines.append(f"    {k}: {_js_const_literal(expr.get('value'))}")
            elif op == "EXPR":
                rewritten = _rewrite_expr_to_scalar_vars(expr.get("expr"), source_columns)
                rewritten, now_hit = _rewrite_now_tokens(rewritten)
                uses_now = uses_now or now_hit
                field_lines.append(f"    {k}: {rewritten or 'null'}")
            elif op == "CONTEXT":
                ck = str(expr.get("context_key") or "").strip()
                field_lines.append(f"    {k}: s_parent_{ck}" if ck else f"    {k}: null")
            else:
                field_lines.append(f"    {k}: null")
        for i, line in enumerate(field_lines):
            suffix = "," if i < len(field_lines) - 1 else ""
            lines.append(line + suffix)
        lines.append("  });")
        lines.append("}")
        lines.append("")

    lines.append("self.result;")
    if uses_now and "var s_now = scalar(now);" not in lines:
        lines.insert(8 + len(source_columns), "var s_now = scalar(now);")
    return "\n".join(lines), source_columns, uses_now


def _build_emit_rows_js_scalar(emit_rows: list[dict[str, Any]]) -> tuple[str, list[str], bool]:
    source_columns: list[str] = []
    context_columns: list[str] = []
    uses_now = False
    for row in emit_rows:
        fields = row.get("fields")
        if not isinstance(fields, dict):
            continue
        for expr in fields.values():
            if not isinstance(expr, dict):
                continue
            op = expr.get("op")
            if op == "PATH":
                path = str(expr.get("path") or "")
                parts = path.split(".")
                if len(parts) == 3 and parts[2] not in source_columns:
                    source_columns.append(parts[2])
            elif op == "EXPR":
                for token in _extract_identifiers(expr.get("expr")):
                    if token not in source_columns:
                        source_columns.append(token)
            elif op == "CONTEXT":
                ck = str(expr.get("context_key") or "").strip()
                if ck and ck not in context_columns:
                    context_columns.append(ck)
                    if ck not in source_columns:
                        source_columns.append(ck)
    lines: list[str] = [
        "function scalar(v) {",
        "  if (v === null || v === undefined) return null;",
        "",
        "  // unwrap 1-element list-ish values",
        "  try {",
        "    if (typeof v !== \"string\" && v[0] !== undefined) v = v[0];",
        "  } catch (e) {}",
        "",
        "  return \"\" + v;",
        "}",
        "",
    ]
    for c in source_columns:
        lines.append(f"var s_{c} = scalar({c});")
    if uses_now:
        lines.append("var s_now = scalar(now);")
    lines.extend(["", "self.result = [];", ""])

    def _rw(v: Any) -> str:
        out = str(v or "")
        for c in source_columns:
            out = re.sub(rf"(?<!['\"])\b{re.escape(c)}\b(?!['\"])", f"s_{c}", out)
        return out

    for row in emit_rows:
        emit_when = row.get("emit_when") or "true"
        lines.append(f"if ({_rw(emit_when)}) {{")
        lines.append("  self.result.push({")
        fields = row.get("fields") if isinstance(row.get("fields"), dict) else {}
        rendered: list[str] = []
        for k, expr in fields.items():
            if not isinstance(expr, dict):
                rendered.append(f"    {k}: null")
                continue
            op = expr.get("op")
            if op == "PATH":
                parts = str(expr.get("path") or "").split(".")
                col = parts[2] if len(parts) == 3 else ""
                rendered.append(f"    {k}: " + (f"s_{col}" if col else "null"))
            elif op == "CONST":
                rendered.append(f"    {k}: {_js_const_literal(expr.get('value'))}")
            elif op == "EXPR":
                rewritten = _rw(expr.get("expr"))
                rewritten, now_hit = _rewrite_now_tokens(rewritten)
                uses_now = uses_now or now_hit
                rendered.append(f"    {k}: {rewritten or 'null'}")
            elif op == "CONTEXT":
                ck = str(expr.get("context_key") or "").strip()
                rendered.append(f"    {k}: s_{ck}" if ck else f"    {k}: null")
            else:
                rendered.append(f"    {k}: null")
        for i, line in enumerate(rendered):
            lines.append(line + ("," if i < len(rendered) - 1 else ""))
        lines.append("  });")
        lines.append("}")
        lines.append("")
    lines.append("self.result;")
    if uses_now and "var s_now = scalar(now);" not in lines:
        lines.insert(10 + len(source_columns), "var s_now = scalar(now);")
    return "\n".join(lines), source_columns, uses_now


def _render_broadway_join_to_1(plan_id: str, spec: Dict[str, Any]) -> Dict[str, Any]:
    ctx = spec.get("context", {})
    src = spec.get("source", {})
    bridge = spec.get("bridge", {})
    jq = spec.get("join_query", {})
    load = spec.get("load", {})
    behavior = spec.get("behavior", {})

    driver_key = ctx.get("driver_key", "party_id")
    parent_rows_field = ctx.get("parent_rows_field", driver_key)
    rename_alias = ctx.get("rename_alias", driver_key)
    rename_strip_prefix = ctx.get("rename_strip_prefix")
    bridge_output_alias = bridge.get("output_alias") or rename_alias
    row_match_policy = _normalize_row_match_policy(behavior.get("row_match_policy"))
    latest_by = behavior.get("latest_by")
    use_now = bool(behavior.get("use_now"))
    projection_js = behavior.get("projection_js") or "self.result = []; self.result;"
    source_columns = jq.get("source_columns") or src.get("source_columns") or []
    # Keep load wiring resilient: if target_fields are not populated in IR,
    # derive them from join field_bindings so DbLoad still consumes ProjectRows.
    target_fields = load.get("target_fields") or [
        b.get("target_field")
        for b in (load.get("field_bindings") or [])
        if isinstance(b, dict) and b.get("target_field")
    ]
    target_table = load.get("target_table", "UNKNOWN_TARGET")
    rows_dist = _load_template_json("rows_generator_distribution.json")

    bridge_script = _build_rename_script(rename_alias, rename_strip_prefix)

    stages: Dict[str, Any] = {
        "Input": {
            "actors": {
                "PopulationArgs": {
                    "parent": "PopulationArgs",
                    "readonly": True,
                    "in": {
                        driver_key: {"external": driver_key, "schema": "any", "mandatory": False},
                    },
                    "out": {"parent_rows": {"schema": "#ref"}},
                },
            }
        },
        "Stage 3": {
            "actors": {
                "RenameAndChangeValue": {
                    "parent": "JavaScript",
                    "height": 199,
                    "in": {
                        "script": {"const": bridge_script},
                        "inputs": {
                            "link": {"path": f"PopulationArgs/parent_rows/{parent_rows_field}", "pos": 0},
                            "schema": "#ref",
                            "mandatory": False,
                        },
                    },
                    "out": {"result": {"schema": "#ref"}},
                }
            }
        },
        "Source": {"actors": {}},
        "Stage 2": {"actors": {}},
        "Stage 1": {"actors": {}},
        "LU Table": {"last": 1, "actors": {}},
        "Post Load": {},
    }

    if bridge.get("enabled"):
        stages["Source"]["actors"]["XRefBridge"] = {
            "parent": "SourceDbQuery",
            "height": 258,
            "in": {
                "interface": {"const": bridge.get("interface")},
                "sql": {"const": bridge.get("sql")},
                "rowsGeneratorDistribution": {"const": rows_dist},
                "parent_rows": {"link": "RenameAndChangeValue/result"},
            },
            "out": {"result": {"schema": "#ref"}},
        }
        stages["Stage 2"]["actors"]["QueryJoin"] = {
            "parent": "SourceDbQuery",
            "height": 229,
            "in": {
                "interface": {"const": jq.get("interface") or src.get("interface")},
                "sql": {"const": _sql_with_row_policy(jq.get("sql"), row_match_policy, latest_by)},
                "rowsGeneratorDistribution": {"const": rows_dist},
                "parent_rows": {"link": "XRefBridge/result"},
            },
            "out": {"result": {"schema": "#ref"}},
        }
        projection_input_prefix = "QueryJoin/result"
    else:
        stages["Stage 2"]["actors"]["QueryJoin"] = {
            "parent": "SourceDbQuery",
            "height": 229,
            "in": {
                "interface": {"const": jq.get("interface") or src.get("interface")},
                "sql": {"const": _sql_with_row_policy(jq.get("sql") or src.get("sql"), row_match_policy, latest_by)},
                "rowsGeneratorDistribution": {"const": rows_dist},
                "parent_rows": {"link": "RenameAndChangeValue/result"},
            },
            "out": {"result": {"schema": "#ref"}},
        }
        projection_input_prefix = "QueryJoin/result"

    js_inputs: Dict[str, Any] = {
        "script": {"const": projection_js},
        f"parent_{driver_key}": {
            "link": f"PopulationArgs/parent_rows/{parent_rows_field}",
            "schema": "string",
            "mandatory": False,
        },
    }
    if use_now:
        stages["Stage 1"]["actors"]["Now1"] = {"parent": "Now"}
        js_inputs["now"] = {
            "link": "Now1/date",
            "schema": "string",
            "mandatory": False,
        }
    for col in source_columns:
        js_inputs[col] = {
            "link": {"path": f"{projection_input_prefix}/{col}", "iterate": load.get("iterate_mode", "Iterate")},
            "schema": "string",
            "mandatory": False,
        }

    stages["Stage 1"]["actors"]["ProjectRows"] = {
        "parent": "JavaScript",
        "in": js_inputs,
        "out": {"result": {"schema": "#ref"}},
    }

    load_actor_in: Dict[str, Any] = {
        "interface": {"const": load.get("target_interface", "fabric")},
        "schema": {"const": load.get("target_schema"), "external": "schema"},
        "table": {"const": None, "external": "table"},
        "fields": {"const": target_fields},
        "keys": {"const": load.get("keys")},
        "dialect": {"const": load.get("dialect", "sqlite")},
        "params": {"link": {"path": "ProjectRows/result", "iterate": load.get("iterate_mode", "Iterate")}},
    }
    _inject_dbload_command(load_actor_in, load)
    for f in target_fields:
        load_actor_in[f] = {"link": f"ProjectRows/result/{f}", "schema": "string"}

    stages["LU Table"]["actors"][target_table] = {"parent": "DbLoad", "in": load_actor_in}

    schemas: Dict[str, Any] = {
        "PopulationArgs.out.parent_rows": {
            "type": "array",
            "items": {"type": "object", "properties": {driver_key: {"type": "string"}}},
        },
        "RenameAndChangeValue.in.inputs": {
            "type": "array",
            "items": {"type": "object", "properties": {parent_rows_field: {"type": "string"}}},
        },
        "RenameAndChangeValue.out.result": {
            "type": "array",
            "items": {"type": "object", "properties": {rename_alias: {"type": "string"}}},
        },
        "QueryJoin.out.result": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {c: {"type": "string"} for c in source_columns},
            },
        },
        "ProjectRows.out.result": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {f: {"type": "string"} for f in target_fields},
            },
        },
    }
    if bridge.get("enabled"):
        schemas["XRefBridge.out.result"] = {
            "type": "array",
            "items": {"type": "object", "properties": {bridge_output_alias: {"type": "string"}}},
        }
    return {"stages": stages, "schemas": schemas}


def _render_broadway_from_abstract(plan_id: str, spec: Dict[str, Any]) -> Dict[str, Any]:
    if spec.get("profile") == "join_to_1_parent_scoped":
        return _render_broadway_join_to_1(plan_id, spec)
    if spec.get("profile") == "array_input_to_eav_parent_scoped":
        return _render_broadway_array_input_to_eav(plan_id, spec)
    if spec.get("profile") == "array_input_to_columns_parent_scoped":
        return _render_broadway_array_input(plan_id, spec)

    ctx = spec.get("context", {})
    src = spec.get("source", {})
    load = spec.get("load", {})
    bindings = load.get("field_bindings", [])
    source_columns = src.get("source_columns", [])
    behavior = spec.get("behavior", {})
    emit_rows = behavior.get("emit_rows") or []
    is_multirow = bool(emit_rows)
    row_match_policy = _normalize_row_match_policy(behavior.get("row_match_policy"))
    latest_by = behavior.get("latest_by")

    parent_rows_field = ctx.get("parent_rows_field", "__parent__.1")
    rename_alias = ctx.get("rename_alias", "party_id")
    include_population_input = bool(ctx.get("include_population_input"))
    source_table = src.get("table")
    source_interface = src.get("interface")
    target_table = load.get("target_table", "UNKNOWN_TARGET")
    target_interface = load.get("target_interface", "fabric")
    target_schema = load.get("target_schema")
    dialect = load.get("dialect", "sqlite")
    iterate_mode = load.get("iterate_mode", "Iterate")
    keys = load.get("keys", [])

    rename_script = _build_rename_script(rename_alias, ctx.get("rename_strip_prefix"))
    expr_prefix_script_tpl = _load_template_text("change_value_prefix.js")
    rows_dist = _load_template_json("rows_generator_distribution.json")

    stages: Dict[str, Any] = {
        "Input": {
            "actors": {
                "PopulationArgs": {
                    "parent": "PopulationArgs",
                    "readonly": True,
                    "out": {"parent_rows": {"schema": "#ref"}},
                },
                "SyncDeleteMode": {
                    "parent": "SyncDeleteMode",
                    "in": {
                        "interface": {"schema": "any"},
                        "table": {"const": None, "external": "table"},
                    },
                },
            }
        },
        "Stage 2": {
            "actors": {
                "RenameAndChangeValue": {
                    "parent": "JavaScript",
                    "in": {
                        "script": {"const": rename_script},
                        "inputs": {
                            "link": {"path": f"PopulationArgs/parent_rows/{parent_rows_field}", "pos": 0},
                            "schema": "#ref",
                            "mandatory": False,
                        },
                    },
                    "out": {"result": {"schema": "#ref"}},
                }
            }
        },
        "Source": {
            "actors": {
                "Query": {
                    "parent": "SourceDbQuery",
                    "in": {
                        "interface": {"const": source_interface},
                        "sql": {
                            "const": _sql_with_row_policy(
                                src.get("sql") or f"select * from main.{source_table}",
                                row_match_policy,
                                latest_by,
                            )
                        },
                        "rowsGeneratorDistribution": {"const": rows_dist},
                        "parent_rows": {"link": "RenameAndChangeValue/result"},
                    },
                    "out": {"result": {"schema": "#ref"}},
                }
            }
        },
        "Stage 3": {"actors": {}},
        "Stage 1": {"actors": {}},
        "LU Table": {"last": 1, "actors": {}},
        "Post Load": {},
    }

    if include_population_input:
        stages["Input"]["actors"]["PopulationArgs"]["in"] = {
            parent_rows_field: {
                "external": parent_rows_field,
                "schema": "any",
                "mandatory": False,
            }
        }

    if src.get("luid_sql"):
        stages["Source"]["actors"]["Query"]["in"]["luid_column_name"] = {"const": src.get("luid_sql")}

    const_actor_for_field: Dict[str, str] = {}
    expr_actor_for_field: Dict[str, str] = {}
    if is_multirow:
        emit_script, inferred_cols, uses_now = _build_emit_rows_js(emit_rows)
        if inferred_cols:
            source_columns = inferred_cols
        emit_inputs: Dict[str, Any] = {"script": {"const": emit_script}}
        if uses_now:
            stages["Stage 3"]["actors"]["Now1"] = {"parent": "Now"}
            emit_inputs["now"] = {
                "link": "Now1/date",
                "schema": "string",
                "mandatory": False,
            }
        for col in source_columns:
            emit_inputs[col] = {
                "link": {"path": f"Query/result/{col}", "iterate": iterate_mode},
                "schema": "string",
                "mandatory": False,
            }
        if include_population_input:
            emit_inputs[f"parent_{parent_rows_field}"] = {
                "link": f"PopulationArgs/parent_rows/{parent_rows_field}",
                "schema": "string",
                "mandatory": False,
            }
        stages["Stage 1"]["actors"]["EmitRows"] = {
            "parent": "JavaScript",
            "in": emit_inputs,
            "out": {"result": {"schema": "#ref"}},
        }
    else:
        const_idx = 0
        expr_idx = 0
        need_now = any((b.get("value_semantic") == "now" for b in bindings))
        for b in bindings:
            if b.get("value_semantic") == "const":
                const_idx += 1
                actor_id = f"Const{const_idx}"
                const_actor_for_field[b["target_field"]] = actor_id
                stages["Stage 1"]["actors"][actor_id] = {
                    "parent": "Const",
                    "in": {"value": {"const": b.get("const_value"), "schema": "string"}},
                    "out": {"value": {"schema": "string"}},
                }
            elif b.get("value_semantic") == "expr":
                expr_idx += 1
                actor_id = "ChangeValue" if expr_idx == 1 else f"ChangeValue{expr_idx}"
                expr_actor_for_field[b["target_field"]] = actor_id
                if b.get("expr_kind") == "concat_prefix" and b.get("source_column"):
                    input_var = b.get("expr_input_var", "acc_id")
                    prefix_js = json.dumps(b.get("const_prefix", ""))
                    script = expr_prefix_script_tpl.replace("{{prefix_js}}", prefix_js).replace("{{input_var}}", input_var)
                    stages["Stage 1"]["actors"][actor_id] = {
                        "parent": "JavaScript",
                        "in": {
                            "script": {"const": script},
                            input_var: {
                                "link": f"Query/result/{b.get('source_column')}",
                                "schema": "string",
                                "mandatory": False,
                            },
                        },
                        "out": {"result": {"schema": "string"}},
                    }
                else:
                    stages["Stage 1"]["actors"][actor_id] = {
                        "parent": "JavaScript",
                        "in": {"script": {"const": "self.result = null;"}},
                        "out": {"result": {"schema": "any"}},
                    }
        if need_now:
            stages["Stage 1"]["actors"]["Now1"] = {"parent": "Now"}

    load_actor_in: Dict[str, Any] = {
        "interface": {"const": target_interface},
        "schema": {"const": target_schema, "external": "schema"},
        "table": {"const": None, "external": "table"},
        "fields": {"const": load.get("target_fields") or [b["target_field"] for b in bindings]},
        "keys": {"const": keys if keys else None},
        "dialect": {"const": dialect},
    }
    _inject_dbload_command(load_actor_in, load)

    if is_multirow:
        for f in (load.get("target_fields") or []):
            load_actor_in[f] = {"link": f"EmitRows/result/{f}", "schema": "string"}
        load_actor_in["params"] = {"link": {"path": "EmitRows/result", "iterate": iterate_mode}}
    else:
        for b in bindings:
            target_field = b["target_field"]
            semantic = b.get("value_semantic")
            if semantic == "source":
                src_col = b.get("source_column")
                if src_col:
                    load_actor_in[target_field] = {
                        "link": f"Query/result/{src_col}",
                        "schema": "string" if include_population_input else "#ref",
                    }
                else:
                    load_actor_in[target_field] = {"schema": "any"}
            elif semantic == "const":
                actor_id = const_actor_for_field.get(target_field)
                if actor_id:
                    load_actor_in[target_field] = {"link": f"{actor_id}/value", "schema": "string"}
                else:
                    load_actor_in[target_field] = {"const": b.get("const_value"), "schema": "string"}
            elif semantic == "now":
                load_actor_in[target_field] = {"link": "Now1/date", "schema": "date"}
            elif semantic == "null":
                load_actor_in[target_field] = {"schema": "any"}
            elif semantic == "expr":
                actor_id = expr_actor_for_field.get(target_field)
                if actor_id:
                    load_actor_in[target_field] = {"link": f"{actor_id}/result", "schema": "string"}
                else:
                    load_actor_in[target_field] = {"schema": "any"}
            else:
                load_actor_in[target_field] = {"schema": "any"}
        load_actor_in["params"] = {"link": {"path": "Query/result", "iterate": iterate_mode}}
    stages["LU Table"]["actors"][target_table] = {
        "parent": "DbLoad",
        "in": load_actor_in,
    }

    schemas: Dict[str, Any] = {
        "PopulationArgs.out.parent_rows": {
            "type": "array",
            "items": {"type": "object", "properties": {parent_rows_field: {"type": "string"}}},
        },
        "RenameAndChangeValue.in.inputs": {"type": "array", "items": {"type": "object"}},
        "RenameAndChangeValue.out.result": {"type": "array", "items": {"type": "object", "properties": {rename_alias: {"type": "string"}}}},
    }
    if source_columns:
        schemas["Query.out.result"] = {
            "type": "array",
            "items": {"type": "object", "properties": {c: {"type": "string"} for c in source_columns}},
        }
    if is_multirow:
        schemas["EmitRows.out.result"] = {"type": "array", "items": {"type": "object"}}
    else:
        for b in bindings:
            if b.get("value_semantic") in {"source", "expr"} and b.get("source_column"):
                schemas[f"{target_table}.in.{b['target_field']}"] = {"type": "array", "items": {"type": "string"}}

    return {"stages": stages, "schemas": schemas}


def _render_broadway_array_input(plan_id: str, spec: Dict[str, Any]) -> Dict[str, Any]:
    ctx = spec.get("context", {})
    src = spec.get("source", {})
    behavior = spec.get("behavior", {})
    load = spec.get("load", {})
    bindings = load.get("field_bindings", [])
    parent_rows_field = ctx.get("parent_rows_field") or ctx.get("driver_key") or "id"
    target_table = load.get("target_table", "UNKNOWN_TARGET")
    iterate_mode = load.get("iterate_mode", "Iterate")
    row_match_policy = _normalize_row_match_policy(behavior.get("row_match_policy"))
    latest_by = behavior.get("latest_by")
    source_table = src.get("table")
    source_interface = src.get("interface")
    source_columns = src.get("source_columns", [])
    rows_dist = _load_template_json("rows_generator_distribution.json")

    stages: Dict[str, Any] = {
        "Input": {
            "actors": {
                "PopulationArgs": {
                    "parent": "PopulationArgs",
                    "readonly": True,
                    "in": {
                        parent_rows_field: {
                            "external": parent_rows_field,
                            "schema": "any",
                            "mandatory": False,
                        }
                    },
                    "out": {"parent_rows": {"schema": "#ref"}},
                },
                "SyncDeleteMode": {
                    "parent": "SyncDeleteMode",
                    "in": {
                        "interface": {"schema": "any"},
                        "table": {"const": None, "external": "table"},
                    },
                },
            }
        },
        "Source": {
            "actors": {
                "Query": {
                    "parent": "SourceDbQuery",
                    "in": {
                        "interface": {"const": source_interface},
                        "sql": {
                            "const": _sql_with_row_policy(
                                src.get("sql") or f"select * from main.{source_table}",
                                row_match_policy,
                                latest_by,
                            )
                        },
                        "rowsGeneratorDistribution": {"const": rows_dist},
                        "parent_rows": {"link": "PopulationArgs/parent_rows"},
                    },
                    "out": {"result": {"schema": "#ref"}},
                }
            }
        },
        "Stage 1": {"actors": {}},
        "LU Table": {"last": 1, "actors": {}},
        "Post Load": {},
    }

    if src.get("luid_sql"):
        stages["Source"]["actors"]["Query"]["in"]["luid_column_name"] = {"const": src.get("luid_sql")}

    const_actor_for_field: Dict[str, str] = {}
    expr_actor_for_field: Dict[str, str] = {}
    expr_prefix_script_tpl = _load_template_text("change_value_prefix.js")
    const_idx = 0
    expr_idx = 0
    if any((b.get("value_semantic") == "now" for b in bindings)):
        stages["Stage 1"]["actors"]["Now1"] = {"parent": "Now"}
    for b in bindings:
        if b.get("value_semantic") == "const":
            const_idx += 1
            actor_id = f"Const{const_idx}"
            const_actor_for_field[b["target_field"]] = actor_id
            stages["Stage 1"]["actors"][actor_id] = {
                "parent": "Const",
                "in": {"value": {"const": b.get("const_value"), "schema": "string"}},
                "out": {"value": {"schema": "string"}},
            }
        elif b.get("value_semantic") == "expr":
            expr_idx += 1
            actor_id = "ChangeValue" if expr_idx == 1 else f"ChangeValue{expr_idx}"
            expr_actor_for_field[b["target_field"]] = actor_id
            if b.get("expr_kind") == "concat_prefix" and b.get("source_column"):
                input_var = b.get("expr_input_var", "acc_id")
                prefix_js = json.dumps(b.get("const_prefix", ""))
                script = expr_prefix_script_tpl.replace("{{prefix_js}}", prefix_js).replace("{{input_var}}", input_var)
                stages["Stage 1"]["actors"][actor_id] = {
                    "parent": "JavaScript",
                    "in": {
                        "script": {"const": script},
                        input_var: {
                            "link": f"Query/result/{b.get('source_column')}",
                            "schema": "string",
                            "mandatory": False,
                        },
                    },
                    "out": {"result": {"schema": "string"}},
                }
            else:
                stages["Stage 1"]["actors"][actor_id] = {
                    "parent": "JavaScript",
                    "in": {"script": {"const": "self.result = null;"}},
                    "out": {"result": {"schema": "any"}},
                }

    load_actor_in: Dict[str, Any] = {
        "interface": {"const": load.get("target_interface", "fabric")},
        "schema": {"const": load.get("target_schema"), "external": "schema"},
        "table": {"const": None, "external": "table"},
        "fields": {"const": load.get("target_fields") or [b.get("target_field") for b in bindings]},
        "keys": {"const": load.get("keys")},
        "dialect": {"const": load.get("dialect", "sqlite")},
    }
    _inject_dbload_command(load_actor_in, load)
    for b in bindings:
        tf = b.get("target_field")
        sem = b.get("value_semantic")
        if sem == "source":
            sc = b.get("source_column")
            if sc:
                load_actor_in[tf] = {"link": f"Query/result/{sc}", "schema": "string"}
            else:
                load_actor_in[tf] = {"schema": "any"}
        elif sem == "const":
            aid = const_actor_for_field.get(tf)
            if aid:
                load_actor_in[tf] = {"link": f"{aid}/value", "schema": "string"}
            else:
                load_actor_in[tf] = {"const": b.get("const_value"), "schema": "string"}
        elif sem == "now":
            load_actor_in[tf] = {"link": "Now1/date", "schema": "string"}
        elif sem == "expr":
            aid = expr_actor_for_field.get(tf)
            if aid:
                load_actor_in[tf] = {"link": f"{aid}/result", "schema": "string"}
            else:
                load_actor_in[tf] = {"schema": "any"}
        elif sem == "null":
            load_actor_in[tf] = {"schema": "any"}
        else:
            load_actor_in[tf] = {"schema": "any"}
    load_actor_in["params"] = {"link": {"path": "Query/result", "iterate": iterate_mode}}

    stages["LU Table"]["actors"][target_table] = {"parent": "DbLoad", "in": load_actor_in}

    props = {parent_rows_field: {"type": "string"}}
    schemas: Dict[str, Any] = {
        "PopulationArgs.out.parent_rows": {"type": "array", "items": {"type": "object", "properties": props}},
    }
    if source_columns:
        schemas["Query.out.result"] = {
            "type": "array",
            "items": {"type": "object", "properties": {c: {"type": "string"} for c in source_columns}},
        }
    return {"stages": stages, "schemas": schemas}


def _render_broadway_array_input_to_eav(plan_id: str, spec: Dict[str, Any]) -> Dict[str, Any]:
    ctx = spec.get("context", {})
    behavior = spec.get("behavior", {})
    src = spec.get("source", {})
    load = spec.get("load", {})
    emit_rows = behavior.get("emit_rows") or []
    emit_script, source_columns, uses_now = _build_emit_rows_js_scalar(emit_rows)

    parent_rows_field = ctx.get("parent_rows_field") or ctx.get("driver_key") or "id"
    target_table = load.get("target_table", "UNKNOWN_TARGET")
    iterate_mode = load.get("iterate_mode", "Iterate")
    target_fields = load.get("target_fields") or ["product_id", "value_type", "name", "value"]
    rows_dist = _load_template_json("rows_generator_distribution.json")

    js_inputs: Dict[str, Any] = {
        "script": {"const": emit_script},
        "inputs": {
            "link": {"path": "Query/result", "iterate": iterate_mode},
            "schema": "#ref",
            "mandatory": False,
        },
    }
    for col in source_columns:
        js_inputs[col] = {"link": f"Query/result/{col}", "schema": "#ref", "mandatory": False}
    if uses_now:
        js_inputs["now"] = {"link": "Now1/date", "schema": "string", "mandatory": False}

    stages: Dict[str, Any] = {
        "Input": {
            "actors": {
                "PopulationArgs": {
                    "parent": "PopulationArgs",
                    "readonly": True,
                    "in": {
                        parent_rows_field: {
                            "external": parent_rows_field,
                            "schema": "any",
                            "mandatory": False,
                        }
                    },
                    "out": {"parent_rows": {"schema": "#ref"}},
                },
                "SyncDeleteMode": {
                    "parent": "SyncDeleteMode",
                    "in": {
                        "interface": {"schema": "any"},
                        "table": {"const": None, "external": "table"},
                    },
                },
            }
        },
        "Source": {
            "actors": {
                "Query": {
                    "parent": "SourceDbQuery",
                    "in": {
                        "interface": {"const": src.get("interface")},
                        "sql": {"const": src.get("sql")},
                        "rowsGeneratorDistribution": {"const": rows_dist},
                        "parent_rows": {"link": "PopulationArgs/parent_rows"},
                    },
                    "out": {"result": {"schema": "#ref"}},
                }
            }
        },
        "Stage 3": {"actors": {}},
        "Stage 1": {"actors": {}},
        "LU Table": {"last": 1, "actors": {}},
        "Stage 2": {},
        "Post Load": {},
    }
    if src.get("luid_sql"):
        stages["Source"]["actors"]["Query"]["in"]["luid_column_name"] = {"const": src.get("luid_sql")}
    if uses_now:
        stages["Stage 3"]["actors"]["Now1"] = {"parent": "Now"}

    stages["Stage 1"]["actors"]["JavaScript1"] = {
        "parent": "JavaScript",
        "in": js_inputs,
        "out": {"result": {"schema": "#ref"}},
    }

    load_actor_in: Dict[str, Any] = {
        "interface": {"const": load.get("target_interface", "fabric")},
        "schema": {"const": load.get("target_schema"), "external": "schema"},
        "table": {"const": None, "external": "table"},
        "fields": {"const": target_fields},
        "keys": {"const": load.get("keys")},
        "dialect": {"const": load.get("dialect", "sqlite")},
        "params": {"link": {"path": "JavaScript1/result", "iterate": iterate_mode}},
    }
    _inject_dbload_command(load_actor_in, load)
    for f in target_fields:
        load_actor_in[f] = {"link": f"JavaScript1/result/{f}", "schema": "string"}
    stages["LU Table"]["actors"][target_table] = {"parent": "DbLoad", "in": load_actor_in}

    schemas: Dict[str, Any] = {
        "PopulationArgs.out.parent_rows": {
            "type": "array",
            "items": {"type": "object", "properties": {parent_rows_field: {"type": "string"}}},
        },
        "Query.out.result": {
            "type": "array",
            "items": {"type": "object", "properties": {c: {"type": "string"} for c in source_columns}},
        },
        "JavaScript1.in.inputs": {"type": "array", "items": {"type": "object"}},
        "JavaScript1.out.result": {"type": "array", "items": {"type": "object"}},
    }
    for col in source_columns:
        schemas[f"JavaScript1.in.{col}"] = {"type": "array", "items": {"type": "string"}}
    return {"stages": stages, "schemas": schemas}


def _materialize_broadway(
    runtime_plan: Dict[str, Any],
    out_dir: Path,
    target_table: str,
    population_index: int,
    upsert_tables: Optional[set[str]] = None,
) -> Path:
    plan_id = runtime_plan.get("plan_id", "unknown_plan")
    spec = runtime_plan.get("spec", {})
    if upsert_tables and target_table in upsert_tables:
        spec = _copy_spec_with_load_command(spec, "upsert")
    out_file = out_dir / f"{_safe_table_name(target_table)}.population{population_index}.flow"
    concrete = _render_broadway_from_abstract(plan_id, spec)
    payload = {
        "stages": concrete.get("stages", {}),
        "schemas": concrete.get("schemas", {}),
    }
    out_file.write_text(_yaml_dump(payload) + "\n", encoding="utf-8")
    return out_file


def _materialize_python(
    runtime_plan: Dict[str, Any],
    out_dir: Path,
    target_table: str,
    population_index: int,
) -> Path:
    plan_id = runtime_plan.get("plan_id", "unknown_plan")
    spec = runtime_plan.get("spec", {})
    module = spec.get("module", "pipeline.module")
    callable_name = spec.get("callable", "run")
    args = spec.get("args", {})

    out_file = out_dir / f"{_safe_table_name(target_table)}.population{population_index}.py"
    src = f'''"""Auto-generated Python implementation stub.

Plan: {plan_id}
Template: {runtime_plan.get("template_id")}
Module hint: {module}
"""

from __future__ import annotations

from typing import Any, Dict


DEFAULT_ARGS: Dict[str, Any] = {json.dumps(args, indent=2)}


def {callable_name}(context: Dict[str, Any]) -> Dict[str, Any]:
    """Concrete implementation entrypoint for this execution plan."""
    return {{
        "plan_id": "{plan_id}",
        "status": "not_implemented",
        "context": context,
        "default_args": DEFAULT_ARGS,
    }}
'''
    out_file.write_text(src, encoding="utf-8")
    return out_file


def _materialize_java(
    runtime_plan: Dict[str, Any],
    out_dir: Path,
    target_table: str,
    population_index: int,
) -> Path:
    plan_id = runtime_plan.get("plan_id", "unknown_plan")
    spec = runtime_plan.get("spec", {})
    profile = spec.get("profile")
    if target_table == "TC_PTY_CNT_MED" and profile == "multirow_from_columns_parent_scoped":
        return _materialize_java_tmf_contact_medium_siebel(runtime_plan, out_dir)
    if target_table == "TC_PTY_CNT_MED" and profile == "join_to_1_parent_scoped":
        return _materialize_java_tmf_contact_medium_bscs(runtime_plan, out_dir)
    if target_table == "TC_CA_CHAR" and profile == "multirow_from_columns_parent_scoped":
        return _materialize_java_tmf_customer_account_characteristic(runtime_plan, out_dir)
    if target_table == "TC_PTY_EXT_REF" and profile == "join_to_1_parent_scoped":
        return _materialize_java_tmf_external_ref_bscs(runtime_plan, out_dir)
    if target_table == "TC_PRODUCT" and profile == "array_input_to_columns_parent_scoped":
        return _materialize_java_tmf_product(runtime_plan, out_dir)
    if target_table == "TC_CA_PROD_MAP" and profile == "join_to_1_parent_scoped":
        return _materialize_java_tmf_customer_account_product_map(runtime_plan, out_dir)
    if target_table == "TC_PROD_CHAR" and profile == "array_input_to_eav_parent_scoped":
        return _materialize_java_tmf_product_characteristic(runtime_plan, out_dir)
    if profile != "snapshot_1to1_parent_scoped":
        raise ValueError(f"Java materializer only supports snapshot_1to1_parent_scoped, got {profile!r} for {plan_id}")

    context = spec.get("context") if isinstance(spec.get("context"), dict) else {}
    source = spec.get("source") if isinstance(spec.get("source"), dict) else {}
    load = spec.get("load") if isinstance(spec.get("load"), dict) else {}
    bindings = load.get("field_bindings") if isinstance(load.get("field_bindings"), list) else []
    if not bindings:
        raise ValueError(f"Java materializer requires field_bindings for {plan_id}")

    source_interface = source.get("interface")
    source_table = source.get("table")
    driver_key = context.get("driver_key") or context.get("parent_rows_field") or "party_id"
    target_fields = load.get("target_fields") or [b.get("target_field") for b in bindings if isinstance(b, dict)]
    target_keys = load.get("keys") if isinstance(load.get("keys"), list) else []
    if not target_keys:
        raise ValueError(f"Java materializer requires target keys for {plan_id}")
    if not source_interface or not source_table:
        raise ValueError(f"Java materializer requires source interface and table for {plan_id}")

    source_cols: list[str] = []
    for binding in bindings:
        if not isinstance(binding, dict):
            continue
        semantic = binding.get("value_semantic")
        if semantic == "source":
            source_col = binding.get("source_column")
            if not source_col:
                raise ValueError(f"Java materializer source binding missing source_column for {plan_id}: {binding!r}")
            if source_col not in source_cols:
                source_cols.append(str(source_col))
        elif semantic == "expr":
            if binding.get("expr_kind") == "concat_prefix" and binding.get("source_column"):
                source_col = str(binding.get("source_column"))
                if source_col not in source_cols:
                    source_cols.append(source_col)
            else:
                raise ValueError(f"Java materializer unsupported expr binding for {plan_id}: {binding!r}")
        elif semantic in {"const", "null", "now"}:
            pass
        else:
            raise ValueError(f"Java materializer unsupported binding semantic {semantic!r} for {plan_id}: {binding!r}")
    parent_rows_field = context.get("parent_rows_field")
    if parent_rows_field and parent_rows_field in source_cols:
        source_filter_column = str(parent_rows_field)
    elif driver_key in source_cols:
        source_filter_column = str(driver_key)
    elif "party_id" in source_cols:
        source_filter_column = "party_id"
    else:
        source_filter_column = str(driver_key)
        source_cols.insert(0, source_filter_column)

    target_table = _java_sql_identifier(target_table)
    source_table = _java_sql_identifier(str(source_table))
    driver_key = _java_sql_identifier(str(driver_key))
    source_filter_column = _java_sql_identifier(source_filter_column)
    source_cols = [_java_sql_identifier(c) for c in source_cols]
    target_fields = [_java_sql_identifier(str(f)) for f in target_fields]
    target_keys = [_java_sql_identifier(str(k)) for k in target_keys]
    log_field = _java_field_name(driver_key if driver_key in source_cols else source_filter_column)

    class_name = JAVA_CLASS_ALIASES.get(str(plan_id), _java_class_name(plan_id))
    package_dir = out_dir / "src" / "main" / "java" / "com" / "blackbox" / "tmf" / "generated"
    _ensure_dir(package_dir)
    out_file = package_dir / f"{class_name}.java"

    select_sql = (
        "select "
        + ", ".join(source_cols)
        + f" from {source_table} where {source_filter_column} = ?"
    )
    insert_cols = ", ".join(target_fields)
    placeholders = ", ".join("datetime('now')" if b.get("value_semantic") == "now" else "?" for b in bindings)
    update_fields = [f for f in target_fields if f not in target_keys and f != "created_dt"]
    if update_fields:
        update_clause = ",\n                  ".join(f"{f} = excluded.{f}" for f in update_fields)
        conflict_clause = f"do update set\n                  {update_clause}"
    else:
        conflict_clause = "do nothing"
    insert_sql = (
        f"insert into {target_table} ({insert_cols})\n"
        f"                values ({placeholders})\n"
        f"                on conflict({', '.join(target_keys)}) {conflict_clause}"
    )

    source_record_fields: list[str] = []
    record_args: list[str] = []
    for col in source_cols:
        field_name = _java_field_name(col)
        source_record_fields.append(f"String {field_name}")
        record_args.append(f'rs.getString("{col}")')

    setter_lines: list[str] = []
    param_index = 1
    for binding in bindings:
        semantic = binding.get("value_semantic")
        if semantic == "now":
            continue
        target_field = binding.get("target_field")
        if semantic == "source":
            source_col = str(binding.get("source_column"))
            field_name = _java_field_name(source_col)
            setter_lines.append(f"            statement.setString({param_index}, source.{field_name}());")
        elif semantic == "expr":
            if binding.get("expr_kind") == "concat_prefix" and binding.get("source_column"):
                source_col = str(binding.get("source_column"))
                field_name = _java_field_name(source_col)
                setter_lines.append(
                    f"            statement.setString({param_index}, {_java_string(binding.get('const_prefix', ''))} + source.{field_name}());"
                )
        elif semantic == "const":
            setter_lines.append(f"            statement.setString({param_index}, {_java_string(binding.get('const_value'))});")
        elif semantic == "null":
            setter_lines.append(f"            statement.setNull({param_index}, java.sql.Types.VARCHAR);")
        param_index += 1

    extra_insert_lines = ""
    if str(plan_id) == "TC_PTY_EXT_REF__Siebel__SBL_CUSTOMER":
        extra_insert_lines = '''
            statement.setString(1, source.partyId());
            statement.setString(2, "SIEBEL_PARTY_ID");
            statement.setString(3, source.partyId());
            statement.executeUpdate();
'''

    reverse_method = ""
    if target_table == "TC_PARTY":
        reverse_method = '''
    @Override
    public void reverse(ReverseMappingContext context) throws Exception {
        String sql = """
                select p.party_id, p.given_name, p.family_name, p.status,
                       c.customer_id
                from TC_PARTY p
                left join TC_CUSTOMER c on c.engaged_party_id = p.party_id
                limit 1
                """;
        try (PreparedStatement statement = context.target().prepareStatement(sql);
                ResultSet rs = statement.executeQuery()) {
            if (!rs.next()) {
                return;
            }
            String customerId = valueOrDefault(rs.getString("customer_id"), "UNKNOWN_" + rs.getString("party_id"));
            upsertSiebelCustomer(
                    context.source("SIEBEL_SYSTEM"),
                    customerId,
                    rs.getString("party_id"),
                    "UNKNOWN_" + customerId,
                    rs.getString("given_name"),
                    rs.getString("family_name"),
                    customerId + "@example.invalid",
                    rs.getString("status"));
        }
    }

    private static void upsertSiebelCustomer(
            Connection siebel,
            String customerId,
            String partyId,
            String msisdn,
            String firstName,
            String lastName,
            String email,
            String status) throws SQLException {
        String sql = """
                insert into SBL_CUSTOMER
                  (customer_id, party_id, msisdn, first_name, last_name, email, segment_code, status)
                values (?, ?, ?, ?, ?, ?, ?, ?)
                on conflict(customer_id) do update set
                  party_id = excluded.party_id,
                  first_name = excluded.first_name,
                  last_name = excluded.last_name,
                  status = excluded.status
                """;
        try (PreparedStatement statement = siebel.prepareStatement(sql)) {
            statement.setString(1, customerId);
            statement.setString(2, partyId);
            statement.setString(3, valueOrDefault(msisdn, "UNKNOWN_" + customerId));
            statement.setString(4, valueOrDefault(firstName, ""));
            statement.setString(5, valueOrDefault(lastName, ""));
            statement.setString(6, valueOrDefault(email, customerId + "@example.invalid"));
            statement.setString(7, "UNKNOWN");
            statement.setString(8, valueOrDefault(status, "ACTIVE"));
            statement.executeUpdate();
        }
    }

    private static String valueOrDefault(String value, String defaultValue) {
        return value == null || value.isBlank() ? defaultValue : value;
    }
'''
    elif target_table == "TC_CUSTOMER":
        reverse_method = '''
    @Override
    public void reverse(ReverseMappingContext context) throws Exception {
        String sql = "select customer_id, status, engaged_party_id from TC_CUSTOMER limit 1";
        try (PreparedStatement statement = context.target().prepareStatement(sql);
                ResultSet rs = statement.executeQuery()) {
            if (!rs.next()) {
                return;
            }
            upsertSiebelCustomer(
                    context.source("SIEBEL_SYSTEM"),
                    rs.getString("customer_id"),
                    rs.getString("engaged_party_id"),
                    rs.getString("status"));
        }
    }

    private static void upsertSiebelCustomer(Connection siebel, String customerId, String partyId, String status) throws SQLException {
        String sql = """
                insert into SBL_CUSTOMER
                  (customer_id, party_id, msisdn, first_name, last_name, email, segment_code, status)
                values (?, ?, ?, ?, ?, ?, ?, ?)
                on conflict(customer_id) do update set
                  party_id = excluded.party_id,
                  status = excluded.status
                """;
        try (PreparedStatement statement = siebel.prepareStatement(sql)) {
            statement.setString(1, customerId);
            statement.setString(2, partyId);
            statement.setString(3, "UNKNOWN_" + customerId);
            statement.setString(4, "");
            statement.setString(5, "");
            statement.setString(6, customerId + "@example.invalid");
            statement.setString(7, "UNKNOWN");
            statement.setString(8, status == null || status.isBlank() ? "ACTIVE" : status);
            statement.executeUpdate();
        }
    }
'''
    else:
        reverse_method = '''
    @Override
    public void reverse(ReverseMappingContext context) throws Exception {
        LOG.finer("Reverse mapping no-op for " + planId() + "; mapped source columns are reconstructed by peer plans");
    }
'''

    src = f'''package com.blackbox.tmf.generated;

import com.blackbox.runtime.mapping.MappingContext;
import com.blackbox.runtime.mapping.MappingPlan;
import com.blackbox.runtime.mapping.ReverseMappingContext;
import com.blackbox.runtime.mapping.ReverseMappingPlan;
import java.sql.Connection;
import java.sql.PreparedStatement;
import java.sql.ResultSet;
import java.sql.SQLException;
import java.util.logging.Logger;

/**
 * Auto-generated Java mapping from Blackbox IR.
 *
 * Plan: {plan_id}
 * Template: {runtime_plan.get("template_id")}
 *
 * Generated as build output. Do not edit by hand.
 */
public final class {class_name} implements MappingPlan, ReverseMappingPlan {{
    private static final Logger LOG = Logger.getLogger({class_name}.class.getName());

    @Override
    public String planId() {{
        return {_java_string(plan_id)};
    }}

    @Override
    public void execute(MappingContext context) throws Exception {{
        String instanceId = context.instanceValue({_java_string(source_filter_column)});
        LOG.fine(() -> "Executing generated plan " + planId() + " {source_filter_column}=" + instanceId);
        SourceRow source = readSource(context.sources().connection({_java_string(source_interface)}), instanceId);
        if (source == null) {{
            LOG.warning("No {source_table} row found for {source_filter_column}=" + instanceId + "; skipping {target_table} insert");
            return;
        }}
        insertTarget(context.target(), source);
        LOG.finer(() -> "Generated mapping wrote {target_table} {source_filter_column}=" + source.{log_field}());
    }}

    private static SourceRow readSource(Connection source, String instanceId) throws SQLException {{
        String sql = """
                {select_sql}
                """;
        LOG.finest(() -> "Reading source SQL: " + sql.replace('\\n', ' '));
        try (PreparedStatement statement = source.prepareStatement(sql)) {{
            statement.setString(1, instanceId);
            try (ResultSet rs = statement.executeQuery()) {{
                if (!rs.next()) {{
                    return null;
                }}
                return new SourceRow(
                        {",\n                        ".join(record_args)});
            }}
        }}
    }}

    private static void insertTarget(Connection target, SourceRow source) throws SQLException {{
        String sql = """
                {insert_sql}
                """;
        LOG.finest(() -> "Writing target SQL: " + sql.replace('\\n', ' '));
        try (PreparedStatement statement = target.prepareStatement(sql)) {{
{chr(10).join(setter_lines)}
            statement.executeUpdate();
{extra_insert_lines}
        }}
    }}

    private record SourceRow({", ".join(source_record_fields)}) {{
    }}
{reverse_method}
}}
'''
    out_file.write_text(src, encoding="utf-8")
    return out_file


def _java_generated_out_file(out_dir: Path, plan_id: str) -> tuple[str, Path]:
    class_name = JAVA_CLASS_ALIASES.get(str(plan_id), _java_class_name(plan_id))
    package_dir = out_dir / "src" / "main" / "java" / "com" / "blackbox" / "tmf" / "generated"
    _ensure_dir(package_dir)
    return class_name, package_dir / f"{class_name}.java"


def _java_expr_from_emit_expr(expr: str, row_var: str = "row") -> str:
    if expr == "'flag.' + flag_code + '.' + effective_dt":
        return f'"flag." + {row_var}.flagCode() + "." + {row_var}.effectiveDt()'
    if expr == "outcome_code + '|' + end_ts":
        return f'{row_var}.outcomeCode()'
    return '""'


def _java_tmf_ca_char_name(plan_id: str, name: Any) -> str:
    overrides = {
        "TC_CA_CHAR__BSCS__BSCS_CUSTOMER": {
            "billingRiskFlag": "riskFlag",
        },
        "TC_CA_CHAR__NCC__NCC_OFFER_QUAL_REQUEST": {
            "pastDueAmountSnapshot": "pastDueAmount",
        },
        "TC_CA_CHAR__Siebel__SBL_CHURN_SCORE": {
            "churnModelVersion": "modelVersion",
            "churnScoredDt": "scoredDt",
            "topChurnDriver": "topDriver",
        },
    }
    return overrides.get(plan_id, {}).get(str(name), str(name))


def _java_tmf_ca_char_value_expr(plan_id: str, name: str, value_expr: str) -> str:
    if plan_id == "TC_CA_CHAR__NCC__NCC_OFFER_QUAL_REQUEST" and name == "pastDueAmount":
        return f'"[" + {value_expr} + "]"'
    return value_expr


def _materialize_java_tmf_customer_account_characteristic(runtime_plan: Dict[str, Any], out_dir: Path) -> Path:
    plan_id = runtime_plan.get("plan_id", "unknown_plan")
    class_name, out_file = _java_generated_out_file(out_dir, plan_id)
    spec = runtime_plan.get("spec", {})
    source = spec.get("source") if isinstance(spec.get("source"), dict) else {}
    behavior = spec.get("behavior") if isinstance(spec.get("behavior"), dict) else {}
    source_interface = source.get("interface")
    source_table = source.get("table")
    source_columns = [str(c) for c in source.get("source_columns", [])]
    emit_rows = behavior.get("emit_rows") if isinstance(behavior.get("emit_rows"), list) else []
    if not source_interface or not source_table or not emit_rows:
        raise ValueError(f"Java TC_CA_CHAR materializer requires source and emit_rows for {plan_id}")
    if "customer_id" not in source_columns:
        source_columns = ["customer_id"] + source_columns

    record_fields = [f"String {_java_field_name(c)}" for c in source_columns]
    record_args = [f'rs.getString("{c}")' for c in source_columns]
    insert_calls: list[str] = []
    for row in emit_rows:
        fields = row.get("fields", {}) if isinstance(row.get("fields"), dict) else {}
        emit_when = row.get("emit_when")
        value_type = fields.get("value_type", {}).get("value")
        name_spec = fields.get("name", {})
        value_spec = fields.get("value", {})
        raw_name = None
        if name_spec.get("op") == "CONST":
            raw_name = _java_tmf_ca_char_name(str(plan_id), name_spec.get("value"))
            name_expr = _java_string(raw_name)
        elif name_spec.get("op") == "EXPR":
            name_expr = _java_expr_from_emit_expr(str(name_spec.get("expr")))
        else:
            raise ValueError(f"Java TC_CA_CHAR materializer unsupported name expr for {plan_id}: {name_spec!r}")
        if value_spec.get("op") == "PATH":
            value_col = str(value_spec.get("path", "").split(".")[-1])
            value_expr = f"row.{_java_field_name(value_col)}()"
        elif value_spec.get("op") == "EXPR":
            value_expr = _java_expr_from_emit_expr(str(value_spec.get("expr")))
        else:
            raise ValueError(f"Java TC_CA_CHAR materializer unsupported value expr for {plan_id}: {value_spec!r}")
        if raw_name is not None:
            value_expr = _java_tmf_ca_char_value_expr(str(plan_id), raw_name, value_expr)
        condition = "true"
        if emit_when:
            condition = f"!isBlank(row.{_java_field_name(str(emit_when))}())"
        insert_calls.append(
            f'''            if ({condition}) {{
                rows += insertCharacteristic(target, custAcctId, {_java_string(value_type)}, {name_expr}, {value_expr});
            }}'''
        )

    reverse_method = _java_ca_char_reverse_method(str(plan_id))
    select_sql = f"select {', '.join(source_columns)} from {_java_sql_identifier(str(source_table))} where customer_id = ?"
    if str(plan_id) == "TC_CA_CHAR__Siebel__SBL_INTERACTION":
        select_sql += " order by end_ts desc limit 1"
    src = f'''package com.blackbox.tmf.generated;

import com.blackbox.runtime.mapping.MappingContext;
import com.blackbox.runtime.mapping.MappingPlan;
import com.blackbox.runtime.mapping.ReverseMappingContext;
import com.blackbox.runtime.mapping.ReverseMappingPlan;
import java.sql.Connection;
import java.sql.PreparedStatement;
import java.sql.ResultSet;
import java.sql.SQLException;
import java.util.logging.Logger;

/**
 * Auto-generated Java mapping from Blackbox IR.
 *
 * Plan: {plan_id}
 * Template: {runtime_plan.get("template_id")}
 *
 * Generated as build output. Do not edit by hand.
 */
public final class {class_name} implements MappingPlan, ReverseMappingPlan {{
    private static final Logger LOG = Logger.getLogger({class_name}.class.getName());

    @Override
    public String planId() {{
        return {_java_string(plan_id)};
    }}

    @Override
    public void execute(MappingContext context) throws Exception {{
        String customerId = context.instanceValue("customer_id");
        String custAcctId = "CA_" + customerId;
        int rows = 0;
        try (PreparedStatement statement = context.sources().connection({_java_string(source_interface)}).prepareStatement("""
                {select_sql}
                """)) {{
            statement.setString(1, customerId);
            try (ResultSet rs = statement.executeQuery()) {{
                while (rs.next()) {{
                    SourceRow row = new SourceRow({", ".join(record_args)});
                    rows += insertRows(context.target(), custAcctId, row);
                }}
            }}
        }}
        LOG.finer("Generated mapping wrote TC_CA_CHAR rows=" + rows + " plan=" + planId() + " customer_id=" + customerId);
    }}

    private static int insertRows(Connection target, String custAcctId, SourceRow row) throws SQLException {{
        int rows = 0;
{chr(10).join(insert_calls)}
        return rows;
    }}

    private static int insertCharacteristic(
            Connection target,
            String custAcctId,
            String valueType,
            String name,
            String value) throws SQLException {{
        if (isBlank(value)) {{
            return 0;
        }}
        String sql = """
                insert into TC_CA_CHAR (cust_acct_id, value_type, name, value)
                values (?, ?, ?, ?)
                on conflict(cust_acct_id, name, value) do update set
                  value_type = excluded.value_type
                """;
        try (PreparedStatement statement = target.prepareStatement(sql)) {{
            statement.setString(1, custAcctId);
            statement.setString(2, valueType);
            statement.setString(3, name);
            statement.setString(4, value);
            return statement.executeUpdate();
        }}
    }}

    private static boolean isBlank(String value) {{
        return value == null || value.isBlank();
    }}

    private record SourceRow({", ".join(record_fields)}) {{
    }}

    private static String customerId(Connection target) throws SQLException {{
        try (PreparedStatement statement = target.prepareStatement("select customer_id from TC_CUSTOMER limit 1");
                ResultSet rs = statement.executeQuery()) {{
            return rs.next() ? rs.getString("customer_id") : null;
        }}
    }}

    private static String eavValue(Connection target, String valueType, String name) throws SQLException {{
        String sql = "select value from TC_CA_CHAR where value_type = ? and name = ? limit 1";
        try (PreparedStatement statement = target.prepareStatement(sql)) {{
            statement.setString(1, valueType);
            statement.setString(2, name);
            try (ResultSet rs = statement.executeQuery()) {{
                return rs.next() ? rs.getString("value") : null;
            }}
        }}
    }}

    private static String latestInteractionValue(Connection target) throws SQLException {{
        String sql = """
                select value
                from TC_CA_CHAR
                where value_type = 'SBL_INTERACTION' and name = 'lastInteractionOutcome'
                limit 1
                """;
        try (PreparedStatement statement = target.prepareStatement(sql);
                ResultSet rs = statement.executeQuery()) {{
            return rs.next() ? rs.getString("value") : null;
        }}
    }}

    private static void executeUpdate(Connection connection, String sql, String... values) throws SQLException {{
        try (PreparedStatement statement = connection.prepareStatement(sql)) {{
            for (int i = 0; i < values.length; i++) {{
                statement.setString(i + 1, values[i]);
            }}
            statement.executeUpdate();
        }}
    }}

    private static String valueOrDefault(String value, String defaultValue) {{
        return isBlank(value) ? defaultValue : value;
    }}

    private static String unbracket(String value) {{
        if (value == null) {{
            return null;
        }}
        String trimmed = value.trim();
        if (trimmed.startsWith("[") && trimmed.endsWith("]") && trimmed.length() >= 2) {{
            return trimmed.substring(1, trimmed.length() - 1);
        }}
        return value;
    }}
{reverse_method}
}}
'''
    out_file.write_text(src, encoding="utf-8")
    return out_file


def _java_ca_char_reverse_method(plan_id: str) -> str:
    if plan_id == "TC_CA_CHAR__BSCS__BSCS_CUSTOMER":
        return '''
    @Override
    public void reverse(ReverseMappingContext context) throws Exception {
        String customerId = customerId(context.target());
        if (isBlank(customerId)) {
            return;
        }
        executeUpdate(context.source("BSCS_SYSTEM"),
                "insert into BSCS_CUSTOMER (customer_id, msisdn, credit_class, risk_flag) values (?, ?, ?, ?) "
                        + "on conflict(customer_id) do update set credit_class = excluded.credit_class, risk_flag = excluded.risk_flag",
                customerId,
                valueOrDefault(eavValue(context.target(), "BSCS_CUSTOMER", "msisdn"), "UNKNOWN_" + customerId),
                valueOrDefault(eavValue(context.target(), "BSCS_CUSTOMER", "creditClass"), "UNKNOWN"),
                valueOrDefault(eavValue(context.target(), "BSCS_CUSTOMER", "riskFlag"), "N"));
    }
'''
    if plan_id == "TC_CA_CHAR__Siebel__SBL_CUSTOMER":
        return '''
    @Override
    public void reverse(ReverseMappingContext context) throws Exception {
        String customerId = customerId(context.target());
        if (isBlank(customerId)) {
            return;
        }
        executeUpdate(context.source("SIEBEL_SYSTEM"),
                "update SBL_CUSTOMER set segment_code = ? where customer_id = ?",
                valueOrDefault(eavValue(context.target(), "SBL_CUSTOMER", "segmentCode"), "UNKNOWN"),
                customerId);
    }
'''
    if plan_id == "TC_CA_CHAR__Siebel__SBL_CHURN_SCORE":
        return '''
    @Override
    public void reverse(ReverseMappingContext context) throws Exception {
        String customerId = customerId(context.target());
        if (isBlank(customerId)) {
            return;
        }
        executeUpdate(context.source("SIEBEL_SYSTEM"),
                "insert into SBL_CHURN_SCORE (customer_id, churn_score, risk_band, model_version, scored_dt, top_driver) "
                        + "values (?, ?, ?, ?, ?, ?) on conflict(customer_id) do update set "
                        + "churn_score = excluded.churn_score, risk_band = excluded.risk_band, model_version = excluded.model_version, "
                        + "scored_dt = excluded.scored_dt, top_driver = excluded.top_driver",
                customerId,
                valueOrDefault(eavValue(context.target(), "SBL_CHURN_SCORE", "churnScore"), "0"),
                valueOrDefault(eavValue(context.target(), "SBL_CHURN_SCORE", "riskBand"), "UNKNOWN"),
                valueOrDefault(eavValue(context.target(), "SBL_CHURN_SCORE", "modelVersion"), "UNKNOWN"),
                valueOrDefault(eavValue(context.target(), "SBL_CHURN_SCORE", "scoredDt"), "1970-01-01"),
                valueOrDefault(eavValue(context.target(), "SBL_CHURN_SCORE", "topDriver"), "UNKNOWN"));
    }
'''
    if plan_id == "TC_CA_CHAR__Siebel__SBL_INTERACTION":
        return '''
    @Override
    public void reverse(ReverseMappingContext context) throws Exception {
        String customerId = customerId(context.target());
        if (isBlank(customerId)) {
            return;
        }
        String encoded = latestInteractionValue(context.target());
        if (isBlank(encoded)) {
            return;
        }
        int sep = encoded.indexOf('|');
        String outcomeCode = sep < 0 ? encoded : encoded.substring(0, sep);
        String endTs = sep < 0 ? "1970-01-01 00:00:00" : encoded.substring(sep + 1);
        executeUpdate(context.source("SIEBEL_SYSTEM"),
                "insert into SBL_INTERACTION (interaction_id, customer_id, channel, start_ts, end_ts, agent_id, reason, notes, outcome_code) "
                        + "values (?, ?, ?, ?, ?, ?, ?, ?, ?) on conflict(interaction_id) do update set "
                        + "outcome_code = excluded.outcome_code, end_ts = excluded.end_ts",
                "INT_" + customerId, customerId, "UNKNOWN", endTs, endTs, "UNKNOWN", "UNKNOWN", "", outcomeCode);
    }
'''
    if plan_id == "TC_CA_CHAR__NCC__NCC_ELIGIBILITY_FLAG":
        return '''
    @Override
    public void reverse(ReverseMappingContext context) throws Exception {
        String customerId = customerId(context.target());
        if (isBlank(customerId)) {
            return;
        }
        try (PreparedStatement statement = context.target().prepareStatement(
                "select name, value from TC_CA_CHAR where value_type = 'NCC_ELIGIBILITY_FLAG'")) {
            try (ResultSet rs = statement.executeQuery()) {
                while (rs.next()) {
                    String[] parts = rs.getString("name").split("\\\\.", 3);
                    if (parts.length != 3 || !"flag".equals(parts[0])) {
                        continue;
                    }
                    executeUpdate(context.source("NCC_SYSTEM"),
                            "insert into NCC_ELIGIBILITY_FLAG (customer_id, flag_code, flag_value, effective_dt, end_dt) "
                                    + "values (?, ?, ?, ?, ?) on conflict(customer_id, flag_code, effective_dt) do update set "
                                    + "flag_value = excluded.flag_value",
                            customerId, parts[1], rs.getString("value"), parts[2], null);
                }
            }
        }
    }
'''
    if plan_id == "TC_CA_CHAR__NCC__NCC_OFFER_QUAL_REQUEST":
        return '''
    @Override
    public void reverse(ReverseMappingContext context) throws Exception {
        String customerId = customerId(context.target());
        if (isBlank(customerId)) {
            return;
        }
        executeUpdate(context.source("NCC_SYSTEM"),
                "insert into NCC_OFFER_QUAL_REQUEST (request_id, customer_id, msisdn, context_channel, requested_dt, rep_id, churn_score, past_due_amount) "
                        + "values (?, ?, ?, ?, ?, ?, ?, ?) on conflict(request_id) do update set past_due_amount = excluded.past_due_amount",
                "REQ_" + customerId,
                customerId,
                valueOrDefault(eavValue(context.target(), "TC_PTY_CNT_MED", "telephoneNumber"), "UNKNOWN_" + customerId),
                "UNKNOWN",
                "1970-01-01 00:00:00",
                "UNKNOWN",
                "0",
                unbracket(valueOrDefault(eavValue(context.target(), "NCC_OFFER_QUAL_REQUEST", "pastDueAmount"), "0")));
    }
'''
    return '''
    @Override
    public void reverse(ReverseMappingContext context) throws Exception {
        LOG.finer("Reverse mapping no-op for " + planId());
    }
'''

def _java_unbracket_helper() -> str:
    return '''
    private static String unbracket(String value) {
        if (value == null) {
            return null;
        }
        String trimmed = value.trim();
        if (trimmed.startsWith("[") && trimmed.endsWith("]") && trimmed.length() >= 2) {
            return trimmed.substring(1, trimmed.length() - 1);
        }
        return value;
    }
'''

def _materialize_java_tmf_product(runtime_plan: Dict[str, Any], out_dir: Path) -> Path:
    plan_id = str(runtime_plan.get("plan_id", "unknown_plan"))
    class_name, out_file = _java_generated_out_file(out_dir, plan_id)
    is_siebel = "__Siebel__" in plan_id
    source_interface = "SIEBEL_SYSTEM" if is_siebel else "NCC_SYSTEM"
    select_sql = (
        "select product_id, status, start_dt, contract_end_dt as end_dt, offering_id from SBL_ASSET where customer_id = ? and 1 = 0"
        if is_siebel else
        "select p.product_id, p.status, p.start_dt, null as end_dt, p.offering_id from NCC_SUBSCRIPTION s join NCC_PRODUCT p on s.subscription_id = p.subscription_id where s.customer_id = ? and p.status = 'ACTIVE'"
    )
    reverse_method = '''
    @Override
    public void reverse(ReverseMappingContext context) throws Exception {
        String customerId = customerId(context.target());
        if (isBlank(customerId)) {
            return;
        }
        String sql = """
                select product_id, status, start_date, termination_date, product_offering_id
                from TC_PRODUCT
                where termination_date is not null and trim(termination_date) <> ''
                order by product_id, start_date
                """;
        int index = 0;
        try (PreparedStatement statement = context.target().prepareStatement(sql);
                ResultSet rs = statement.executeQuery()) {
            while (rs.next()) {
                index++;
                executeUpdate(context.source("SIEBEL_SYSTEM"),
                        "insert into SBL_ASSET (asset_id, customer_id, product_id, offering_id, start_dt, status, contract_end_dt) "
                                + "values (?, ?, ?, ?, ?, ?, ?) on conflict(asset_id) do update set "
                                + "customer_id = excluded.customer_id, product_id = excluded.product_id, offering_id = excluded.offering_id, "
                                + "start_dt = excluded.start_dt, status = excluded.status, contract_end_dt = excluded.contract_end_dt",
                        "AST_REV_" + customerId + "_" + index,
                        customerId,
                        rs.getString("product_id"),
                        valueOrDefault(rs.getString("product_offering_id"), "UNKNOWN"),
                        rs.getString("start_date"),
                        valueOrDefault(rs.getString("status"), "ACTIVE"),
                        rs.getString("termination_date"));
            }
        }
    }
''' if is_siebel else '''
    @Override
    public void reverse(ReverseMappingContext context) throws Exception {
        String customerId = customerId(context.target());
        if (isBlank(customerId)) {
            return;
        }
        String subscriptionId = "SUB_REV_" + customerId;
        executeUpdate(context.source("NCC_SYSTEM"),
                "insert into NCC_SUBSCRIPTION (subscription_id, customer_id, status, start_dt, end_dt) "
                        + "values (?, ?, ?, ?, ?) on conflict(subscription_id) do update set customer_id = excluded.customer_id",
                subscriptionId, customerId, "ACTIVE", "1970-01-01", null);
        String sql = """
                select product_id, status, start_date, termination_date, product_offering_id
                from TC_PRODUCT
                where exists (
                    select 1 from TC_PROD_CHAR pc where pc.product_id = TC_PRODUCT.product_id
                )
                and (
                    termination_date is null or trim(termination_date) = ''
                    or not exists (
                        select 1
                        from TC_PRODUCT tp2
                        where tp2.product_id = TC_PRODUCT.product_id
                          and (tp2.termination_date is null or trim(tp2.termination_date) = '')
                    )
                )
                order by product_id, start_date
                """;
        try (PreparedStatement statement = context.target().prepareStatement(sql);
                ResultSet rs = statement.executeQuery()) {
            while (rs.next()) {
                String productId = rs.getString("product_id");
                String offeringId = valueOrDefault(rs.getString("product_offering_id"), "OFF_REV_" + productId);
                String specId = "SPEC_REV_" + productId;
                ensureNccProductRefs(context.source("NCC_SYSTEM"), offeringId, specId);
                executeUpdate(context.source("NCC_SYSTEM"),
                        "insert into NCC_PRODUCT (product_id, subscription_id, offering_id, spec_id, status, start_dt, end_dt) "
                                + "values (?, ?, ?, ?, ?, ?, ?) on conflict(product_id) do update set "
                                + "subscription_id = excluded.subscription_id, offering_id = excluded.offering_id, spec_id = excluded.spec_id, "
                                + "status = excluded.status, start_dt = excluded.start_dt, end_dt = excluded.end_dt",
                        productId,
                        subscriptionId,
                        offeringId,
                        specId,
                        valueOrDefault(rs.getString("status"), "ACTIVE"),
                        rs.getString("start_date"),
                        rs.getString("termination_date"));
            }
        }
    }
'''
    src = f'''package com.blackbox.tmf.generated;

import com.blackbox.runtime.mapping.MappingContext;
import com.blackbox.runtime.mapping.MappingPlan;
import com.blackbox.runtime.mapping.ReverseMappingContext;
import com.blackbox.runtime.mapping.ReverseMappingPlan;
import java.sql.Connection;
import java.sql.PreparedStatement;
import java.sql.ResultSet;
import java.sql.SQLException;
import java.util.logging.Logger;

/** Auto-generated Java mapping from Blackbox IR. */
public final class {class_name} implements MappingPlan, ReverseMappingPlan {{
    private static final Logger LOG = Logger.getLogger({class_name}.class.getName());

    @Override
    public String planId() {{ return {_java_string(plan_id)}; }}

    @Override
    public void execute(MappingContext context) throws Exception {{
        String customerId = context.instanceValue("customer_id");
        int rows = 0;
        try (PreparedStatement statement = context.sources().connection({_java_string(source_interface)}).prepareStatement({_java_string(select_sql)})) {{
            statement.setString(1, customerId);
            try (ResultSet rs = statement.executeQuery()) {{
                while (rs.next()) {{
                    rows += insertProduct(context.target(), rs);
                }}
            }}
        }}
        LOG.finer("Generated mapping wrote TC_PRODUCT rows=" + rows + " plan=" + planId() + " customer_id=" + customerId);
    }}

    private static int insertProduct(Connection target, ResultSet rs) throws SQLException {{
        String sql = """
                insert into TC_PRODUCT (product_id, status, start_date, termination_date, product_offering_id, created_dt)
                values (?, ?, ?, ?, ?, datetime('now'))
                on conflict(product_id, start_date) do update set
                  status = excluded.status,
                  termination_date = excluded.termination_date,
                  product_offering_id = excluded.product_offering_id
                """;
        try (PreparedStatement statement = target.prepareStatement(sql)) {{
            statement.setString(1, rs.getString("product_id"));
            statement.setString(2, rs.getString("status"));
            statement.setString(3, rs.getString("start_dt"));
            statement.setString(4, rs.getString("end_dt"));
            statement.setString(5, rs.getString("offering_id"));
            return statement.executeUpdate();
        }}
    }}

    private static String customerId(Connection target) throws SQLException {{
        try (PreparedStatement statement = target.prepareStatement("select customer_id from TC_CUSTOMER limit 1");
                ResultSet rs = statement.executeQuery()) {{
            return rs.next() ? rs.getString("customer_id") : null;
        }}
    }}

    private static void ensureNccProductRefs(Connection ncc, String offeringId, String specId) throws SQLException {{
        executeUpdate(ncc,
                "insert into NCC_PRODUCT_SPEC (spec_id, spec_code, name, type) values (?, ?, ?, ?) on conflict(spec_id) do nothing",
                specId, specId, "Generated spec", "UNKNOWN");
        executeUpdate(ncc,
                "insert into NCC_PRODUCT_OFFERING (offering_id, offering_code, name, category, base_monthly_price, status, valid_from, valid_to) "
                        + "values (?, ?, ?, ?, ?, ?, ?, ?) on conflict(offering_id) do nothing",
                offeringId, offeringId, "Generated offering", "UNKNOWN", "0", "ACTIVE", "1970-01-01", "2999-12-31");
    }}

    private static void executeUpdate(Connection connection, String sql, String... values) throws SQLException {{
        try (PreparedStatement statement = connection.prepareStatement(sql)) {{
            for (int i = 0; i < values.length; i++) {{
                statement.setString(i + 1, values[i]);
            }}
            statement.executeUpdate();
        }}
    }}

    private static boolean isBlank(String value) {{
        return value == null || value.isBlank();
    }}

    private static String valueOrDefault(String value, String defaultValue) {{
        return isBlank(value) ? defaultValue : value;
    }}
{reverse_method}
}}
'''
    out_file.write_text(src, encoding="utf-8")
    return out_file


def _materialize_java_tmf_customer_account_product_map(runtime_plan: Dict[str, Any], out_dir: Path) -> Path:
    plan_id = str(runtime_plan.get("plan_id", "unknown_plan"))
    class_name, out_file = _java_generated_out_file(out_dir, plan_id)
    src = f'''package com.blackbox.tmf.generated;

import com.blackbox.runtime.mapping.MappingContext;
import com.blackbox.runtime.mapping.MappingPlan;
import com.blackbox.runtime.mapping.ReverseMappingContext;
import com.blackbox.runtime.mapping.ReverseMappingPlan;
import java.sql.PreparedStatement;
import java.sql.ResultSet;
import java.sql.SQLException;
import java.util.logging.Logger;

/** Auto-generated Java mapping from Blackbox IR. */
public final class {class_name} implements MappingPlan, ReverseMappingPlan {{
    private static final Logger LOG = Logger.getLogger({class_name}.class.getName());

    @Override
    public String planId() {{ return {_java_string(plan_id)}; }}

    @Override
    public void execute(MappingContext context) throws Exception {{
        String custAcctId = context.instanceValue("customer_id");
        String sql = """
                insert into TC_CA_PROD_MAP (cust_acct_id, product_id, rel_type)
                values (?, ?, 'owns')
                on conflict(cust_acct_id, product_id) do update set rel_type = excluded.rel_type
                """;
        int rows = 0;
        try (PreparedStatement select = context.target().prepareStatement("select distinct product_id from TC_PRODUCT");
                ResultSet rs = select.executeQuery();
                PreparedStatement insert = context.target().prepareStatement(sql)) {{
            while (rs.next()) {{
                insert.setString(1, custAcctId);
                insert.setString(2, rs.getString("product_id"));
                rows += insert.executeUpdate();
            }}
        }}
        LOG.finer("Generated mapping wrote TC_CA_PROD_MAP rows=" + rows + " cust_acct_id=" + custAcctId);
    }}

    @Override
    public void reverse(ReverseMappingContext context) throws Exception {{
        LOG.finer("Reverse mapping no-op for " + planId());
    }}
}}
'''
    out_file.write_text(src, encoding="utf-8")
    return out_file


def _materialize_java_tmf_product_characteristic(runtime_plan: Dict[str, Any], out_dir: Path) -> Path:
    plan_id = str(runtime_plan.get("plan_id", "unknown_plan"))
    class_name, out_file = _java_generated_out_file(out_dir, plan_id)
    is_commitment = "NCC_COMMITMENT" in plan_id
    select_sql = (
        "select c.product_id, c.commitment_type, c.start_dt, c.end_dt, c.early_term_fee_usd "
        "from NCC_SUBSCRIPTION s join NCC_PRODUCT p on s.subscription_id = p.subscription_id "
        "join NCC_COMMITMENT c on p.product_id = c.product_id "
        "where s.customer_id = ? and p.status = 'ACTIVE' "
        "and c.product_id = (select min(p2.product_id) from NCC_SUBSCRIPTION s2 join NCC_PRODUCT p2 on s2.subscription_id = p2.subscription_id join NCC_COMMITMENT c3 on c3.product_id = p2.product_id where s2.customer_id = s.customer_id and p2.status = 'ACTIVE') "
        "and c.commitment_type = (select c2.commitment_type from NCC_COMMITMENT c2 where c2.product_id = c.product_id order by case when c2.commitment_type = 'CONTRACT' then 0 else 1 end, c2.commitment_type limit 1)"
        if is_commitment else
        "select v.product_id, v.param_name, v.param_value from NCC_SUBSCRIPTION s join NCC_PRODUCT p on s.subscription_id = p.subscription_id join NCC_PRODUCT_PARAM_VALUE v on p.product_id = v.product_id where s.customer_id = ? and p.status = 'ACTIVE'"
    )
    emit = '''
                    String valueType = rs.getString("commitment_type");
                    rows += insertCharacteristic(context, rs.getString("product_id"), "commitmentEndDt", rs.getString("end_dt"), valueType);
                    rows += insertCharacteristic(context, rs.getString("product_id"), "earlyTermFeeUsd", formatDecimal(rs.getString("early_term_fee_usd")), valueType);
''' if is_commitment else '''
                    rows += insertCharacteristic(context, rs.getString("product_id"), rs.getString("param_name"), rs.getString("param_value"), "product characteristic");
'''
    reverse_method = '''
    @Override
    public void reverse(ReverseMappingContext context) throws Exception {
        String sql = """
                select product_id, value_type
                from TC_PROD_CHAR
                where name in ('commitmentEndDt', 'earlyTermFeeUsd')
                group by product_id, value_type
                order by product_id, value_type
                """;
        try (PreparedStatement statement = context.target().prepareStatement(sql);
                ResultSet rs = statement.executeQuery()) {
            while (rs.next()) {
                String[] parts = rs.getString("value_type").split(":", 2);
                if (parts.length != 2) {
                    continue;
                }
                executeUpdate(context.source("NCC_SYSTEM"),
                        "insert into NCC_COMMITMENT (product_id, commitment_type, start_dt, end_dt, early_term_fee_usd) "
                                + "values (?, ?, ?, ?, ?) on conflict(product_id, commitment_type) do update set "
                                + "start_dt = excluded.start_dt, end_dt = excluded.end_dt, early_term_fee_usd = excluded.early_term_fee_usd",
                        rs.getString("product_id"),
                        parts[0],
                        parts[1],
                        valueOrDefault(prodCharValue(context, rs.getString("product_id"), "commitmentEndDt", rs.getString("value_type")), "2999-12-31"),
                        valueOrDefault(prodCharValue(context, rs.getString("product_id"), "earlyTermFeeUsd", rs.getString("value_type")), "0"));
            }
        }
    }
''' if is_commitment else '''
    @Override
    public void reverse(ReverseMappingContext context) throws Exception {
        String sql = """
                select product_id, name, value
                from TC_PROD_CHAR
                where value_type = 'product characteristic'
                order by product_id, name
                """;
        try (PreparedStatement statement = context.target().prepareStatement(sql);
                ResultSet rs = statement.executeQuery()) {
            while (rs.next()) {
                executeUpdate(context.source("NCC_SYSTEM"),
                        "insert into NCC_PRODUCT_PARAM_VALUE (product_id, param_name, param_value) "
                                + "values (?, ?, ?) on conflict(product_id, param_name) do update set param_value = excluded.param_value",
                        rs.getString("product_id"),
                        rs.getString("name"),
                        rs.getString("value"));
            }
        }
    }
'''
    src = f'''package com.blackbox.tmf.generated;

import com.blackbox.runtime.mapping.MappingContext;
import com.blackbox.runtime.mapping.MappingPlan;
import com.blackbox.runtime.mapping.ReverseMappingContext;
import com.blackbox.runtime.mapping.ReverseMappingPlan;
import java.sql.PreparedStatement;
import java.sql.ResultSet;
import java.sql.SQLException;
import java.util.logging.Logger;

/** Auto-generated Java mapping from Blackbox IR. */
public final class {class_name} implements MappingPlan, ReverseMappingPlan {{
    private static final Logger LOG = Logger.getLogger({class_name}.class.getName());

    @Override
    public String planId() {{ return {_java_string(plan_id)}; }}

    @Override
    public void execute(MappingContext context) throws Exception {{
        String customerId = context.instanceValue("customer_id");
        int rows = 0;
        try (PreparedStatement statement = context.sources().connection("NCC_SYSTEM").prepareStatement({_java_string(select_sql)})) {{
            statement.setString(1, customerId);
            try (ResultSet rs = statement.executeQuery()) {{
                while (rs.next()) {{
{emit}
                }}
            }}
        }}
        LOG.finer("Generated mapping wrote TC_PROD_CHAR rows=" + rows + " plan=" + planId() + " customer_id=" + customerId);
    }}

    private static int insertCharacteristic(MappingContext context, String productId, String name, String value, String valueType) throws SQLException {{
        if (value == null || value.isBlank()) {{
            return 0;
        }}
        String sql = """
                insert into TC_PROD_CHAR (product_id, name, value, value_type)
                values (?, ?, ?, ?)
                on conflict(product_id, name, value_type) do update set value = excluded.value
                """;
        try (PreparedStatement statement = context.target().prepareStatement(sql)) {{
            statement.setString(1, productId);
            statement.setString(2, name);
            statement.setString(3, value);
            statement.setString(4, valueType);
            return statement.executeUpdate();
        }}
    }}

    private static String prodCharValue(MappingContext context, String productId, String name, String valueType) {{
        throw new UnsupportedOperationException("Forward context cannot read reverse values");
    }}

    private static String prodCharValue(ReverseMappingContext context, String productId, String name, String valueType) throws SQLException {{
        String sql = "select value from TC_PROD_CHAR where product_id = ? and name = ? and value_type = ? limit 1";
        try (PreparedStatement statement = context.target().prepareStatement(sql)) {{
            statement.setString(1, productId);
            statement.setString(2, name);
            statement.setString(3, valueType);
            try (ResultSet rs = statement.executeQuery()) {{
                return rs.next() ? rs.getString("value") : null;
            }}
        }}
    }}

    private static void executeUpdate(java.sql.Connection connection, String sql, String... values) throws SQLException {{
        try (PreparedStatement statement = connection.prepareStatement(sql)) {{
            for (int i = 0; i < values.length; i++) {{
                statement.setString(i + 1, values[i]);
            }}
            statement.executeUpdate();
        }}
    }}

    private static String valueOrDefault(String value, String defaultValue) {{
        return value == null || value.isBlank() ? defaultValue : value;
    }}

    private static String formatDecimal(String value) {{
        if (value == null || value.isBlank()) {{
            return value;
        }}
        if (value.endsWith(".0")) {{
            return value.substring(0, value.length() - 2);
        }}
        return value;
    }}
{reverse_method}
}}
'''
    out_file.write_text(src, encoding="utf-8")
    return out_file


def _materialize_java_tmf_contact_medium_siebel(runtime_plan: Dict[str, Any], out_dir: Path) -> Path:
    plan_id = runtime_plan.get("plan_id", "unknown_plan")
    class_name, out_file = _java_generated_out_file(out_dir, plan_id)
    src = f'''package com.blackbox.tmf.generated;

import com.blackbox.runtime.mapping.MappingContext;
import com.blackbox.runtime.mapping.MappingPlan;
import com.blackbox.runtime.mapping.ReverseMappingContext;
import com.blackbox.runtime.mapping.ReverseMappingPlan;
import java.sql.Connection;
import java.sql.PreparedStatement;
import java.sql.ResultSet;
import java.sql.SQLException;
import java.util.logging.Logger;

/**
 * Auto-generated Java mapping from Blackbox IR.
 *
 * Plan: {plan_id}
 * Template: {runtime_plan.get("template_id")}
 *
 * Generated as build output. Do not edit by hand.
 */
public final class {class_name} implements MappingPlan, ReverseMappingPlan {{
    private static final Logger LOG = Logger.getLogger({class_name}.class.getName());

    @Override
    public String planId() {{
        return {_java_string(plan_id)};
    }}

    @Override
    public void execute(MappingContext context) throws Exception {{
        String partyId = context.instanceValue("party_id");
        SourceRow source = readSource(context.sources().connection("SIEBEL_SYSTEM"), partyId);
        if (source == null) {{
            LOG.warning("No SBL_CUSTOMER contact row found for party_id=" + partyId + "; skipping TC_PTY_CNT_MED Siebel rows");
            return;
        }}
        int rows = 0;
        if (hasText(source.email())) {{
            insertContactMedium(context.target(), source.partyId(), "emailAddress", hasText(source.msisdn()) ? 0 : 1, source.email());
            rows++;
        }}
        if (hasText(source.msisdn())) {{
            insertContactMedium(context.target(), source.partyId(), "telephoneNumber", 1, source.msisdn());
            rows++;
        }}
        LOG.finer("Generated mapping wrote TC_PTY_CNT_MED Siebel rows=" + rows + " party_id=" + source.partyId());
    }}

    private static SourceRow readSource(Connection source, String partyId) throws SQLException {{
        String sql = """
                select party_id, email, msisdn from SBL_CUSTOMER where party_id = ?
                """;
        try (PreparedStatement statement = source.prepareStatement(sql)) {{
            statement.setString(1, partyId);
            try (ResultSet rs = statement.executeQuery()) {{
                if (!rs.next()) {{
                    return null;
                }}
                return new SourceRow(rs.getString("party_id"), rs.getString("email"), rs.getString("msisdn"));
            }}
        }}
    }}

    private static void insertContactMedium(
            Connection target,
            String partyId,
            String mediumType,
            int preferredFlag,
            String characteristicJson) throws SQLException {{
        String sql = """
                insert into TC_PTY_CNT_MED (party_id, medium_type, preferred_flag, characteristic_json)
                values (?, ?, ?, ?)
                on conflict(party_id, medium_type, characteristic_json) do update set
                  preferred_flag = excluded.preferred_flag
                """;
        try (PreparedStatement statement = target.prepareStatement(sql)) {{
            statement.setString(1, partyId);
            statement.setString(2, mediumType);
            statement.setInt(3, preferredFlag);
            statement.setString(4, characteristicJson);
            statement.executeUpdate();
        }}
    }}

    private static boolean hasText(String value) {{
        return value != null && !value.isBlank();
    }}

    @Override
    public void reverse(ReverseMappingContext context) throws Exception {{
        String sql = """
                select c.customer_id, c.engaged_party_id,
                       email.characteristic_json as email,
                       phone.characteristic_json as msisdn
                from TC_CUSTOMER c
                left join TC_PTY_CNT_MED email
                  on email.party_id = c.engaged_party_id and email.medium_type = 'emailAddress'
                left join TC_PTY_CNT_MED phone
                  on phone.party_id = c.engaged_party_id and phone.medium_type = 'telephoneNumber'
                limit 1
                """;
        try (PreparedStatement statement = context.target().prepareStatement(sql);
                ResultSet rs = statement.executeQuery()) {{
            if (!rs.next()) {{
                return;
            }}
            upsertSiebelContact(
                    context.source("SIEBEL_SYSTEM"),
                    rs.getString("customer_id"),
                    rs.getString("engaged_party_id"),
                    rs.getString("email"),
                    rs.getString("msisdn"));
        }}
    }}

    private static void upsertSiebelContact(
            Connection siebel,
            String customerId,
            String partyId,
            String email,
            String msisdn) throws SQLException {{
        String sql = """
                insert into SBL_CUSTOMER
                  (customer_id, party_id, msisdn, first_name, last_name, email, segment_code, status)
                values (?, ?, ?, ?, ?, ?, ?, ?)
                on conflict(customer_id) do update set
                  msisdn = excluded.msisdn,
                  email = excluded.email
                """;
        try (PreparedStatement statement = siebel.prepareStatement(sql)) {{
            statement.setString(1, customerId);
            statement.setString(2, partyId);
            statement.setString(3, hasText(msisdn) ? msisdn : "UNKNOWN_" + customerId);
            statement.setString(4, "");
            statement.setString(5, "");
            statement.setString(6, hasText(email) ? email : customerId + "@example.invalid");
            statement.setString(7, "UNKNOWN");
            statement.setString(8, "ACTIVE");
            statement.executeUpdate();
        }}
    }}

    private record SourceRow(String partyId, String email, String msisdn) {{
    }}
}}
'''
    out_file.write_text(src, encoding="utf-8")
    return out_file


def _materialize_java_tmf_contact_medium_bscs(runtime_plan: Dict[str, Any], out_dir: Path) -> Path:
    plan_id = runtime_plan.get("plan_id", "unknown_plan")
    class_name, out_file = _java_generated_out_file(out_dir, plan_id)
    src = f'''package com.blackbox.tmf.generated;

import com.blackbox.runtime.mapping.MappingContext;
import com.blackbox.runtime.mapping.MappingPlan;
import com.blackbox.runtime.mapping.ReverseMappingContext;
import com.blackbox.runtime.mapping.ReverseMappingPlan;
import java.sql.Connection;
import java.sql.PreparedStatement;
import java.sql.ResultSet;
import java.sql.SQLException;
import java.util.logging.Logger;

/**
 * Auto-generated Java mapping from Blackbox IR.
 *
 * Plan: {plan_id}
 * Template: {runtime_plan.get("template_id")}
 *
 * Generated as build output. Do not edit by hand.
 */
public final class {class_name} implements MappingPlan, ReverseMappingPlan {{
    private static final Logger LOG = Logger.getLogger({class_name}.class.getName());

    @Override
    public String planId() {{
        return {_java_string(plan_id)};
    }}

    @Override
    public void execute(MappingContext context) throws Exception {{
        String partyId = context.instanceValue("party_id");
        String customerId = context.instanceValue("customer_id");
        if (customerId == null) {{
            LOG.warning("No customer_id resolved for party_id=" + partyId + "; skipping TC_PTY_CNT_MED BSCS rows");
            return;
        }}
        int rows = insertPostalRows(context.target(), context.sources().connection("BSCS_SYSTEM"), partyId, customerId);
        LOG.finer("Generated mapping wrote TC_PTY_CNT_MED BSCS rows=" + rows + " party_id=" + partyId);
    }}

    private static int insertPostalRows(Connection target, Connection bscs, String partyId, String customerId) throws SQLException {{
        String sql = """
                select distinct t2.is_primary as is_primary, t3.line1 as line1
                from BSCS_BILLING_ACCOUNT t1
                join BSCS_ACCOUNT_ADDRESS t2 on t1.billing_account_id = t2.billing_account_id
                join BSCS_ADDRESS t3 on t2.address_id = t3.address_id
                where t1.customer_id = ?
                order by t1.billing_account_id, t2.address_role, t2.address_id
                limit 1
                """;
        int rows = 0;
        try (PreparedStatement statement = bscs.prepareStatement(sql)) {{
            statement.setString(1, customerId);
            try (ResultSet rs = statement.executeQuery()) {{
                while (rs.next()) {{
                    String line1 = rs.getString("line1");
                    if (line1 == null || line1.isBlank()) {{
                        continue;
                    }}
                    insertContactMedium(target, partyId, "postalAddress", 0, line1);
                    rows++;
                }}
            }}
        }}
        return rows;
    }}

    private static void insertContactMedium(
            Connection target,
            String partyId,
            String mediumType,
            int preferredFlag,
            String characteristicJson) throws SQLException {{
        String sql = """
                insert into TC_PTY_CNT_MED (party_id, medium_type, preferred_flag, characteristic_json)
                values (?, ?, ?, ?)
                on conflict(party_id, medium_type, characteristic_json) do update set
                  preferred_flag = excluded.preferred_flag
                """;
        try (PreparedStatement statement = target.prepareStatement(sql)) {{
            statement.setString(1, partyId);
            statement.setString(2, mediumType);
            statement.setInt(3, preferredFlag);
            statement.setString(4, characteristicJson);
            statement.executeUpdate();
        }}
    }}

    @Override
    public void reverse(ReverseMappingContext context) throws Exception {{
        String customerId = readCustomerId(context.target());
        if (customerId == null) {{
            return;
        }}
        String billingAccountId = "BA_" + customerId;
        executeUpdate(context.source("BSCS_SYSTEM"),
                "insert into BSCS_CUSTOMER (customer_id, msisdn, credit_class, risk_flag) values (?, ?, ?, ?) "
                        + "on conflict(customer_id) do update set msisdn = excluded.msisdn",
                customerId, "UNKNOWN_" + customerId, "STANDARD", "N");
        executeUpdate(context.source("BSCS_SYSTEM"),
                "insert into BSCS_BILLING_ACCOUNT (billing_account_id, customer_id, bill_cycle, currency, status) values (?, ?, ?, ?, ?) "
                        + "on conflict(billing_account_id) do update set customer_id = excluded.customer_id",
                billingAccountId, customerId, "1", "USD", "ACTIVE");
        String sql = """
                select preferred_flag, characteristic_json
                from TC_PTY_CNT_MED
                where medium_type = 'postalAddress'
                order by characteristic_json
                """;
        int index = 0;
        try (PreparedStatement statement = context.target().prepareStatement(sql);
                ResultSet rs = statement.executeQuery()) {{
            while (rs.next()) {{
                index++;
                String line1 = rs.getString("characteristic_json");
                if (line1 == null || line1.isBlank()) {{
                    continue;
                }}
                String addressId = "ADDR_" + customerId + "_" + index;
                String addressRole = "BILL_TO_" + index;
                executeUpdate(context.source("BSCS_SYSTEM"),
                        "insert into BSCS_ADDRESS (address_id, line1, city, state, postal_code, country) values (?, ?, ?, ?, ?, ?) "
                                + "on conflict(address_id) do update set line1 = excluded.line1",
                        addressId, line1, "UNKNOWN", "NA", "00000", "US");
                executeUpdate(context.source("BSCS_SYSTEM"),
                        "insert into BSCS_ACCOUNT_ADDRESS (billing_account_id, address_id, address_role, is_primary) values (?, ?, ?, ?) "
                                + "on conflict(billing_account_id, address_role) do update set address_id = excluded.address_id, is_primary = excluded.is_primary",
                        billingAccountId, addressId, addressRole, String.valueOf(rs.getInt("preferred_flag")));
            }}
        }}
    }}

    private static String readCustomerId(Connection target) throws SQLException {{
        try (PreparedStatement statement = target.prepareStatement("select customer_id from TC_CUSTOMER limit 1");
                ResultSet rs = statement.executeQuery()) {{
            return rs.next() ? rs.getString("customer_id") : null;
        }}
    }}

    private static void executeUpdate(Connection connection, String sql, String... values) throws SQLException {{
        try (PreparedStatement statement = connection.prepareStatement(sql)) {{
            for (int i = 0; i < values.length; i++) {{
                statement.setString(i + 1, values[i]);
            }}
            statement.executeUpdate();
        }}
    }}
}}
'''
    out_file.write_text(src, encoding="utf-8")
    return out_file


def _materialize_java_tmf_external_ref_bscs(runtime_plan: Dict[str, Any], out_dir: Path) -> Path:
    plan_id = runtime_plan.get("plan_id", "unknown_plan")
    class_name, out_file = _java_generated_out_file(out_dir, plan_id)
    src = f'''package com.blackbox.tmf.generated;

import com.blackbox.runtime.mapping.MappingContext;
import com.blackbox.runtime.mapping.MappingPlan;
import com.blackbox.runtime.mapping.ReverseMappingContext;
import com.blackbox.runtime.mapping.ReverseMappingPlan;
import java.sql.Connection;
import java.sql.PreparedStatement;
import java.sql.ResultSet;
import java.sql.SQLException;
import java.util.logging.Logger;

/**
 * Auto-generated Java mapping from Blackbox IR.
 *
 * Plan: {plan_id}
 * Template: {runtime_plan.get("template_id")}
 *
 * Generated as build output. Do not edit by hand.
 */
public final class {class_name} implements MappingPlan, ReverseMappingPlan {{
    private static final Logger LOG = Logger.getLogger({class_name}.class.getName());

    @Override
    public String planId() {{
        return {_java_string(plan_id)};
    }}

    @Override
    public void execute(MappingContext context) throws Exception {{
        String partyId = context.instanceValue("party_id");
        String customerId = context.instanceValue("customer_id");
        if (customerId == null || customerId.isBlank()) {{
            LOG.warning("No customer_id resolved for party_id=" + partyId + "; skipping TC_PTY_EXT_REF BSCS rows");
            return;
        }}
        SourceRow source = readBscsCustomer(context.sources().connection("BSCS_SYSTEM"), customerId);
        if (source == null) {{
            LOG.warning("No BSCS_CUSTOMER row found for customer_id=" + customerId + "; skipping TC_PTY_EXT_REF BSCS rows");
            return;
        }}
        int rows = insertExternalRefs(context.target(), partyId, source);
        LOG.finer("Generated mapping wrote TC_PTY_EXT_REF BSCS rows=" + rows + " party_id=" + partyId);
    }}

    private static SourceRow readBscsCustomer(Connection bscs, String customerId) throws SQLException {{
        String sql = "select customer_id, msisdn from BSCS_CUSTOMER where customer_id = ?";
        LOG.finest(() -> "Reading BSCS external reference SQL: " + sql);
        try (PreparedStatement statement = bscs.prepareStatement(sql)) {{
            statement.setString(1, customerId);
            try (ResultSet rs = statement.executeQuery()) {{
                if (!rs.next()) {{
                    return null;
                }}
                return new SourceRow(rs.getString("customer_id"), rs.getString("msisdn"));
            }}
        }}
    }}

    private static int insertExternalRefs(Connection target, String partyId, SourceRow source) throws SQLException {{
        String sql = """
                insert into TC_PTY_EXT_REF (party_id, external_ref_type, external_id)
                values (?, ?, ?)
                on conflict(party_id, external_ref_type, external_id) do nothing
                """;
        int rows = 0;
        try (PreparedStatement statement = target.prepareStatement(sql)) {{
            rows += insertOne(statement, partyId, "MSISDN", source.msisdn());
        }}
        return rows;
    }}

    private static int insertOne(
            PreparedStatement statement,
            String partyId,
            String externalRefType,
            String externalId) throws SQLException {{
        if (externalId == null || externalId.isBlank()) {{
            return 0;
        }}
        statement.setString(1, partyId);
        statement.setString(2, externalRefType);
        statement.setString(3, externalId);
        return statement.executeUpdate();
    }}

    @Override
    public void reverse(ReverseMappingContext context) throws Exception {{
        String customerId = scalar(context.target(), "select customer_id from TC_CUSTOMER limit 1");
        String bscsCustomerId = scalar(
                context.target(),
                "select external_id from TC_PTY_EXT_REF where external_ref_type = 'BSCS_CUSTOMER_ID' limit 1");
        if (bscsCustomerId != null && !bscsCustomerId.isBlank()) {{
            customerId = bscsCustomerId;
        }}
        if (customerId == null || customerId.isBlank()) {{
            return;
        }}
        String msisdn = scalar(
                context.target(),
                "select external_id from TC_PTY_EXT_REF where external_ref_type = 'MSISDN' limit 1");
        upsertBscsCustomer(context.source("BSCS_SYSTEM"), customerId, msisdn);
    }}

    private static String scalar(Connection connection, String sql) throws SQLException {{
        try (PreparedStatement statement = connection.prepareStatement(sql);
                ResultSet rs = statement.executeQuery()) {{
            return rs.next() ? rs.getString(1) : null;
        }}
    }}

    private static void upsertBscsCustomer(Connection bscs, String customerId, String msisdn) throws SQLException {{
        String sql = """
                insert into BSCS_CUSTOMER (customer_id, msisdn, credit_class, risk_flag)
                values (?, ?, ?, ?)
                on conflict(customer_id) do update set
                  msisdn = excluded.msisdn
                """;
        try (PreparedStatement statement = bscs.prepareStatement(sql)) {{
            statement.setString(1, customerId);
            statement.setString(2, valueOrDefault(msisdn, "UNKNOWN_" + customerId));
            statement.setString(3, "UNKNOWN");
            statement.setString(4, "N");
            statement.executeUpdate();
        }}
    }}

    private static String valueOrDefault(String value, String defaultValue) {{
        return value == null || value.isBlank() ? defaultValue : value;
    }}

    private record SourceRow(String customerId, String msisdn) {{
    }}
}}
'''
    out_file.write_text(src, encoding="utf-8")
    return out_file


def materialize_execution_plans(
    ir_path: Path,
    out_dir: Path,
    runtimes: Optional[Iterable[str]] = None,
    canonical_ddl_path: Optional[Path] = None,
) -> Dict[str, Any]:
    data = json.loads(ir_path.read_text(encoding="utf-8"))
    execution_plans = data.get("execution_plans", {})
    selected = set(runtimes or list(execution_plans.keys()) + ["java"])

    outputs: Dict[str, Any] = {"generated": {}}
    runtime_items = list(execution_plans.items())
    if "java" in selected:
        runtime_items.append(("java", execution_plans.get("broadway", [])))
    for runtime, plans in runtime_items:
        if runtime not in selected:
            continue
        runtime_out_dir = out_dir / runtime
        _ensure_dir(runtime_out_dir)
        for existing in runtime_out_dir.iterdir():
            if existing.is_file():
                existing.unlink()
            elif runtime == "java" and existing.is_dir():
                shutil.rmtree(existing)
        generated_files = []
        table_counters: Dict[str, int] = {}
        upsert_tables: set[str] = set()
        if runtime == "broadway":
            table_totals: Dict[str, int] = {}
            for runtime_plan in plans:
                target_table = _target_table_from_runtime_plan(runtime_plan)
                table_totals[target_table] = table_totals.get(target_table, 0) + 1
            upsert_tables = {target_table for target_table, count in table_totals.items() if count > 1}
        for runtime_plan in plans:
            target_table = _target_table_from_runtime_plan(runtime_plan)
            if runtime == "java" and target_table not in {
                "TC_PARTY",
                "TC_CUSTOMER",
                "TC_CUST_ACCT",
                "TC_CA_CHAR",
                "TC_PRODUCT",
                "TC_CA_PROD_MAP",
                "TC_PROD_CHAR",
                "TC_PTY_CNT_MED",
                "TC_PTY_EXT_REF",
            }:
                continue
            table_counters[target_table] = table_counters.get(target_table, 0) + 1
            population_index = table_counters[target_table]
            if runtime == "broadway":
                fpath = _materialize_broadway(
                    runtime_plan,
                    runtime_out_dir,
                    target_table,
                    population_index,
                    upsert_tables=upsert_tables,
                )
            elif runtime == "python":
                fpath = _materialize_python(runtime_plan, runtime_out_dir, target_table, population_index)
            elif runtime == "java":
                fpath = _materialize_java(runtime_plan, runtime_out_dir, target_table, population_index)
            else:
                # Unknown runtime: emit passthrough JSON so nothing is lost.
                plan_id = runtime_plan.get("plan_id", "unknown_plan")
                fpath = runtime_out_dir / f"{_safe_name(plan_id)}.{runtime}.json"
                fpath.write_text(json.dumps(runtime_plan, indent=2), encoding="utf-8")
            generated_files.append(str(fpath))
        outputs["generated"][runtime] = generated_files

    if "broadway" in selected and "broadway" in execution_plans:
        k2_out_dir = out_dir / "broadway"
        k2_files = materialize_k2tables(data, k2_out_dir, canonical_ddl_path=canonical_ddl_path)
        outputs["generated"]["k2tables"] = k2_files

    manifest = out_dir / "materialization_manifest.json"
    manifest.write_text(json.dumps(outputs, indent=2), encoding="utf-8")
    outputs["manifest"] = str(manifest)
    return outputs
