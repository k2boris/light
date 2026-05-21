"""Auto-generated Python implementation stub.

Plan: SOURCE_SYSTEM__MDM_INFA_DS__C_XREF_PARTY
Template: TPL_JOIN_TO_1_PARENT_SCOPED
Module hint: pipelines.tpl_join_to_1_parent_scoped
"""

from __future__ import annotations

from typing import Any, Dict


DEFAULT_ARGS: Dict[str, Any] = {
  "mode": "batch",
  "target_table": "BI_SOURCE_SYSTEM",
  "source_system": "MDM_INFA_DS",
  "source_table": "C_XREF_PARTY",
  "source_interface": "MDM_INFA_DS",
  "driver_key": "source_system_id",
  "target_fields": [
    "source_system_id",
    "source_code",
    "source_name",
    "source_type",
    "is_active",
    "created_at"
  ],
  "join_key_notation": []
}


def run(context: Dict[str, Any]) -> Dict[str, Any]:
    """Concrete implementation entrypoint for this execution plan."""
    return {
        "plan_id": "SOURCE_SYSTEM__MDM_INFA_DS__C_XREF_PARTY",
        "status": "not_implemented",
        "context": context,
        "default_args": DEFAULT_ARGS,
    }
