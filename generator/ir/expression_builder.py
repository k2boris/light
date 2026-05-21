"""Expression builder: FieldMaps/EAVRules + Patterns -> Expression trees.

This module is where engine-neutral *intent* becomes a structured expression model.

Patterns baseline:
- P_DIRECT: PATH(source_path)
- P_CONST: CONST(value=...)
- P_NOW: NOW()
- P_ENUM_MAP: ENUM_MAP(map_name, input_expr)
- P_EXPR: EXPR(expr_intent_string, optional_inputs)

This file is currently a stub; implementers should keep it deterministic and well-logged.
"""

from __future__ import annotations
import logging
from typing import Dict, Optional

from ..spec.spec_model import FieldMap, WorkbookSpec
from .ir_model import Expression

logger = logging.getLogger(__name__)

def parse_pattern_args(pattern_args: Optional[str]) -> Dict[str, str]:
    """Parse pattern_args from key=value;key=value format.

    Deterministic parsing rules:
    - pairs separated by ';'
    - key and value separated by first '='
    - whitespace around key/value trimmed
    - empty input -> {}
    """
    if not pattern_args:
        return {}
    out: Dict[str, str] = {}
    parts = [p.strip() for p in pattern_args.split(';') if p.strip()]
    for p in parts:
        if '=' not in p:
            # Allow flags like "trim" as key with value "true"
            out[p] = "true"
            continue
        k, v = p.split('=', 1)
        out[k.strip()] = v.strip()
    return out

def build_expression_from_parts(pattern_id: str, source_path: Optional[str], pattern_args: Optional[str], transform_rule: Optional[str]) -> Expression:
    """Build a structured Expression from generic mapping parts."""
    args = parse_pattern_args(pattern_args)

    if pattern_id == "P_DIRECT":
        return Expression(op="PATH", args={"path": source_path})
    if pattern_id == "P_CONST":
        return Expression(op="CONST", args={"value": args.get("value")})
    if pattern_id == "P_NOW":
        return Expression(op="NOW", args={})
    if pattern_id == "P_ENUM_MAP":
        return Expression(op="ENUM_MAP", args={
            "map": args.get("map"),
            "input": {"op": "PATH", "path": source_path} if source_path else None
        })
    if pattern_id == "P_EXPR":
        return Expression(op="EXPR", args={"expr": args.get("expr") or transform_rule})

    logger.error("Unknown pattern_id in build_expression", extra={"phase":"IR"})
    return Expression(op="UNKNOWN", args={"pattern_id": pattern_id, "source_path": source_path, **args})


def build_expression(spec: WorkbookSpec, fm: FieldMap) -> Expression:
    """Build a structured Expression from a FieldMap row."""
    return build_expression_from_parts(
        pattern_id=fm.pattern_id,
        source_path=fm.source_path,
        pattern_args=fm.pattern_args,
        transform_rule=fm.transform_rule,
    )
