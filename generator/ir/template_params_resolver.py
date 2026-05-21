"""Resolve template parameter values from Template_Params contracts."""

from __future__ import annotations

from collections import OrderedDict
from typing import Any, Dict, List, Optional

from ..spec.spec_model import WorkbookSpec, EntityPlan, FieldMap, TemplateParam, MultiRowRule, EAVRule
from .expression_builder import build_expression_from_parts


def _parse_source_table(source_path: Optional[str]) -> Optional[str]:
    if not source_path:
        return None
    parts = source_path.split(".")
    if len(parts) != 3:
        return None
    return parts[1]


def _default_cast(value: Optional[str], typ: str) -> Any:
    if value is None:
        return None
    t = (typ or "").lower()
    if t == "bool":
        return str(value).strip().lower() in {"1", "true", "y", "yes"}
    if t == "int":
        try:
            return int(str(value).strip())
        except Exception:
            return None
    if t == "json":
        return value
    return value


def _resolve_from_source(source: str, ep: EntityPlan, field_maps: List[FieldMap], project_map: Dict[str, Any]) -> Any:
    s = (source or "").strip()
    if not s:
        return None

    if s.startswith("EntityPlans."):
        attr = s.split(".", 1)[1]
        return getattr(ep, attr, None)

    if "row_policy==SYNC_DELETE" in s:
        return ep.row_policy == "SYNC_DELETE"

    if "multiplicity_expectation==EXPECT_ONE" in s:
        return 1 if ep.multiplicity_expectation == "EXPECT_ONE" else None

    if "FieldMaps grouped by plan_id" in s:
        return project_map

    return None

def _canonical_source_interface(source_system: Optional[str]) -> Optional[str]:
    if not source_system:
        return source_system
    s = str(source_system).strip()
    if not s:
        return s
    if s.upper().endswith("_SYSTEM"):
        return s.upper()
    return f"{s.upper()}_SYSTEM"

def _build_multirow_emit_rows(multirow_rules: List[MultiRowRule]) -> List[Dict[str, Any]]:
    grouped: "OrderedDict[str, Dict[str, Any]]" = OrderedDict()
    for r in sorted(multirow_rules, key=lambda x: (x.row_id, x.row_index)):
        row = grouped.setdefault(
            r.row_id,
            {"row_id": r.row_id, "emit_when": r.emit_when, "fields": OrderedDict()},
        )
        expr = build_expression_from_parts(
            pattern_id=r.pattern_id,
            source_path=r.source_path,
            pattern_args=r.pattern_args,
            transform_rule=None,
        )
        row["fields"][r.target_field] = {"op": expr.op, **expr.args}
        if row.get("emit_when") is None and r.emit_when:
            row["emit_when"] = r.emit_when

    out: List[Dict[str, Any]] = []
    for row in grouped.values():
        out.append(
            {
                "row_id": row["row_id"],
                "emit_when": row.get("emit_when"),
                "fields": dict(row["fields"]),
            }
        )
    return out


def _build_eav_emit_rows(eav_rules: List[EAVRule], emit_when_driver_key: bool = False) -> List[Dict[str, Any]]:
    out: List[Dict[str, Any]] = []
    for idx, r in enumerate(sorted(eav_rules, key=lambda x: x.row_index), start=1):
        fields: Dict[str, Any] = {
            r.driver_key: {"op": "CONTEXT", "context_key": r.driver_key},
        }
        vt = (r.value_type or "").strip()
        if vt.startswith("expr="):
            fields["value_type"] = {"op": "EXPR", "expr": vt.split("=", 1)[1].strip()}
        elif vt.startswith("path="):
            fields["value_type"] = {"op": "PATH", "path": vt.split("=", 1)[1].strip()}
        else:
            fields["value_type"] = {"op": "CONST", "value": r.value_type}
        if r.name_expr:
            fields["name"] = {"op": "EXPR", "expr": r.name_expr}
        else:
            fields["name"] = {"op": "CONST", "value": r.name}

        if r.value_source_path:
            fields["value"] = {"op": "PATH", "path": r.value_source_path}
        elif r.value_expr:
            fields["value"] = {"op": "EXPR", "expr": r.value_expr}
        else:
            fields["value"] = {"op": "CONST", "value": None}

        emit_when = r.driver_key if emit_when_driver_key else None
        if not emit_when and r.value_source_path:
            parts = r.value_source_path.split(".")
            if len(parts) == 3:
                emit_when = parts[2]

        out.append(
            {
                "row_id": f"EAV_{idx}",
                "emit_when": emit_when,
                "fields": fields,
            }
        )
    return out


def resolve_template_params(spec: WorkbookSpec, ep: EntityPlan, field_maps: List[FieldMap], project_map: Dict[str, Any]) -> Dict[str, Any]:
    params: Dict[str, Any] = {}
    tps: List[TemplateParam] = [tp for tp in spec.template_params if tp.template_id == ep.template_id]

    for tp in tps:
        value = _resolve_from_source(tp.source, ep, field_maps, project_map)
        if value is None and "MultiRowRules rows for plan_id" in (tp.source or ""):
            value = _build_multirow_emit_rows(spec.multirow_rules_by_plan.get(ep.plan_id, []))
        if value is None:
            value = _default_cast(tp.default, tp.type)
        params[tp.param_name] = value

    if ep.template_id in {
        "TPL_EAV_FROM_COLUMNS_PARENT_SCOPED",
        "TPL_MULTIROW_TO_EAV_PARENT_SCOPED",
        "TPL_EAV_PARENT_SCOPED",
        "TPL_ARRAY_INPUT_TO_EAV_PARENT_SCOPED",
    } and not params.get("emit_rows"):
        params["emit_rows"] = _build_eav_emit_rows(
            spec.eav_rules_by_plan.get(ep.plan_id, []),
            emit_when_driver_key=(ep.template_id == "TPL_ARRAY_INPUT_TO_EAV_PARENT_SCOPED"),
        )
    if ep.template_id in {"TPL_JOIN_TO_1_PARENT_SCOPED", "TPL_XREF_JOIN_PARENT_SCOPED"} and not params.get("emit_rows"):
        mr_rows = spec.multirow_rules_by_plan.get(ep.plan_id, [])
        if mr_rows:
            params["emit_rows"] = _build_multirow_emit_rows(mr_rows)

    # Runtime-related convenience defaults for templates that do not define all params yet.
    inferred_source_table = next((_parse_source_table(fm.source_path) for fm in field_maps if _parse_source_table(fm.source_path)), None)
    params.setdefault("source_interface", ep.source_interface or _canonical_source_interface(ep.source_system))
    params.setdefault("source_system", ep.source_system)
    params.setdefault("source_table", ep.source_table or inferred_source_table)
    params.setdefault("target_interface", ep.target_interface or "fabric")
    params.setdefault("target_schema", ep.target_schema)
    params.setdefault("target_table", ep.target_table)
    params.setdefault("driver_key", ep.driver_key)
    params.setdefault("dialect", ep.dialect or "sqlite")
    params.setdefault("iterate_mode", ep.iterate_mode or "Iterate")
    params.setdefault("row_policy", ep.row_policy)
    params.setdefault("as_of_policy", ep.as_of_policy)
    params.setdefault("multiplicity_expectation", ep.multiplicity_expectation)

    return params
