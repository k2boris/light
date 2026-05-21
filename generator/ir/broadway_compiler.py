"""Broadway runtime compilation (abstract execution plan).

This emits runtime semantics only. Concrete Broadway actor/stage structure is
materialized later by the Broadway materializer.

Reference for template-to-actor procedural shape:
- see generator/materialize/materializer.py
  TEMPLATE_BROADWAY_ACTOR_REFERENCE
"""

from __future__ import annotations

import json
import re
from typing import Any, Dict, List, Optional, Tuple

from ..spec.spec_model import WorkbookSpec, EntityPlan, FieldMap
from ..ddl.schema_model import Schema
from ..join_notation import (
    parse_join_key,
    resolve_node,
    normalize_system_name,
    find_table_path,
    join_condition,
)


def _parse_source_column(source_path: Optional[str]) -> Optional[str]:
    if not source_path:
        return None
    parts = source_path.split(".")
    if len(parts) != 3:
        return None
    return parts[2]

def _parse_source_parts(source_path: Optional[str]) -> Optional[List[str]]:
    if not source_path:
        return None
    parts = source_path.split(".")
    if len(parts) != 3:
        return None
    return parts

def _split_csv(value: str) -> List[str]:
    return [x.strip() for x in (value or "").split(",") if x.strip()]


def _dedupe_keep_order(values: List[str]) -> List[str]:
    seen = set()
    out: List[str] = []
    for v in values:
        if not v or v in seen:
            continue
        seen.add(v)
        out.append(v)
    return out


def _canonical_source_interface(source_system: str) -> str:
    s = (source_system or "").strip()
    if not s:
        return s
    if s.upper().endswith("_SYSTEM"):
        return s.upper()
    return f"{s.upper()}_SYSTEM"


def _parse_pattern_args(pattern_args: Optional[str]) -> Dict[str, str]:
    if not pattern_args:
        return {}
    out: Dict[str, str] = {}
    parts = [p.strip() for p in pattern_args.split(";") if p.strip()]
    for p in parts:
        if "=" not in p:
            out[p] = "true"
            continue
        k, v = p.split("=", 1)
        out[k.strip()] = v.strip()
    return out


def _parse_driver_args(driver_args: Optional[str]) -> Dict[str, str]:
    if not driver_args:
        return {}
    out: Dict[str, str] = {}
    parts = [p.strip() for p in str(driver_args).split(";") if p.strip()]
    for p in parts:
        if "=" not in p:
            continue
        k, v = p.split("=", 1)
        out[k.strip()] = v.strip()
    return out


def _row_match_policy(ep: EntityPlan, is_multirow: bool) -> str:
    raw = (ep.multiplicity_expectation or "").strip().upper()
    if raw in {"ONE_ONLY", "LATEST", "MULTIPLE", "ZERO_OR_ONE"}:
        return raw
    if raw == "EXPECT_ONE":
        return "ONE_ONLY"
    if raw in {"ALLOW_MANY", "EXPECT_MANY"}:
        return "MULTIPLE"
    return "MULTIPLE" if is_multirow else "ONE_ONLY"


def _latest_by_from_as_of_policy(ep: EntityPlan) -> Optional[str]:
    s = (ep.as_of_policy or "").strip()
    if not s:
        return None
    parts = _parse_pattern_args(s.replace(",", ";"))
    if parts.get("latest_by"):
        return parts.get("latest_by")
    if "=" not in s and re.match(r"^[A-Za-z_][A-Za-z0-9_]*$", s):
        return s
    return None


def _parse_concat_prefix_expr(expr: Optional[str]) -> Optional[Dict[str, str]]:
    if not expr:
        return None
    # Supports: 'CA_' || customer_id   or   "CA_" || customer_id
    m = re.match(r'^\s*(?:"([^"]*)"|\'([^\']*)\')\s*\|\|\s*([A-Za-z_][A-Za-z0-9_]*)\s*$', expr)
    if not m:
        return None
    prefix = m.group(1) if m.group(1) is not None else m.group(2)
    return {"prefix": prefix, "source_column": m.group(3)}


_IDENT_RE = re.compile(r"\b[A-Za-z_][A-Za-z0-9_]*\b")
_RESERVED_WORDS = {
    "true", "false", "null", "undefined", "NaN", "Infinity",
    "if", "else", "return", "var", "let", "const", "new", "typeof",
}


def _extract_identifiers(expr: Optional[str]) -> List[str]:
    if not expr:
        return []
    out: List[str] = []
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


def _collect_source_columns_from_emit_rows(emit_rows: List[Dict[str, Any]]) -> List[str]:
    source_columns: List[str] = []
    for row in emit_rows:
        for token in _extract_identifiers(row.get("emit_when")):
            if token not in source_columns:
                source_columns.append(token)
        fields = row.get("fields") or {}
        if not isinstance(fields, dict):
            continue
        for expr in fields.values():
            if not isinstance(expr, dict):
                continue
            op = expr.get("op")
            if op == "PATH":
                parts = _parse_source_parts(expr.get("path"))
                if parts and parts[2] not in source_columns:
                    source_columns.append(parts[2])
            elif op == "EXPR":
                for token in _extract_identifiers(expr.get("expr")):
                    if token not in source_columns:
                        source_columns.append(token)
    return source_columns


def _collect_target_fields_from_emit_rows(emit_rows: List[Dict[str, Any]]) -> List[str]:
    out: List[str] = []
    seen = set()
    for row in emit_rows:
        fields = row.get("fields") or {}
        if not isinstance(fields, dict):
            continue
        for f in fields.keys():
            if f not in seen:
                seen.add(f)
                out.append(f)
    return out


def _schema_by_system(sources: Optional[Dict[str, Schema]], system_name: Optional[str]) -> Optional[Schema]:
    if not sources:
        return None
    ns = normalize_system_name(system_name)
    for k, s in sources.items():
        if normalize_system_name(k) == ns:
            return s
    return None


def _default_xref_system_code(source_system: Optional[str]) -> str:
    ns = normalize_system_name(source_system) or str(source_system or "").strip().upper()
    mapping = {
        "CRM_SF_DS": "SFDC",
        "SF-CRM": "SFDC",
        "SFDC": "SFDC",
        "DOWJONES_DS": "DJ",
        "DOWJONES": "DJ",
        "DJ": "DJ",
        "MDM_INFA_DS": "MDM",
        "MDM-INFA": "MDM",
        "MDM": "MDM",
        "CORE_TMNS_DS": "TEMENOS",
        "TMNS-CORE": "TEMENOS",
        "TEMENOS": "TEMENOS",
        "AML_ORA_DS": "ORACLE_AML",
        "ORA-AML": "ORACLE_AML",
        "ORACLE_AML": "ORACLE_AML",
    }
    return mapping.get(ns, ns)


def _compile_join_projection_script(field_bindings: List[Dict[str, Any]]) -> str:
    lines = [
        "function scalar(v) {",
        "  if (v === null || v === undefined) return null;",
        "  try { if (typeof v !== 'string' && v[0] !== undefined) v = v[0]; } catch (e) {}",
        "  return '' + v;",
        "}",
        "self.result = [];",
        "self.result.push({",
    ]
    rendered = []
    for b in field_bindings:
        tf = b.get("target_field")
        sem = b.get("value_semantic")
        if sem == "const":
            val = b.get("const_value")
            lit = json.dumps(str(val)) if val is not None else "null"
            rendered.append(f"  {tf}: {lit}")
        elif sem == "now":
            rendered.append(f"  {tf}: scalar(now)")
        elif sem == "expr":
            rendered.append(f"  {tf}: {b.get('expr') or 'null'}")
        elif sem == "context":
            rendered.append(f"  {tf}: scalar(parent_{b.get('context_column')})")
        else:
            sc = b.get("source_column")
            rendered.append(f"  {tf}: scalar({sc})" if sc else f"  {tf}: null")
    for i, r in enumerate(rendered):
        lines.append(r + ("," if i < len(rendered) - 1 else ""))
    lines.extend(["});", "self.result;"])
    return "\n".join(lines)


def _compile_join_projection_script_emit_rows(emit_rows: List[Dict[str, Any]], driver_key: str) -> str:
    source_columns = _collect_source_columns_from_emit_rows(emit_rows)
    lines = [
        "function scalar(v) {",
        "  if (v === null || v === undefined) return null;",
        "  try { if (typeof v !== 'string' && v[0] !== undefined) v = v[0]; } catch (e) {}",
        "  return '' + v;",
        "}",
        f"var s_parent_{driver_key} = scalar(parent_{driver_key});",
    ]
    for c in source_columns:
        lines.append(f"var s_{c} = scalar({c});")
    lines.append("self.result = [];")

    for row in emit_rows:
        raw_cond = row.get("emit_when")
        if isinstance(raw_cond, str) and raw_cond.strip():
            cond = raw_cond
            for c in source_columns:
                cond = re.sub(rf"(?<!['\"])\\b{re.escape(c)}\\b(?!['\"])", f"s_{c}", cond)
            lines.append(f"if ({cond}) {{")
            indent = "  "
        else:
            indent = ""

        lines.append(f"{indent}self.result.push({{")
        rendered: List[str] = [f"{indent}  {driver_key}: s_parent_{driver_key}"]
        fields = row.get("fields") if isinstance(row, dict) else None
        if isinstance(fields, dict):
            for tf, expr in fields.items():
                if tf == driver_key:
                    continue
                value = "null"
                if isinstance(expr, dict):
                    op = expr.get("op")
                    if op == "PATH":
                        parts = _parse_source_parts(expr.get("path"))
                        if parts:
                            value = f"s_{parts[2]}"
                    elif op == "CONST":
                        value = json.dumps(expr.get("value"))
                    elif op == "EXPR":
                        rexpr = str(expr.get("expr") or "")
                        for c in source_columns:
                            rexpr = re.sub(rf"(?<!['\"])\\b{re.escape(c)}\\b(?!['\"])", f"s_{c}", rexpr)
                        value = rexpr if rexpr else "null"
                    elif op == "CONTEXT":
                        ck = str(expr.get("context_key") or "").strip()
                        value = f"scalar(parent_{ck})" if ck else "null"
                rendered.append(f"{indent}  {tf}: {value}")
        for i, r in enumerate(rendered):
            lines.append(r + ("," if i < len(rendered) - 1 else ""))
        lines.append(f"{indent}}});")
        if indent:
            lines.append("}")

    lines.append("self.result;")
    return "\n".join(lines)


def _compile_join_template_plan(
    ep: EntityPlan,
    field_maps: List[FieldMap],
    template_params: Dict[str, Any],
    impl_cfg: Dict[str, Any],
    sources: Optional[Dict[str, Schema]],
) -> Dict[str, Any]:
    source_system = template_params.get("source_system") or ep.source_system
    source_interface = template_params.get("source_interface") or _canonical_source_interface(source_system)
    source_schema = _schema_by_system(sources, source_system)
    if not source_schema:
        return {}

    emit_rows = template_params.get("emit_rows") or []
    is_multirow = isinstance(emit_rows, list) and len(emit_rows) > 0

    bridge_interface = impl_cfg.get("bridge_interface")
    bridge_sql = impl_cfg.get("bridge_sql")
    dargs = _parse_driver_args(ep.driver_args)
    driver_lookup_column = dargs.get("to") or ep.driver_key
    rename_strip_prefix = dargs.get("strip_prefix")
    bridge_lookup_column = None
    bridge_lookup_table = None
    bridge_key_column = ep.driver_key
    bridge_local_key_column = None
    join_chain_tables: List[str] = []
    join_required_columns: List[str] = []
    explicit_join_hops: Dict[Tuple[str, str], Tuple[str, str]] = {}

    field_bindings: List[Dict[str, Any]] = []
    for fm in field_maps:
        bind: Dict[str, Any] = {"target_field": fm.target_field, "join_key": fm.join_key}
        if fm.pattern_id == "P_CONST":
            raw = (fm.pattern_args or "").strip()
            value = raw.split("=", 1)[1] if raw.startswith("value=") else raw
            bind["value_semantic"] = "const"
            bind["const_value"] = value
        elif fm.pattern_id == "P_NOW":
            bind["value_semantic"] = "now"
        elif fm.pattern_id == "P_EXPR":
            args = _parse_pattern_args(fm.pattern_args)
            bind["value_semantic"] = "expr"
            bind["expr"] = args.get("expr") or fm.transform_rule
        else:
            bind["value_semantic"] = "source"
            bind["source_column"] = _parse_source_column(fm.source_path)
        if fm.target_field == ep.driver_key and fm.pattern_id == "P_EXPR":
            bind["value_semantic"] = "context"
            bind["context_column"] = ep.driver_key
        field_bindings.append(bind)

        if fm.join_key:
            parsed = parse_join_key(fm.join_key)
            if parsed.get("errors"):
                continue
            resolved = [resolve_node(n, ep.source_system, sources or {}) for n in parsed["nodes"]]
            ops = parsed["ops"]
            for i, op in enumerate(ops):
                l = resolved[i]
                r = resolved[i + 1]
                if not (l.get("ok") and r.get("ok")):
                    continue
                if op == "-->" and bridge_lookup_table is None:
                    if r.get("table"):
                        bridge_lookup_table = r["table"]
                        bridge_lookup_column = r["column"]
                        if not bridge_interface:
                            bridge_interface = _canonical_source_interface(r.get("system"))
                    if l.get("table") and l.get("column"):
                        bridge_key_column = l["column"]
                if op == "->" and l.get("system") and normalize_system_name(l["system"]) == normalize_system_name(source_system):
                    if l.get("table"):
                        join_chain_tables.append(l["table"])
                if op == "->" and r.get("system") and normalize_system_name(r["system"]) == normalize_system_name(source_system):
                    if r.get("table"):
                        join_chain_tables.append(r["table"])
                if (
                    op == "->"
                    and l.get("table")
                    and l.get("column")
                    and r.get("table")
                    and r.get("column")
                    and normalize_system_name(l.get("system")) == normalize_system_name(source_system)
                    and normalize_system_name(r.get("system")) == normalize_system_name(source_system)
                ):
                    explicit_join_hops[(l["table"], r["table"])] = (l["column"], r["column"])
                if op == "-->" and r.get("system") and normalize_system_name(r["system"]) == normalize_system_name(source_system):
                    bridge_local_key_column = r.get("column")
                    if r.get("table"):
                        join_chain_tables.append(r["table"])

    if not join_chain_tables:
        join_chain_tables.append(ep.source_table)
    # Deduplicate while preserving order.
    ordered_tables: List[str] = []
    for t in join_chain_tables:
        if t not in ordered_tables:
            ordered_tables.append(t)

    # Expand gaps using schema graph.
    expanded: List[str] = [ordered_tables[0]]
    for nxt in ordered_tables[1:]:
        last = expanded[-1]
        if last == nxt:
            continue
        p = find_table_path(source_schema, last, nxt)
        if not p:
            if nxt not in expanded:
                expanded.append(nxt)
            continue
        for t in p[1:]:
            if t not in expanded:
                expanded.append(t)

    from_table = expanded[0]
    alias_map = {from_table: "t1"}
    alias_idx = 1
    joins: List[Dict[str, str]] = []
    for i, t in enumerate(expanded[1:], start=1):
        if t in alias_map:
            continue
        alias_idx += 1
        alias = f"t{alias_idx}"
        alias_map[t] = alias
        prev = expanded[i - 1]
        cond = None
        explicit = explicit_join_hops.get((prev, t))
        if explicit:
            lcol, rcol = explicit
            cond = (f"{prev}.{lcol}", f"{t}.{rcol}")
        if not cond:
            cond = join_condition(source_schema, prev, t)
        if cond:
            left_expr, right_expr = cond
            ltab, lcol = left_expr.split(".")
            rtab, rcol = right_expr.split(".")
            joins.append({
                "table": t,
                "alias": alias,
                "on": f"{alias_map.get(ltab, 't1')}.{lcol} = {alias}.{rcol}" if rtab == t else f"{alias}.{lcol} = {alias_map.get(rtab, 't1')}.{rcol}",
            })
        else:
            joins.append({"table": t, "alias": alias, "on": "1=1"})

    for b in field_bindings:
        sc = b.get("source_column")
        if sc and sc not in join_required_columns:
            join_required_columns.append(sc)
    if is_multirow:
        for sc in _collect_source_columns_from_emit_rows(emit_rows):
            if sc and sc not in join_required_columns:
                join_required_columns.append(sc)
    if bridge_local_key_column and bridge_local_key_column not in join_required_columns:
        join_required_columns.append(bridge_local_key_column)
    if ep.driver_key not in join_required_columns:
        for t in expanded:
            tt = source_schema.get_table(t)
            if tt and tt.get_column(ep.driver_key):
                join_required_columns.append(ep.driver_key)
                break

    # Ensure the implicit query filter column is projected when available.
    if driver_lookup_column and driver_lookup_column not in join_required_columns:
        for t in expanded:
            tt = source_schema.get_table(t)
            if tt and tt.get_column(driver_lookup_column):
                join_required_columns.insert(0, driver_lookup_column)
                break

    select_exprs: List[str] = []
    for c in join_required_columns:
        picked_table = from_table
        for t in expanded:
            tt = source_schema.get_table(t)
            if tt and tt.get_column(c):
                picked_table = t
                break
        select_exprs.append(f"{alias_map.get(picked_table, alias_map[from_table])}.{c} AS {c}")
    select_list = ",\n    ".join(select_exprs)
    join_sql = f"SELECT DISTINCT\n    {select_list}\nFROM {from_table} {alias_map[from_table]}"
    for j in joins:
        join_sql += f"\nJOIN {j['table']} {j['alias']} ON {j['on']}"
    if bridge_lookup_table and bridge_lookup_column and not bridge_sql:
        bridge_sql = (
            f"SELECT {bridge_lookup_column} "
            f"FROM main.{bridge_lookup_table}"
        )

    target_fields = [b["target_field"] for b in field_bindings]
    if is_multirow:
        target_fields = _collect_target_fields_from_emit_rows(emit_rows)
        dkey = template_params.get("driver_key") or ep.driver_key
        if dkey and dkey not in target_fields:
            target_fields = [dkey] + target_fields

    return {
        "profile": impl_cfg.get("profile", "join_to_1_parent_scoped"),
        "context": {
            "driver_key": template_params.get("driver_key") or ep.driver_key,
            "parent_rows_field": ep.driver_key,
            "rename_alias": driver_lookup_column,
            "rename_strip_prefix": rename_strip_prefix,
            "include_population_input": True,
            "required": False,
        },
        "source": {
            "interface": source_interface,
            "system": source_system,
            "table": ep.source_table,
            "sql": f"select * from main.{ep.source_table}",
            "luid_sql": None,
            "source_columns": join_required_columns,
        },
        "bridge": {
            "enabled": bool(bridge_sql),
            "interface": bridge_interface or source_interface,
            "sql": bridge_sql,
            "bridge_input": ep.driver_key,
        },
        "join_query": {
            "interface": source_interface,
            "sql": join_sql,
            "source_columns": join_required_columns,
        },
        "load": {
            "target_table": template_params.get("target_table") or ep.target_table,
            "target_interface": template_params.get("target_interface") or "fabric",
            "target_schema": template_params.get("target_schema"),
            "dialect": template_params.get("dialect") or "sqlite",
            "keys": _split_csv(ep.keys),
            "iterate_mode": template_params.get("iterate_mode") or "Iterate",
            "field_bindings": field_bindings,
            "target_fields": target_fields,
        },
        "behavior": {
            "sync_delete": bool(template_params.get("sync_delete")),
            "assert_max_rows": template_params.get("assert_max_rows"),
            "emit_rows": emit_rows if is_multirow else None,
            "projection_js": (
                _compile_join_projection_script_emit_rows(emit_rows, template_params.get("driver_key") or ep.driver_key)
                if is_multirow
                else _compile_join_projection_script(field_bindings)
            ),
            "use_now": any(b.get("value_semantic") == "now" for b in field_bindings),
            "row_match_policy": _row_match_policy(ep, is_multirow=is_multirow),
            "latest_by": _latest_by_from_as_of_policy(ep),
        },
    }


def _compile_xref_join_template_plan(
    ep: EntityPlan,
    field_maps: List[FieldMap],
    template_params: Dict[str, Any],
    impl_cfg: Dict[str, Any],
    sources: Optional[Dict[str, Schema]],
) -> Dict[str, Any]:
    resolved_source_system = template_params.get("source_system") or ep.source_system
    dargs = _parse_driver_args(ep.driver_args)
    source_lookup_alias = dargs.get("to") or ep.driver_key

    xref_output_col = impl_cfg.get("xref_output_col") or template_params.get("xref_output_col") or "SOURCE_KEY"
    xref_table = impl_cfg.get("xref_table") or template_params.get("xref_table") or "C_XREF_PARTY"
    xref_interface = (
        impl_cfg.get("xref_interface")
        or template_params.get("xref_interface")
        or "MDM_INFA_DS"
    )
    xref_system_code = (
        impl_cfg.get("xref_system_code")
        or template_params.get("xref_system_code")
        or _default_xref_system_code(resolved_source_system)
    )
    xref_sql = (
        impl_cfg.get("xref_sql")
        or template_params.get("xref_sql")
        or (
            f"SELECT {xref_output_col} AS {source_lookup_alias} "
            f"FROM main.{xref_table} "
            f"WHERE SYSTEM_CODE = '{xref_system_code}'"
        )
    )

    merged_impl = dict(impl_cfg or {})
    merged_impl.setdefault("profile", "join_to_1_parent_scoped")
    merged_impl.setdefault("bridge_interface", xref_interface)
    merged_impl.setdefault("bridge_sql", xref_sql)
    compiled = _compile_join_template_plan(ep, field_maps, template_params, merged_impl, sources)
    if not compiled:
        return compiled

    # XREF join always seeds bridge with canonical id and resolves source lookup key.
    xref_input_col = impl_cfg.get("xref_input_col") or template_params.get("xref_input_col") or "ROWID_OBJECT"
    compiled.setdefault("context", {})
    compiled["context"]["rename_alias"] = xref_input_col
    compiled.setdefault("bridge", {})
    compiled["bridge"]["output_alias"] = source_lookup_alias

    # Keep canonical identity stable on target driver key for XREF plans.
    field_bindings = compiled.get("load", {}).get("field_bindings") or []
    updated_context = False
    for bind in field_bindings:
        if bind.get("target_field") == ep.driver_key:
            bind["value_semantic"] = "context"
            bind["context_column"] = ep.driver_key
            bind.pop("source_column", None)
            updated_context = True
    if updated_context:
        compiled.setdefault("behavior", {})
        compiled["behavior"]["projection_js"] = _compile_join_projection_script(field_bindings)

    return compiled


def _compile_xref_template_plan(
    ep: EntityPlan,
    field_maps: List[FieldMap],
    template_params: Dict[str, Any],
    impl_cfg: Dict[str, Any],
) -> Dict[str, Any]:
    resolved_source_system = template_params.get("source_system") or ep.source_system
    resolved_source_table = template_params.get("source_table") or ep.source_table
    resolved_source_interface = (
        template_params.get("source_interface")
        or ep.source_interface
        or _canonical_source_interface(resolved_source_system)
    )

    field_bindings: List[Dict[str, Any]] = []
    source_columns: List[str] = []
    for fm in field_maps:
        binding: Dict[str, Any] = {"target_field": fm.target_field}
        if fm.pattern_id == "P_CONST":
            raw = (fm.pattern_args or "").strip()
            value = raw.split("=", 1)[1] if raw.startswith("value=") else raw
            if isinstance(value, str) and value.strip().upper().startswith("NULL"):
                binding["value_semantic"] = "null"
            else:
                binding["value_semantic"] = "const"
                binding["const_value"] = value
        elif fm.pattern_id == "P_NOW":
            binding["value_semantic"] = "now"
        elif fm.pattern_id == "P_EXPR":
            args = _parse_pattern_args(fm.pattern_args)
            expr = args.get("expr") or fm.transform_rule or fm.pattern_args
            binding["value_semantic"] = "expr"
            binding["expr"] = expr
            col = _parse_source_column(fm.source_path)
            binding["source_column"] = col
            if col and col not in source_columns:
                source_columns.append(col)
        else:
            binding["value_semantic"] = "source"
            col = _parse_source_column(fm.source_path)
            binding["source_column"] = col
            if col and col not in source_columns:
                source_columns.append(col)
        field_bindings.append(binding)

    source_lookup_alias = impl_cfg.get("xref_source_lookup_alias")
    if not source_lookup_alias:
        party_bind = next(
            (
                b
                for b in field_bindings
                if b.get("value_semantic") == "source"
                and b.get("target_field") == "party_id"
                and b.get("source_column")
            ),
            None,
        )
        if party_bind:
            source_lookup_alias = party_bind.get("source_column")
    if not source_lookup_alias:
        dargs = _parse_driver_args(ep.driver_args)
        source_lookup_alias = dargs.get("to")
    if not source_lookup_alias:
        source_lookup_alias = ep.driver_key

    xref_driver_key = impl_cfg.get("xref_driver_key") or template_params.get("xref_driver_key")
    if not xref_driver_key:
        if any(b.get("target_field") == "party_id" for b in field_bindings):
            xref_driver_key = "party_id"
        else:
            xref_driver_key = template_params.get("driver_key") or ep.driver_key

    # In XREF parent-scoped plans, keep canonical identity stable:
    # target driver field must come from parent context, not source rows.
    for binding in field_bindings:
        if binding.get("target_field") == xref_driver_key:
            binding["value_semantic"] = "context"
            binding["context_column"] = xref_driver_key

    xref_input_col = impl_cfg.get("xref_input_col") or template_params.get("xref_input_col") or "ROWID_OBJECT"
    xref_output_col = impl_cfg.get("xref_output_col") or template_params.get("xref_output_col") or "SOURCE_KEY"
    xref_table = impl_cfg.get("xref_table") or template_params.get("xref_table") or "C_XREF_PARTY"
    xref_interface = (
        impl_cfg.get("xref_interface")
        or template_params.get("xref_interface")
        or "MDM_INFA_DS"
    )
    xref_system_code = (
        impl_cfg.get("xref_system_code")
        or template_params.get("xref_system_code")
        or _default_xref_system_code(resolved_source_system)
    )
    xref_sql = (
        impl_cfg.get("xref_sql")
        or template_params.get("xref_sql")
        or (
            f"SELECT {xref_output_col} AS {source_lookup_alias} "
            f"FROM main.{xref_table} "
            f"WHERE SYSTEM_CODE = '{xref_system_code}'"
        )
    )

    luid_sql = impl_cfg.get("luid_sql")
    if not luid_sql and source_columns:
        luid_sql = (
            f"select {', '.join(source_columns)} "
            f"from {resolved_source_system}.{resolved_source_table}"
        )

    return {
        "profile": impl_cfg.get("profile", "join_to_1_parent_scoped"),
        "context": {
            "driver_key": xref_driver_key,
            "parent_rows_field": xref_driver_key,
            "rename_alias": xref_input_col,
            "rename_strip_prefix": None,
            "include_population_input": True,
            "required": False,
        },
        "source": {
            "interface": resolved_source_interface,
            "system": resolved_source_system,
            "table": resolved_source_table,
            "sql": f"select * from main.{resolved_source_table}",
            "luid_sql": luid_sql,
            "source_columns": source_columns,
        },
        "bridge": {
            "enabled": True,
            "interface": xref_interface,
            "sql": xref_sql,
            "bridge_input": xref_driver_key,
            "output_alias": source_lookup_alias,
        },
        "join_query": {
            "interface": resolved_source_interface,
            "sql": f"select * from main.{resolved_source_table}",
            "source_columns": source_columns,
        },
        "load": {
            "target_table": template_params.get("target_table") or ep.target_table,
            "target_interface": template_params.get("target_interface") or "fabric",
            "target_schema": template_params.get("target_schema"),
            "dialect": template_params.get("dialect") or "sqlite",
            "keys": _split_csv(ep.keys),
            "iterate_mode": template_params.get("iterate_mode") or "Iterate",
            "field_bindings": field_bindings,
            "target_fields": [b["target_field"] for b in field_bindings],
        },
        "behavior": {
            "sync_delete": bool(template_params.get("sync_delete")),
            "assert_max_rows": template_params.get("assert_max_rows"),
            "emit_rows": None,
            "projection_js": _compile_join_projection_script(field_bindings),
            "use_now": any(b.get("value_semantic") == "now" for b in field_bindings),
            "row_match_policy": _row_match_policy(ep, is_multirow=False),
            "latest_by": _latest_by_from_as_of_policy(ep),
        },
    }


def _compile_array_input_template_plan(
    ep: EntityPlan,
    field_maps: List[FieldMap],
    template_params: Dict[str, Any],
    impl_cfg: Dict[str, Any],
) -> Dict[str, Any]:
    field_bindings: List[Dict[str, Any]] = []
    source_columns: List[str] = []
    for fm in field_maps:
        binding: Dict[str, Any] = {"target_field": fm.target_field}
        if fm.pattern_id == "P_CONST":
            raw = (fm.pattern_args or "").strip()
            value = raw.split("=", 1)[1] if raw.startswith("value=") else raw
            if isinstance(value, str) and value.strip().upper().startswith("NULL"):
                binding["value_semantic"] = "null"
            else:
                binding["value_semantic"] = "const"
                binding["const_value"] = value
        elif fm.pattern_id == "P_NOW":
            binding["value_semantic"] = "now"
        elif fm.pattern_id == "P_EXPR":
            args = _parse_pattern_args(fm.pattern_args)
            expr = args.get("expr") or fm.transform_rule or fm.pattern_args
            binding["value_semantic"] = "expr"
            binding["expr"] = expr
            col = _parse_source_column(fm.source_path)
            binding["source_column"] = col
            if col and col not in source_columns:
                source_columns.append(col)
        else:
            binding["value_semantic"] = "source"
            col = _parse_source_column(fm.source_path)
            binding["source_column"] = col
            if col and col not in source_columns:
                source_columns.append(col)
        field_bindings.append(binding)

    resolved_driver_key = template_params.get("driver_key") or ep.driver_key
    target_fields = [b["target_field"] for b in field_bindings]
    resolved_source_system = template_params.get("source_system") or ep.source_system
    resolved_source_table = template_params.get("source_table") or ep.source_table
    resolved_source_interface = (
        template_params.get("source_interface")
        or ep.source_interface
        or _canonical_source_interface(resolved_source_system)
    )
    luid_sql = impl_cfg.get("luid_sql")
    if not luid_sql and source_columns:
        luid_sql = (
            f"select {', '.join(source_columns)} "
            f"from {resolved_source_system}.{resolved_source_table}"
        )
    return {
        "profile": impl_cfg.get("profile", "array_input_to_columns_parent_scoped"),
        "context": {
            "driver_key": resolved_driver_key,
            "parent_rows_field": resolved_driver_key,
            "include_population_input": True,
            "required": False,
        },
        "source": {
            "interface": resolved_source_interface,
            "system": resolved_source_system,
            "table": resolved_source_table,
            "sql": impl_cfg.get("sql") or f"select * from main.{resolved_source_table}",
            "luid_sql": luid_sql,
            "source_columns": source_columns,
        },
        "load": {
            "target_table": template_params.get("target_table") or ep.target_table,
            "target_interface": template_params.get("target_interface") or "fabric",
            "target_schema": template_params.get("target_schema"),
            "dialect": template_params.get("dialect") or "sqlite",
            "keys": _split_csv(ep.keys),
            "iterate_mode": template_params.get("iterate_mode") or "Iterate",
            "field_bindings": field_bindings,
            "target_fields": target_fields,
        },
        "behavior": {
            "row_match_policy": _row_match_policy(ep, is_multirow=False),
            "latest_by": _latest_by_from_as_of_policy(ep),
        },
    }


def _compile_array_input_to_eav_template_plan(
    ep: EntityPlan,
    template_params: Dict[str, Any],
    impl_cfg: Dict[str, Any],
) -> Dict[str, Any]:
    emit_rows = template_params.get("emit_rows") or []
    source_columns = _collect_source_columns_from_emit_rows(emit_rows)
    target_fields = ["product_id", "name", "value", "value_type"]
    resolved_driver_key = template_params.get("driver_key") or ep.driver_key
    resolved_source_system = template_params.get("source_system") or ep.source_system
    resolved_source_table = template_params.get("source_table") or ep.source_table
    resolved_source_interface = (
        template_params.get("source_interface")
        or ep.source_interface
        or _canonical_source_interface(resolved_source_system)
    )
    luid_sql = impl_cfg.get("luid_sql")
    if not luid_sql and source_columns:
        luid_sql = (
            f"select {', '.join(source_columns)} "
            f"from {resolved_source_system}.{resolved_source_table}"
        )
    return {
        "profile": impl_cfg.get("profile", "array_input_to_eav_parent_scoped"),
        "context": {
            "driver_key": resolved_driver_key,
            "parent_rows_field": resolved_driver_key,
            "include_population_input": True,
            "required": False,
        },
        "source": {
            "interface": resolved_source_interface,
            "system": resolved_source_system,
            "table": resolved_source_table,
            "sql": impl_cfg.get("sql") or f"select * from main.{resolved_source_table}",
            "luid_sql": luid_sql,
            "source_columns": source_columns,
        },
        "load": {
            "target_table": template_params.get("target_table") or ep.target_table,
            "target_interface": template_params.get("target_interface") or "fabric",
            "target_schema": template_params.get("target_schema"),
            "dialect": template_params.get("dialect") or "sqlite",
            "keys": _split_csv(ep.keys),
            "iterate_mode": template_params.get("iterate_mode") or "Iterate",
            "target_fields": target_fields,
        },
        "behavior": {
            "emit_rows": emit_rows,
        },
    }


def compile_broadway_plan(
    spec: WorkbookSpec,
    ep: EntityPlan,
    field_maps: List[FieldMap],
    template_params: Dict[str, Any],
    sources: Optional[Dict[str, Schema]] = None,
) -> Dict[str, Any]:
    t_impl = spec.template_impls_by_template.get(ep.template_id, {}).get("broadway")
    if not t_impl and ep.template_id not in {
        "TPL_MULTIROW_FROM_COLUMNS_PARENT_SCOPED",
        "TPL_EAV_FROM_COLUMNS_PARENT_SCOPED",
        "TPL_MULTIROW_TO_EAV_PARENT_SCOPED",
        "TPL_COLUMNS_PARENT_SCOPED",
        "TPL_COLUMNS_XREF_PARENT_SCOPED",
        "TPL_XREF_JOIN_PARENT_SCOPED",
        "TPL_EAV_PARENT_SCOPED",
        "TPL_ARRAY_INPUT_TO_COLUMNS_PARENT_SCOPED",
        "TPL_ARRAY_INPUT_TO_EAV_PARENT_SCOPED",
    }:
        return {}
    if t_impl and (t_impl.enabled or "Y").upper() == "N":
        return {}

    impl_cfg: Dict[str, Any] = {}
    if t_impl and t_impl.impl_json:
        try:
            parsed = json.loads(t_impl.impl_json)
            if isinstance(parsed, dict):
                impl_cfg = parsed
        except Exception:
            impl_cfg = {}

    if ep.template_id == "TPL_JOIN_TO_1_PARENT_SCOPED":
        return _compile_join_template_plan(ep, field_maps, template_params, impl_cfg, sources)
    if ep.template_id == "TPL_XREF_JOIN_PARENT_SCOPED":
        return _compile_xref_join_template_plan(ep, field_maps, template_params, impl_cfg, sources)
    if ep.template_id == "TPL_COLUMNS_XREF_PARENT_SCOPED":
        return _compile_xref_template_plan(ep, field_maps, template_params, impl_cfg)
    if ep.template_id == "TPL_ARRAY_INPUT_TO_COLUMNS_PARENT_SCOPED":
        return _compile_array_input_template_plan(ep, field_maps, template_params, impl_cfg)
    if ep.template_id == "TPL_ARRAY_INPUT_TO_EAV_PARENT_SCOPED":
        return _compile_array_input_to_eav_template_plan(ep, template_params, impl_cfg)

    resolved_source_system = template_params.get("source_system") or ep.source_system
    resolved_source_table = template_params.get("source_table") or ep.source_table
    resolved_source_interface = (
        template_params.get("source_interface")
        or ep.source_interface
        or _canonical_source_interface(resolved_source_system)
    )

    emit_rows = template_params.get("emit_rows")
    field_bindings: List[Dict[str, Any]] = []
    source_columns: List[str] = []
    for fm in field_maps:
        binding: Dict[str, Any] = {"target_field": fm.target_field}
        if fm.pattern_id == "P_CONST":
            raw = (fm.pattern_args or "").strip()
            value = raw.split("=", 1)[1] if raw.startswith("value=") else raw
            if isinstance(value, str) and value.strip().upper().startswith("NULL"):
                binding["value_semantic"] = "null"
            else:
                binding["value_semantic"] = "const"
                binding["const_value"] = value
        elif fm.pattern_id == "P_NOW":
            binding["value_semantic"] = "now"
        elif fm.pattern_id == "P_EXPR":
            args = _parse_pattern_args(fm.pattern_args)
            expr = args.get("expr") or fm.transform_rule or fm.pattern_args
            binding["value_semantic"] = "expr"
            binding["expr"] = expr
            parsed_expr = _parse_concat_prefix_expr(expr)
            if parsed_expr:
                binding["expr_kind"] = "concat_prefix"
                binding["const_prefix"] = parsed_expr["prefix"]
                binding["source_column"] = parsed_expr["source_column"]
                if parsed_expr["source_column"] not in source_columns:
                    source_columns.append(parsed_expr["source_column"])
            else:
                col = _parse_source_column(fm.source_path)
                binding["source_column"] = col
                if col and col not in source_columns:
                    source_columns.append(col)
        else:
            binding["value_semantic"] = "source"
            col = _parse_source_column(fm.source_path)
            binding["source_column"] = col
            if col and col not in source_columns:
                source_columns.append(col)
        field_bindings.append(binding)

    is_multirow = isinstance(emit_rows, list) and len(emit_rows) > 0
    if is_multirow:
        source_columns = _collect_source_columns_from_emit_rows(emit_rows)
        target_fields = _collect_target_fields_from_emit_rows(emit_rows)
    else:
        target_fields = [b["target_field"] for b in field_bindings]

    resolved_driver_key = template_params.get("driver_key") or ep.driver_key
    # Context binding inference order:
    # 1) explicit impl override (context_target_field)
    # 2) EntityPlans.driver_key target binding (spec-first)
    # 3) engaged_* semantic convention
    # 4) party_id semantic convention
    # 5) customer_id semantic convention (used by account-style entity plans)
    explicit_context_target = str(impl_cfg.get("context_target_field") or "").strip()
    context_binding: Optional[Dict[str, Any]] = None
    if explicit_context_target:
        context_binding = next(
            (
                b
                for b in field_bindings
                if b.get("value_semantic") == "source"
                and b.get("target_field") == explicit_context_target
                and b.get("source_column")
            ),
            None,
        )
    if not context_binding and resolved_driver_key:
        context_binding = next(
            (
                b
                for b in field_bindings
                if b.get("value_semantic") == "source"
                and b.get("target_field") == resolved_driver_key
                and b.get("source_column")
            ),
            None,
        )
    if not context_binding:
        context_binding = next(
            (
                b
                for b in field_bindings
                if b.get("value_semantic") == "source"
                and str(b.get("target_field", "")).startswith("engaged_")
                and b.get("source_column")
            ),
            None,
        )
    if not context_binding:
        context_binding = next(
            (
                b
                for b in field_bindings
                if b.get("value_semantic") == "source"
                and b.get("target_field") == "party_id"
                and b.get("source_column")
            ),
            None,
        )
    if not context_binding:
        context_binding = next(
            (
                b
                for b in field_bindings
                if b.get("value_semantic") == "source"
                and b.get("target_field") == "customer_id"
                and b.get("source_column")
            ),
            None,
        )
    if not context_binding and ep.target_table == "TC_PTY_CNT_MED" and resolved_driver_key:
        context_binding = {
            "target_field": resolved_driver_key,
            "source_column": impl_cfg.get("rename_alias", "party_id"),
        }
    if is_multirow and not context_binding:
        driver_col = None
        for row in emit_rows:
            fields = row.get("fields") if isinstance(row, dict) else None
            if not isinstance(fields, dict):
                continue
            driver_expr = fields.get(resolved_driver_key)
            if isinstance(driver_expr, dict) and driver_expr.get("op") == "PATH":
                driver_col = _parse_source_column(driver_expr.get("path"))
                if driver_col:
                    break
        if driver_col:
            context_binding = {"target_field": resolved_driver_key, "source_column": driver_col}

    parent_rows_field = context_binding.get("target_field") if context_binding else impl_cfg.get("parent_rows_field", "__parent__.1")
    rename_alias = context_binding.get("source_column") if context_binding else impl_cfg.get("rename_alias", "party_id")
    include_population_input = bool(context_binding)
    dargs = _parse_driver_args(ep.driver_args)

    # Parent-scoped templates should expose the driver key as PopulationArgs input,
    # even when field maps do not include an inferable context binding yet.
    if (
        not include_population_input
        and resolved_driver_key
        and "PARENT_SCOPED" in (ep.template_id or "")
    ):
        include_population_input = True
        parent_rows_field = resolved_driver_key
        rename_alias = dargs.get("to") or resolved_driver_key
    # TC_CA_CHAR flows are context-scoped by EntityPlans.driver_key.
    # Keep PopulationArgs external port explicit even when source-only mappings
    # would not infer a context binding.
    if ep.target_table == "TC_CA_CHAR":
        include_population_input = True
        parent_rows_field = resolved_driver_key
        rename_alias = resolved_driver_key
        if dargs.get("to"):
            rename_alias = dargs.get("to") or rename_alias
        rename_strip_prefix = dargs.get("strip_prefix")
    else:
        rename_strip_prefix = None
    luid_sql = impl_cfg.get("luid_sql")
    if include_population_input and not luid_sql:
        projected = _dedupe_keep_order([
            b.get("source_column")
            for b in field_bindings
            if b.get("value_semantic") in {"source", "expr"} and b.get("source_column")
        ])
        if projected:
            luid_sql = f"select {', '.join(projected)} from {resolved_source_system}.{resolved_source_table}"

    return {
        "profile": impl_cfg.get("profile", "multirow_from_columns_parent_scoped" if is_multirow else "snapshot_1to1_parent_scoped"),
        "context": {
            "driver_key": resolved_driver_key,
            "parent_rows_field": parent_rows_field,
            "rename_alias": rename_alias,
            "rename_strip_prefix": rename_strip_prefix,
            "include_population_input": include_population_input,
            "required": impl_cfg.get("context_required", False),
        },
        "source": {
            "interface": resolved_source_interface,
            "system": resolved_source_system,
            "table": resolved_source_table,
            "sql": impl_cfg.get("sql") or f"select * from main.{resolved_source_table}",
            "luid_sql": luid_sql,
            "source_columns": source_columns,
        },
        "load": {
            "target_table": template_params.get("target_table") or ep.target_table,
            "target_interface": template_params.get("target_interface") or "fabric",
            "target_schema": template_params.get("target_schema"),
            "dialect": template_params.get("dialect") or "sqlite",
            "keys": _split_csv(ep.keys),
            "iterate_mode": template_params.get("iterate_mode") or "Iterate",
            "field_bindings": field_bindings,
            "target_fields": target_fields,
        },
        "behavior": {
            "sync_delete": bool(template_params.get("sync_delete")),
            "assert_max_rows": template_params.get("assert_max_rows"),
            "emit_rows": emit_rows if is_multirow else None,
            "row_match_policy": _row_match_policy(ep, is_multirow=is_multirow),
            "latest_by": _latest_by_from_as_of_policy(ep),
        },
    }
