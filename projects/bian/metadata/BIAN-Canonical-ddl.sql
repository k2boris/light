-- ============================================================
-- BIAN-harmonized Canonical DDL for a KYC Service (SQLite)
-- Purpose:
--   Canonical model to harmonize multiple SORs (Salesforce onboarding,
--   Temenos core, MDM hub, Oracle AML/case mgmt, Dow Jones watchlist feed).
--
-- BIAN alignment (conceptual):
--   - Party Data Management: BI_PARTY, BI_PERSON, BI_PARTY_IDENTIFIER, BI_CONTACT_POINT, BI_POSTAL_ADDRESS
--   - Know Your Customer / Compliance: BI_KYC_CASE, BI_KYC_ASSESSMENT, BI_KYC_REQUIREMENT_ITEM
--   - Screening: BI_SCREENING_RUN, BI_SCREENING_HIT, BI_SCREENING_DISPOSITION
--   - Evidence/Records: BI_EVIDENCE_DOCUMENT
--   - Source lineage: BI_SOURCE_SYSTEM, BI_SOURCE_REFERENCE (crosswalk)
--
-- Notes:
--   - This is a logical canonical model (BIAN-style), not vendor physical schemas.
--   - Designed for "KYC Service" boundary: identity data + checks + screening + case workflow.
-- ============================================================

PRAGMA foreign_keys = ON;

-- ------------------------------------------------------------
-- 1) BI_SOURCE_SYSTEM: register each SOR / feeder
-- ------------------------------------------------------------
CREATE TABLE IF NOT EXISTS BI_SOURCE_SYSTEM (
  source_system_id   TEXT PRIMARY KEY,
  source_code        TEXT NOT NULL UNIQUE,    -- "SFDC","TEMENOS","MDM","ORACLE_AML","DJ"
  source_name        TEXT,
  source_type        TEXT,                   -- ONBOARDING|CORE|MDM|AML|WATCHLIST|CARDS|DIGITAL
  is_active          INTEGER NOT NULL DEFAULT 1,
  created_at         TEXT NOT NULL DEFAULT (datetime('now'))
);

-- ------------------------------------------------------------
-- 2) BI_PARTY: canonical Party (golden, or “enterprise BI_PARTY” within KYC domain)
-- ------------------------------------------------------------
CREATE TABLE IF NOT EXISTS BI_PARTY (
  party_id           TEXT PRIMARY KEY,       -- canonical BI_PARTY id
  party_type         TEXT NOT NULL DEFAULT 'PERSON', -- PERSON|ORGANIZATION
  status_code        TEXT NOT NULL DEFAULT 'ACTIVE', -- ACTIVE|INACTIVE|DECEASED|UNKNOWN
  created_at         TEXT NOT NULL DEFAULT (datetime('now')),
  updated_at         TEXT NOT NULL DEFAULT (datetime('now'))
);

-- ------------------------------------------------------------
-- 3) BI_PERSON: canonical BI_PERSON demographics (retail focus)
-- ------------------------------------------------------------
CREATE TABLE IF NOT EXISTS BI_PERSON (
  party_id           TEXT PRIMARY KEY,
  first_name         TEXT,
  middle_name        TEXT,
  last_name          TEXT,
  date_of_birth      TEXT,                   -- YYYY-MM-DD (or NULL if not known)
  gender_code        TEXT,
  citizenship_code   TEXT,
  residency_country  TEXT,
  occupation         TEXT,
  employer_name      TEXT,
  FOREIGN KEY (party_id) REFERENCES BI_PARTY(party_id) ON DELETE CASCADE
);

CREATE INDEX IF NOT EXISTS idx_person_name ON BI_PERSON(last_name, first_name);
CREATE INDEX IF NOT EXISTS idx_person_dob  ON BI_PERSON(date_of_birth);

-- ------------------------------------------------------------
-- 4) BI_PARTY_IDENTIFIER: canonical identifiers (masked/hashed only)
-- ------------------------------------------------------------
CREATE TABLE IF NOT EXISTS BI_PARTY_IDENTIFIER (
  identifier_id      TEXT PRIMARY KEY,
  party_id           TEXT NOT NULL,
  id_type            TEXT NOT NULL,          -- SSN_LAST4|NATIONAL_ID_HASH|DL_HASH|PASSPORT_HASH|CIF|EMAIL_HASH
  id_value           TEXT NOT NULL,          -- masked or hashed
  issuing_country    TEXT,
  issuing_region     TEXT,
  expiration_date    TEXT,
  verified_flag      INTEGER NOT NULL DEFAULT 0,
  verified_at        TEXT,
  FOREIGN KEY (party_id) REFERENCES BI_PARTY(party_id) ON DELETE CASCADE
);

CREATE INDEX IF NOT EXISTS idx_pid_party ON BI_PARTY_IDENTIFIER(party_id);
CREATE INDEX IF NOT EXISTS idx_pid_type  ON BI_PARTY_IDENTIFIER(id_type);

-- ------------------------------------------------------------
-- 5) BI_CONTACT_POINT: canonical email/phone
-- ------------------------------------------------------------
CREATE TABLE IF NOT EXISTS BI_CONTACT_POINT (
  contact_point_id   TEXT PRIMARY KEY,
  party_id           TEXT NOT NULL,
  contact_type       TEXT NOT NULL,          -- EMAIL|MOBILE|HOME_PHONE
  contact_value      TEXT NOT NULL,          -- normalized (E.164 for phone)
  is_primary         INTEGER NOT NULL DEFAULT 0,
  verified_flag      INTEGER NOT NULL DEFAULT 0,
  verified_at        TEXT,
  FOREIGN KEY (party_id) REFERENCES BI_PARTY(party_id) ON DELETE CASCADE
);

CREATE INDEX IF NOT EXISTS idx_cp_party ON BI_CONTACT_POINT(party_id);
CREATE INDEX IF NOT EXISTS idx_cp_type  ON BI_CONTACT_POINT(contact_type);

-- ------------------------------------------------------------
-- 6) BI_POSTAL_ADDRESS: canonical addresses
-- ------------------------------------------------------------
CREATE TABLE IF NOT EXISTS BI_POSTAL_ADDRESS (
  address_id         TEXT PRIMARY KEY,
  party_id           TEXT NOT NULL,
  address_type       TEXT NOT NULL DEFAULT 'PHYSICAL', -- PHYSICAL|MAILING|PREVIOUS
  line1              TEXT,
  line2              TEXT,
  city               TEXT,
  state_region       TEXT,
  postal_code        TEXT,
  country_code       TEXT NOT NULL DEFAULT 'US',
  is_primary         INTEGER NOT NULL DEFAULT 0,
  valid_from         TEXT,
  valid_to           TEXT,
  FOREIGN KEY (party_id) REFERENCES BI_PARTY(party_id) ON DELETE CASCADE
);

CREATE INDEX IF NOT EXISTS idx_addr_party ON BI_POSTAL_ADDRESS(party_id);

-- ------------------------------------------------------------
-- 7) BI_SOURCE_REFERENCE: crosswalk + lineage (BI_PARTY-level)
--    Use this to map each SOR record to the canonical party_id.
-- ------------------------------------------------------------
CREATE TABLE IF NOT EXISTS BI_SOURCE_REFERENCE (
  source_reference_id TEXT PRIMARY KEY,
  party_id            TEXT NOT NULL,
  source_system_id    TEXT NOT NULL,
  source_entity       TEXT NOT NULL,         -- "APPLICANT","CUSTOMER","CARDHOLDER","SCREENED_ENTITY"
  source_key          TEXT NOT NULL,         -- native id in the source system
  is_primary_in_source INTEGER NOT NULL DEFAULT 0,
  effective_from      TEXT,
  effective_to        TEXT,
  created_at          TEXT NOT NULL DEFAULT (datetime('now')),
  FOREIGN KEY (party_id) REFERENCES BI_PARTY(party_id) ON DELETE CASCADE,
  FOREIGN KEY (source_system_id) REFERENCES BI_SOURCE_SYSTEM(source_system_id)
);

CREATE UNIQUE INDEX IF NOT EXISTS ux_source_ref
  ON BI_SOURCE_REFERENCE(source_system_id, source_entity, source_key);

CREATE INDEX IF NOT EXISTS idx_source_ref_party ON BI_SOURCE_REFERENCE(party_id);

-- ------------------------------------------------------------
-- 8) BI_KYC_CASE: canonical KYC work item / case (CDD/EDD, onboarding, refresh)
-- ------------------------------------------------------------
CREATE TABLE IF NOT EXISTS BI_KYC_CASE (
  kyc_case_id        TEXT PRIMARY KEY,
  party_id           TEXT NOT NULL,
  case_type          TEXT NOT NULL,          -- ONBOARDING_CDD|PERIODIC_REFRESH|EVENT_DRIVEN_REFRESH|EDD|SCREENING_INVESTIGATION
  status_code        TEXT NOT NULL DEFAULT 'OPEN', -- OPEN|ASSIGNED|IN_PROGRESS|ON_HOLD|CLOSED
  priority_code      TEXT NOT NULL DEFAULT 'NORMAL', -- LOW|NORMAL|HIGH|URGENT
  opened_at          TEXT NOT NULL DEFAULT (datetime('now')),
  closed_at          TEXT,
  assigned_to        TEXT,                   -- analyst/user id (or group)
  outcome_code       TEXT,                   -- VERIFIED|REJECTED|EDD_REQUIRED|SAR_FILED|ACCOUNT_RESTRICTED|CLEARED
  outcome_notes      TEXT,
  FOREIGN KEY (party_id) REFERENCES BI_PARTY(party_id) ON DELETE CASCADE
);

CREATE INDEX IF NOT EXISTS idx_kyc_case_party ON BI_KYC_CASE(party_id);
CREATE INDEX IF NOT EXISTS idx_kyc_case_status ON BI_KYC_CASE(status_code);

-- ------------------------------------------------------------
-- 9) BI_KYC_ASSESSMENT: canonical “KYC profile / risk assessment snapshot”
--    This is where you harmonize risk ratings from Oracle AML, onboarding, etc.
-- ------------------------------------------------------------
CREATE TABLE IF NOT EXISTS BI_KYC_ASSESSMENT (
  kyc_assessment_id  TEXT PRIMARY KEY,
  party_id           TEXT NOT NULL,
  kyc_status         TEXT NOT NULL,          -- NOT_STARTED|IN_PROGRESS|VERIFIED|FAILED|REVIEW_REQUIRED
  risk_rating        TEXT,                   -- LOW|MEDIUM|HIGH
  risk_score         REAL,
  pep_flag           INTEGER NOT NULL DEFAULT 0,
  sanctions_flag     INTEGER NOT NULL DEFAULT 0,
  adverse_media_flag INTEGER NOT NULL DEFAULT 0,
  last_reviewed_at   TEXT,
  next_review_due_at TEXT,
  assessment_reason  TEXT,                   -- ONBOARDING|PERIODIC|EVENT|CASE_OUTCOME
  source_system_id   TEXT,                   -- where this assessment came from (optional)
  source_record_ref  TEXT,                   -- e.g., Oracle AML risk_id / SFDC check id
  created_at         TEXT NOT NULL DEFAULT (datetime('now')),
  updated_at         TEXT NOT NULL DEFAULT (datetime('now')),
  FOREIGN KEY (party_id) REFERENCES BI_PARTY(party_id) ON DELETE CASCADE,
  FOREIGN KEY (source_system_id) REFERENCES BI_SOURCE_SYSTEM(source_system_id)
);

CREATE INDEX IF NOT EXISTS idx_kyc_assessment_party ON BI_KYC_ASSESSMENT(party_id);

-- ------------------------------------------------------------
-- 10) BI_KYC_REQUIREMENT_ITEM: what was collected/verified (CIP/CDD checklist)
--     Lets you harmonize onboarding “steps” and evidence completeness.
-- ------------------------------------------------------------
CREATE TABLE IF NOT EXISTS BI_KYC_REQUIREMENT_ITEM (
  requirement_item_id TEXT PRIMARY KEY,
  kyc_case_id         TEXT NOT NULL,
  requirement_type    TEXT NOT NULL,         -- ID_DOCUMENT|ADDRESS|PHONE|EMAIL|TAX_ID|SOURCE_OF_FUNDS|BENEFICIAL_OWNERSHIP|CONSENT
  status_code         TEXT NOT NULL,         -- NOT_PROVIDED|PROVIDED|VERIFIED|FAILED|WAIVED
  verified_at         TEXT,
  notes               TEXT,
  source_system_id    TEXT,
  source_record_ref   TEXT,
  FOREIGN KEY (kyc_case_id) REFERENCES BI_KYC_CASE(kyc_case_id) ON DELETE CASCADE,
  FOREIGN KEY (source_system_id) REFERENCES BI_SOURCE_SYSTEM(source_system_id)
);

CREATE INDEX IF NOT EXISTS idx_req_case ON BI_KYC_REQUIREMENT_ITEM(kyc_case_id);
CREATE INDEX IF NOT EXISTS idx_req_type ON BI_KYC_REQUIREMENT_ITEM(requirement_type);

-- ------------------------------------------------------------
-- 11) BI_SCREENING_RUN: canonical screening execution (real-time/batch/rescreen)
--     Harmonizes Oracle AML screening runs + rescreen triggers.
-- ------------------------------------------------------------
CREATE TABLE IF NOT EXISTS BI_SCREENING_RUN (
  screening_run_id   TEXT PRIMARY KEY,
  party_id           TEXT NOT NULL,
  run_type           TEXT NOT NULL,          -- REALTIME|BATCH|RESCREEN
  trigger_reason     TEXT,                   -- ONBOARDING|PERIODIC|CHANGE_EVENT|CASE_REQUEST
  started_at         TEXT NOT NULL DEFAULT (datetime('now')),
  completed_at       TEXT,
  status_code        TEXT NOT NULL DEFAULT 'RUNNING', -- RUNNING|COMPLETED|FAILED
  source_system_id   TEXT,                   -- "ORACLE_AML" typically
  source_record_ref  TEXT,
  FOREIGN KEY (party_id) REFERENCES BI_PARTY(party_id) ON DELETE CASCADE,
  FOREIGN KEY (source_system_id) REFERENCES BI_SOURCE_SYSTEM(source_system_id)
);

CREATE INDEX IF NOT EXISTS idx_screen_run_party ON BI_SCREENING_RUN(party_id);
CREATE INDEX IF NOT EXISTS idx_screen_run_status ON BI_SCREENING_RUN(status_code);

-- ------------------------------------------------------------
-- 12) BI_SCREENING_HIT: canonical hit against watchlists (DJ sanctions/PEP etc.)
--     Harmonizes (a) Oracle AML matches and (b) watchlist provider entity/listing references.
-- ------------------------------------------------------------
CREATE TABLE IF NOT EXISTS BI_SCREENING_HIT (
  screening_hit_id    TEXT PRIMARY KEY,
  screening_run_id    TEXT NOT NULL,
  hit_type            TEXT NOT NULL,         -- SANCTIONS|PEP|ADVERSE_MEDIA|WATCHLIST
  provider_code       TEXT,                  -- "DJ","LSEG","LN", etc. (here: DJ)
  provider_entity_id  TEXT,                  -- dj_entity.entity_id (or equivalent)
  provider_listing_id TEXT,                  -- dj_listing.listing_id (or equivalent)
  matched_name        TEXT,
  match_score         REAL,
  hit_status          TEXT NOT NULL DEFAULT 'OPEN', -- OPEN|CLOSED
  created_at          TEXT NOT NULL DEFAULT (datetime('now')),
  FOREIGN KEY (screening_run_id) REFERENCES BI_SCREENING_RUN(screening_run_id) ON DELETE CASCADE
);

CREATE INDEX IF NOT EXISTS idx_hit_run ON BI_SCREENING_HIT(screening_run_id);
CREATE INDEX IF NOT EXISTS idx_hit_type ON BI_SCREENING_HIT(hit_type);
CREATE INDEX IF NOT EXISTS idx_hit_status ON BI_SCREENING_HIT(hit_status);

-- ------------------------------------------------------------
-- 13) BI_SCREENING_DISPOSITION: decision trail for a hit (true/false positive, etc.)
-- ------------------------------------------------------------
CREATE TABLE IF NOT EXISTS BI_SCREENING_DISPOSITION (
  disposition_id      TEXT PRIMARY KEY,
  screening_hit_id    TEXT NOT NULL,
  disposition_code    TEXT NOT NULL,         -- TRUE_MATCH|FALSE_POSITIVE|ESCALATED|INCONCLUSIVE
  disposition_reason  TEXT,
  decided_by          TEXT,
  decided_at          TEXT NOT NULL DEFAULT (datetime('now')),
  notes               TEXT,
  FOREIGN KEY (screening_hit_id) REFERENCES BI_SCREENING_HIT(screening_hit_id) ON DELETE CASCADE
);

CREATE INDEX IF NOT EXISTS idx_disp_hit ON BI_SCREENING_DISPOSITION(screening_hit_id);
CREATE INDEX IF NOT EXISTS idx_disp_code ON BI_SCREENING_DISPOSITION(disposition_code);

-- ------------------------------------------------------------
-- 14) BI_EVIDENCE_DOCUMENT: canonical pointers to evidence / artifacts
--     (ID scans, proof of address, screening reports, consent forms, etc.)
-- ------------------------------------------------------------
CREATE TABLE IF NOT EXISTS BI_EVIDENCE_DOCUMENT (
  evidence_document_id TEXT PRIMARY KEY,
  party_id             TEXT NOT NULL,
  kyc_case_id          TEXT,                  -- optional link to case
  document_type        TEXT NOT NULL,         -- ID_DOCUMENT|PROOF_OF_ADDRESS|CONSENT|SCREENING_REPORT|RISK_ASSESSMENT|OTHER
  document_ref         TEXT,         -- pointer/URI/key in a secure document store
  captured_at          TEXT NOT NULL DEFAULT (datetime('now')),
  source_system_id     TEXT,
  source_record_ref    TEXT,
  FOREIGN KEY (party_id) REFERENCES BI_PARTY(party_id) ON DELETE CASCADE,
  FOREIGN KEY (kyc_case_id) REFERENCES BI_KYC_CASE(kyc_case_id) ON DELETE SET NULL,
  FOREIGN KEY (source_system_id) REFERENCES BI_SOURCE_SYSTEM(source_system_id)
);

CREATE INDEX IF NOT EXISTS idx_ev_party ON BI_EVIDENCE_DOCUMENT(party_id);
CREATE INDEX IF NOT EXISTS idx_ev_case ON BI_EVIDENCE_DOCUMENT(kyc_case_id);
CREATE INDEX IF NOT EXISTS idx_ev_type ON BI_EVIDENCE_DOCUMENT(document_type);

-- ============================================================
-- End BIAN-harmonized KYC Service Canonical Schema
-- ============================================================
