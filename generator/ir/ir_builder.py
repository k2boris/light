"""IR builder (COM + execution plans)."""

from __future__ import annotations
import logging
from typing import Dict, Any, List
from datetime import datetime

from ..ddl.schema_model import Schema
from ..spec.spec_model import WorkbookSpec
from ..validate.report_model import ValidationReport
from .ir_model import IRBundle, COMPlan, COMOperation, ExecutionPlan
from .expression_builder import build_expression
from .runtime_compiler import compile_runtimes
from .template_params_resolver import resolve_template_params

logger = logging.getLogger(__name__)


def _split_csv(value: str) -> List[str]:
    return [x.strip() for x in (value or "").split(",") if x.strip()]


def _build_com_operations(ep, field_maps, project_map, template_params) -> List[COMOperation]:
    ops: List[COMOperation] = [
        COMOperation(
            op_id="op_source_read",
            kind="SelectEntity",
            params={"from": f"{ep.source_system}.{ep.source_table}"},
        ),
        COMOperation(
            op_id="op_context_filter",
            kind="ConstrainByContext",
            params={
                "input": "op_source_read",
                "context_key": template_params.get("driver_key") or ep.driver_key,
                "source_field": template_params.get("driver_key") or ep.driver_key,
                "required": False,
            },
        ),
    ]

    assert_max_rows = template_params.get("assert_max_rows")
    input_for_project = "op_context_filter"
    if assert_max_rows is not None:
        ops.append(
            COMOperation(
                op_id="op_assert_cardinality",
                kind="AssertCardinality",
                params={
                    "input": "op_context_filter",
                    "max_rows": assert_max_rows,
                    "scope": "per_driver",
                },
            )
        )
        input_for_project = "op_assert_cardinality"

    emit_rows = template_params.get("emit_rows")
    if isinstance(emit_rows, list) and emit_rows:
        ops.append(
            COMOperation(
                op_id="op_emit_rows",
                kind="EmitRows",
                params={"input": input_for_project, "rows": emit_rows},
            )
        )
        persist_input = "op_emit_rows"
    else:
        mappings: List[Dict[str, Any]] = []
        for fm in sorted(field_maps, key=lambda x: x.target_field):
            mappings.append(
                {
                    "target_field": fm.target_field,
                    "expr": project_map.get(fm.target_field, {"op": "UNKNOWN"}),
                }
            )
        ops.append(
            COMOperation(
                op_id="op_project",
                kind="ProjectAttributes",
                params={"input": input_for_project, "mappings": mappings},
            )
        )
        persist_input = "op_project"

    ops.append(
        COMOperation(
            op_id="op_persist",
            kind="PersistEntity",
            params={
                "input": persist_input,
                "target_entity": ep.target_table,
                "mode": "UPSERT",
                "keys": _split_csv(ep.keys),
            },
        )
    )
    return ops

def build_ir_bundle(spec: WorkbookSpec, canonical: Schema, sources: Dict[str, Schema], report: ValidationReport, strict: bool = True) -> IRBundle:
    bundle = IRBundle(meta={
        "generated_at": datetime.utcnow().isoformat() + "Z",
        "strict": strict,
        "canonical_schema": canonical.name,
        "source_systems": sorted(list(sources.keys())),
        "validation": {"errors": len(report.errors), "warnings": len(report.warnings)},
    })

    # Dictionaries: group by name
    dicts: Dict[str, Dict[str, Any]] = {}
    for d in spec.dictionaries:
        dicts.setdefault(d.name, {})[d.key] = d.value
    bundle.dictionaries = dicts

    # Deterministic plan order
    plans = sorted(spec.entity_plans.values(), key=lambda ep: (ep.target_table, ep.source_system, ep.source_table))
    for ep in plans:
        logger.info("Building plan IR", extra={"phase":"IR", "tab":"EntityPlans", "row":ep.row_index, "plan_id":ep.plan_id})

        field_maps = spec.field_maps_by_plan.get(ep.plan_id, [])

        # Build projection expressions from FieldMaps for this plan.
        proj: Dict[str, Any] = {}
        for fm in sorted(field_maps, key=lambda x: x.target_field):
            expr = build_expression(spec, fm)
            proj[fm.target_field] = {"op": expr.op, **expr.args}

        params = resolve_template_params(spec, ep, field_maps, proj)
        operations = _build_com_operations(ep, field_maps, proj, params)
        runtimes = compile_runtimes(spec, ep, field_maps, params, sources=sources)

        plan_ir = COMPlan(
            plan_id=ep.plan_id,
            template_id=ep.template_id,
            target={
                "entity": ep.target_table,
                "keys": _split_csv(ep.keys),
            },
            source={
                "system": ep.source_system,
                "table": ep.source_table,
            },
            contract={
                "driver_key": ep.driver_key,
                "row_policy": ep.row_policy,
                "as_of_policy": ep.as_of_policy,
                "multiplicity_expectation": ep.multiplicity_expectation,
            },
            params=params,
            operations=operations,
            lineage={
                "source_entity": ep.source_entity,
                "target_table": ep.target_table,
            },
        )

        bundle.plans.append(plan_ir)
        for runtime_name, runtime_spec in runtimes.items():
            bundle.execution_plans.append(
                ExecutionPlan(
                    runtime=runtime_name,
                    plan_id=ep.plan_id,
                    template_id=ep.template_id,
                    spec=runtime_spec,
                )
            )

    return bundle
