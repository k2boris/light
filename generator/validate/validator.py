"""Validation orchestrator.

We validate in deterministic phases:
0) Preflight (tabs/columns already in loader; DDL parse handled in CLI)
1) Library tabs
2) EntityPlans
3) FieldMaps
4) EAVRules
5) MultiRowRules
6) Dictionaries
7) Overrides
8) Cross-tab consistency

This file orchestrates and logs phase boundaries. Individual rule modules keep logic isolated.
"""

from __future__ import annotations

import json
import logging
import re
from typing import Dict

from ..ddl.schema_model import Schema
from ..spec.spec_model import WorkbookSpec
from ..join_notation import (
    parse_join_key,
    resolve_node,
    normalize_system_name,
    table_path_exists,
    join_condition,
)
from .report_model import ValidationReport

logger = logging.getLogger(__name__)

PLAN_ID_RE = re.compile(r"^([A-Za-z0-9_-]+)__([A-Za-z0-9_-]+)__([A-Za-z0-9_-]+)$")

def validate_all(spec: WorkbookSpec, canonical: Schema, sources: Dict[str, Schema], strict: bool = True) -> ValidationReport:
    report = ValidationReport(meta={"strict": strict})

    _validate_library(spec, report)
    _validate_entity_plans(spec, canonical, sources, report, strict=strict)
    _validate_field_maps(spec, canonical, sources, report, strict=strict)
    _validate_eav_rules(spec, canonical, sources, report, strict=strict)
    _validate_multirow_rules(spec, canonical, sources, report, strict=strict)
    _validate_dictionaries(spec, report)
    _validate_overrides(spec, report)
    _validate_cross_tab(spec, canonical, report)

    logger.info(
        f"Validation complete: errors={len(report.errors)} warnings={len(report.warnings)}",
        extra={"phase":"VALIDATE"}
    )
    return report

def _validate_library(spec: WorkbookSpec, report: ValidationReport) -> None:
    phase = "LIB"
    # Templates JSON must parse
    for tid, t in spec.templates.items():
        try:
            json.loads(t.ir_skeleton_json or "{}")
        except Exception as e:
            report.add_error(
                code="E110_TEMPLATE_JSON",
                message=f"Template ir_skeleton_json is not valid JSON: {e}",
                phase=phase, tab="Templates", row=t.row_index, plan_id=None,
                details={"template_id": tid}
            )
            logger.error("Invalid template JSON", extra={"phase":phase, "tab":"Templates", "row":t.row_index, "plan_id":"-"})

    # Template_Params must reference existing template_id
    for tp in spec.template_params:
        if tp.template_id not in spec.templates:
            report.add_error(
                code="E111_TEMPLATE_PARAM_REF",
                message="Template_Params.template_id not found in Templates",
                phase=phase, tab="Template_Params", row=tp.row_index, plan_id=None,
                details={"template_id": tp.template_id, "param_name": tp.param_name}
            )

    # Patterns must be present (already keyed)
    if not spec.patterns:
        report.add_error(
            code="E112_NO_PATTERNS",
            message="No patterns found in Patterns tab",
            phase=phase, tab="Patterns", row=1, plan_id=None
        )

    # BroadwayActors.template_id must reference Templates
    for ba in spec.broadway_actors:
        if ba.template_id not in spec.templates:
            report.add_error(
                code="E113_BROADWAY_TEMPLATE_REF",
                message="BroadwayActors.template_id not found in Templates",
                phase=phase, tab="BroadwayActors", row=ba.row_index, plan_id=None,
                details={"template_id": ba.template_id, "actor_id": ba.actor_id}
            )

    # TemplateImplementations validity
    seen_impl = set()
    allowed_runtimes = {"broadway", "python"}
    for ti in spec.template_implementations:
        if ti.template_id not in spec.templates:
            report.add_error(
                code="E114_TEMPLATE_IMPL_REF",
                message="TemplateImplementations.template_id not found in Templates",
                phase=phase, tab="TemplateImplementations", row=ti.row_index, plan_id=None,
                details={"template_id": ti.template_id, "runtime": ti.runtime}
            )
        if ti.runtime not in allowed_runtimes:
            report.add_error(
                code="E115_TEMPLATE_IMPL_RUNTIME",
                message="TemplateImplementations.runtime must be one of: broadway, python",
                phase=phase, tab="TemplateImplementations", row=ti.row_index, plan_id=None,
                details={"template_id": ti.template_id, "runtime": ti.runtime}
            )
        key = (ti.template_id, ti.runtime)
        if key in seen_impl:
            report.add_error(
                code="E116_TEMPLATE_IMPL_DUP",
                message="Duplicate TemplateImplementations row for (template_id, runtime)",
                phase=phase, tab="TemplateImplementations", row=ti.row_index, plan_id=None,
                details={"template_id": ti.template_id, "runtime": ti.runtime}
            )
        seen_impl.add(key)

def _validate_entity_plans(spec: WorkbookSpec, canonical: Schema, sources: Dict[str, Schema], report: ValidationReport, strict: bool) -> None:
    phase = "EP"
    allowed_match_policies = {"EXPECT_ONE", "ALLOW_MANY", "EXPECT_MANY", "ONE_ONLY", "ZERO_OR_ONE", "MULTIPLE", "LATEST", ""}
    for plan_id, ep in spec.entity_plans.items():
        logger.debug("Validating EntityPlan", extra={"phase":phase, "tab":"EntityPlans", "row":ep.row_index, "plan_id":plan_id})

        # plan_id format
        if not PLAN_ID_RE.match(plan_id):
            report.add_error(
                code="E200_PLAN_ID_FORMAT",
                message="plan_id does not match <target_table>__<source_system>__<source_table>",
                phase=phase, tab="EntityPlans", row=ep.row_index, plan_id=plan_id
            )
            continue

        # target_table exists
        t = canonical.get_table(ep.target_table)
        if t is None:
            report.add_error(
                code="E201_TARGET_TABLE_MISSING",
                message=f"target_table '{ep.target_table}' not found in canonical DDL",
                phase=phase, tab="EntityPlans", row=ep.row_index, plan_id=plan_id
            )
        else:
            # keys match PK (best-effort)
            pk = [c.strip() for c in ep.keys.split(",") if c.strip()]
            if t.primary_key.columns and pk != t.primary_key.columns:
                report.add_warning(
                    code="W202_KEYS_MISMATCH",
                    message=f"EntityPlans.keys does not match canonical PK order. spec={pk} ddl={t.primary_key.columns}",
                    phase=phase, tab="EntityPlans", row=ep.row_index, plan_id=plan_id
                )

        # template exists
        if ep.template_id not in spec.templates:
            report.add_error(
                code="E203_TEMPLATE_MISSING",
                message=f"template_id '{ep.template_id}' not found in Templates tab",
                phase=phase, tab="EntityPlans", row=ep.row_index, plan_id=plan_id
            )

        # source system/table exists
        if ep.source_system not in sources:
            report.add_error(
                code="E204_SOURCE_SYSTEM_MISSING",
                message=f"source_system '{ep.source_system}' not provided via --source-ddl",
                phase=phase, tab="EntityPlans", row=ep.row_index, plan_id=plan_id
            )
            continue
        st = sources[ep.source_system].get_table(ep.source_table)
        if st is None:
            report.add_error(
                code="E205_SOURCE_TABLE_MISSING",
                message=f"source_table '{ep.source_table}' not found in source DDL for {ep.source_system}",
                phase=phase, tab="EntityPlans", row=ep.row_index, plan_id=plan_id
            )

        if (ep.multiplicity_expectation or "").strip().upper() not in allowed_match_policies:
            report.add_error(
                code="E206_ROW_MATCH_POLICY",
                message="multiplicity_expectation must be one of EXPECT_ONE, ALLOW_MANY, EXPECT_MANY, ONE_ONLY, ZERO_OR_ONE, MULTIPLE, LATEST",
                phase=phase, tab="EntityPlans", row=ep.row_index, plan_id=plan_id,
                details={"multiplicity_expectation": ep.multiplicity_expectation},
            )

def _parse_source_path(sp: str):
    parts = sp.split(".")
    if len(parts) != 3:
        return None
    return parts[0], parts[1], parts[2]

def _validate_field_maps(spec: WorkbookSpec, canonical: Schema, sources: Dict[str, Schema], report: ValidationReport, strict: bool) -> None:
    phase = "FM"
    for fm in spec.field_maps:
        logger.debug("Validating FieldMap", extra={"phase":phase, "tab":"FieldMaps", "row":fm.row_index, "plan_id":fm.plan_id})

        ep = spec.entity_plans.get(fm.plan_id)
        if ep is None:
            report.add_error(
                code="E300_PLAN_REF_MISSING",
                message="FieldMaps.plan_id not found in EntityPlans",
                phase=phase, tab="FieldMaps", row=fm.row_index, plan_id=fm.plan_id
            )
            continue

        # target_table match
        if fm.target_table != ep.target_table:
            report.add_warning(
                code="W301_TARGET_TABLE_MISMATCH",
                message=f"FieldMaps.target_table '{fm.target_table}' != EntityPlans.target_table '{ep.target_table}'",
                phase=phase, tab="FieldMaps", row=fm.row_index, plan_id=fm.plan_id
            )

        # target_field exists in canonical
        t = canonical.get_table(ep.target_table)
        if t and not t.get_column(fm.target_field):
            report.add_error(
                code="E302_TARGET_FIELD_MISSING",
                message=f"target_field '{fm.target_field}' not found in canonical table '{ep.target_table}'",
                phase=phase, tab="FieldMaps", row=fm.row_index, plan_id=fm.plan_id
            )

        # pattern exists
        if fm.pattern_id not in spec.patterns:
            report.add_error(
                code="E303_PATTERN_MISSING",
                message=f"pattern_id '{fm.pattern_id}' not found in Patterns tab",
                phase=phase, tab="FieldMaps", row=fm.row_index, plan_id=fm.plan_id
            )

        # source_path validity
        if fm.source_path:
            parsed = _parse_source_path(fm.source_path)
            if not parsed:
                report.add_error(
                    code="E304_SOURCE_PATH_FORMAT",
                    message="source_path must be <source_system>.<source_table>.<source_column>",
                    phase=phase, tab="FieldMaps", row=fm.row_index, plan_id=fm.plan_id,
                    details={"source_path": fm.source_path}
                )
            else:
                sys, table, col = parsed
                if strict:
                    if (
                        sys != ep.source_system
                        or (
                            table != ep.source_table
                            and ep.template_id
                            not in {
                                "TPL_JOIN_TO_1_PARENT_SCOPED",
                                "TPL_XREF_JOIN_PARENT_SCOPED",
                                "TPL_ARRAY_INPUT_TO_COLUMNS_PARENT_SCOPED",
                            }
                        )
                    ):
                        if ep.template_id == "TPL_ARRAY_INPUT_TO_COLUMNS_PARENT_SCOPED" and sys == "Input":
                            pass
                        else:
                            report.add_error(
                                code="E305_SOURCE_PATH_SCOPE",
                                message="source_path system/table must match plan's source_system/source_table in strict mode",
                                phase=phase, tab="FieldMaps", row=fm.row_index, plan_id=fm.plan_id,
                                details={"source_path": fm.source_path, "plan_source": f"{ep.source_system}.{ep.source_table}"}
                            )
                if ep.template_id == "TPL_ARRAY_INPUT_TO_COLUMNS_PARENT_SCOPED" and sys == "Input":
                    continue
                if sys in sources:
                    st = sources[sys].get_table(table)
                    if st and not st.get_column(col):
                        report.add_error(
                            code="E306_SOURCE_COLUMN_MISSING",
                            message=f"source column '{col}' not found in '{sys}.{table}'",
                            phase=phase, tab="FieldMaps", row=fm.row_index, plan_id=fm.plan_id,
                            details={"source_path": fm.source_path}
                        )
        if fm.join_key:
            jk = str(fm.join_key)
            has_notation = ("->" in jk) or ("-->" in jk) or ("→" in jk)
            if has_notation or ep.template_id in {"TPL_JOIN_TO_1_PARENT_SCOPED", "TPL_XREF_JOIN_PARENT_SCOPED"}:
                _validate_join_key(
                    join_key=fm.join_key,
                    ep_source_system=ep.source_system,
                    sources=sources,
                    report=report,
                    phase=phase,
                    tab="FieldMaps",
                    row=fm.row_index,
                    plan_id=fm.plan_id,
                )

def _validate_eav_rules(spec: WorkbookSpec, canonical: Schema, sources: Dict[str, Schema], report: ValidationReport, strict: bool) -> None:
    phase = "EAV"
    for er in spec.eav_rules:
        logger.debug("Validating EAVRule", extra={"phase":phase, "tab":"EAVRules", "row":er.row_index, "plan_id":er.plan_id})

        ep = spec.entity_plans.get(er.plan_id)
        if ep is None:
            report.add_error(
                code="E400_PLAN_REF_MISSING",
                message="EAVRules.plan_id not found in EntityPlans",
                phase=phase, tab="EAVRules", row=er.row_index, plan_id=er.plan_id
            )
            continue

        # XOR name vs name_expr
        if bool(er.name) == bool(er.name_expr):
            report.add_error(
                code="E401_NAME_XOR",
                message="Exactly one of name or name_expr must be provided",
                phase=phase, tab="EAVRules", row=er.row_index, plan_id=er.plan_id
            )

        # value required
        if not er.value_source_path and not er.value_expr:
            report.add_error(
                code="E402_VALUE_REQUIRED",
                message="At least one of value_source_path or value_expr must be provided",
                phase=phase, tab="EAVRules", row=er.row_index, plan_id=er.plan_id
            )

        # value_source_path validation
        if er.value_source_path:
            parsed = _parse_source_path(er.value_source_path)
            if not parsed:
                report.add_error(
                    code="E403_SOURCE_PATH_FORMAT",
                    message="value_source_path must be <source_system>.<source_table>.<source_column>",
                    phase=phase, tab="EAVRules", row=er.row_index, plan_id=er.plan_id,
                    details={"value_source_path": er.value_source_path}
                )
            else:
                sys, table, col = parsed
                if strict and (sys != ep.source_system or table != ep.source_table):
                    if not (ep.template_id == "TPL_ARRAY_INPUT_TO_EAV_PARENT_SCOPED" and sys == "Input"):
                        report.add_error(
                            code="E404_SOURCE_PATH_SCOPE",
                            message="value_source_path system/table must match plan's source in strict mode",
                            phase=phase, tab="EAVRules", row=er.row_index, plan_id=er.plan_id,
                            details={"value_source_path": er.value_source_path, "plan_source": f"{ep.source_system}.{ep.source_table}"}
                        )
                if ep.template_id == "TPL_ARRAY_INPUT_TO_EAV_PARENT_SCOPED" and sys == "Input":
                    continue
                if sys in sources:
                    st = sources[sys].get_table(table)
                    if st and not st.get_column(col):
                        report.add_error(
                            code="E405_SOURCE_COLUMN_MISSING",
                            message=f"source column '{col}' not found in '{sys}.{table}'",
                            phase=phase, tab="EAVRules", row=er.row_index, plan_id=er.plan_id
                        )

def _validate_dictionaries(spec: WorkbookSpec, report: ValidationReport) -> None:
    phase = "DICT"
    seen = set()
    for d in spec.dictionaries:
        key = (d.dict_type, d.name, d.key)
        if key in seen:
            report.add_error(
                code="E500_DUP_DICT_KEY",
                message="Duplicate dictionary key for (dict_type, name, key)",
                phase=phase, tab="Dictionaries", row=d.row_index, plan_id=None,
                details={"dict_type": d.dict_type, "name": d.name, "key": d.key}
            )
        seen.add(key)

def _validate_multirow_rules(spec: WorkbookSpec, canonical: Schema, sources: Dict[str, Schema], report: ValidationReport, strict: bool) -> None:
    phase = "MR"
    for mr in spec.multirow_rules:
        logger.debug("Validating MultiRowRule", extra={"phase":phase, "tab":"MultiRowRules", "row":mr.row_index, "plan_id":mr.plan_id})
        ep = spec.entity_plans.get(mr.plan_id)
        if ep is None:
            report.add_error(
                code="E450_PLAN_REF_MISSING",
                message="MultiRowRules.plan_id not found in EntityPlans",
                phase=phase, tab="MultiRowRules", row=mr.row_index, plan_id=mr.plan_id
            )
            continue

        if mr.pattern_id not in spec.patterns:
            report.add_error(
                code="E451_PATTERN_MISSING",
                message=f"pattern_id '{mr.pattern_id}' not found in Patterns tab",
                phase=phase, tab="MultiRowRules", row=mr.row_index, plan_id=mr.plan_id
            )

        t = canonical.get_table(ep.target_table)
        if t and not t.get_column(mr.target_field):
            report.add_error(
                code="E452_TARGET_FIELD_MISSING",
                message=f"target_field '{mr.target_field}' not found in canonical table '{ep.target_table}'",
                phase=phase, tab="MultiRowRules", row=mr.row_index, plan_id=mr.plan_id
            )

        if mr.source_path:
            parsed = _parse_source_path(mr.source_path)
            if not parsed:
                report.add_error(
                    code="E453_SOURCE_PATH_FORMAT",
                    message="source_path must be <source_system>.<source_table>.<source_column>",
                    phase=phase, tab="MultiRowRules", row=mr.row_index, plan_id=mr.plan_id,
                    details={"source_path": mr.source_path}
                )
            else:
                sys, table, col = parsed
                if strict and (sys != ep.source_system or table != ep.source_table):
                    report.add_error(
                        code="E454_SOURCE_PATH_SCOPE",
                        message="source_path system/table must match plan's source_system/source_table in strict mode",
                        phase=phase, tab="MultiRowRules", row=mr.row_index, plan_id=mr.plan_id,
                        details={"source_path": mr.source_path, "plan_source": f"{ep.source_system}.{ep.source_table}"}
                    )
                if sys in sources:
                    st = sources[sys].get_table(table)
                    if st and not st.get_column(col):
                        report.add_error(
                            code="E455_SOURCE_COLUMN_MISSING",
                            message=f"source column '{col}' not found in '{sys}.{table}'",
                            phase=phase, tab="MultiRowRules", row=mr.row_index, plan_id=mr.plan_id
                        )

def _validate_join_key(
    join_key: str,
    ep_source_system: str,
    sources: Dict[str, Schema],
    report: ValidationReport,
    phase: str,
    tab: str,
    row: int,
    plan_id: str,
) -> None:
    parsed = parse_join_key(join_key)
    for err in parsed.get("errors", []):
        report.add_error(
            code="E307_JOIN_KEY_SYNTAX",
            message=f"Invalid join_key syntax: {err}",
            phase=phase, tab=tab, row=row, plan_id=plan_id, details={"join_key": join_key},
        )
        return

    resolved = []
    for n in parsed["nodes"]:
        rn = resolve_node(n, ep_source_system, sources)
        if not rn.get("ok"):
            report.add_error(
                code="E308_JOIN_KEY_NODE",
                message=f"Invalid join_key node: {rn.get('error')}",
                phase=phase, tab=tab, row=row, plan_id=plan_id, details={"join_key": join_key, "node": n.get("raw")},
            )
            return
        resolved.append(rn)

    ops = parsed["ops"]
    for i, op in enumerate(ops):
        left = resolved[i]
        right = resolved[i + 1]
        if op == "->":
            ls = normalize_system_name(left.get("system"))
            rs = normalize_system_name(right.get("system"))
            if ls and rs and ls != rs:
                report.add_error(
                    code="E309_JOIN_KEY_OPERATOR",
                    message="Use '-->' for cross-system bridge hops",
                    phase=phase, tab=tab, row=row, plan_id=plan_id, details={"join_key": join_key},
                )
                return
            # context_col -> table.col is allowed for driver-key hints
            if left.get("table") and right.get("table") and left.get("table") != right.get("table"):
                schema = None
                for k, s in sources.items():
                    if normalize_system_name(k) == (ls or rs):
                        schema = s
                        break
                if schema and not table_path_exists(schema, left["table"], right["table"]):
                    # Some source DDLs do not expose FK metadata to the parser;
                    # allow direct hop when a join condition can still be inferred.
                    if join_condition(schema, left["table"], right["table"]):
                        continue
                    report.add_error(
                        code="E310_JOIN_KEY_CONNECTIVITY",
                        message="No join path found between hop tables in schema graph",
                        phase=phase, tab=tab, row=row, plan_id=plan_id,
                        details={"join_key": join_key, "from": left["table"], "to": right["table"]},
                    )
                    return

def _validate_overrides(spec: WorkbookSpec, report: ValidationReport) -> None:
    phase = "OVR"
    import json
    for o in spec.overrides:
        try:
            json.loads(o.params or "{}")
        except Exception as e:
            report.add_error(
                code="E600_OVERRIDE_JSON",
                message=f"Override params is not valid JSON: {e}",
                phase=phase, tab="Overrides", row=o.row_index, plan_id=o.plan_id or None
            )

def _validate_cross_tab(spec: WorkbookSpec, canonical: Schema, report: ValidationReport) -> None:
    phase = "X"
    # Detect duplicates for same (plan_id, target_field)
    from collections import defaultdict
    bucket = defaultdict(list)
    for fm in spec.field_maps:
        bucket[(fm.plan_id, fm.target_field)].append(fm)

    for (plan_id, target_field), rows in bucket.items():
        if len(rows) > 1:
            report.add_error(
                code="E700_DUP_FIELD_MAP",
                message="Multiple FieldMaps rows for same (plan_id, target_field); add PRECEDENCE override or remove duplicates",
                phase=phase, tab="FieldMaps", row=min(r.row_index for r in rows), plan_id=plan_id,
                details={"target_field": target_field, "rows": [r.row_index for r in rows]}
            )

    multirow_plan_ids = {
        ep.plan_id
        for ep in spec.entity_plans.values()
        if ep.template_id == "TPL_MULTIROW_FROM_COLUMNS_PARENT_SCOPED"
    }
    for plan_id in sorted(multirow_plan_ids):
        if not spec.multirow_rules_by_plan.get(plan_id):
            ep = spec.entity_plans[plan_id]
            report.add_error(
                code="E701_MULTIROW_RULES_REQUIRED",
                message="MultiRow template plan requires at least one MultiRowRules row",
                phase=phase, tab="EntityPlans", row=ep.row_index, plan_id=plan_id
            )
