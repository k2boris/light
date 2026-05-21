"""Auto-generated Python implementation stub.

Plan: SCREENING_HIT__AML_ORA_DS__aml_screening_match
Template: TPL_JOIN_TO_1_PARENT_SCOPED
Module hint: pipelines.tpl_join_to_1_parent_scoped
"""

from __future__ import annotations

from typing import Any, Dict


DEFAULT_ARGS: Dict[str, Any] = {
  "mode": "batch",
  "target_table": "BI_SCREENING_HIT",
  "source_system": "AML_ORA_DS",
  "source_table": "aml_screening_match",
  "source_interface": "AML_ORA_DS",
  "driver_key": "screening_run_id",
  "target_fields": [
    "screening_hit_id",
    "screening_run_id",
    "hit_type",
    "provider_code",
    "provider_entity_id",
    "provider_listing_id",
    "matched_name",
    "match_score",
    "hit_status",
    "created_at"
  ],
  "emit_rows": [
    {
      "row_id": "AML_ROW",
      "emit_when": "match_id",
      "fields": {
        "screening_hit_id": {
          "op": "PATH",
          "path": "AML_ORA_DS.aml_screening_match.match_id"
        },
        "hit_type": {
          "op": "PATH",
          "path": "AML_ORA_DS.aml_screening_match.match_status"
        },
        "provider_code": {
          "op": "CONST",
          "value": "ORA-AML"
        },
        "provider_entity_id": {
          "op": "PATH",
          "path": "AML_ORA_DS.aml_screening_match.list_id"
        },
        "provider_listing_id": {
          "op": "PATH",
          "path": "AML_ORA_DS.aml_screening_match.list_id"
        },
        "matched_name": {
          "op": "PATH",
          "path": "AML_ORA_DS.aml_screening_match.matched_name"
        },
        "match_score": {
          "op": "PATH",
          "path": "AML_ORA_DS.aml_screening_match.match_score"
        },
        "hit_status": {
          "op": "CONST",
          "value": "OPEN"
        },
        "created_at": {
          "op": "PATH",
          "path": "AML_ORA_DS.aml_screening_match.created_at"
        }
      }
    },
    {
      "row_id": "DJ_ROW",
      "emit_when": "matched_name && matched_name.indexOf(':')>=0 && matched_name.lastIndexOf(':')>matched_name.indexOf('|')",
      "fields": {
        "screening_hit_id": {
          "op": "EXPR",
          "expr": "match_id + ':2'"
        },
        "hit_type": {
          "op": "CONST",
          "value": "WATCHLIST"
        },
        "provider_code": {
          "op": "CONST",
          "value": "DOWJONES"
        },
        "provider_entity_id": {
          "op": "EXPR",
          "expr": "(matched_name && matched_name.indexOf(':')>=0 && matched_name.indexOf('|')>matched_name.indexOf(':')) ? matched_name.substring(matched_name.indexOf(':')+1, matched_name.indexOf('|')) : null"
        },
        "provider_listing_id": {
          "op": "EXPR",
          "expr": "(matched_name && matched_name.lastIndexOf(':')>matched_name.indexOf('|')) ? matched_name.substring(matched_name.lastIndexOf(':')+1) : null"
        },
        "matched_name": {
          "op": "PATH",
          "path": "AML_ORA_DS.aml_screening_match.matched_name"
        },
        "match_score": {
          "op": "PATH",
          "path": "AML_ORA_DS.aml_screening_match.match_score"
        },
        "hit_status": {
          "op": "CONST",
          "value": "OPEN"
        },
        "created_at": {
          "op": "PATH",
          "path": "AML_ORA_DS.aml_screening_match.created_at"
        }
      }
    }
  ],
  "join_key_notation": [
    {
      "target_field": "screening_hit_id",
      "source_path": "AML_ORA_DS.aml_screening_match.match_id",
      "join_key": "AML_ORA_DS.aml_screening_match.subject_id -> AML_ORA_DS.aml_screening_subject.subject_id",
      "pattern_id": "P_DIRECT",
      "pattern_args": null
    },
    {
      "target_field": "screening_run_id",
      "source_path": "AML_ORA_DS.aml_screening_subject.run_id",
      "join_key": "AML_ORA_DS.aml_screening_match.subject_id -> AML_ORA_DS.aml_screening_subject.subject_id",
      "pattern_id": "P_DIRECT",
      "pattern_args": null
    }
  ]
}


def run(context: Dict[str, Any]) -> Dict[str, Any]:
    """Concrete implementation entrypoint for this execution plan."""
    return {
        "plan_id": "SCREENING_HIT__AML_ORA_DS__aml_screening_match",
        "status": "not_implemented",
        "context": context,
        "default_args": DEFAULT_ARGS,
    }
