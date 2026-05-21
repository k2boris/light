"""Python runtime compilation from template implementation metadata."""

from __future__ import annotations

import json
from typing import Any, Dict, List, Optional

from ..spec.spec_model import WorkbookSpec, EntityPlan, FieldMap
from ..ddl.schema_model import Schema


def _target_fields_from_multirow(template_params: Dict[str, Any]) -> List[str]:
    out: List[str] = []
    seen = set()
    for row in template_params.get("emit_rows") or []:
        fields = row.get("fields") if isinstance(row, dict) else None
        if not isinstance(fields, dict):
            continue
        for f in fields.keys():
            if f not in seen:
                seen.add(f)
                out.append(f)
    return out


def compile_python_plan(
    spec: WorkbookSpec,
    ep: EntityPlan,
    field_maps: List[FieldMap],
    template_params: Dict[str, Any],
    sources: Optional[Dict[str, Schema]] = None,
) -> Dict[str, Any]:
    t_impl = spec.template_impls_by_template.get(ep.template_id, {}).get("python")
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

    payload: Dict[str, Any] = {}
    if t_impl and t_impl.impl_json:
        try:
            parsed = json.loads(t_impl.impl_json)
            if isinstance(parsed, dict):
                payload = parsed
        except Exception:
            payload = {}

    payload.setdefault("module", f"pipelines.{ep.template_id.lower()}")
    payload.setdefault("callable", "run")
    payload.setdefault("args", {})
    target_fields = [fm.target_field for fm in field_maps]
    if not target_fields:
        target_fields = _target_fields_from_multirow(template_params)
    payload["args"].setdefault("target_table", template_params.get("target_table") or ep.target_table)
    payload["args"].setdefault("source_system", template_params.get("source_system") or ep.source_system)
    payload["args"].setdefault("source_table", template_params.get("source_table") or ep.source_table)
    payload["args"].setdefault("source_interface", template_params.get("source_interface"))
    payload["args"].setdefault("driver_key", template_params.get("driver_key") or ep.driver_key)
    payload["args"].setdefault("target_fields", target_fields)
    if template_params.get("emit_rows"):
        payload["args"].setdefault("emit_rows", template_params.get("emit_rows"))
    if ep.template_id in {"TPL_JOIN_TO_1_PARENT_SCOPED", "TPL_XREF_JOIN_PARENT_SCOPED"}:
        payload["args"].setdefault(
            "join_key_notation",
            [
                {
                    "target_field": fm.target_field,
                    "source_path": fm.source_path,
                    "join_key": fm.join_key,
                    "pattern_id": fm.pattern_id,
                    "pattern_args": fm.pattern_args,
                }
                for fm in field_maps
                if fm.join_key
            ],
        )
    return payload
