-- ============================================================
-- Oracle AML (FCCM-style) - SQLite DDL (10 tables)
-- Purpose: Logical KYC/AML "source-of-record" schema for mapping into BIAN KYC.
-- Notes:
--  - This is a public-domain *logical* model inspired by common Oracle AML / FCCM
--    concepts (Customer/Party, Screening, Alerts, Cases, Risk).
--  - Vendor physical schemas vary by module/version; this is designed for
--    integration + canonical mapping, not to mirror internal Oracle tables.
-- ============================================================

PRAGMA foreign_keys = ON;

-- ------------------------------------------------------------
-- 1) aml_party: party/customer record as known to AML (may be sourced from MDM/Core)
-- ------------------------------------------------------------
CREATE TABLE IF NOT EXISTS aml_party (
  party_id            TEXT PRIMARY KEY,              -- AML internal party key
  external_party_id   TEXT,                          -- CIF/MDM party key if available
  party_type          TEXT NOT NULL DEFAULT 'PERSON',-- PERSON|ORG
  full_name           TEXT,
  first_name          TEXT,
  last_name           TEXT,
  date_of_birth       TEXT,                          -- YYYY-MM-DD
  tax_id_last4        TEXT,                          -- masked
  country_of_res      TEXT,
  status_code         TEXT NOT NULL DEFAULT 'ACTIVE',-- ACTIVE|INACTIVE|DECEASED|UNKNOWN
  created_at          TEXT NOT NULL DEFAULT (datetime('now')),
  updated_at          TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE INDEX IF NOT EXISTS idx_aml_party_ext ON aml_party(external_party_id);
CREATE INDEX IF NOT EXISTS idx_aml_party_name ON aml_party(last_name, first_name);

-- ------------------------------------------------------------
-- 2) aml_screening_list: metadata about watchlists/data sources
-- ------------------------------------------------------------
CREATE TABLE IF NOT EXISTS aml_screening_list (
  list_id             TEXT PRIMARY KEY,
  list_name           TEXT NOT NULL,                 -- "OFAC_SDN", "UN_CONSOLIDATED", "EU_SANCTIONS", "PEP_DB"
  list_type           TEXT NOT NULL,                 -- SANCTIONS|PEP|ADVERSE_MEDIA|INTERNAL
  provider_name       TEXT,                          -- "ORACLE", "LSEG", "DJ", etc. (optional)
  version_label       TEXT,                          -- vendor version/date
  effective_date      TEXT,
  created_at          TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE INDEX IF NOT EXISTS idx_aml_list_type ON aml_screening_list(list_type);

-- ------------------------------------------------------------
-- 3) aml_screening_run: one execution of screening (batch or real-time)
-- ------------------------------------------------------------
CREATE TABLE IF NOT EXISTS aml_screening_run (
  run_id              TEXT PRIMARY KEY,
  run_type            TEXT NOT NULL,                 -- REALTIME|BATCH|RESCREEN
  trigger_reason      TEXT,                          -- ONBOARDING|PERIODIC|CHANGE_EVENT|CASE_REQUEST
  initiated_by        TEXT,                          -- user/system
  started_at          TEXT NOT NULL DEFAULT (datetime('now')),
  completed_at        TEXT,
  status_code         TEXT NOT NULL DEFAULT 'RUNNING', -- RUNNING|COMPLETED|FAILED
  created_at          TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE INDEX IF NOT EXISTS idx_aml_run_status ON aml_screening_run(status_code);

-- ------------------------------------------------------------
-- 4) aml_screening_subject: party screened in a run (can screen many parties per run)
-- ------------------------------------------------------------
CREATE TABLE IF NOT EXISTS aml_screening_subject (
  subject_id          TEXT PRIMARY KEY,
  run_id              TEXT NOT NULL,
  party_id            TEXT NOT NULL,
  subject_role        TEXT NOT NULL DEFAULT 'CUSTOMER', -- CUSTOMER|BENEFICIAL_OWNER|AUTHORIZED_SIGNER
  screened_at         TEXT NOT NULL DEFAULT (datetime('now')),
  overall_result      TEXT,                          -- CLEAR|POTENTIAL_MATCH|TRUE_MATCH|REVIEW
  created_at          TEXT NOT NULL DEFAULT (datetime('now')),
  FOREIGN KEY (run_id)  REFERENCES aml_screening_run(run_id) ON DELETE CASCADE,
  FOREIGN KEY (party_id) REFERENCES aml_party(party_id) ON DELETE CASCADE
);

CREATE INDEX IF NOT EXISTS idx_aml_subject_run ON aml_screening_subject(run_id);
CREATE INDEX IF NOT EXISTS idx_aml_subject_party ON aml_screening_subject(party_id);

-- ------------------------------------------------------------
-- 5) aml_screening_match: candidate match hits from screening
-- ------------------------------------------------------------
CREATE TABLE IF NOT EXISTS aml_screening_match (
  match_id            TEXT PRIMARY KEY,
  subject_id          TEXT NOT NULL,
  list_id             TEXT NOT NULL,
  matched_name        TEXT,
  match_score         REAL,                          -- vendor similarity score
  match_status        TEXT NOT NULL DEFAULT 'OPEN',   -- OPEN|CLOSED
  created_at          TEXT NOT NULL DEFAULT (datetime('now')),
  FOREIGN KEY (subject_id) REFERENCES aml_screening_subject(subject_id) ON DELETE CASCADE,
  FOREIGN KEY (list_id)    REFERENCES aml_screening_list(list_id)
);

CREATE INDEX IF NOT EXISTS idx_aml_match_subject ON aml_screening_match(subject_id);
CREATE INDEX IF NOT EXISTS idx_aml_match_list ON aml_screening_match(list_id);
CREATE INDEX IF NOT EXISTS idx_aml_match_status ON aml_screening_match(match_status);

-- ------------------------------------------------------------
-- 6) aml_match_disposition: analyst decision on a match (audit trail)
-- ------------------------------------------------------------
CREATE TABLE IF NOT EXISTS aml_match_disposition (
  disposition_id      TEXT PRIMARY KEY,
  match_id            TEXT NOT NULL,
  disposition         TEXT NOT NULL,                 -- TRUE_MATCH|FALSE_POSITIVE|ESCALATED|INCONCLUSIVE
  disposition_reason  TEXT,
  decided_by          TEXT,
  decided_at          TEXT NOT NULL DEFAULT (datetime('now')),
  notes               TEXT,
  FOREIGN KEY (match_id) REFERENCES aml_screening_match(match_id) ON DELETE CASCADE
);

CREATE INDEX IF NOT EXISTS idx_aml_disp_match ON aml_match_disposition(match_id);
CREATE INDEX IF NOT EXISTS idx_aml_disp_type ON aml_match_disposition(disposition);

-- ------------------------------------------------------------
-- 7) aml_alert: alert generated by scenarios (TM), screening, or rules
-- ------------------------------------------------------------
CREATE TABLE IF NOT EXISTS aml_alert (
  alert_id            TEXT PRIMARY KEY,
  party_id            TEXT NOT NULL,
  alert_type          TEXT NOT NULL,                 -- SCREENING|TRANSACTION_MONITORING|FRAUD_SIGNAL|CDD_RULE
  severity            TEXT NOT NULL DEFAULT 'MEDIUM',-- LOW|MEDIUM|HIGH|CRITICAL
  status_code         TEXT NOT NULL DEFAULT 'OPEN',  -- OPEN|IN_REVIEW|CLOSED
  created_at          TEXT NOT NULL DEFAULT (datetime('now')),
  closed_at           TEXT,
  source_ref          TEXT,                          -- pointer (match_id / scenario id / transaction ref)
  description         TEXT,
  FOREIGN KEY (party_id) REFERENCES aml_party(party_id) ON DELETE CASCADE
);

CREATE INDEX IF NOT EXISTS idx_aml_alert_party ON aml_alert(party_id);
CREATE INDEX IF NOT EXISTS idx_aml_alert_status ON aml_alert(status_code);
CREATE INDEX IF NOT EXISTS idx_aml_alert_type ON aml_alert(alert_type);

-- ------------------------------------------------------------
-- 8) aml_case: investigation case (can include multiple alerts/matches)
-- ------------------------------------------------------------
CREATE TABLE IF NOT EXISTS aml_case (
  case_id             TEXT PRIMARY KEY,
  case_type           TEXT NOT NULL,                 -- KYC_REVIEW|SCREENING_INVESTIGATION|TM_INVESTIGATION|EDD
  status_code         TEXT NOT NULL DEFAULT 'OPEN',  -- OPEN|ASSIGNED|IN_PROGRESS|CLOSED
  priority            TEXT NOT NULL DEFAULT 'NORMAL',-- LOW|NORMAL|HIGH|URGENT
  opened_at           TEXT NOT NULL DEFAULT (datetime('now')),
  closed_at           TEXT,
  assigned_to         TEXT,
  outcome_code        TEXT,                          -- CLEARED|SAR_FILED|ACCOUNT_CLOSED|EDD_REQUIRED|OTHER
  outcome_notes       TEXT
);

CREATE INDEX IF NOT EXISTS idx_aml_case_status ON aml_case(status_code);
CREATE INDEX IF NOT EXISTS idx_aml_case_type ON aml_case(case_type);

-- ------------------------------------------------------------
-- 9) aml_case_item: link table connecting cases to alerts/matches/parties
-- ------------------------------------------------------------
CREATE TABLE IF NOT EXISTS aml_case_item (
  case_item_id        TEXT PRIMARY KEY,
  case_id             TEXT NOT NULL,
  item_type           TEXT NOT NULL,                 -- ALERT|MATCH|PARTY|DOCUMENT|TRANSACTION
  item_id             TEXT NOT NULL,                 -- e.g., alert_id, match_id, party_id
  added_at            TEXT NOT NULL DEFAULT (datetime('now')),
  FOREIGN KEY (case_id) REFERENCES aml_case(case_id) ON DELETE CASCADE
);

CREATE INDEX IF NOT EXISTS idx_aml_case_item_case ON aml_case_item(case_id);
CREATE INDEX IF NOT EXISTS idx_aml_case_item_type ON aml_case_item(item_type);

-- ------------------------------------------------------------
-- 10) aml_party_risk: KYC/AML risk rating snapshot for a party
-- ------------------------------------------------------------
CREATE TABLE IF NOT EXISTS aml_party_risk (
  risk_id             TEXT PRIMARY KEY,
  party_id            TEXT NOT NULL,
  risk_rating         TEXT NOT NULL,                 -- LOW|MEDIUM|HIGH
  risk_score          REAL,                          -- numeric score
  model_name          TEXT,                          -- e.g., "CUSTOMER_RISK_V1"
  calculated_at       TEXT NOT NULL DEFAULT (datetime('now')),
  next_review_due_at  TEXT,
  pep_flag            INTEGER NOT NULL DEFAULT 0,
  sanctions_flag      INTEGER NOT NULL DEFAULT 0,
  adverse_media_flag  INTEGER NOT NULL DEFAULT 0,
  rationale           TEXT,
  FOREIGN KEY (party_id) REFERENCES aml_party(party_id) ON DELETE CASCADE
);

CREATE UNIQUE INDEX IF NOT EXISTS ux_aml_risk_party ON aml_party_risk(party_id);
CREATE INDEX IF NOT EXISTS idx_aml_risk_rating ON aml_party_risk(risk_rating);

-- ============================================================
-- End Oracle AML logical schema
-- ============================================================