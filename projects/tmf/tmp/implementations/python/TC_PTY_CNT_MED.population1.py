"""Auto-generated Python implementation stub.

Plan: TC_PTY_CNT_MED__BSCS__JOINED
Template: TPL_JOIN_TO_1_PARENT_SCOPED
Module hint: pipelines.tpl_join_to_1_parent_scoped
"""

from __future__ import annotations

from typing import Any, Dict


DEFAULT_ARGS: Dict[str, Any] = {
  "mode": "batch",
  "target_table": "TC_PTY_CNT_MED",
  "source_system": "BSCS_SYSTEM",
  "source_table": "BSCS_BILLING_ACCOUNT",
  "source_interface": "BSCS_SYSTEM",
  "driver_key": "party_id",
  "target_fields": [
    "party_id",
    "medium_type",
    "preferred_flag",
    "characteristic_json"
  ],
  "join_key_notation": [
    {
      "target_field": "party_id",
      "source_path": null,
      "join_key": "SBL_CUSTOMER.party_id --> SBL_CUSTOMER.customer_id",
      "pattern_id": "P_EXPR",
      "pattern_args": "expr=party_id"
    },
    {
      "target_field": "preferred_flag",
      "source_path": "BSCS_SYSTEM.BSCS_ACCOUNT_ADDRESS.is_primary",
      "join_key": "BSCS_BILLING_ACCOUNT.billing_account_id -> BSCS_ACCOUNT_ADDRESS.billing_account_id -> BSCS_ACCOUNT_ADDRESS.is_primary",
      "pattern_id": "P_DIRECT",
      "pattern_args": null
    },
    {
      "target_field": "characteristic_json",
      "source_path": "BSCS_SYSTEM.BSCS_ADDRESS.line1",
      "join_key": "SBL_CUSTOMER.party_id --> SBL_CUSTOMER.customer_id --> BSCS_BILLING_ACCOUNT.customer_id -> BSCS_ACCOUNT_ADDRESS.billing_account_id -> BSCS_ADDRESS.address_id -> BSCS_ADDRESS.line1",
      "pattern_id": "P_DIRECT",
      "pattern_args": null
    }
  ]
}


def run(context: Dict[str, Any]) -> Dict[str, Any]:
    """Concrete implementation entrypoint for this execution plan."""
    return {
        "plan_id": "TC_PTY_CNT_MED__BSCS__JOINED",
        "status": "not_implemented",
        "context": context,
        "default_args": DEFAULT_ARGS,
    }
