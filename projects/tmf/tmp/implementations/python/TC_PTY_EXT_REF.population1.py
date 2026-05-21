"""Auto-generated Python implementation stub.

Plan: TC_PTY_EXT_REF__BSCS__BSCS_CUSTOMER
Template: TPL_JOIN_TO_1_PARENT_SCOPED
Module hint: pipelines.tpl_join_to_1_parent_scoped
"""

from __future__ import annotations

from typing import Any, Dict


DEFAULT_ARGS: Dict[str, Any] = {
  "mode": "batch",
  "target_table": "TC_PTY_EXT_REF",
  "source_system": "BSCS_SYSTEM",
  "source_table": "BSCS_CUSTOMER",
  "source_interface": "BSCS_SYSTEM",
  "driver_key": "party_id",
  "target_fields": [
    "party_id",
    "external_ref_type",
    "external_id"
  ],
  "emit_rows": [
    {
      "row_id": "BSCS_CUSTOMER_ID",
      "emit_when": "customer_id",
      "fields": {
        "external_ref_type": {
          "op": "CONST",
          "value": "BSCS_CUSTOMER_ID"
        },
        "external_id": {
          "op": "PATH",
          "path": "BSCS_SYSTEM.BSCS_CUSTOMER.customer_id"
        }
      }
    },
    {
      "row_id": "MSISDN",
      "emit_when": "msisdn",
      "fields": {
        "external_ref_type": {
          "op": "CONST",
          "value": "MSISDN"
        },
        "external_id": {
          "op": "PATH",
          "path": "BSCS_SYSTEM.BSCS_CUSTOMER.msisdn"
        }
      }
    }
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
      "target_field": "external_id",
      "source_path": "BSCS_SYSTEM.BSCS_CUSTOMER.msisdn",
      "join_key": "SBL_CUSTOMER.party_id --> SBL_CUSTOMER.customer_id --> BSCS_SYSTEM.BSCS_CUSTOMER.customer_id",
      "pattern_id": "P_DIRECT",
      "pattern_args": null
    }
  ]
}


def run(context: Dict[str, Any]) -> Dict[str, Any]:
    """Concrete implementation entrypoint for this execution plan."""
    return {
        "plan_id": "TC_PTY_EXT_REF__BSCS__BSCS_CUSTOMER",
        "status": "not_implemented",
        "context": context,
        "default_args": DEFAULT_ARGS,
    }
