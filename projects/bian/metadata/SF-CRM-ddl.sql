-- ============================================================
-- Salesforce Onboarding (Retail) - SQLite DDL (10 core tables)
-- Goal: represent the key “customer onboarding + KYC intake” data
--       typically captured in Salesforce (system of engagement).
-- Notes:
--  - This is a *logical* public-domain style schema (not Salesforce’s
--    internal physical tables). It mirrors common Salesforce objects
--    and onboarding flows used by mid-tier banks.
--  - Designed to map cleanly into a BIAN Party/KYC canonical.
-- ============================================================

PRAGMA foreign_keys = ON;

-- ------------------------------------------------------------
-- 1) sf_user: who performed actions (branch rep, ops, system user)
-- ------------------------------------------------------------
CREATE TABLE IF NOT EXISTS sf_user (
  user_id           TEXT PRIMARY KEY,
  username          TEXT NOT NULL UNIQUE,
  display_name      TEXT,
  email             TEXT,
  role_code         TEXT,                 -- e.g., "BRANCH_REP", "KYC_ANALYST", "SYSTEM"
  is_active         INTEGER NOT NULL DEFAULT 1,
  created_at        TEXT NOT NULL DEFAULT (datetime('now')),
  updated_at        TEXT NOT NULL DEFAULT (datetime('now'))
);

-- ------------------------------------------------------------
-- 2) sf_onboarding_application: the onboarding case/application
-- ------------------------------------------------------------
CREATE TABLE IF NOT EXISTS sf_onboarding_application (
  application_id    TEXT PRIMARY KEY,
  application_ref   TEXT UNIQUE,          -- external reference shown to customer
  channel_code      TEXT NOT NULL,         -- "ONLINE", "MOBILE", "BRANCH", "CALL_CENTER"
  product_code      TEXT NOT NULL,         -- "DDA", "SAVINGS", "STUDENT_DDA", etc.
  status_code       TEXT NOT NULL,         -- "STARTED","SUBMITTED","IN_REVIEW","APPROVED","REJECTED","ABANDONED"
  submitted_at      TEXT,
  decided_at        TEXT,
  decision_code     TEXT,                 -- "APPROVE","DECLINE","REFER"
  decision_reason   TEXT,                 -- free text or code list
  created_by        TEXT,
  created_at        TEXT NOT NULL DEFAULT (datetime('now')),
  updated_at        TEXT NOT NULL DEFAULT (datetime('now')),
  FOREIGN KEY (created_by) REFERENCES sf_user(user_id)
);

CREATE INDEX IF NOT EXISTS idx_sf_app_status ON sf_onboarding_application(status_code);
CREATE INDEX IF NOT EXISTS idx_sf_app_channel ON sf_onboarding_application(channel_code);

-- ------------------------------------------------------------
-- 3) sf_party_person: the retail customer identity record captured in onboarding
-- ------------------------------------------------------------
CREATE TABLE IF NOT EXISTS sf_party_person (
  party_id          TEXT PRIMARY KEY,
  application_id    TEXT NOT NULL,
  customer_type     TEXT NOT NULL DEFAULT 'PERSON', -- retail focus
  first_name        TEXT NOT NULL,
  middle_name       TEXT,
  last_name         TEXT NOT NULL,
  date_of_birth     TEXT,                 -- ISO date "YYYY-MM-DD"
  ssn_last4         TEXT,                 -- store last4 only (common practice)
  tax_id_type       TEXT,                 -- "SSN","ITIN","OTHER"
  citizenship_code  TEXT,                 -- "US", etc.
  residency_code    TEXT,                 -- "US_RESIDENT", etc.
  pep_declared_flag INTEGER NOT NULL DEFAULT 0,
  occupation        TEXT,
  employer_name     TEXT,
  created_at        TEXT NOT NULL DEFAULT (datetime('now')),
  updated_at        TEXT NOT NULL DEFAULT (datetime('now')),
  FOREIGN KEY (application_id) REFERENCES sf_onboarding_application(application_id) ON DELETE CASCADE
);

CREATE INDEX IF NOT EXISTS idx_sf_party_app ON sf_party_person(application_id);

-- ------------------------------------------------------------
-- 4) sf_address: addresses collected during onboarding (mailing, physical, etc.)
-- ------------------------------------------------------------
CREATE TABLE IF NOT EXISTS sf_address (
  address_id        TEXT PRIMARY KEY,
  party_id          TEXT NOT NULL,
  address_type      TEXT NOT NULL,        -- "PHYSICAL","MAILING","PREVIOUS"
  line1             TEXT NOT NULL,
  line2             TEXT,
  city              TEXT NOT NULL,
  state_region      TEXT,
  postal_code       TEXT,
  country_code      TEXT NOT NULL DEFAULT 'US',
  valid_from        TEXT,
  valid_to          TEXT,
  is_primary        INTEGER NOT NULL DEFAULT 0,
  created_at        TEXT NOT NULL DEFAULT (datetime('now')),
  updated_at        TEXT NOT NULL DEFAULT (datetime('now')),
  FOREIGN KEY (party_id) REFERENCES sf_party_person(party_id) ON DELETE CASCADE
);

CREATE INDEX IF NOT EXISTS idx_sf_addr_party ON sf_address(party_id);
CREATE INDEX IF NOT EXISTS idx_sf_addr_type ON sf_address(address_type);

-- ------------------------------------------------------------
-- 5) sf_contact_point: email/phone collected during onboarding
-- ------------------------------------------------------------
CREATE TABLE IF NOT EXISTS sf_contact_point (
  contact_point_id  TEXT PRIMARY KEY,
  party_id          TEXT NOT NULL,
  contact_type      TEXT NOT NULL,        -- "EMAIL","MOBILE","HOME_PHONE"
  contact_value     TEXT NOT NULL,        -- email address or phone number (E.164 recommended)
  is_primary        INTEGER NOT NULL DEFAULT 0,
  verified_flag     INTEGER NOT NULL DEFAULT 0,
  verified_at       TEXT,
  created_at        TEXT NOT NULL DEFAULT (datetime('now')),
  updated_at        TEXT NOT NULL DEFAULT (datetime('now')),
  FOREIGN KEY (party_id) REFERENCES sf_party_person(party_id) ON DELETE CASCADE
);

CREATE INDEX IF NOT EXISTS idx_sf_cp_party ON sf_contact_point(party_id);
CREATE INDEX IF NOT EXISTS idx_sf_cp_type ON sf_contact_point(contact_type);

-- ------------------------------------------------------------
-- 6) sf_identity_document: ID documents captured (DL, passport)
-- ------------------------------------------------------------
CREATE TABLE IF NOT EXISTS sf_identity_document (
  document_id       TEXT PRIMARY KEY,
  party_id          TEXT NOT NULL,
  doc_type          TEXT NOT NULL,        -- "DRIVERS_LICENSE","PASSPORT","STATE_ID"
  doc_number_masked TEXT,                 -- masked/partial; avoid full storage
  issuing_country   TEXT,
  issuing_region    TEXT,                 -- state/province
  expiration_date   TEXT,                 -- "YYYY-MM-DD"
  issue_date        TEXT,
  capture_method    TEXT,                 -- "UPLOAD","IN_BRANCH_SCAN","VENDOR"
  created_at        TEXT NOT NULL DEFAULT (datetime('now')),
  updated_at        TEXT NOT NULL DEFAULT (datetime('now')),
  FOREIGN KEY (party_id) REFERENCES sf_party_person(party_id) ON DELETE CASCADE
);

CREATE INDEX IF NOT EXISTS idx_sf_doc_party ON sf_identity_document(party_id);
CREATE INDEX IF NOT EXISTS idx_sf_doc_type ON sf_identity_document(doc_type);

-- ------------------------------------------------------------
-- 7) sf_consent: consent and disclosures (privacy, e-sign, marketing)
-- ------------------------------------------------------------
CREATE TABLE IF NOT EXISTS sf_consent (
  consent_id        TEXT PRIMARY KEY,
  party_id          TEXT NOT NULL,
  consent_type      TEXT NOT NULL,        -- "PRIVACY_NOTICE","ESIGN","MARKETING_EMAIL","TCPA_SMS"
  consent_status    TEXT NOT NULL,        -- "GRANTED","DENIED","REVOKED"
  consented_at      TEXT,
  revoked_at        TEXT,
  source_channel    TEXT,                 -- "ONLINE","BRANCH", etc.
  evidence_ref      TEXT,                 -- link/id to document store if used
  created_at        TEXT NOT NULL DEFAULT (datetime('now')),
  updated_at        TEXT NOT NULL DEFAULT (datetime('now')),
  FOREIGN KEY (party_id) REFERENCES sf_party_person(party_id) ON DELETE CASCADE
);

CREATE INDEX IF NOT EXISTS idx_sf_consent_party ON sf_consent(party_id);
CREATE INDEX IF NOT EXISTS idx_sf_consent_type ON sf_consent(consent_type);

-- ------------------------------------------------------------
-- 8) sf_kyc_check: KYC / CIP / identity verification checks (one or more per application/party)
-- ------------------------------------------------------------
CREATE TABLE IF NOT EXISTS sf_kyc_check (
  kyc_check_id      TEXT PRIMARY KEY,
  application_id    TEXT NOT NULL,
  party_id          TEXT NOT NULL,
  check_type        TEXT NOT NULL,        -- "CIP_IDV","OFAC_SCREEN","ADDRESS_VERIFY","PHONE_VERIFY","FRAUD_SCORE"
  provider_name     TEXT,                 -- e.g., "LEXISNEXIS", "TRULIOO", etc.
  status_code       TEXT NOT NULL,        -- "PENDING","PASSED","FAILED","REVIEW"
  score_value       REAL,                 -- optional numeric score
  risk_level        TEXT,                 -- "LOW","MEDIUM","HIGH"
  performed_at      TEXT,
  raw_result_ref    TEXT,                 -- pointer to stored payload in secure store
  created_at        TEXT NOT NULL DEFAULT (datetime('now')),
  updated_at        TEXT NOT NULL DEFAULT (datetime('now')),
  FOREIGN KEY (application_id) REFERENCES sf_onboarding_application(application_id) ON DELETE CASCADE,
  FOREIGN KEY (party_id) REFERENCES sf_party_person(party_id) ON DELETE CASCADE
);

CREATE INDEX IF NOT EXISTS idx_sf_kyc_app ON sf_kyc_check(application_id);
CREATE INDEX IF NOT EXISTS idx_sf_kyc_party ON sf_kyc_check(party_id);
CREATE INDEX IF NOT EXISTS idx_sf_kyc_type ON sf_kyc_check(check_type);

-- ------------------------------------------------------------
-- 9) sf_screening_match: sanctions/PEP matches and dispositions (often downstream of a check)
-- ------------------------------------------------------------
CREATE TABLE IF NOT EXISTS sf_screening_match (
  match_id          TEXT PRIMARY KEY,
  kyc_check_id      TEXT NOT NULL,
  match_type        TEXT NOT NULL,        -- "SANCTIONS","PEP","ADVERSE_MEDIA","WATCHLIST"
  list_source       TEXT,                 -- e.g., "OFAC", "UN", "EU", "VENDOR_DB"
  matched_name      TEXT,
  match_score       REAL,                 -- vendor score
  disposition       TEXT,                 -- "TRUE_MATCH","FALSE_POSITIVE","ESCALATED"
  disposition_by    TEXT,
  disposition_at    TEXT,
  notes             TEXT,
  created_at        TEXT NOT NULL DEFAULT (datetime('now')),
  updated_at        TEXT NOT NULL DEFAULT (datetime('now')),
  FOREIGN KEY (kyc_check_id) REFERENCES sf_kyc_check(kyc_check_id) ON DELETE CASCADE,
  FOREIGN KEY (disposition_by) REFERENCES sf_user(user_id)
);

CREATE INDEX IF NOT EXISTS idx_sf_match_check ON sf_screening_match(kyc_check_id);
CREATE INDEX IF NOT EXISTS idx_sf_match_type ON sf_screening_match(match_type);
CREATE INDEX IF NOT EXISTS idx_sf_match_disp ON sf_screening_match(disposition);

-- ------------------------------------------------------------
-- 10) sf_application_audit_event: event trail (status changes, edits, approvals)
-- ------------------------------------------------------------
CREATE TABLE IF NOT EXISTS sf_application_audit_event (
  event_id          TEXT PRIMARY KEY,
  application_id    TEXT NOT NULL,
  party_id          TEXT,
  event_type        TEXT NOT NULL,        -- "STATUS_CHANGE","DATA_UPDATE","DOC_UPLOAD","KYC_DECISION","MANUAL_REVIEW"
  event_at          TEXT NOT NULL DEFAULT (datetime('now')),
  actor_user_id     TEXT,                 -- null for system automation
  old_value         TEXT,
  new_value         TEXT,
  comment           TEXT,
  created_at        TEXT NOT NULL DEFAULT (datetime('now')),
  FOREIGN KEY (application_id) REFERENCES sf_onboarding_application(application_id) ON DELETE CASCADE,
  FOREIGN KEY (party_id) REFERENCES sf_party_person(party_id) ON DELETE SET NULL,
  FOREIGN KEY (actor_user_id) REFERENCES sf_user(user_id)
);

CREATE INDEX IF NOT EXISTS idx_sf_evt_app ON sf_application_audit_event(application_id);
CREATE INDEX IF NOT EXISTS idx_sf_evt_type ON sf_application_audit_event(event_type);

-- ============================================================
-- End of Salesforce Onboarding DDL
-- ============================================================