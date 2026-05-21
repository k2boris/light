# BIAN Project Run Summary

The BIAN Java runtime creates one target SQLite database per `BI_PARTY`
instance. It maps party-scoped source records from MDM, Salesforce CRM, Temenos
Core, Oracle AML, and Dow Jones into the BIAN canonical target schema. Reverse
mapping rebuilds source databases from the generated target databases and
checks mapped-column equivalence.

## Current Mapping Position

- Generated Java mappings use a self-contained K2View-style flow layout with
  visible SQL, typed `SourceRow` records, and consistent
  forward/source/target/audit/reverse sections.
- `BI_SOURCE_SYSTEM` is party-scoped and contains only source systems referenced
  by the party's MDM cross-reference rows.
- Temenos/Core `payment_screening` records map to screening runs, screening
  hits, and screening dispositions.
- CRM residency status values are normalized to target country codes for
  `BI_PERSON.residency_country`; non-US residency is resolved through the
  party's Oracle AML country-of-residence value.
- Golden validation ignores case differences in table names, column names, and
  string values; timestamp/date fields are ignored; numeric strings such as
  `93` and `93.0` compare as equivalent.

## Latest Validation Run

Last full BIAN Java validation run: May 21, 2026.

Commands run:
- `mvn -q test` from `projects/bian/runtime/java`
- `projects/bian/runtime/java/scripts/smoke-bian.sh`
- `PYTHONDONTWRITEBYTECODE=1 projects/bian/runtime/java/scripts/validate-golden-targets.sh`

Forward/runtime result:
- Status: `passed`
- Target databases generated: `200`
- Target data directory: `projects/bian/tmp/java-runtime/data`
- Forward log: `projects/bian/tmp/java-runtime/logs/bian-forward.log`

Reverse mapped-column consistency result:
- Status: `passed`
- Target databases checked: `200`
- Compared plans: `26`
- Compared mapped source rows: `5211`
- Mismatches: `0`
- Reverse report: `projects/bian/tmp/java-runtime/reverse-compare.json`
- Reverse source databases: `projects/bian/tmp/java-runtime/reverse-sources`
- Reverse log: `projects/bian/tmp/java-runtime/logs/bian-reverse.log`

Golden target comparison result:
- Status: `failed`
- Golden files checked: `200`
- Remaining golden mismatches: `33`
- Golden report: `projects/bian/tmp/java-runtime/golden-target-compare.json`

## Remaining Golden Deltas

| Table | Count | Summary |
| --- | ---: | --- |
| `BI_SCREENING_DISPOSITION` | 10 | Golden omits some source-backed Temenos/Core payment-screening dispositions that the current mapping now emits. |
| `BI_SCREENING_RUN` | 7 | Golden omits some source-backed screening runs emitted by the runtime. |
| `BI_SCREENING_HIT` | 7 | Golden omits some source-backed screening hits, with one reviewed case also differing on extra source-backed Dow Jones/TMNS hits. |
| `BI_SOURCE_SYSTEM` | 5 | Golden sometimes omits party-scoped source-system lookup rows emitted from MDM xref systems. |
| `BI_PARTY_IDENTIFIER` | 2 | Golden omits identifiers for a small number of parties where source-backed identifiers exist. |
| `BI_SOURCE_REFERENCE` | 1 | Golden omits source references where MDM xref-backed source references exist. |
| `BI_CONTACT_POINT` | 1 | Golden omits a source-backed primary email contact point. |

Current interpretation:
- Forward mapping and reverse mapped-column equivalence are internally
  consistent.
- Remaining golden failures are aggregate golden/spec alignment items, not
  reverse-consistency failures.
- Reviewed golden-empty deltas have backing source rows and MDM xrefs; current
  implementation keeps those source-backed mappings unless a future spec rule
  defines suppression.
