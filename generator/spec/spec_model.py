"""Spec dataclasses for V4.1 workbook.

The loader should:
- read required tabs
- enforce required columns
- normalize strings (strip, None for empty)
- store row_index for actionable errors

We treat the Excel workbook as the ground truth for mapping WHAT.
"""

from __future__ import annotations
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Any

@dataclass(frozen=True)
class EntityPlan:
    row_index: int
    plan_id: str
    target_table: str
    target_entity: Optional[str]
    target_grain: str
    keys: str
    source_system: str
    source_table: str
    source_entity: str
    template_id: str
    driver_key: str
    driver_args: Optional[str]
    row_policy: str
    multiplicity_expectation: str
    as_of_policy: str
    source_interface: Optional[str] = None
    target_interface: Optional[str] = None
    target_schema: Optional[str] = None
    dialect: Optional[str] = None
    iterate_mode: Optional[str] = None
    notes: Optional[str] = None

@dataclass(frozen=True)
class FieldMap:
    row_index: int
    plan_id: str
    target_table: str
    target_field: str
    target_description: Optional[str]
    source_path: Optional[str]
    pattern_id: str
    pattern_args: Optional[str]
    required: str
    default: Optional[str]
    transform_rule: Optional[str]
    join_key: Optional[str]
    notes: Optional[str]

@dataclass(frozen=True)
class EAVRule:
    row_index: int
    plan_id: str
    target_table: str
    driver_key: str
    name: Optional[str]
    name_expr: Optional[str]
    value_source_path: Optional[str]
    value_expr: Optional[str]
    value_type: str
    join_key: Optional[str]
    notes: Optional[str]
    transform_rule: Optional[str]

@dataclass(frozen=True)
class MultiRowRule:
    row_index: int
    plan_id: str
    row_id: str
    emit_when: Optional[str]
    target_field: str
    pattern_id: str
    source_path: Optional[str]
    pattern_args: Optional[str]
    required: str
    notes: Optional[str]

@dataclass(frozen=True)
class DictEntry:
    row_index: int
    dict_type: str
    name: str
    key: str
    value: str
    notes: Optional[str]

@dataclass(frozen=True)
class Override:
    row_index: int
    plan_id: Optional[str]
    target_table: Optional[str]
    override_type: str
    name: str
    params: str
    notes: Optional[str]

@dataclass(frozen=True)
class TemplateDef:
    row_index: int
    template_id: str
    version: str
    description: str
    ir_skeleton_json: str
    notes: Optional[str]

@dataclass(frozen=True)
class TemplateParam:
    row_index: int
    template_id: str
    param_name: str
    required: str
    type: str
    default: Optional[str]
    source: str
    notes: Optional[str]

@dataclass(frozen=True)
class PatternDef:
    row_index: int
    pattern_id: str
    version: str
    description: str
    expr_template: str
    required_inputs: str
    notes: Optional[str]

@dataclass(frozen=True)
class BroadwayActor:
    row_index: int
    template_id: str
    stage: str
    actor_id: str
    parent: str
    enabled: str
    in_json: Optional[str]
    out_json: Optional[str]
    notes: Optional[str]

@dataclass(frozen=True)
class TemplateImplementation:
    row_index: int
    template_id: str
    runtime: str
    enabled: str
    impl_json: Optional[str]
    notes: Optional[str]

@dataclass
class WorkbookSpec:
    entity_plans: Dict[str, EntityPlan] = field(default_factory=dict)
    field_maps: List[FieldMap] = field(default_factory=list)
    eav_rules: List[EAVRule] = field(default_factory=list)
    multirow_rules: List[MultiRowRule] = field(default_factory=list)
    dictionaries: List[DictEntry] = field(default_factory=list)
    overrides: List[Override] = field(default_factory=list)
    templates: Dict[str, TemplateDef] = field(default_factory=dict)
    template_params: List[TemplateParam] = field(default_factory=list)
    patterns: Dict[str, PatternDef] = field(default_factory=dict)
    broadway_actors: List[BroadwayActor] = field(default_factory=list)
    template_implementations: List[TemplateImplementation] = field(default_factory=list)

    # Convenience indexes built post-load (optional in loader)
    field_maps_by_plan: Dict[str, List[FieldMap]] = field(default_factory=dict)
    eav_rules_by_plan: Dict[str, List[EAVRule]] = field(default_factory=dict)
    multirow_rules_by_plan: Dict[str, List[MultiRowRule]] = field(default_factory=dict)
    broadway_actors_by_template: Dict[str, List[BroadwayActor]] = field(default_factory=dict)
    template_impls_by_template: Dict[str, Dict[str, TemplateImplementation]] = field(default_factory=dict)
