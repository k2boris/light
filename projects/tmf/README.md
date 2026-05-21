# TMF Project Run Summary

The TMF Java runtime creates one target SQLite database per `TC_PARTY`
instance. It maps party-scoped source records from Siebel, BSCS, and NCC into
the TMF canonical target schema. Reverse mapping rebuilds source databases from
the generated target databases and checks mapped-column equivalence.

## Current Mapping Position

- Generated Java mappings use a concise, self-contained layout with visible SQL,
  typed `SourceRow` records, and consistent forward/source/target/reverse
  sections.
- The runtime maps the full current TMF canonical scope used by the smoke test:
  party, customer, customer account, contact media, external references, billing
  accounts, billing balances, products, product relationships, and product
  characteristics.
- Golden validation ignores view-only expectations and timestamp/date fields.

## Latest Validation Run

Last full TMF Java validation run: May 21, 2026.

Commands run:
- `mvn -q test` from `projects/tmf/runtime/java`
- `projects/tmf/runtime/java/scripts/smoke-party.sh`
- `PYTHONDONTWRITEBYTECODE=1 projects/tmf/runtime/java/scripts/validate-golden-targets.sh`

Forward/runtime result:
- Status: `passed`
- Target databases generated: `100`
- Target data directory: `projects/tmf/tmp/java-runtime/data`
- Runtime logs: `projects/tmf/tmp/java-runtime/logs`

Reverse mapped-column consistency result:
- Status: `passed`
- Compared mapped source rows: `5085`
- Mismatches: `0`
- Reverse report: `projects/tmf/tmp/java-runtime/reverse-compare.json`
- Reverse source databases: `projects/tmf/tmp/java-runtime/reverse-sources`

Golden target comparison result:
- Status: `failed`
- Golden files checked: `99`
- Remaining golden mismatches: `293`
- Golden report: `projects/tmf/tmp/java-runtime/golden-target-compare.json`

## Remaining Golden Deltas

The remaining TMF golden failures are aggregate golden/spec alignment items.
They are concentrated around source-backed rows that the runtime emits when
data exists, while some golden files expect omissions or narrower cardinality.

Current interpretation:
- Forward mapping and reverse mapped-column equivalence are internally
  consistent.
- Remaining golden failures should be resolved by explicit TMF spec/IR filtering
  and selection rules before being treated as Java mapping defects.
