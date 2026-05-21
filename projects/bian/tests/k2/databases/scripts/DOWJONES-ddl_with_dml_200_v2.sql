-- ============================================================
-- Dow Jones Risk & Compliance Feed (Sanctions + PEP) - SQLite DDL (10 tables)
-- Purpose: Logical representation of an external DJ watchlist feed
--          used for screening + ongoing monitoring, mapped into BIAN KYC.
--
-- Notes:
--  - This is a public-domain *logical* feed model (not DJ's proprietary schema).
--  - Designed for typical ingestion patterns:
--      * Entities (person/org) with names, identifiers, nationality, DOB, etc.
--      * Lists/classifications (SANCTIONS, PEP) and programs/regimes
--      * Aliases, addresses, documents, relationships (family/associate)
--      * Change history + delta loads (effective timestamps)
-- ============================================================

PRAGMA foreign_keys = ON;

-- ------------------------------------------------------------
-- 1) dj_feed_batch: ingest batch metadata (file pull / API snapshot)
-- ------------------------------------------------------------
CREATE TABLE IF NOT EXISTS dj_feed_batch (
  batch_id          TEXT PRIMARY KEY,
  source_name       TEXT NOT NULL DEFAULT 'DOW_JONES_RISK_COMPLIANCE',
  feed_type         TEXT NOT NULL,                 -- SANCTIONS|PEP|BOTH
  batch_version     TEXT,                          -- vendor version/date label
  extracted_at      TEXT NOT NULL DEFAULT (datetime('now')),
  record_count      INTEGER,
  checksum          TEXT
);

-- ------------------------------------------------------------
-- 2) dj_entity: the watchlist entity (person or organization)
-- ------------------------------------------------------------
CREATE TABLE IF NOT EXISTS dj_entity (
  entity_id         TEXT PRIMARY KEY,              -- vendor entity key
  entity_type       TEXT NOT NULL,                 -- PERSON|ORGANIZATION
  primary_name      TEXT NOT NULL,
  gender_code       TEXT,                          -- M|F|X|U (optional)
  date_of_birth     TEXT,                          -- for persons (YYYY-MM-DD or partial allowed)
  place_of_birth    TEXT,
  deceased_flag     INTEGER NOT NULL DEFAULT 0,
  nationality_code  TEXT,
  country_of_res    TEXT,
  risk_category     TEXT NOT NULL,                 -- SANCTIONS|PEP|BOTH (how you classify for your use)
  created_at        TEXT NOT NULL DEFAULT (datetime('now')),
  updated_at        TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE INDEX IF NOT EXISTS idx_dj_entity_name ON dj_entity(primary_name);
CREATE INDEX IF NOT EXISTS idx_dj_entity_type ON dj_entity(entity_type);
CREATE INDEX IF NOT EXISTS idx_dj_entity_cat  ON dj_entity(risk_category);

-- ------------------------------------------------------------
-- 3) dj_entity_alias: alternate names, transliterations, aka
-- ------------------------------------------------------------
CREATE TABLE IF NOT EXISTS dj_entity_alias (
  alias_id          TEXT PRIMARY KEY,
  entity_id         TEXT NOT NULL,
  alias_name        TEXT NOT NULL,
  alias_type        TEXT,                          -- AKA|FORMER_NAME|TRANSLITERATION|LOW_QUALITY
  language_code     TEXT,
  created_at        TEXT NOT NULL DEFAULT (datetime('now')),
  FOREIGN KEY (entity_id) REFERENCES dj_entity(entity_id) ON DELETE CASCADE
);

CREATE INDEX IF NOT EXISTS idx_dj_alias_entity ON dj_entity_alias(entity_id);

-- ------------------------------------------------------------
-- 4) dj_listing: sanctions/pep listing record (one entity can have many listings)
-- ------------------------------------------------------------
CREATE TABLE IF NOT EXISTS dj_listing (
  listing_id        TEXT PRIMARY KEY,
  entity_id         TEXT NOT NULL,
  listing_type      TEXT NOT NULL,                 -- SANCTIONS|PEP
  source_authority  TEXT,                          -- e.g., "OFAC", "UN", "EU", "HMT", "LOCAL_GOV"
  program_name      TEXT,                          -- sanctions program or PEP category name
  program_code      TEXT,                          -- optional
  active_flag       INTEGER NOT NULL DEFAULT 1,
  listed_date       TEXT,
  delisted_date     TEXT,
  remarks           TEXT,
  created_at        TEXT NOT NULL DEFAULT (datetime('now')),
  updated_at        TEXT NOT NULL DEFAULT (datetime('now')),
  FOREIGN KEY (entity_id) REFERENCES dj_entity(entity_id) ON DELETE CASCADE
);

CREATE INDEX IF NOT EXISTS idx_dj_listing_entity ON dj_listing(entity_id);
CREATE INDEX IF NOT EXISTS idx_dj_listing_type   ON dj_listing(listing_type);
CREATE INDEX IF NOT EXISTS idx_dj_listing_active ON dj_listing(active_flag);

-- ------------------------------------------------------------
-- 5) dj_identifier: passports, national IDs, tax IDs, other identifiers (masked/partial)
-- ------------------------------------------------------------
CREATE TABLE IF NOT EXISTS dj_identifier (
  identifier_id     TEXT PRIMARY KEY,
  entity_id         TEXT NOT NULL,
  id_type           TEXT NOT NULL,                 -- PASSPORT|NATIONAL_ID|TAX_ID|OTHER
  id_value          TEXT,                          -- vendor may provide masked/partial
  issuing_country   TEXT,
  issue_date        TEXT,
  expiry_date       TEXT,
  created_at        TEXT NOT NULL DEFAULT (datetime('now')),
  FOREIGN KEY (entity_id) REFERENCES dj_entity(entity_id) ON DELETE CASCADE
);

CREATE INDEX IF NOT EXISTS idx_dj_ident_entity ON dj_identifier(entity_id);
CREATE INDEX IF NOT EXISTS idx_dj_ident_type   ON dj_identifier(id_type);

-- ------------------------------------------------------------
-- 6) dj_address: known addresses / locations for entity
-- ------------------------------------------------------------
CREATE TABLE IF NOT EXISTS dj_address (
  address_id        TEXT PRIMARY KEY,
  entity_id         TEXT NOT NULL,
  address_type      TEXT,                          -- HOME|BUSINESS|REGISTERED|OTHER
  line1             TEXT,
  line2             TEXT,
  city              TEXT,
  state_region      TEXT,
  postal_code       TEXT,
  country_code      TEXT,
  created_at        TEXT NOT NULL DEFAULT (datetime('now')),
  FOREIGN KEY (entity_id) REFERENCES dj_entity(entity_id) ON DELETE CASCADE
);

CREATE INDEX IF NOT EXISTS idx_dj_addr_entity ON dj_address(entity_id);

-- ------------------------------------------------------------
-- 7) dj_pep_role: PEP positions / functions (only for PEP listings typically)
-- ------------------------------------------------------------
CREATE TABLE IF NOT EXISTS dj_pep_role (
  pep_role_id       TEXT PRIMARY KEY,
  entity_id         TEXT NOT NULL,
  role_title        TEXT,                          -- e.g., "Minister of Finance"
  role_type         TEXT,                          -- "GOVERNMENT","MILITARY","JUDICIARY","SOE","POLITICAL_PARTY"
  country_code      TEXT,
  start_date        TEXT,
  end_date          TEXT,
  current_flag      INTEGER NOT NULL DEFAULT 0,
  created_at        TEXT NOT NULL DEFAULT (datetime('now')),
  FOREIGN KEY (entity_id) REFERENCES dj_entity(entity_id) ON DELETE CASCADE
);

CREATE INDEX IF NOT EXISTS idx_dj_pep_entity ON dj_pep_role(entity_id);

-- ------------------------------------------------------------
-- 8) dj_relationship: associates/family/linked entities (useful for PEP networks)
-- ------------------------------------------------------------
CREATE TABLE IF NOT EXISTS dj_relationship (
  relationship_id   TEXT PRIMARY KEY,
  from_entity_id    TEXT NOT NULL,
  to_entity_id      TEXT NOT NULL,
  relationship_type TEXT NOT NULL,                 -- FAMILY|CLOSE_ASSOCIATE|BUSINESS_ASSOCIATE|LINKED_ENTITY
  relationship_desc TEXT,
  created_at        TEXT NOT NULL DEFAULT (datetime('now')),
  FOREIGN KEY (from_entity_id) REFERENCES dj_entity(entity_id) ON DELETE CASCADE,
  FOREIGN KEY (to_entity_id)   REFERENCES dj_entity(entity_id) ON DELETE CASCADE
);

CREATE INDEX IF NOT EXISTS idx_dj_rel_from ON dj_relationship(from_entity_id);
CREATE INDEX IF NOT EXISTS idx_dj_rel_to   ON dj_relationship(to_entity_id);

-- ------------------------------------------------------------
-- 9) dj_change_event: delta/change log for updates (for incremental loads)
-- ------------------------------------------------------------
CREATE TABLE IF NOT EXISTS dj_change_event (
  change_id         TEXT PRIMARY KEY,
  batch_id          TEXT NOT NULL,
  entity_id         TEXT NOT NULL,
  change_type       TEXT NOT NULL,                 -- ADD|UPDATE|DELETE|RELIST|DELIST
  changed_at        TEXT NOT NULL DEFAULT (datetime('now')),
  changed_field     TEXT,                          -- e.g., "PRIMARY_NAME","LISTING_ACTIVE"
  old_value         TEXT,
  new_value         TEXT,
  FOREIGN KEY (batch_id) REFERENCES dj_feed_batch(batch_id) ON DELETE CASCADE,
  FOREIGN KEY (entity_id) REFERENCES dj_entity(entity_id) ON DELETE CASCADE
);

CREATE INDEX IF NOT EXISTS idx_dj_change_batch ON dj_change_event(batch_id);
CREATE INDEX IF NOT EXISTS idx_dj_change_entity ON dj_change_event(entity_id);
CREATE INDEX IF NOT EXISTS idx_dj_change_type ON dj_change_event(change_type);

-- ------------------------------------------------------------
-- 10) dj_entity_version: snapshotting for history/audit (optional but common)
-- ------------------------------------------------------------
CREATE TABLE IF NOT EXISTS dj_entity_version (
  version_id        TEXT PRIMARY KEY,
  entity_id         TEXT NOT NULL,
  batch_id          TEXT NOT NULL,
  version_effective_at TEXT NOT NULL DEFAULT (datetime('now')),
  primary_name      TEXT,
  risk_category     TEXT,
  active_summary    TEXT,                          -- e.g., "SANCTIONS_ACTIVE=1;PEP_ACTIVE=0"
  serialized_ref    TEXT,                          -- pointer to stored full raw entity payload if you store it
  FOREIGN KEY (entity_id) REFERENCES dj_entity(entity_id) ON DELETE CASCADE,
  FOREIGN KEY (batch_id)  REFERENCES dj_feed_batch(batch_id) ON DELETE CASCADE
);

CREATE INDEX IF NOT EXISTS idx_dj_ver_entity ON dj_entity_version(entity_id);
CREATE INDEX IF NOT EXISTS idx_dj_ver_batch  ON dj_entity_version(batch_id);

-- ============================================================
-- End Dow Jones Risk & Compliance logical feed schema
-- ============================================================


-- ============================================================
-- DATA (DML): Demo population for Dow Jones watchlist feed schema
-- Source: seed_shared_truth_200_v2.sql (shared seed) - uses seed_dj_* subset
-- Coverage: 1 batch, 70 entities (linked to screening plans), listings, aliases, ids, roles, relationships
-- ============================================================

BEGIN TRANSACTION;

-- Populate dj_feed_batch: 1 rows
INSERT INTO dj_feed_batch (batch_id, source_name, feed_type, batch_version, extracted_at, record_count) VALUES
  ('DJBATCH20260227', 'DOW_JONES_RISK_COMPLIANCE', 'BOTH', 'v2026.02', '2026-02-27 08:45:00', 70);

-- Populate dj_entity: 70 rows
INSERT INTO dj_entity (entity_id, entity_type, primary_name, gender_code, date_of_birth, place_of_birth, deceased_flag, nationality_code, country_of_res, risk_category, created_at, updated_at) VALUES
  ('DJENT000001', 'PERSON', 'Naomi Garcia', 'F', '1956-01-18', NULL, 0, 'US', 'US', 'PEP', '2026-02-27 09:00:00', '2026-02-27 09:30:00'),
  ('DJENT000002', 'PERSON', 'Harper S. Lewis', 'F', '1996-03-06', NULL, 0, 'US', 'US', 'SANCTIONS', '2026-02-27 09:00:00', '2026-02-27 09:30:00'),
  ('DJENT000003', 'PERSON', 'Elena Jackson', 'M', '1971-01-10', NULL, 0, 'US', 'US', 'PEP', '2026-02-27 09:00:00', '2026-02-27 09:30:00'),
  ('DJENT000004', 'PERSON', 'Sebastian R. Gonzalez', 'F', '1973-06-09', NULL, 0, 'US', 'US', 'SANCTIONS', '2026-02-27 09:00:00', '2026-02-27 09:30:00'),
  ('DJENT000005', 'PERSON', 'Liam P. King', 'U', '1991-04-05', NULL, 0, 'US', 'US', 'PEP', '2026-02-27 09:00:00', '2026-02-27 09:30:00'),
  ('DJENT000006', 'PERSON', 'Owen T. Jones', 'F', '1975-06-22', NULL, 0, 'US', 'US', 'SANCTIONS', '2026-02-27 09:00:00', '2026-02-27 09:30:00'),
  ('DJENT000007', 'PERSON', 'Ella K. Nelson', 'F', '1990-05-24', NULL, 0, 'MX', 'MX', 'PEP', '2026-02-27 09:00:00', '2026-02-27 09:30:00'),
  ('DJENT000008', 'PERSON', 'Hazel Mitchell', 'U', '1997-06-17', NULL, 0, 'US', 'US', 'SANCTIONS', '2026-02-27 09:00:00', '2026-02-27 09:30:00'),
  ('DJENT000009', 'PERSON', 'Paisley A. Flores', 'M', '1976-05-18', NULL, 0, 'CA', 'CA', 'PEP', '2026-02-27 09:00:00', '2026-02-27 09:30:00'),
  ('DJENT000010', 'PERSON', 'Mia Moore', 'U', '1979-02-22', NULL, 0, 'US', 'US', 'SANCTIONS', '2026-02-27 09:00:00', '2026-02-27 09:30:00'),
  ('DJENT000011', 'PERSON', 'Wyatt F. Hernandez', 'F', '1998-05-10', NULL, 0, 'GB', 'GB', 'PEP', '2026-02-27 09:00:00', '2026-02-27 09:30:00'),
  ('DJENT000012', 'PERSON', 'Paisley F. Jones', 'F', '1998-05-02', NULL, 0, 'US', 'US', 'SANCTIONS', '2026-02-27 09:00:00', '2026-02-27 09:30:00'),
  ('DJENT000013', 'PERSON', 'Lillian Q. Green', 'U', '1968-06-27', NULL, 0, 'US', 'US', 'PEP', '2026-02-27 09:00:00', '2026-02-27 09:30:00'),
  ('DJENT000014', 'PERSON', 'Lucy White', 'F', '1986-09-15', NULL, 0, 'US', 'US', 'SANCTIONS', '2026-02-27 09:00:00', '2026-02-27 09:30:00'),
  ('DJENT000015', 'PERSON', 'Julia E. Phillips', 'F', '1970-03-23', NULL, 0, 'US', 'US', 'PEP', '2026-02-27 09:00:00', '2026-02-27 09:30:00'),
  ('DJENT000016', 'PERSON', 'John O. Harris', 'M', '2005-03-11', NULL, 0, 'US', 'US', 'SANCTIONS', '2026-02-27 09:00:00', '2026-02-27 09:30:00'),
  ('DJENT000017', 'PERSON', 'Evelyn M. Green', 'M', '1971-06-25', NULL, 0, 'US', 'US', 'PEP', '2026-02-27 09:00:00', '2026-02-27 09:30:00'),
  ('DJENT000018', 'PERSON', 'Charlotte Allen', 'U', '1997-01-06', NULL, 0, 'MX', 'MX', 'SANCTIONS', '2026-02-27 09:00:00', '2026-02-27 09:30:00'),
  ('DJENT000019', 'PERSON', 'Lucas M. Wright', 'F', '1969-10-22', NULL, 0, 'US', 'US', 'PEP', '2026-02-27 09:00:00', '2026-02-27 09:30:00'),
  ('DJENT000020', 'PERSON', 'Maverick C. Rodriguez', 'F', '1971-08-19', NULL, 0, 'US', 'US', 'SANCTIONS', '2026-02-27 09:00:00', '2026-02-27 09:30:00'),
  ('DJENT000021', 'PERSON', 'William G. Baker', 'M', '1987-09-27', NULL, 0, 'US', 'US', 'PEP', '2026-02-27 09:00:00', '2026-02-27 09:30:00'),
  ('DJENT000022', 'PERSON', 'Evelyn Lee', 'F', '1993-08-12', NULL, 0, 'US', 'US', 'SANCTIONS', '2026-02-27 09:00:00', '2026-02-27 09:30:00'),
  ('DJENT000023', 'PERSON', 'David L. Wilson', 'U', '1968-06-23', NULL, 0, 'US', 'US', 'PEP', '2026-02-27 09:00:00', '2026-02-27 09:30:00'),
  ('DJENT000024', 'PERSON', 'Henry F. Evans', 'F', '1983-02-13', NULL, 0, 'US', 'US', 'SANCTIONS', '2026-02-27 09:00:00', '2026-02-27 09:30:00'),
  ('DJENT000025', 'PERSON', 'Oliver White', 'M', '1993-10-05', NULL, 0, 'CA', 'CA', 'PEP', '2026-02-27 09:00:00', '2026-02-27 09:30:00'),
  ('DJENT000026', 'PERSON', 'Dylan Moore', 'M', '1967-12-25', NULL, 0, 'US', 'US', 'SANCTIONS', '2026-02-27 09:00:00', '2026-02-27 09:30:00'),
  ('DJENT000027', 'PERSON', 'Penelope Q. Wilson', 'M', '1962-12-18', NULL, 0, 'CA', 'CA', 'PEP', '2026-02-27 09:00:00', '2026-02-27 09:30:00'),
  ('DJENT000028', 'PERSON', 'Savannah M. Phillips', 'M', '1982-11-20', NULL, 0, 'US', 'US', 'SANCTIONS', '2026-02-27 09:00:00', '2026-02-27 09:30:00'),
  ('DJENT000029', 'PERSON', 'Nora M. Williams', 'F', '1956-03-01', NULL, 0, 'CA', 'CA', 'PEP', '2026-02-27 09:00:00', '2026-02-27 09:30:00'),
  ('DJENT000030', 'PERSON', 'Sofia D. Campbell', 'U', '1968-12-08', NULL, 0, 'CA', 'CA', 'SANCTIONS', '2026-02-27 09:00:00', '2026-02-27 09:30:00'),
  ('DJENT000031', 'PERSON', 'Maverick Parker', 'F', '1962-10-13', NULL, 0, 'US', 'US', 'PEP', '2026-02-27 09:00:00', '2026-02-27 09:30:00'),
  ('DJENT000032', 'PERSON', 'Samuel O. Edwards', 'U', '1992-10-12', NULL, 0, 'US', 'US', 'SANCTIONS', '2026-02-27 09:00:00', '2026-02-27 09:30:00'),
  ('DJENT000033', 'PERSON', 'Leo Torres', 'U', '1974-09-24', NULL, 0, 'US', 'US', 'PEP', '2026-02-27 09:00:00', '2026-02-27 09:30:00'),
  ('DJENT000034', 'PERSON', 'Paisley Turner', 'F', '1970-03-18', NULL, 0, 'US', 'US', 'SANCTIONS', '2026-02-27 09:00:00', '2026-02-27 09:30:00'),
  ('DJENT000035', 'PERSON', 'Madelyn M. Smith', 'M', '1963-08-20', NULL, 0, 'MX', 'MX', 'PEP', '2026-02-27 09:00:00', '2026-02-27 09:30:00'),
  ('DJENT000036', 'PERSON', 'Matthew Johnson', 'F', '1985-11-05', NULL, 0, 'US', 'US', 'SANCTIONS', '2026-02-27 09:00:00', '2026-02-27 09:30:00'),
  ('DJENT000037', 'PERSON', 'Levi Green', 'F', '1997-07-21', NULL, 0, 'US', 'US', 'PEP', '2026-02-27 09:00:00', '2026-02-27 09:30:00'),
  ('DJENT000038', 'PERSON', 'Leo A. Hill', 'U', '1996-04-01', NULL, 0, 'US', 'US', 'SANCTIONS', '2026-02-27 09:00:00', '2026-02-27 09:30:00'),
  ('DJENT000039', 'PERSON', 'Joseph O. Anderson', 'F', '1993-10-26', NULL, 0, 'US', 'US', 'PEP', '2026-02-27 09:00:00', '2026-02-27 09:30:00'),
  ('DJENT000040', 'PERSON', 'Isaac Torres', 'U', '1977-03-16', NULL, 0, 'US', 'US', 'SANCTIONS', '2026-02-27 09:00:00', '2026-02-27 09:30:00'),
  ('DJENT000041', 'PERSON', 'Chloe J. Smith', 'M', '2005-09-04', NULL, 0, 'US', 'US', 'PEP', '2026-02-27 09:00:00', '2026-02-27 09:30:00'),
  ('DJENT000042', 'PERSON', 'Sofia H. King', 'U', '1981-02-24', NULL, 0, 'US', 'US', 'SANCTIONS', '2026-02-27 09:00:00', '2026-02-27 09:30:00'),
  ('DJENT000043', 'PERSON', 'Zoe L. Taylor', 'U', '1980-02-16', NULL, 0, 'MX', 'MX', 'PEP', '2026-02-27 09:00:00', '2026-02-27 09:30:00'),
  ('DJENT000044', 'PERSON', 'Evelyn Hernandez', 'F', '1996-10-06', NULL, 0, 'US', 'US', 'SANCTIONS', '2026-02-27 09:00:00', '2026-02-27 09:30:00'),
  ('DJENT000045', 'PERSON', 'Samantha Lewis', 'M', '1961-10-15', NULL, 0, 'CA', 'CA', 'PEP', '2026-02-27 09:00:00', '2026-02-27 09:30:00'),
  ('DJENT000046', 'PERSON', 'Oliver K. Williams', 'U', '1997-10-14', NULL, 0, 'MX', 'MX', 'SANCTIONS', '2026-02-27 09:00:00', '2026-02-27 09:30:00'),
  ('DJENT000047', 'PERSON', 'William Ramirez', 'M', '1999-04-18', NULL, 0, 'US', 'US', 'PEP', '2026-02-27 09:00:00', '2026-02-27 09:30:00'),
  ('DJENT000048', 'PERSON', 'Addison Taylor', 'F', '1960-01-04', NULL, 0, 'CA', 'CA', 'SANCTIONS', '2026-02-27 09:00:00', '2026-02-27 09:30:00'),
  ('DJENT000049', 'PERSON', 'Hannah D. Jones', 'M', '1974-07-12', NULL, 0, 'US', 'US', 'PEP', '2026-02-27 09:00:00', '2026-02-27 09:30:00'),
  ('DJENT000050', 'PERSON', 'Charlotte Thompson', 'F', '1971-04-10', NULL, 0, 'US', 'US', 'SANCTIONS', '2026-02-27 09:00:00', '2026-02-27 09:30:00'),
  ('DJENT000051', 'PERSON', 'Gabriel N. Parker', 'F', '1957-02-28', NULL, 0, 'US', 'US', 'PEP', '2026-02-27 09:00:00', '2026-02-27 09:30:00'),
  ('DJENT000052', 'PERSON', 'Allison Lewis', 'U', '1973-06-07', NULL, 0, 'US', 'US', 'SANCTIONS', '2026-02-27 09:00:00', '2026-02-27 09:30:00'),
  ('DJENT000053', 'PERSON', 'Maya Anderson', 'U', '1968-09-09', NULL, 0, 'US', 'US', 'PEP', '2026-02-27 09:00:00', '2026-02-27 09:30:00'),
  ('DJENT000054', 'PERSON', 'Violet K. Clark', 'M', '1985-06-08', NULL, 0, 'GB', 'GB', 'SANCTIONS', '2026-02-27 09:00:00', '2026-02-27 09:30:00'),
  ('DJENT000055', 'PERSON', 'Benjamin Collins', 'F', '2004-10-05', NULL, 0, 'US', 'US', 'PEP', '2026-02-27 09:00:00', '2026-02-27 09:30:00'),
  ('DJENT000056', 'PERSON', 'Sebastian Davis', 'U', '1953-11-27', NULL, 0, 'US', 'US', 'SANCTIONS', '2026-02-27 09:00:00', '2026-02-27 09:30:00'),
  ('DJENT000057', 'PERSON', 'Leo Torres', 'F', '1971-03-01', NULL, 0, 'US', 'US', 'PEP', '2026-02-27 09:00:00', '2026-02-27 09:30:00'),
  ('DJENT000058', 'PERSON', 'Olivia Carter', 'F', '1990-04-04', NULL, 0, 'US', 'US', 'SANCTIONS', '2026-02-27 09:00:00', '2026-02-27 09:30:00'),
  ('DJENT000059', 'PERSON', 'Ivy Allen', 'F', '1968-04-01', NULL, 0, 'US', 'US', 'PEP', '2026-02-27 09:00:00', '2026-02-27 09:30:00'),
  ('DJENT000060', 'PERSON', 'Grace R. Jones', 'M', '1993-04-22', NULL, 0, 'US', 'US', 'SANCTIONS', '2026-02-27 09:00:00', '2026-02-27 09:30:00'),
  ('DJENT000061', 'PERSON', 'James Q. Mitchell', 'M', '1992-05-26', NULL, 0, 'US', 'US', 'PEP', '2026-02-27 09:00:00', '2026-02-27 09:30:00'),
  ('DJENT000062', 'PERSON', 'Mia M. Gonzalez', 'M', '1999-11-01', NULL, 0, 'GB', 'GB', 'SANCTIONS', '2026-02-27 09:00:00', '2026-02-27 09:30:00'),
  ('DJENT000063', 'PERSON', 'Elena F. Jones', 'M', '1956-03-11', NULL, 0, 'MX', 'MX', 'PEP', '2026-02-27 09:00:00', '2026-02-27 09:30:00'),
  ('DJENT000064', 'PERSON', 'Mia R. Garcia', 'F', '2006-06-20', NULL, 0, 'CA', 'CA', 'SANCTIONS', '2026-02-27 09:00:00', '2026-02-27 09:30:00'),
  ('DJENT000065', 'PERSON', 'Stella Torres', 'U', '1994-09-22', NULL, 0, 'US', 'US', 'PEP', '2026-02-27 09:00:00', '2026-02-27 09:30:00'),
  ('DJENT000066', 'PERSON', 'Julia Phillips', 'F', '1978-08-25', NULL, 0, 'US', 'US', 'SANCTIONS', '2026-02-27 09:00:00', '2026-02-27 09:30:00'),
  ('DJENT000067', 'PERSON', 'Quinn D. Moore', 'U', '1990-07-16', NULL, 0, 'US', 'US', 'PEP', '2026-02-27 09:00:00', '2026-02-27 09:30:00'),
  ('DJENT000068', 'PERSON', 'Carter D. Robinson', 'M', '1952-01-26', NULL, 0, 'US', 'US', 'SANCTIONS', '2026-02-27 09:00:00', '2026-02-27 09:30:00'),
  ('DJENT000069', 'PERSON', 'Josiah Clark', 'F', '1968-12-08', NULL, 0, 'US', 'US', 'PEP', '2026-02-27 09:00:00', '2026-02-27 09:30:00'),
  ('DJENT000070', 'PERSON', 'Maverick Walker', 'F', '1971-09-08', NULL, 0, 'US', 'US', 'SANCTIONS', '2026-02-27 09:00:00', '2026-02-27 09:30:00');

-- Populate dj_listing: 70 rows
INSERT INTO dj_listing (listing_id, entity_id, listing_type, source_authority, program_name, program_code, active_flag, listed_date, delisted_date, remarks, created_at, updated_at) VALUES
  ('DJLST000001', 'DJENT000001', 'PEP', 'OTHER', 'PEP_GENERAL', NULL, 1, '2020-10-05', NULL, NULL, '2026-02-27 09:00:00', '2026-02-27 09:30:00'),
  ('DJLST000002', 'DJENT000002', 'SANCTIONS', 'OFAC', 'SDN', NULL, 1, '2021-08-06', NULL, NULL, '2026-02-27 09:00:00', '2026-02-27 09:30:00'),
  ('DJLST000003', 'DJENT000003', 'PEP', 'OTHER', 'PEP_GENERAL', NULL, 1, '2022-04-02', NULL, NULL, '2026-02-27 09:00:00', '2026-02-27 09:30:00'),
  ('DJLST000004', 'DJENT000004', 'SANCTIONS', 'OFAC', 'SDN', NULL, 1, '2024-05-17', NULL, NULL, '2026-02-27 09:00:00', '2026-02-27 09:30:00'),
  ('DJLST000005', 'DJENT000005', 'PEP', 'OTHER', 'PEP_GENERAL', NULL, 1, '2020-07-04', NULL, NULL, '2026-02-27 09:00:00', '2026-02-27 09:30:00'),
  ('DJLST000006', 'DJENT000006', 'SANCTIONS', 'OFAC', 'SDN', NULL, 1, '2024-05-18', NULL, NULL, '2026-02-27 09:00:00', '2026-02-27 09:30:00'),
  ('DJLST000007', 'DJENT000007', 'PEP', 'OTHER', 'PEP_GENERAL', NULL, 1, '2023-07-18', NULL, NULL, '2026-02-27 09:00:00', '2026-02-27 09:30:00'),
  ('DJLST000008', 'DJENT000008', 'SANCTIONS', 'OFAC', 'SDN', NULL, 1, '2023-10-07', NULL, NULL, '2026-02-27 09:00:00', '2026-02-27 09:30:00'),
  ('DJLST000009', 'DJENT000009', 'PEP', 'OTHER', 'PEP_GENERAL', NULL, 1, '2025-05-15', NULL, NULL, '2026-02-27 09:00:00', '2026-02-27 09:30:00'),
  ('DJLST000010', 'DJENT000010', 'SANCTIONS', 'OFAC', 'SDN', NULL, 1, '2024-01-14', NULL, NULL, '2026-02-27 09:00:00', '2026-02-27 09:30:00'),
  ('DJLST000011', 'DJENT000011', 'PEP', 'OTHER', 'PEP_GENERAL', NULL, 1, '2022-09-15', NULL, NULL, '2026-02-27 09:00:00', '2026-02-27 09:30:00'),
  ('DJLST000012', 'DJENT000012', 'SANCTIONS', 'OFAC', 'SDN', NULL, 1, '2023-12-09', NULL, NULL, '2026-02-27 09:00:00', '2026-02-27 09:30:00'),
  ('DJLST000013', 'DJENT000013', 'PEP', 'OTHER', 'PEP_GENERAL', NULL, 1, '2021-10-10', NULL, NULL, '2026-02-27 09:00:00', '2026-02-27 09:30:00'),
  ('DJLST000014', 'DJENT000014', 'SANCTIONS', 'OFAC', 'SDN', NULL, 1, '2020-09-23', NULL, NULL, '2026-02-27 09:00:00', '2026-02-27 09:30:00'),
  ('DJLST000015', 'DJENT000015', 'PEP', 'OTHER', 'PEP_GENERAL', NULL, 1, '2025-06-22', NULL, NULL, '2026-02-27 09:00:00', '2026-02-27 09:30:00'),
  ('DJLST000016', 'DJENT000016', 'SANCTIONS', 'OFAC', 'SDN', NULL, 1, '2024-11-30', NULL, NULL, '2026-02-27 09:00:00', '2026-02-27 09:30:00'),
  ('DJLST000017', 'DJENT000017', 'PEP', 'OTHER', 'PEP_GENERAL', NULL, 1, '2021-01-25', NULL, NULL, '2026-02-27 09:00:00', '2026-02-27 09:30:00'),
  ('DJLST000018', 'DJENT000018', 'SANCTIONS', 'OFAC', 'SDN', NULL, 1, '2021-09-16', NULL, NULL, '2026-02-27 09:00:00', '2026-02-27 09:30:00'),
  ('DJLST000019', 'DJENT000019', 'PEP', 'OTHER', 'PEP_GENERAL', NULL, 1, '2021-03-28', NULL, NULL, '2026-02-27 09:00:00', '2026-02-27 09:30:00'),
  ('DJLST000020', 'DJENT000020', 'SANCTIONS', 'OFAC', 'SDN', NULL, 1, '2025-03-07', NULL, NULL, '2026-02-27 09:00:00', '2026-02-27 09:30:00'),
  ('DJLST000021', 'DJENT000021', 'PEP', 'OTHER', 'PEP_GENERAL', NULL, 1, '2025-10-16', NULL, NULL, '2026-02-27 09:00:00', '2026-02-27 09:30:00'),
  ('DJLST000022', 'DJENT000022', 'SANCTIONS', 'OFAC', 'SDN', NULL, 1, '2025-12-08', NULL, NULL, '2026-02-27 09:00:00', '2026-02-27 09:30:00'),
  ('DJLST000023', 'DJENT000023', 'PEP', 'OTHER', 'PEP_GENERAL', NULL, 1, '2020-05-26', NULL, NULL, '2026-02-27 09:00:00', '2026-02-27 09:30:00'),
  ('DJLST000024', 'DJENT000024', 'SANCTIONS', 'OFAC', 'SDN', NULL, 1, '2020-02-24', NULL, NULL, '2026-02-27 09:00:00', '2026-02-27 09:30:00'),
  ('DJLST000025', 'DJENT000025', 'PEP', 'OTHER', 'PEP_GENERAL', NULL, 1, '2022-11-12', NULL, NULL, '2026-02-27 09:00:00', '2026-02-27 09:30:00'),
  ('DJLST000026', 'DJENT000026', 'SANCTIONS', 'OFAC', 'SDN', NULL, 1, '2021-03-11', NULL, NULL, '2026-02-27 09:00:00', '2026-02-27 09:30:00'),
  ('DJLST000027', 'DJENT000027', 'PEP', 'OTHER', 'PEP_GENERAL', NULL, 1, '2023-07-27', NULL, NULL, '2026-02-27 09:00:00', '2026-02-27 09:30:00'),
  ('DJLST000028', 'DJENT000028', 'SANCTIONS', 'OFAC', 'SDN', NULL, 1, '2024-05-25', NULL, NULL, '2026-02-27 09:00:00', '2026-02-27 09:30:00'),
  ('DJLST000029', 'DJENT000029', 'PEP', 'OTHER', 'PEP_GENERAL', NULL, 1, '2022-05-16', NULL, NULL, '2026-02-27 09:00:00', '2026-02-27 09:30:00'),
  ('DJLST000030', 'DJENT000030', 'SANCTIONS', 'OFAC', 'SDN', NULL, 1, '2024-02-17', NULL, NULL, '2026-02-27 09:00:00', '2026-02-27 09:30:00'),
  ('DJLST000031', 'DJENT000031', 'PEP', 'OTHER', 'PEP_GENERAL', NULL, 1, '2024-10-13', NULL, NULL, '2026-02-27 09:00:00', '2026-02-27 09:30:00'),
  ('DJLST000032', 'DJENT000032', 'SANCTIONS', 'OFAC', 'SDN', NULL, 1, '2022-07-04', NULL, NULL, '2026-02-27 09:00:00', '2026-02-27 09:30:00'),
  ('DJLST000033', 'DJENT000033', 'PEP', 'OTHER', 'PEP_GENERAL', NULL, 1, '2021-09-24', NULL, NULL, '2026-02-27 09:00:00', '2026-02-27 09:30:00'),
  ('DJLST000034', 'DJENT000034', 'SANCTIONS', 'OFAC', 'SDN', NULL, 1, '2024-06-02', NULL, NULL, '2026-02-27 09:00:00', '2026-02-27 09:30:00'),
  ('DJLST000035', 'DJENT000035', 'PEP', 'OTHER', 'PEP_GENERAL', NULL, 1, '2022-05-02', NULL, NULL, '2026-02-27 09:00:00', '2026-02-27 09:30:00'),
  ('DJLST000036', 'DJENT000036', 'SANCTIONS', 'OFAC', 'SDN', NULL, 1, '2020-06-06', NULL, NULL, '2026-02-27 09:00:00', '2026-02-27 09:30:00'),
  ('DJLST000037', 'DJENT000037', 'PEP', 'OTHER', 'PEP_GENERAL', NULL, 1, '2022-10-16', NULL, NULL, '2026-02-27 09:00:00', '2026-02-27 09:30:00'),
  ('DJLST000038', 'DJENT000038', 'SANCTIONS', 'OFAC', 'SDN', NULL, 1, '2025-03-12', NULL, NULL, '2026-02-27 09:00:00', '2026-02-27 09:30:00'),
  ('DJLST000039', 'DJENT000039', 'PEP', 'OTHER', 'PEP_GENERAL', NULL, 1, '2021-11-08', NULL, NULL, '2026-02-27 09:00:00', '2026-02-27 09:30:00'),
  ('DJLST000040', 'DJENT000040', 'SANCTIONS', 'OFAC', 'SDN', NULL, 1, '2023-08-07', NULL, NULL, '2026-02-27 09:00:00', '2026-02-27 09:30:00'),
  ('DJLST000041', 'DJENT000041', 'PEP', 'OTHER', 'PEP_GENERAL', NULL, 1, '2021-06-25', NULL, NULL, '2026-02-27 09:00:00', '2026-02-27 09:30:00'),
  ('DJLST000042', 'DJENT000042', 'SANCTIONS', 'OFAC', 'SDN', NULL, 1, '2020-05-01', NULL, NULL, '2026-02-27 09:00:00', '2026-02-27 09:30:00'),
  ('DJLST000043', 'DJENT000043', 'PEP', 'OTHER', 'PEP_GENERAL', NULL, 1, '2023-12-21', NULL, NULL, '2026-02-27 09:00:00', '2026-02-27 09:30:00'),
  ('DJLST000044', 'DJENT000044', 'SANCTIONS', 'OFAC', 'SDN', NULL, 1, '2020-08-02', NULL, NULL, '2026-02-27 09:00:00', '2026-02-27 09:30:00'),
  ('DJLST000045', 'DJENT000045', 'PEP', 'OTHER', 'PEP_GENERAL', NULL, 1, '2021-09-13', NULL, NULL, '2026-02-27 09:00:00', '2026-02-27 09:30:00'),
  ('DJLST000046', 'DJENT000046', 'SANCTIONS', 'OFAC', 'SDN', NULL, 1, '2021-06-13', NULL, NULL, '2026-02-27 09:00:00', '2026-02-27 09:30:00'),
  ('DJLST000047', 'DJENT000047', 'PEP', 'OTHER', 'PEP_GENERAL', NULL, 1, '2023-12-14', NULL, NULL, '2026-02-27 09:00:00', '2026-02-27 09:30:00'),
  ('DJLST000048', 'DJENT000048', 'SANCTIONS', 'OFAC', 'SDN', NULL, 1, '2025-12-04', NULL, NULL, '2026-02-27 09:00:00', '2026-02-27 09:30:00'),
  ('DJLST000049', 'DJENT000049', 'PEP', 'OTHER', 'PEP_GENERAL', NULL, 1, '2024-09-19', NULL, NULL, '2026-02-27 09:00:00', '2026-02-27 09:30:00'),
  ('DJLST000050', 'DJENT000050', 'SANCTIONS', 'OFAC', 'SDN', NULL, 1, '2024-06-13', NULL, NULL, '2026-02-27 09:00:00', '2026-02-27 09:30:00'),
  ('DJLST000051', 'DJENT000051', 'PEP', 'OTHER', 'PEP_GENERAL', NULL, 1, '2023-07-08', NULL, NULL, '2026-02-27 09:00:00', '2026-02-27 09:30:00'),
  ('DJLST000052', 'DJENT000052', 'SANCTIONS', 'OFAC', 'SDN', NULL, 1, '2021-07-03', NULL, NULL, '2026-02-27 09:00:00', '2026-02-27 09:30:00'),
  ('DJLST000053', 'DJENT000053', 'PEP', 'OTHER', 'PEP_GENERAL', NULL, 1, '2020-07-19', NULL, NULL, '2026-02-27 09:00:00', '2026-02-27 09:30:00'),
  ('DJLST000054', 'DJENT000054', 'SANCTIONS', 'OFAC', 'SDN', NULL, 1, '2020-03-21', NULL, NULL, '2026-02-27 09:00:00', '2026-02-27 09:30:00'),
  ('DJLST000055', 'DJENT000055', 'PEP', 'OTHER', 'PEP_GENERAL', NULL, 1, '2025-02-25', NULL, NULL, '2026-02-27 09:00:00', '2026-02-27 09:30:00'),
  ('DJLST000056', 'DJENT000056', 'SANCTIONS', 'OFAC', 'SDN', NULL, 1, '2024-04-07', NULL, NULL, '2026-02-27 09:00:00', '2026-02-27 09:30:00'),
  ('DJLST000057', 'DJENT000057', 'PEP', 'OTHER', 'PEP_GENERAL', NULL, 1, '2023-09-19', NULL, NULL, '2026-02-27 09:00:00', '2026-02-27 09:30:00'),
  ('DJLST000058', 'DJENT000058', 'SANCTIONS', 'OFAC', 'SDN', NULL, 1, '2025-03-17', NULL, NULL, '2026-02-27 09:00:00', '2026-02-27 09:30:00'),
  ('DJLST000059', 'DJENT000059', 'PEP', 'OTHER', 'PEP_GENERAL', NULL, 1, '2022-11-11', NULL, NULL, '2026-02-27 09:00:00', '2026-02-27 09:30:00'),
  ('DJLST000060', 'DJENT000060', 'SANCTIONS', 'OFAC', 'SDN', NULL, 1, '2022-03-29', NULL, NULL, '2026-02-27 09:00:00', '2026-02-27 09:30:00'),
  ('DJLST000061', 'DJENT000061', 'PEP', 'OTHER', 'PEP_GENERAL', NULL, 1, '2023-12-07', NULL, NULL, '2026-02-27 09:00:00', '2026-02-27 09:30:00'),
  ('DJLST000062', 'DJENT000062', 'SANCTIONS', 'OFAC', 'SDN', NULL, 1, '2021-11-16', NULL, NULL, '2026-02-27 09:00:00', '2026-02-27 09:30:00'),
  ('DJLST000063', 'DJENT000063', 'PEP', 'OTHER', 'PEP_GENERAL', NULL, 1, '2022-04-23', NULL, NULL, '2026-02-27 09:00:00', '2026-02-27 09:30:00'),
  ('DJLST000064', 'DJENT000064', 'SANCTIONS', 'OFAC', 'SDN', NULL, 1, '2023-04-20', NULL, NULL, '2026-02-27 09:00:00', '2026-02-27 09:30:00'),
  ('DJLST000065', 'DJENT000065', 'PEP', 'OTHER', 'PEP_GENERAL', NULL, 1, '2023-02-26', NULL, NULL, '2026-02-27 09:00:00', '2026-02-27 09:30:00'),
  ('DJLST000066', 'DJENT000066', 'SANCTIONS', 'OFAC', 'SDN', NULL, 1, '2025-01-20', NULL, NULL, '2026-02-27 09:00:00', '2026-02-27 09:30:00'),
  ('DJLST000067', 'DJENT000067', 'PEP', 'OTHER', 'PEP_GENERAL', NULL, 1, '2021-05-03', NULL, NULL, '2026-02-27 09:00:00', '2026-02-27 09:30:00'),
  ('DJLST000068', 'DJENT000068', 'SANCTIONS', 'OFAC', 'SDN', NULL, 1, '2022-06-11', NULL, NULL, '2026-02-27 09:00:00', '2026-02-27 09:30:00'),
  ('DJLST000069', 'DJENT000069', 'PEP', 'OTHER', 'PEP_GENERAL', NULL, 1, '2020-11-13', NULL, NULL, '2026-02-27 09:00:00', '2026-02-27 09:30:00'),
  ('DJLST000070', 'DJENT000070', 'SANCTIONS', 'OFAC', 'SDN', NULL, 1, '2020-06-30', NULL, NULL, '2026-02-27 09:00:00', '2026-02-27 09:30:00');

-- Populate dj_entity_alias: 109 rows
INSERT INTO dj_entity_alias (alias_id, entity_id, alias_name, alias_type, language_code, created_at) VALUES
  ('DJAL000001', 'DJENT000001', 'Garcia, Naomi', 'AKA', 'en', '2026-02-27 09:00:00'),
  ('DJAL000002', 'DJENT000002', 'Lewis, Harper', 'AKA', 'en', '2026-02-27 09:00:00'),
  ('DJAL000003', 'DJENT000002', 'Harper Lewis', 'AKA', 'en', '2026-02-27 09:00:00'),
  ('DJAL000004', 'DJENT000003', 'Jackson, Elena', 'AKA', 'en', '2026-02-27 09:00:00'),
  ('DJAL000005', 'DJENT000004', 'Gonzalez, Sebastian', 'AKA', 'en', '2026-02-27 09:00:00'),
  ('DJAL000006', 'DJENT000004', 'Sebastian Gonzalez', 'AKA', 'en', '2026-02-27 09:00:00'),
  ('DJAL000007', 'DJENT000005', 'King, Liam', 'AKA', 'en', '2026-02-27 09:00:00'),
  ('DJAL000008', 'DJENT000005', 'Liam King', 'AKA', 'en', '2026-02-27 09:00:00'),
  ('DJAL000009', 'DJENT000006', 'Jones, Owen', 'AKA', 'en', '2026-02-27 09:00:00'),
  ('DJAL000010', 'DJENT000006', 'Owen Jones', 'AKA', 'en', '2026-02-27 09:00:00'),
  ('DJAL000011', 'DJENT000007', 'Nelson, Ella', 'AKA', 'en', '2026-02-27 09:00:00'),
  ('DJAL000012', 'DJENT000007', 'Ella Nelson', 'AKA', 'en', '2026-02-27 09:00:00'),
  ('DJAL000013', 'DJENT000008', 'Mitchell, Hazel', 'AKA', 'en', '2026-02-27 09:00:00'),
  ('DJAL000014', 'DJENT000009', 'Flores, Paisley', 'AKA', 'en', '2026-02-27 09:00:00'),
  ('DJAL000015', 'DJENT000009', 'Paisley Flores', 'AKA', 'en', '2026-02-27 09:00:00'),
  ('DJAL000016', 'DJENT000010', 'Moore, Mia', 'AKA', 'en', '2026-02-27 09:00:00'),
  ('DJAL000017', 'DJENT000011', 'Hernandez, Wyatt', 'AKA', 'en', '2026-02-27 09:00:00'),
  ('DJAL000018', 'DJENT000011', 'Wyatt Hernandez', 'AKA', 'en', '2026-02-27 09:00:00'),
  ('DJAL000019', 'DJENT000012', 'Jones, Paisley', 'AKA', 'en', '2026-02-27 09:00:00'),
  ('DJAL000020', 'DJENT000012', 'Paisley Jones', 'AKA', 'en', '2026-02-27 09:00:00'),
  ('DJAL000021', 'DJENT000013', 'Green, Lillian', 'AKA', 'en', '2026-02-27 09:00:00'),
  ('DJAL000022', 'DJENT000013', 'Lillian Green', 'AKA', 'en', '2026-02-27 09:00:00'),
  ('DJAL000023', 'DJENT000014', 'White, Lucy', 'AKA', 'en', '2026-02-27 09:00:00'),
  ('DJAL000024', 'DJENT000015', 'Phillips, Julia', 'AKA', 'en', '2026-02-27 09:00:00'),
  ('DJAL000025', 'DJENT000015', 'Julia Phillips', 'AKA', 'en', '2026-02-27 09:00:00'),
  ('DJAL000026', 'DJENT000016', 'Harris, John', 'AKA', 'en', '2026-02-27 09:00:00'),
  ('DJAL000027', 'DJENT000016', 'John Harris', 'AKA', 'en', '2026-02-27 09:00:00'),
  ('DJAL000028', 'DJENT000017', 'Green, Evelyn', 'AKA', 'en', '2026-02-27 09:00:00'),
  ('DJAL000029', 'DJENT000017', 'Evelyn Green', 'AKA', 'en', '2026-02-27 09:00:00'),
  ('DJAL000030', 'DJENT000018', 'Allen, Charlotte', 'AKA', 'en', '2026-02-27 09:00:00'),
  ('DJAL000031', 'DJENT000019', 'Wright, Lucas', 'AKA', 'en', '2026-02-27 09:00:00'),
  ('DJAL000032', 'DJENT000019', 'Lucas Wright', 'AKA', 'en', '2026-02-27 09:00:00'),
  ('DJAL000033', 'DJENT000020', 'Rodriguez, Maverick', 'AKA', 'en', '2026-02-27 09:00:00'),
  ('DJAL000034', 'DJENT000020', 'Maverick Rodriguez', 'AKA', 'en', '2026-02-27 09:00:00'),
  ('DJAL000035', 'DJENT000021', 'Baker, William', 'AKA', 'en', '2026-02-27 09:00:00'),
  ('DJAL000036', 'DJENT000021', 'William Baker', 'AKA', 'en', '2026-02-27 09:00:00'),
  ('DJAL000037', 'DJENT000022', 'Lee, Evelyn', 'AKA', 'en', '2026-02-27 09:00:00'),
  ('DJAL000038', 'DJENT000023', 'Wilson, David', 'AKA', 'en', '2026-02-27 09:00:00'),
  ('DJAL000039', 'DJENT000023', 'David Wilson', 'AKA', 'en', '2026-02-27 09:00:00'),
  ('DJAL000040', 'DJENT000024', 'Evans, Henry', 'AKA', 'en', '2026-02-27 09:00:00'),
  ('DJAL000041', 'DJENT000024', 'Henry Evans', 'AKA', 'en', '2026-02-27 09:00:00'),
  ('DJAL000042', 'DJENT000025', 'White, Oliver', 'AKA', 'en', '2026-02-27 09:00:00'),
  ('DJAL000043', 'DJENT000026', 'Moore, Dylan', 'AKA', 'en', '2026-02-27 09:00:00'),
  ('DJAL000044', 'DJENT000027', 'Wilson, Penelope', 'AKA', 'en', '2026-02-27 09:00:00'),
  ('DJAL000045', 'DJENT000027', 'Penelope Wilson', 'AKA', 'en', '2026-02-27 09:00:00'),
  ('DJAL000046', 'DJENT000028', 'Phillips, Savannah', 'AKA', 'en', '2026-02-27 09:00:00'),
  ('DJAL000047', 'DJENT000028', 'Savannah Phillips', 'AKA', 'en', '2026-02-27 09:00:00'),
  ('DJAL000048', 'DJENT000029', 'Williams, Nora', 'AKA', 'en', '2026-02-27 09:00:00'),
  ('DJAL000049', 'DJENT000029', 'Nora Williams', 'AKA', 'en', '2026-02-27 09:00:00'),
  ('DJAL000050', 'DJENT000030', 'Campbell, Sofia', 'AKA', 'en', '2026-02-27 09:00:00'),
  ('DJAL000051', 'DJENT000030', 'Sofia Campbell', 'AKA', 'en', '2026-02-27 09:00:00'),
  ('DJAL000052', 'DJENT000031', 'Parker, Maverick', 'AKA', 'en', '2026-02-27 09:00:00'),
  ('DJAL000053', 'DJENT000032', 'Edwards, Samuel', 'AKA', 'en', '2026-02-27 09:00:00'),
  ('DJAL000054', 'DJENT000032', 'Samuel Edwards', 'AKA', 'en', '2026-02-27 09:00:00'),
  ('DJAL000055', 'DJENT000033', 'Torres, Leo', 'AKA', 'en', '2026-02-27 09:00:00'),
  ('DJAL000056', 'DJENT000034', 'Turner, Paisley', 'AKA', 'en', '2026-02-27 09:00:00'),
  ('DJAL000057', 'DJENT000035', 'Smith, Madelyn', 'AKA', 'en', '2026-02-27 09:00:00'),
  ('DJAL000058', 'DJENT000035', 'Madelyn Smith', 'AKA', 'en', '2026-02-27 09:00:00'),
  ('DJAL000059', 'DJENT000036', 'Johnson, Matthew', 'AKA', 'en', '2026-02-27 09:00:00'),
  ('DJAL000060', 'DJENT000037', 'Green, Levi', 'AKA', 'en', '2026-02-27 09:00:00'),
  ('DJAL000061', 'DJENT000038', 'Hill, Leo', 'AKA', 'en', '2026-02-27 09:00:00'),
  ('DJAL000062', 'DJENT000038', 'Leo Hill', 'AKA', 'en', '2026-02-27 09:00:00'),
  ('DJAL000063', 'DJENT000039', 'Anderson, Joseph', 'AKA', 'en', '2026-02-27 09:00:00'),
  ('DJAL000064', 'DJENT000039', 'Joseph Anderson', 'AKA', 'en', '2026-02-27 09:00:00'),
  ('DJAL000065', 'DJENT000040', 'Torres, Isaac', 'AKA', 'en', '2026-02-27 09:00:00'),
  ('DJAL000066', 'DJENT000041', 'Smith, Chloe', 'AKA', 'en', '2026-02-27 09:00:00'),
  ('DJAL000067', 'DJENT000041', 'Chloe Smith', 'AKA', 'en', '2026-02-27 09:00:00'),
  ('DJAL000068', 'DJENT000042', 'King, Sofia', 'AKA', 'en', '2026-02-27 09:00:00'),
  ('DJAL000069', 'DJENT000042', 'Sofia King', 'AKA', 'en', '2026-02-27 09:00:00'),
  ('DJAL000070', 'DJENT000043', 'Taylor, Zoe', 'AKA', 'en', '2026-02-27 09:00:00'),
  ('DJAL000071', 'DJENT000043', 'Zoe Taylor', 'AKA', 'en', '2026-02-27 09:00:00'),
  ('DJAL000072', 'DJENT000044', 'Hernandez, Evelyn', 'AKA', 'en', '2026-02-27 09:00:00'),
  ('DJAL000073', 'DJENT000045', 'Lewis, Samantha', 'AKA', 'en', '2026-02-27 09:00:00'),
  ('DJAL000074', 'DJENT000046', 'Williams, Oliver', 'AKA', 'en', '2026-02-27 09:00:00'),
  ('DJAL000075', 'DJENT000046', 'Oliver Williams', 'AKA', 'en', '2026-02-27 09:00:00'),
  ('DJAL000076', 'DJENT000047', 'Ramirez, William', 'AKA', 'en', '2026-02-27 09:00:00'),
  ('DJAL000077', 'DJENT000048', 'Taylor, Addison', 'AKA', 'en', '2026-02-27 09:00:00'),
  ('DJAL000078', 'DJENT000049', 'Jones, Hannah', 'AKA', 'en', '2026-02-27 09:00:00'),
  ('DJAL000079', 'DJENT000049', 'Hannah Jones', 'AKA', 'en', '2026-02-27 09:00:00'),
  ('DJAL000080', 'DJENT000050', 'Thompson, Charlotte', 'AKA', 'en', '2026-02-27 09:00:00'),
  ('DJAL000081', 'DJENT000051', 'Parker, Gabriel', 'AKA', 'en', '2026-02-27 09:00:00'),
  ('DJAL000082', 'DJENT000051', 'Gabriel Parker', 'AKA', 'en', '2026-02-27 09:00:00'),
  ('DJAL000083', 'DJENT000052', 'Lewis, Allison', 'AKA', 'en', '2026-02-27 09:00:00'),
  ('DJAL000084', 'DJENT000053', 'Anderson, Maya', 'AKA', 'en', '2026-02-27 09:00:00'),
  ('DJAL000085', 'DJENT000054', 'Clark, Violet', 'AKA', 'en', '2026-02-27 09:00:00'),
  ('DJAL000086', 'DJENT000054', 'Violet Clark', 'AKA', 'en', '2026-02-27 09:00:00'),
  ('DJAL000087', 'DJENT000055', 'Collins, Benjamin', 'AKA', 'en', '2026-02-27 09:00:00'),
  ('DJAL000088', 'DJENT000056', 'Davis, Sebastian', 'AKA', 'en', '2026-02-27 09:00:00'),
  ('DJAL000089', 'DJENT000057', 'Torres, Leo', 'AKA', 'en', '2026-02-27 09:00:00'),
  ('DJAL000090', 'DJENT000058', 'Carter, Olivia', 'AKA', 'en', '2026-02-27 09:00:00'),
  ('DJAL000091', 'DJENT000059', 'Allen, Ivy', 'AKA', 'en', '2026-02-27 09:00:00'),
  ('DJAL000092', 'DJENT000060', 'Jones, Grace', 'AKA', 'en', '2026-02-27 09:00:00'),
  ('DJAL000093', 'DJENT000060', 'Grace Jones', 'AKA', 'en', '2026-02-27 09:00:00'),
  ('DJAL000094', 'DJENT000061', 'Mitchell, James', 'AKA', 'en', '2026-02-27 09:00:00'),
  ('DJAL000095', 'DJENT000061', 'James Mitchell', 'AKA', 'en', '2026-02-27 09:00:00'),
  ('DJAL000096', 'DJENT000062', 'Gonzalez, Mia', 'AKA', 'en', '2026-02-27 09:00:00'),
  ('DJAL000097', 'DJENT000062', 'Mia Gonzalez', 'AKA', 'en', '2026-02-27 09:00:00'),
  ('DJAL000098', 'DJENT000063', 'Jones, Elena', 'AKA', 'en', '2026-02-27 09:00:00'),
  ('DJAL000099', 'DJENT000063', 'Elena Jones', 'AKA', 'en', '2026-02-27 09:00:00'),
  ('DJAL000100', 'DJENT000064', 'Garcia, Mia', 'AKA', 'en', '2026-02-27 09:00:00'),
  ('DJAL000101', 'DJENT000064', 'Mia Garcia', 'AKA', 'en', '2026-02-27 09:00:00'),
  ('DJAL000102', 'DJENT000065', 'Torres, Stella', 'AKA', 'en', '2026-02-27 09:00:00'),
  ('DJAL000103', 'DJENT000066', 'Phillips, Julia', 'AKA', 'en', '2026-02-27 09:00:00'),
  ('DJAL000104', 'DJENT000067', 'Moore, Quinn', 'AKA', 'en', '2026-02-27 09:00:00'),
  ('DJAL000105', 'DJENT000067', 'Quinn Moore', 'AKA', 'en', '2026-02-27 09:00:00'),
  ('DJAL000106', 'DJENT000068', 'Robinson, Carter', 'AKA', 'en', '2026-02-27 09:00:00'),
  ('DJAL000107', 'DJENT000068', 'Carter Robinson', 'AKA', 'en', '2026-02-27 09:00:00'),
  ('DJAL000108', 'DJENT000069', 'Clark, Josiah', 'AKA', 'en', '2026-02-27 09:00:00'),
  ('DJAL000109', 'DJENT000070', 'Walker, Maverick', 'AKA', 'en', '2026-02-27 09:00:00');

-- Populate dj_identifier: 70 rows
INSERT INTO dj_identifier (identifier_id, entity_id, id_type, id_value, issuing_country, issue_date, expiry_date, created_at) VALUES
  ('DJID000001', 'DJENT000001', 'NATIONAL_ID', 'N***3991', 'US', NULL, NULL, '2026-02-27 09:00:00'),
  ('DJID000002', 'DJENT000002', 'PASSPORT', 'P***9967', 'US', NULL, NULL, '2026-02-27 09:00:00'),
  ('DJID000003', 'DJENT000003', 'NATIONAL_ID', 'N***1504', 'US', NULL, NULL, '2026-02-27 09:00:00'),
  ('DJID000004', 'DJENT000004', 'PASSPORT', 'P***2434', 'US', NULL, NULL, '2026-02-27 09:00:00'),
  ('DJID000005', 'DJENT000005', 'NATIONAL_ID', 'N***9964', 'US', NULL, NULL, '2026-02-27 09:00:00'),
  ('DJID000006', 'DJENT000006', 'PASSPORT', 'P***5292', 'US', NULL, NULL, '2026-02-27 09:00:00'),
  ('DJID000007', 'DJENT000007', 'NATIONAL_ID', 'N***8534', 'MX', NULL, NULL, '2026-02-27 09:00:00'),
  ('DJID000008', 'DJENT000008', 'PASSPORT', 'P***9522', 'US', NULL, NULL, '2026-02-27 09:00:00'),
  ('DJID000009', 'DJENT000009', 'NATIONAL_ID', 'N***8728', 'CA', NULL, NULL, '2026-02-27 09:00:00'),
  ('DJID000010', 'DJENT000010', 'PASSPORT', 'P***8878', 'US', NULL, NULL, '2026-02-27 09:00:00'),
  ('DJID000011', 'DJENT000011', 'NATIONAL_ID', 'N***6398', 'GB', NULL, NULL, '2026-02-27 09:00:00'),
  ('DJID000012', 'DJENT000012', 'PASSPORT', 'P***6135', 'US', NULL, NULL, '2026-02-27 09:00:00'),
  ('DJID000013', 'DJENT000013', 'NATIONAL_ID', 'N***6653', 'US', NULL, NULL, '2026-02-27 09:00:00'),
  ('DJID000014', 'DJENT000014', 'PASSPORT', 'P***7797', 'US', NULL, NULL, '2026-02-27 09:00:00'),
  ('DJID000015', 'DJENT000015', 'NATIONAL_ID', 'N***4980', 'US', NULL, NULL, '2026-02-27 09:00:00'),
  ('DJID000016', 'DJENT000016', 'PASSPORT', 'P***5724', 'US', NULL, NULL, '2026-02-27 09:00:00'),
  ('DJID000017', 'DJENT000017', 'NATIONAL_ID', 'N***9787', 'US', NULL, NULL, '2026-02-27 09:00:00'),
  ('DJID000018', 'DJENT000018', 'PASSPORT', 'P***8233', 'MX', NULL, NULL, '2026-02-27 09:00:00'),
  ('DJID000019', 'DJENT000019', 'NATIONAL_ID', 'N***1112', 'US', NULL, NULL, '2026-02-27 09:00:00'),
  ('DJID000020', 'DJENT000020', 'PASSPORT', 'P***3629', 'US', NULL, NULL, '2026-02-27 09:00:00'),
  ('DJID000021', 'DJENT000021', 'NATIONAL_ID', 'N***6105', 'US', NULL, NULL, '2026-02-27 09:00:00'),
  ('DJID000022', 'DJENT000022', 'PASSPORT', 'P***8690', 'US', NULL, NULL, '2026-02-27 09:00:00'),
  ('DJID000023', 'DJENT000023', 'NATIONAL_ID', 'N***5644', 'US', NULL, NULL, '2026-02-27 09:00:00'),
  ('DJID000024', 'DJENT000024', 'PASSPORT', 'P***2845', 'US', NULL, NULL, '2026-02-27 09:00:00'),
  ('DJID000025', 'DJENT000025', 'NATIONAL_ID', 'N***4747', 'CA', NULL, NULL, '2026-02-27 09:00:00'),
  ('DJID000026', 'DJENT000026', 'PASSPORT', 'P***4742', 'US', NULL, NULL, '2026-02-27 09:00:00'),
  ('DJID000027', 'DJENT000027', 'NATIONAL_ID', 'N***4026', 'CA', NULL, NULL, '2026-02-27 09:00:00'),
  ('DJID000028', 'DJENT000028', 'PASSPORT', 'P***9820', 'US', NULL, NULL, '2026-02-27 09:00:00'),
  ('DJID000029', 'DJENT000029', 'NATIONAL_ID', 'N***3121', 'CA', NULL, NULL, '2026-02-27 09:00:00'),
  ('DJID000030', 'DJENT000030', 'PASSPORT', 'P***9504', 'CA', NULL, NULL, '2026-02-27 09:00:00'),
  ('DJID000031', 'DJENT000031', 'NATIONAL_ID', 'N***6813', 'US', NULL, NULL, '2026-02-27 09:00:00'),
  ('DJID000032', 'DJENT000032', 'PASSPORT', 'P***1999', 'US', NULL, NULL, '2026-02-27 09:00:00'),
  ('DJID000033', 'DJENT000033', 'NATIONAL_ID', 'N***5866', 'US', NULL, NULL, '2026-02-27 09:00:00'),
  ('DJID000034', 'DJENT000034', 'PASSPORT', 'P***4175', 'US', NULL, NULL, '2026-02-27 09:00:00'),
  ('DJID000035', 'DJENT000035', 'NATIONAL_ID', 'N***2651', 'MX', NULL, NULL, '2026-02-27 09:00:00'),
  ('DJID000036', 'DJENT000036', 'PASSPORT', 'P***5429', 'US', NULL, NULL, '2026-02-27 09:00:00'),
  ('DJID000037', 'DJENT000037', 'NATIONAL_ID', 'N***6164', 'US', NULL, NULL, '2026-02-27 09:00:00'),
  ('DJID000038', 'DJENT000038', 'PASSPORT', 'P***6203', 'US', NULL, NULL, '2026-02-27 09:00:00'),
  ('DJID000039', 'DJENT000039', 'NATIONAL_ID', 'N***6315', 'US', NULL, NULL, '2026-02-27 09:00:00'),
  ('DJID000040', 'DJENT000040', 'PASSPORT', 'P***1267', 'US', NULL, NULL, '2026-02-27 09:00:00'),
  ('DJID000041', 'DJENT000041', 'NATIONAL_ID', 'N***4414', 'US', NULL, NULL, '2026-02-27 09:00:00'),
  ('DJID000042', 'DJENT000042', 'PASSPORT', 'P***7925', 'US', NULL, NULL, '2026-02-27 09:00:00'),
  ('DJID000043', 'DJENT000043', 'NATIONAL_ID', 'N***3023', 'MX', NULL, NULL, '2026-02-27 09:00:00'),
  ('DJID000044', 'DJENT000044', 'PASSPORT', 'P***6181', 'US', NULL, NULL, '2026-02-27 09:00:00'),
  ('DJID000045', 'DJENT000045', 'NATIONAL_ID', 'N***6744', 'CA', NULL, NULL, '2026-02-27 09:00:00'),
  ('DJID000046', 'DJENT000046', 'PASSPORT', 'P***8344', 'MX', NULL, NULL, '2026-02-27 09:00:00'),
  ('DJID000047', 'DJENT000047', 'NATIONAL_ID', 'N***5764', 'US', NULL, NULL, '2026-02-27 09:00:00'),
  ('DJID000048', 'DJENT000048', 'PASSPORT', 'P***1330', 'CA', NULL, NULL, '2026-02-27 09:00:00'),
  ('DJID000049', 'DJENT000049', 'NATIONAL_ID', 'N***3652', 'US', NULL, NULL, '2026-02-27 09:00:00'),
  ('DJID000050', 'DJENT000050', 'PASSPORT', 'P***3454', 'US', NULL, NULL, '2026-02-27 09:00:00'),
  ('DJID000051', 'DJENT000051', 'NATIONAL_ID', 'N***4381', 'US', NULL, NULL, '2026-02-27 09:00:00'),
  ('DJID000052', 'DJENT000052', 'PASSPORT', 'P***2825', 'US', NULL, NULL, '2026-02-27 09:00:00'),
  ('DJID000053', 'DJENT000053', 'NATIONAL_ID', 'N***6053', 'US', NULL, NULL, '2026-02-27 09:00:00'),
  ('DJID000054', 'DJENT000054', 'PASSPORT', 'P***6952', 'GB', NULL, NULL, '2026-02-27 09:00:00'),
  ('DJID000055', 'DJENT000055', 'NATIONAL_ID', 'N***9037', 'US', NULL, NULL, '2026-02-27 09:00:00'),
  ('DJID000056', 'DJENT000056', 'PASSPORT', 'P***7959', 'US', NULL, NULL, '2026-02-27 09:00:00'),
  ('DJID000057', 'DJENT000057', 'NATIONAL_ID', 'N***6395', 'US', NULL, NULL, '2026-02-27 09:00:00'),
  ('DJID000058', 'DJENT000058', 'PASSPORT', 'P***7638', 'US', NULL, NULL, '2026-02-27 09:00:00'),
  ('DJID000059', 'DJENT000059', 'NATIONAL_ID', 'N***5270', 'US', NULL, NULL, '2026-02-27 09:00:00'),
  ('DJID000060', 'DJENT000060', 'PASSPORT', 'P***4725', 'US', NULL, NULL, '2026-02-27 09:00:00'),
  ('DJID000061', 'DJENT000061', 'NATIONAL_ID', 'N***3783', 'US', NULL, NULL, '2026-02-27 09:00:00'),
  ('DJID000062', 'DJENT000062', 'PASSPORT', 'P***2330', 'GB', NULL, NULL, '2026-02-27 09:00:00'),
  ('DJID000063', 'DJENT000063', 'NATIONAL_ID', 'N***5718', 'MX', NULL, NULL, '2026-02-27 09:00:00'),
  ('DJID000064', 'DJENT000064', 'PASSPORT', 'P***3343', 'CA', NULL, NULL, '2026-02-27 09:00:00'),
  ('DJID000065', 'DJENT000065', 'NATIONAL_ID', 'N***5876', 'US', NULL, NULL, '2026-02-27 09:00:00'),
  ('DJID000066', 'DJENT000066', 'PASSPORT', 'P***3560', 'US', NULL, NULL, '2026-02-27 09:00:00'),
  ('DJID000067', 'DJENT000067', 'NATIONAL_ID', 'N***2580', 'US', NULL, NULL, '2026-02-27 09:00:00'),
  ('DJID000068', 'DJENT000068', 'PASSPORT', 'P***2661', 'US', NULL, NULL, '2026-02-27 09:00:00'),
  ('DJID000069', 'DJENT000069', 'NATIONAL_ID', 'N***3469', 'US', NULL, NULL, '2026-02-27 09:00:00'),
  ('DJID000070', 'DJENT000070', 'PASSPORT', 'P***5980', 'US', NULL, NULL, '2026-02-27 09:00:00');

-- Populate dj_address: 70 rows
INSERT INTO dj_address (address_id, entity_id, address_type, line1, line2, city, state_region, postal_code, country_code, created_at) VALUES
  ('DJADR000001', 'DJENT000001', 'LAST_KNOWN', '502 Michigan Ave', NULL, 'New York', 'NY', '26998', 'US', '2026-02-27 09:00:00'),
  ('DJADR000002', 'DJENT000002', 'LAST_KNOWN', '7786 Michigan Ave', NULL, 'Washington', 'DC', '34953', 'US', '2026-02-27 09:00:00'),
  ('DJADR000003', 'DJENT000003', 'LAST_KNOWN', '3125 Market St', NULL, 'Miami', 'FL', '91615', 'US', '2026-02-27 09:00:00'),
  ('DJADR000004', 'DJENT000004', 'LAST_KNOWN', '4014 Broadway', NULL, 'Chicago', 'IL', '90861', 'US', '2026-02-27 09:00:00'),
  ('DJADR000005', 'DJENT000005', 'LAST_KNOWN', '8811 Peachtree St', NULL, 'Los Angeles', 'CA', '57889', 'US', '2026-02-27 09:00:00'),
  ('DJADR000006', 'DJENT000006', 'LAST_KNOWN', '4720 Sunset Blvd', NULL, 'Houston', 'TX', '46014', 'US', '2026-02-27 09:00:00'),
  ('DJADR000007', 'DJENT000007', 'LAST_KNOWN', '2 Peachtree St', NULL, 'Boston', 'MA', '26565', 'US', '2026-02-27 09:00:00'),
  ('DJADR000008', 'DJENT000008', 'LAST_KNOWN', '4409 Michigan Ave', NULL, 'San Francisco', 'CA', '45704', 'US', '2026-02-27 09:00:00'),
  ('DJADR000009', 'DJENT000009', 'LAST_KNOWN', '11 Market St', NULL, 'Seattle', 'WA', '79577', 'US', '2026-02-27 09:00:00'),
  ('DJADR000010', 'DJENT000010', 'LAST_KNOWN', '2226 Michigan Ave', NULL, 'Denver', 'CO', '33961', 'US', '2026-02-27 09:00:00'),
  ('DJADR000011', 'DJENT000011', 'LAST_KNOWN', '3088 Sunset Blvd', NULL, 'New York', 'NY', '97781', 'US', '2026-02-27 09:00:00'),
  ('DJADR000012', 'DJENT000012', 'LAST_KNOWN', '4966 Peachtree St', NULL, 'Washington', 'DC', '81933', 'US', '2026-02-27 09:00:00'),
  ('DJADR000013', 'DJENT000013', 'LAST_KNOWN', '8 Market St', NULL, 'Miami', 'FL', '71439', 'US', '2026-02-27 09:00:00'),
  ('DJADR000014', 'DJENT000014', 'LAST_KNOWN', '5749 Broadway', NULL, 'Chicago', 'IL', '54714', 'US', '2026-02-27 09:00:00'),
  ('DJADR000015', 'DJENT000015', 'LAST_KNOWN', '8445 Market St', NULL, 'Los Angeles', 'CA', '26404', 'US', '2026-02-27 09:00:00'),
  ('DJADR000016', 'DJENT000016', 'LAST_KNOWN', '3937 Broadway', NULL, 'Houston', 'TX', '23799', 'US', '2026-02-27 09:00:00'),
  ('DJADR000017', 'DJENT000017', 'LAST_KNOWN', '2052 Sunset Blvd', NULL, 'Boston', 'MA', '14918', 'US', '2026-02-27 09:00:00'),
  ('DJADR000018', 'DJENT000018', 'LAST_KNOWN', '5302 Market St', NULL, 'San Francisco', 'CA', '39491', 'US', '2026-02-27 09:00:00'),
  ('DJADR000019', 'DJENT000019', 'LAST_KNOWN', '5636 Sunset Blvd', NULL, 'Seattle', 'WA', '80065', 'US', '2026-02-27 09:00:00'),
  ('DJADR000020', 'DJENT000020', 'LAST_KNOWN', '8152 Broadway', NULL, 'Denver', 'CO', '54390', 'US', '2026-02-27 09:00:00'),
  ('DJADR000021', 'DJENT000021', 'LAST_KNOWN', '3106 Sunset Blvd', NULL, 'New York', 'NY', '11795', 'US', '2026-02-27 09:00:00'),
  ('DJADR000022', 'DJENT000022', 'LAST_KNOWN', '6316 K St', NULL, 'Washington', 'DC', '35313', 'US', '2026-02-27 09:00:00'),
  ('DJADR000023', 'DJENT000023', 'LAST_KNOWN', '2606 Peachtree St', NULL, 'Miami', 'FL', '95364', 'US', '2026-02-27 09:00:00'),
  ('DJADR000024', 'DJENT000024', 'LAST_KNOWN', '7672 K St', NULL, 'Chicago', 'IL', '34734', 'US', '2026-02-27 09:00:00'),
  ('DJADR000025', 'DJENT000025', 'LAST_KNOWN', '5779 Peachtree St', NULL, 'Los Angeles', 'CA', '21789', 'US', '2026-02-27 09:00:00'),
  ('DJADR000026', 'DJENT000026', 'LAST_KNOWN', '6862 Michigan Ave', NULL, 'Houston', 'TX', '97125', 'US', '2026-02-27 09:00:00'),
  ('DJADR000027', 'DJENT000027', 'LAST_KNOWN', '3008 K St', NULL, 'Boston', 'MA', '46378', 'US', '2026-02-27 09:00:00'),
  ('DJADR000028', 'DJENT000028', 'LAST_KNOWN', '8106 Market St', NULL, 'San Francisco', 'CA', '85335', 'US', '2026-02-27 09:00:00'),
  ('DJADR000029', 'DJENT000029', 'LAST_KNOWN', '3908 Peachtree St', NULL, 'Seattle', 'WA', '80583', 'US', '2026-02-27 09:00:00'),
  ('DJADR000030', 'DJENT000030', 'LAST_KNOWN', '9251 Market St', NULL, 'Denver', 'CO', '12504', 'US', '2026-02-27 09:00:00'),
  ('DJADR000031', 'DJENT000031', 'LAST_KNOWN', '4790 Market St', NULL, 'New York', 'NY', '75086', 'US', '2026-02-27 09:00:00'),
  ('DJADR000032', 'DJENT000032', 'LAST_KNOWN', '716 Broadway', NULL, 'Washington', 'DC', '35953', 'US', '2026-02-27 09:00:00'),
  ('DJADR000033', 'DJENT000033', 'LAST_KNOWN', '3338 Peachtree St', NULL, 'Miami', 'FL', '69846', 'US', '2026-02-27 09:00:00'),
  ('DJADR000034', 'DJENT000034', 'LAST_KNOWN', '8650 Broadway', NULL, 'Chicago', 'IL', '27571', 'US', '2026-02-27 09:00:00'),
  ('DJADR000035', 'DJENT000035', 'LAST_KNOWN', '9480 Broadway', NULL, 'Los Angeles', 'CA', '69578', 'US', '2026-02-27 09:00:00'),
  ('DJADR000036', 'DJENT000036', 'LAST_KNOWN', '1396 K St', NULL, 'Houston', 'TX', '10209', 'US', '2026-02-27 09:00:00'),
  ('DJADR000037', 'DJENT000037', 'LAST_KNOWN', '2508 Michigan Ave', NULL, 'Boston', 'MA', '51755', 'US', '2026-02-27 09:00:00'),
  ('DJADR000038', 'DJENT000038', 'LAST_KNOWN', '9127 Market St', NULL, 'San Francisco', 'CA', '67516', 'US', '2026-02-27 09:00:00'),
  ('DJADR000039', 'DJENT000039', 'LAST_KNOWN', '5788 Broadway', NULL, 'Seattle', 'WA', '74308', 'US', '2026-02-27 09:00:00'),
  ('DJADR000040', 'DJENT000040', 'LAST_KNOWN', '1963 Michigan Ave', NULL, 'Denver', 'CO', '93461', 'US', '2026-02-27 09:00:00'),
  ('DJADR000041', 'DJENT000041', 'LAST_KNOWN', '3729 Broadway', NULL, 'New York', 'NY', '18441', 'US', '2026-02-27 09:00:00'),
  ('DJADR000042', 'DJENT000042', 'LAST_KNOWN', '9729 Market St', NULL, 'Washington', 'DC', '98306', 'US', '2026-02-27 09:00:00'),
  ('DJADR000043', 'DJENT000043', 'LAST_KNOWN', '1568 Broadway', NULL, 'Miami', 'FL', '63824', 'US', '2026-02-27 09:00:00'),
  ('DJADR000044', 'DJENT000044', 'LAST_KNOWN', '3898 Market St', NULL, 'Chicago', 'IL', '70351', 'US', '2026-02-27 09:00:00'),
  ('DJADR000045', 'DJENT000045', 'LAST_KNOWN', '6198 Broadway', NULL, 'Los Angeles', 'CA', '44282', 'US', '2026-02-27 09:00:00'),
  ('DJADR000046', 'DJENT000046', 'LAST_KNOWN', '5294 Michigan Ave', NULL, 'Houston', 'TX', '47841', 'US', '2026-02-27 09:00:00'),
  ('DJADR000047', 'DJENT000047', 'LAST_KNOWN', '2040 Broadway', NULL, 'Boston', 'MA', '99590', 'US', '2026-02-27 09:00:00'),
  ('DJADR000048', 'DJENT000048', 'LAST_KNOWN', '928 Market St', NULL, 'San Francisco', 'CA', '84892', 'US', '2026-02-27 09:00:00'),
  ('DJADR000049', 'DJENT000049', 'LAST_KNOWN', '1476 Sunset Blvd', NULL, 'Seattle', 'WA', '91399', 'US', '2026-02-27 09:00:00'),
  ('DJADR000050', 'DJENT000050', 'LAST_KNOWN', '2381 K St', NULL, 'Denver', 'CO', '98270', 'US', '2026-02-27 09:00:00'),
  ('DJADR000051', 'DJENT000051', 'LAST_KNOWN', '1723 Market St', NULL, 'New York', 'NY', '98004', 'US', '2026-02-27 09:00:00'),
  ('DJADR000052', 'DJENT000052', 'LAST_KNOWN', '3658 Sunset Blvd', NULL, 'Washington', 'DC', '69186', 'US', '2026-02-27 09:00:00'),
  ('DJADR000053', 'DJENT000053', 'LAST_KNOWN', '8911 Michigan Ave', NULL, 'Miami', 'FL', '19724', 'US', '2026-02-27 09:00:00'),
  ('DJADR000054', 'DJENT000054', 'LAST_KNOWN', '3451 Market St', NULL, 'Chicago', 'IL', '29595', 'US', '2026-02-27 09:00:00'),
  ('DJADR000055', 'DJENT000055', 'LAST_KNOWN', '1384 Sunset Blvd', NULL, 'Los Angeles', 'CA', '65211', 'US', '2026-02-27 09:00:00'),
  ('DJADR000056', 'DJENT000056', 'LAST_KNOWN', '4308 Michigan Ave', NULL, 'Houston', 'TX', '64478', 'US', '2026-02-27 09:00:00'),
  ('DJADR000057', 'DJENT000057', 'LAST_KNOWN', '8090 Michigan Ave', NULL, 'Boston', 'MA', '28952', 'US', '2026-02-27 09:00:00'),
  ('DJADR000058', 'DJENT000058', 'LAST_KNOWN', '2428 Broadway', NULL, 'San Francisco', 'CA', '48630', 'US', '2026-02-27 09:00:00'),
  ('DJADR000059', 'DJENT000059', 'LAST_KNOWN', '9952 Broadway', NULL, 'Seattle', 'WA', '50765', 'US', '2026-02-27 09:00:00'),
  ('DJADR000060', 'DJENT000060', 'LAST_KNOWN', '9538 Broadway', NULL, 'Denver', 'CO', '39575', 'US', '2026-02-27 09:00:00'),
  ('DJADR000061', 'DJENT000061', 'LAST_KNOWN', '7031 Broadway', NULL, 'New York', 'NY', '90228', 'US', '2026-02-27 09:00:00'),
  ('DJADR000062', 'DJENT000062', 'LAST_KNOWN', '2890 Market St', NULL, 'Washington', 'DC', '44929', 'US', '2026-02-27 09:00:00'),
  ('DJADR000063', 'DJENT000063', 'LAST_KNOWN', '9215 Michigan Ave', NULL, 'Miami', 'FL', '98963', 'US', '2026-02-27 09:00:00'),
  ('DJADR000064', 'DJENT000064', 'LAST_KNOWN', '8401 Michigan Ave', NULL, 'Chicago', 'IL', '10965', 'US', '2026-02-27 09:00:00'),
  ('DJADR000065', 'DJENT000065', 'LAST_KNOWN', '7051 K St', NULL, 'Los Angeles', 'CA', '37732', 'US', '2026-02-27 09:00:00'),
  ('DJADR000066', 'DJENT000066', 'LAST_KNOWN', '166 Michigan Ave', NULL, 'Houston', 'TX', '87871', 'US', '2026-02-27 09:00:00'),
  ('DJADR000067', 'DJENT000067', 'LAST_KNOWN', '2818 Michigan Ave', NULL, 'Boston', 'MA', '32414', 'US', '2026-02-27 09:00:00'),
  ('DJADR000068', 'DJENT000068', 'LAST_KNOWN', '9486 Michigan Ave', NULL, 'San Francisco', 'CA', '43608', 'US', '2026-02-27 09:00:00'),
  ('DJADR000069', 'DJENT000069', 'LAST_KNOWN', '5617 K St', NULL, 'Seattle', 'WA', '15912', 'US', '2026-02-27 09:00:00'),
  ('DJADR000070', 'DJENT000070', 'LAST_KNOWN', '8891 Sunset Blvd', NULL, 'Denver', 'CO', '72947', 'US', '2026-02-27 09:00:00');

-- Populate dj_pep_role: 35 rows
INSERT INTO dj_pep_role (pep_role_id, entity_id, role_title, role_type, country_code, start_date, end_date, current_flag, created_at) VALUES
  ('DJPEP000001', 'DJENT000001', 'Mayor', 'POLITICAL_PARTY', 'US', '2020-09-14', '2023-04-05', 0, '2026-02-27 09:00:00'),
  ('DJPEP000002', 'DJENT000003', 'Mayor', 'JUDICIARY', 'US', '2017-04-27', '2021-02-21', 0, '2026-02-27 09:00:00'),
  ('DJPEP000003', 'DJENT000005', 'Senior Advisor', 'GOVERNMENT', 'US', '2018-04-17', NULL, 1, '2026-02-27 09:00:00'),
  ('DJPEP000004', 'DJENT000007', 'Ambassador', 'POLITICAL_PARTY', 'MX', '2018-10-18', NULL, 1, '2026-02-27 09:00:00'),
  ('DJPEP000005', 'DJENT000009', 'Member of Parliament', 'JUDICIARY', 'CA', '2017-06-13', '2024-12-31', 0, '2026-02-27 09:00:00'),
  ('DJPEP000006', 'DJENT000011', 'Mayor', 'GOVERNMENT', 'GB', '2020-11-16', NULL, 1, '2026-02-27 09:00:00'),
  ('DJPEP000007', 'DJENT000013', 'Chief of Staff', 'POLITICAL_PARTY', 'US', '2019-08-11', NULL, 1, '2026-02-27 09:00:00'),
  ('DJPEP000008', 'DJENT000015', 'Deputy Minister', 'SOE', 'US', '2016-03-08', NULL, 1, '2026-02-27 09:00:00'),
  ('DJPEP000009', 'DJENT000017', 'Central Bank Official', 'JUDICIARY', 'US', '2016-11-11', NULL, 1, '2026-02-27 09:00:00'),
  ('DJPEP000010', 'DJENT000019', 'Member of Parliament', 'SOE', 'US', '2017-10-17', NULL, 1, '2026-02-27 09:00:00'),
  ('DJPEP000011', 'DJENT000021', 'Central Bank Official', 'JUDICIARY', 'US', '2016-12-20', NULL, 1, '2026-02-27 09:00:00'),
  ('DJPEP000012', 'DJENT000023', 'Deputy Minister', 'GOVERNMENT', 'US', '2017-01-28', '2021-02-17', 0, '2026-02-27 09:00:00'),
  ('DJPEP000013', 'DJENT000025', 'Senior Advisor', 'SOE', 'CA', '2021-05-04', NULL, 1, '2026-02-27 09:00:00'),
  ('DJPEP000014', 'DJENT000027', 'Chief of Staff', 'SOE', 'CA', '2019-10-26', NULL, 1, '2026-02-27 09:00:00'),
  ('DJPEP000015', 'DJENT000029', 'Ambassador', 'JUDICIARY', 'CA', '2021-05-21', NULL, 1, '2026-02-27 09:00:00'),
  ('DJPEP000016', 'DJENT000031', 'Member of Parliament', 'JUDICIARY', 'US', '2016-09-19', NULL, 1, '2026-02-27 09:00:00'),
  ('DJPEP000017', 'DJENT000033', 'Central Bank Official', 'JUDICIARY', 'US', '2019-11-16', NULL, 1, '2026-02-27 09:00:00'),
  ('DJPEP000018', 'DJENT000035', 'Deputy Minister', 'SOE', 'MX', '2016-07-12', '2025-06-18', 0, '2026-02-27 09:00:00'),
  ('DJPEP000019', 'DJENT000037', 'Deputy Minister', 'POLITICAL_PARTY', 'US', '2019-12-13', '2020-10-08', 0, '2026-02-27 09:00:00'),
  ('DJPEP000020', 'DJENT000039', 'Member of Parliament', 'SOE', 'US', '2021-08-22', NULL, 1, '2026-02-27 09:00:00'),
  ('DJPEP000021', 'DJENT000041', 'Senior Advisor', 'GOVERNMENT', 'US', '2020-04-20', '2021-04-14', 0, '2026-02-27 09:00:00'),
  ('DJPEP000022', 'DJENT000043', 'Member of Parliament', 'JUDICIARY', 'MX', '2019-01-15', NULL, 1, '2026-02-27 09:00:00'),
  ('DJPEP000023', 'DJENT000045', 'Mayor', 'POLITICAL_PARTY', 'CA', '2015-10-21', '2023-08-04', 0, '2026-02-27 09:00:00'),
  ('DJPEP000024', 'DJENT000047', 'Central Bank Official', 'JUDICIARY', 'US', '2016-08-29', '2021-11-09', 0, '2026-02-27 09:00:00'),
  ('DJPEP000025', 'DJENT000049', 'Central Bank Official', 'GOVERNMENT', 'US', '2021-07-30', NULL, 1, '2026-02-27 09:00:00'),
  ('DJPEP000026', 'DJENT000051', 'Senior Advisor', 'GOVERNMENT', 'US', '2018-07-24', '2023-11-20', 0, '2026-02-27 09:00:00'),
  ('DJPEP000027', 'DJENT000053', 'Deputy Minister', 'JUDICIARY', 'US', '2017-01-05', NULL, 1, '2026-02-27 09:00:00'),
  ('DJPEP000028', 'DJENT000055', 'Central Bank Official', 'POLITICAL_PARTY', 'US', '2019-08-20', NULL, 1, '2026-02-27 09:00:00'),
  ('DJPEP000029', 'DJENT000057', 'Central Bank Official', 'GOVERNMENT', 'US', '2017-09-19', NULL, 1, '2026-02-27 09:00:00'),
  ('DJPEP000030', 'DJENT000059', 'Ambassador', 'SOE', 'US', '2017-07-08', NULL, 1, '2026-02-27 09:00:00'),
  ('DJPEP000031', 'DJENT000061', 'Chief of Staff', 'JUDICIARY', 'US', '2017-08-25', NULL, 1, '2026-02-27 09:00:00'),
  ('DJPEP000032', 'DJENT000063', 'Deputy Minister', 'GOVERNMENT', 'MX', '2021-05-24', NULL, 1, '2026-02-27 09:00:00'),
  ('DJPEP000033', 'DJENT000065', 'Mayor', 'SOE', 'US', '2017-06-25', NULL, 1, '2026-02-27 09:00:00'),
  ('DJPEP000034', 'DJENT000067', 'Chief of Staff', 'POLITICAL_PARTY', 'US', '2021-03-07', NULL, 1, '2026-02-27 09:00:00'),
  ('DJPEP000035', 'DJENT000069', 'Member of Parliament', 'JUDICIARY', 'US', '2016-12-16', NULL, 1, '2026-02-27 09:00:00');

-- Populate dj_relationship: 17 rows
INSERT INTO dj_relationship (relationship_id, from_entity_id, to_entity_id, relationship_type, relationship_desc, created_at) VALUES
  ('DJREL000001', 'DJENT000001', 'DJENT000069', 'CLOSE_ASSOCIATE', 'Associated in public reporting', '2026-02-27 09:00:00'),
  ('DJREL000002', 'DJENT000003', 'DJENT000067', 'CLOSE_ASSOCIATE', 'Associated in public reporting', '2026-02-27 09:00:00'),
  ('DJREL000003', 'DJENT000005', 'DJENT000065', 'CLOSE_ASSOCIATE', 'Associated in public reporting', '2026-02-27 09:00:00'),
  ('DJREL000004', 'DJENT000007', 'DJENT000063', 'CLOSE_ASSOCIATE', 'Associated in public reporting', '2026-02-27 09:00:00'),
  ('DJREL000005', 'DJENT000009', 'DJENT000061', 'CLOSE_ASSOCIATE', 'Associated in public reporting', '2026-02-27 09:00:00'),
  ('DJREL000006', 'DJENT000011', 'DJENT000059', 'CLOSE_ASSOCIATE', 'Associated in public reporting', '2026-02-27 09:00:00'),
  ('DJREL000007', 'DJENT000013', 'DJENT000057', 'CLOSE_ASSOCIATE', 'Associated in public reporting', '2026-02-27 09:00:00'),
  ('DJREL000008', 'DJENT000015', 'DJENT000055', 'CLOSE_ASSOCIATE', 'Associated in public reporting', '2026-02-27 09:00:00'),
  ('DJREL000009', 'DJENT000017', 'DJENT000053', 'CLOSE_ASSOCIATE', 'Associated in public reporting', '2026-02-27 09:00:00'),
  ('DJREL000010', 'DJENT000019', 'DJENT000051', 'CLOSE_ASSOCIATE', 'Associated in public reporting', '2026-02-27 09:00:00'),
  ('DJREL000011', 'DJENT000021', 'DJENT000049', 'CLOSE_ASSOCIATE', 'Associated in public reporting', '2026-02-27 09:00:00'),
  ('DJREL000012', 'DJENT000023', 'DJENT000047', 'CLOSE_ASSOCIATE', 'Associated in public reporting', '2026-02-27 09:00:00'),
  ('DJREL000013', 'DJENT000025', 'DJENT000045', 'CLOSE_ASSOCIATE', 'Associated in public reporting', '2026-02-27 09:00:00'),
  ('DJREL000014', 'DJENT000027', 'DJENT000043', 'CLOSE_ASSOCIATE', 'Associated in public reporting', '2026-02-27 09:00:00'),
  ('DJREL000015', 'DJENT000029', 'DJENT000041', 'CLOSE_ASSOCIATE', 'Associated in public reporting', '2026-02-27 09:00:00'),
  ('DJREL000016', 'DJENT000031', 'DJENT000039', 'CLOSE_ASSOCIATE', 'Associated in public reporting', '2026-02-27 09:00:00'),
  ('DJREL000017', 'DJENT000033', 'DJENT000037', 'CLOSE_ASSOCIATE', 'Associated in public reporting', '2026-02-27 09:00:00');

-- Populate dj_change_event: 15 rows
INSERT INTO dj_change_event (change_id, batch_id, entity_id, change_type, changed_at, changed_field, old_value, new_value) VALUES
  ('DJCHG000001', 'DJBATCH20260227', 'DJENT000001', 'UPDATE', '2026-02-27 08:45:00', 'PRIMARY_NAME', NULL, 'Naomi Garcia'),
  ('DJCHG000002', 'DJBATCH20260227', 'DJENT000002', 'UPDATE', '2026-02-27 08:45:00', 'PRIMARY_NAME', NULL, 'Harper S. Lewis'),
  ('DJCHG000003', 'DJBATCH20260227', 'DJENT000003', 'UPDATE', '2026-02-27 08:45:00', 'PRIMARY_NAME', NULL, 'Elena Jackson'),
  ('DJCHG000004', 'DJBATCH20260227', 'DJENT000004', 'UPDATE', '2026-02-27 08:45:00', 'PRIMARY_NAME', NULL, 'Sebastian R. Gonzalez'),
  ('DJCHG000005', 'DJBATCH20260227', 'DJENT000005', 'UPDATE', '2026-02-27 08:45:00', 'PRIMARY_NAME', NULL, 'Liam P. King'),
  ('DJCHG000006', 'DJBATCH20260227', 'DJENT000006', 'UPDATE', '2026-02-27 08:45:00', 'PRIMARY_NAME', NULL, 'Owen T. Jones'),
  ('DJCHG000007', 'DJBATCH20260227', 'DJENT000007', 'UPDATE', '2026-02-27 08:45:00', 'PRIMARY_NAME', NULL, 'Ella K. Nelson'),
  ('DJCHG000008', 'DJBATCH20260227', 'DJENT000008', 'UPDATE', '2026-02-27 08:45:00', 'PRIMARY_NAME', NULL, 'Hazel Mitchell'),
  ('DJCHG000009', 'DJBATCH20260227', 'DJENT000009', 'UPDATE', '2026-02-27 08:45:00', 'PRIMARY_NAME', NULL, 'Paisley A. Flores'),
  ('DJCHG000010', 'DJBATCH20260227', 'DJENT000010', 'UPDATE', '2026-02-27 08:45:00', 'PRIMARY_NAME', NULL, 'Mia Moore'),
  ('DJCHG000011', 'DJBATCH20260227', 'DJENT000011', 'UPDATE', '2026-02-27 08:45:00', 'PRIMARY_NAME', NULL, 'Wyatt F. Hernandez'),
  ('DJCHG000012', 'DJBATCH20260227', 'DJENT000012', 'UPDATE', '2026-02-27 08:45:00', 'PRIMARY_NAME', NULL, 'Paisley F. Jones'),
  ('DJCHG000013', 'DJBATCH20260227', 'DJENT000013', 'UPDATE', '2026-02-27 08:45:00', 'PRIMARY_NAME', NULL, 'Lillian Q. Green'),
  ('DJCHG000014', 'DJBATCH20260227', 'DJENT000014', 'UPDATE', '2026-02-27 08:45:00', 'PRIMARY_NAME', NULL, 'Lucy White'),
  ('DJCHG000015', 'DJBATCH20260227', 'DJENT000015', 'UPDATE', '2026-02-27 08:45:00', 'PRIMARY_NAME', NULL, 'Julia E. Phillips');

-- Populate dj_entity_version: 70 rows
INSERT INTO dj_entity_version (version_id, entity_id, batch_id, version_effective_at, primary_name, risk_category, active_summary, serialized_ref) VALUES
  ('DJVER000001', 'DJENT000001', 'DJBATCH20260227', '2026-02-27 08:45:00', 'Naomi Garcia', 'PEP', 'PEP_ACTIVE=1', 'REF:RAW:DJENT000001'),
  ('DJVER000002', 'DJENT000002', 'DJBATCH20260227', '2026-02-27 08:45:00', 'Harper S. Lewis', 'SANCTIONS', 'SANCTIONS_ACTIVE=1', 'REF:RAW:DJENT000002'),
  ('DJVER000003', 'DJENT000003', 'DJBATCH20260227', '2026-02-27 08:45:00', 'Elena Jackson', 'PEP', 'PEP_ACTIVE=1', 'REF:RAW:DJENT000003'),
  ('DJVER000004', 'DJENT000004', 'DJBATCH20260227', '2026-02-27 08:45:00', 'Sebastian R. Gonzalez', 'SANCTIONS', 'SANCTIONS_ACTIVE=1', 'REF:RAW:DJENT000004'),
  ('DJVER000005', 'DJENT000005', 'DJBATCH20260227', '2026-02-27 08:45:00', 'Liam P. King', 'PEP', 'PEP_ACTIVE=1', 'REF:RAW:DJENT000005'),
  ('DJVER000006', 'DJENT000006', 'DJBATCH20260227', '2026-02-27 08:45:00', 'Owen T. Jones', 'SANCTIONS', 'SANCTIONS_ACTIVE=1', 'REF:RAW:DJENT000006'),
  ('DJVER000007', 'DJENT000007', 'DJBATCH20260227', '2026-02-27 08:45:00', 'Ella K. Nelson', 'PEP', 'PEP_ACTIVE=1', 'REF:RAW:DJENT000007'),
  ('DJVER000008', 'DJENT000008', 'DJBATCH20260227', '2026-02-27 08:45:00', 'Hazel Mitchell', 'SANCTIONS', 'SANCTIONS_ACTIVE=1', 'REF:RAW:DJENT000008'),
  ('DJVER000009', 'DJENT000009', 'DJBATCH20260227', '2026-02-27 08:45:00', 'Paisley A. Flores', 'PEP', 'PEP_ACTIVE=1', 'REF:RAW:DJENT000009'),
  ('DJVER000010', 'DJENT000010', 'DJBATCH20260227', '2026-02-27 08:45:00', 'Mia Moore', 'SANCTIONS', 'SANCTIONS_ACTIVE=1', 'REF:RAW:DJENT000010'),
  ('DJVER000011', 'DJENT000011', 'DJBATCH20260227', '2026-02-27 08:45:00', 'Wyatt F. Hernandez', 'PEP', 'PEP_ACTIVE=1', 'REF:RAW:DJENT000011'),
  ('DJVER000012', 'DJENT000012', 'DJBATCH20260227', '2026-02-27 08:45:00', 'Paisley F. Jones', 'SANCTIONS', 'SANCTIONS_ACTIVE=1', 'REF:RAW:DJENT000012'),
  ('DJVER000013', 'DJENT000013', 'DJBATCH20260227', '2026-02-27 08:45:00', 'Lillian Q. Green', 'PEP', 'PEP_ACTIVE=1', 'REF:RAW:DJENT000013'),
  ('DJVER000014', 'DJENT000014', 'DJBATCH20260227', '2026-02-27 08:45:00', 'Lucy White', 'SANCTIONS', 'SANCTIONS_ACTIVE=1', 'REF:RAW:DJENT000014'),
  ('DJVER000015', 'DJENT000015', 'DJBATCH20260227', '2026-02-27 08:45:00', 'Julia E. Phillips', 'PEP', 'PEP_ACTIVE=1', 'REF:RAW:DJENT000015'),
  ('DJVER000016', 'DJENT000016', 'DJBATCH20260227', '2026-02-27 08:45:00', 'John O. Harris', 'SANCTIONS', 'SANCTIONS_ACTIVE=1', 'REF:RAW:DJENT000016'),
  ('DJVER000017', 'DJENT000017', 'DJBATCH20260227', '2026-02-27 08:45:00', 'Evelyn M. Green', 'PEP', 'PEP_ACTIVE=1', 'REF:RAW:DJENT000017'),
  ('DJVER000018', 'DJENT000018', 'DJBATCH20260227', '2026-02-27 08:45:00', 'Charlotte Allen', 'SANCTIONS', 'SANCTIONS_ACTIVE=1', 'REF:RAW:DJENT000018'),
  ('DJVER000019', 'DJENT000019', 'DJBATCH20260227', '2026-02-27 08:45:00', 'Lucas M. Wright', 'PEP', 'PEP_ACTIVE=1', 'REF:RAW:DJENT000019'),
  ('DJVER000020', 'DJENT000020', 'DJBATCH20260227', '2026-02-27 08:45:00', 'Maverick C. Rodriguez', 'SANCTIONS', 'SANCTIONS_ACTIVE=1', 'REF:RAW:DJENT000020'),
  ('DJVER000021', 'DJENT000021', 'DJBATCH20260227', '2026-02-27 08:45:00', 'William G. Baker', 'PEP', 'PEP_ACTIVE=1', 'REF:RAW:DJENT000021'),
  ('DJVER000022', 'DJENT000022', 'DJBATCH20260227', '2026-02-27 08:45:00', 'Evelyn Lee', 'SANCTIONS', 'SANCTIONS_ACTIVE=1', 'REF:RAW:DJENT000022'),
  ('DJVER000023', 'DJENT000023', 'DJBATCH20260227', '2026-02-27 08:45:00', 'David L. Wilson', 'PEP', 'PEP_ACTIVE=1', 'REF:RAW:DJENT000023'),
  ('DJVER000024', 'DJENT000024', 'DJBATCH20260227', '2026-02-27 08:45:00', 'Henry F. Evans', 'SANCTIONS', 'SANCTIONS_ACTIVE=1', 'REF:RAW:DJENT000024'),
  ('DJVER000025', 'DJENT000025', 'DJBATCH20260227', '2026-02-27 08:45:00', 'Oliver White', 'PEP', 'PEP_ACTIVE=1', 'REF:RAW:DJENT000025'),
  ('DJVER000026', 'DJENT000026', 'DJBATCH20260227', '2026-02-27 08:45:00', 'Dylan Moore', 'SANCTIONS', 'SANCTIONS_ACTIVE=1', 'REF:RAW:DJENT000026'),
  ('DJVER000027', 'DJENT000027', 'DJBATCH20260227', '2026-02-27 08:45:00', 'Penelope Q. Wilson', 'PEP', 'PEP_ACTIVE=1', 'REF:RAW:DJENT000027'),
  ('DJVER000028', 'DJENT000028', 'DJBATCH20260227', '2026-02-27 08:45:00', 'Savannah M. Phillips', 'SANCTIONS', 'SANCTIONS_ACTIVE=1', 'REF:RAW:DJENT000028'),
  ('DJVER000029', 'DJENT000029', 'DJBATCH20260227', '2026-02-27 08:45:00', 'Nora M. Williams', 'PEP', 'PEP_ACTIVE=1', 'REF:RAW:DJENT000029'),
  ('DJVER000030', 'DJENT000030', 'DJBATCH20260227', '2026-02-27 08:45:00', 'Sofia D. Campbell', 'SANCTIONS', 'SANCTIONS_ACTIVE=1', 'REF:RAW:DJENT000030'),
  ('DJVER000031', 'DJENT000031', 'DJBATCH20260227', '2026-02-27 08:45:00', 'Maverick Parker', 'PEP', 'PEP_ACTIVE=1', 'REF:RAW:DJENT000031'),
  ('DJVER000032', 'DJENT000032', 'DJBATCH20260227', '2026-02-27 08:45:00', 'Samuel O. Edwards', 'SANCTIONS', 'SANCTIONS_ACTIVE=1', 'REF:RAW:DJENT000032'),
  ('DJVER000033', 'DJENT000033', 'DJBATCH20260227', '2026-02-27 08:45:00', 'Leo Torres', 'PEP', 'PEP_ACTIVE=1', 'REF:RAW:DJENT000033'),
  ('DJVER000034', 'DJENT000034', 'DJBATCH20260227', '2026-02-27 08:45:00', 'Paisley Turner', 'SANCTIONS', 'SANCTIONS_ACTIVE=1', 'REF:RAW:DJENT000034'),
  ('DJVER000035', 'DJENT000035', 'DJBATCH20260227', '2026-02-27 08:45:00', 'Madelyn M. Smith', 'PEP', 'PEP_ACTIVE=1', 'REF:RAW:DJENT000035'),
  ('DJVER000036', 'DJENT000036', 'DJBATCH20260227', '2026-02-27 08:45:00', 'Matthew Johnson', 'SANCTIONS', 'SANCTIONS_ACTIVE=1', 'REF:RAW:DJENT000036'),
  ('DJVER000037', 'DJENT000037', 'DJBATCH20260227', '2026-02-27 08:45:00', 'Levi Green', 'PEP', 'PEP_ACTIVE=1', 'REF:RAW:DJENT000037'),
  ('DJVER000038', 'DJENT000038', 'DJBATCH20260227', '2026-02-27 08:45:00', 'Leo A. Hill', 'SANCTIONS', 'SANCTIONS_ACTIVE=1', 'REF:RAW:DJENT000038'),
  ('DJVER000039', 'DJENT000039', 'DJBATCH20260227', '2026-02-27 08:45:00', 'Joseph O. Anderson', 'PEP', 'PEP_ACTIVE=1', 'REF:RAW:DJENT000039'),
  ('DJVER000040', 'DJENT000040', 'DJBATCH20260227', '2026-02-27 08:45:00', 'Isaac Torres', 'SANCTIONS', 'SANCTIONS_ACTIVE=1', 'REF:RAW:DJENT000040'),
  ('DJVER000041', 'DJENT000041', 'DJBATCH20260227', '2026-02-27 08:45:00', 'Chloe J. Smith', 'PEP', 'PEP_ACTIVE=1', 'REF:RAW:DJENT000041'),
  ('DJVER000042', 'DJENT000042', 'DJBATCH20260227', '2026-02-27 08:45:00', 'Sofia H. King', 'SANCTIONS', 'SANCTIONS_ACTIVE=1', 'REF:RAW:DJENT000042'),
  ('DJVER000043', 'DJENT000043', 'DJBATCH20260227', '2026-02-27 08:45:00', 'Zoe L. Taylor', 'PEP', 'PEP_ACTIVE=1', 'REF:RAW:DJENT000043'),
  ('DJVER000044', 'DJENT000044', 'DJBATCH20260227', '2026-02-27 08:45:00', 'Evelyn Hernandez', 'SANCTIONS', 'SANCTIONS_ACTIVE=1', 'REF:RAW:DJENT000044'),
  ('DJVER000045', 'DJENT000045', 'DJBATCH20260227', '2026-02-27 08:45:00', 'Samantha Lewis', 'PEP', 'PEP_ACTIVE=1', 'REF:RAW:DJENT000045'),
  ('DJVER000046', 'DJENT000046', 'DJBATCH20260227', '2026-02-27 08:45:00', 'Oliver K. Williams', 'SANCTIONS', 'SANCTIONS_ACTIVE=1', 'REF:RAW:DJENT000046'),
  ('DJVER000047', 'DJENT000047', 'DJBATCH20260227', '2026-02-27 08:45:00', 'William Ramirez', 'PEP', 'PEP_ACTIVE=1', 'REF:RAW:DJENT000047'),
  ('DJVER000048', 'DJENT000048', 'DJBATCH20260227', '2026-02-27 08:45:00', 'Addison Taylor', 'SANCTIONS', 'SANCTIONS_ACTIVE=1', 'REF:RAW:DJENT000048'),
  ('DJVER000049', 'DJENT000049', 'DJBATCH20260227', '2026-02-27 08:45:00', 'Hannah D. Jones', 'PEP', 'PEP_ACTIVE=1', 'REF:RAW:DJENT000049'),
  ('DJVER000050', 'DJENT000050', 'DJBATCH20260227', '2026-02-27 08:45:00', 'Charlotte Thompson', 'SANCTIONS', 'SANCTIONS_ACTIVE=1', 'REF:RAW:DJENT000050'),
  ('DJVER000051', 'DJENT000051', 'DJBATCH20260227', '2026-02-27 08:45:00', 'Gabriel N. Parker', 'PEP', 'PEP_ACTIVE=1', 'REF:RAW:DJENT000051'),
  ('DJVER000052', 'DJENT000052', 'DJBATCH20260227', '2026-02-27 08:45:00', 'Allison Lewis', 'SANCTIONS', 'SANCTIONS_ACTIVE=1', 'REF:RAW:DJENT000052'),
  ('DJVER000053', 'DJENT000053', 'DJBATCH20260227', '2026-02-27 08:45:00', 'Maya Anderson', 'PEP', 'PEP_ACTIVE=1', 'REF:RAW:DJENT000053'),
  ('DJVER000054', 'DJENT000054', 'DJBATCH20260227', '2026-02-27 08:45:00', 'Violet K. Clark', 'SANCTIONS', 'SANCTIONS_ACTIVE=1', 'REF:RAW:DJENT000054'),
  ('DJVER000055', 'DJENT000055', 'DJBATCH20260227', '2026-02-27 08:45:00', 'Benjamin Collins', 'PEP', 'PEP_ACTIVE=1', 'REF:RAW:DJENT000055'),
  ('DJVER000056', 'DJENT000056', 'DJBATCH20260227', '2026-02-27 08:45:00', 'Sebastian Davis', 'SANCTIONS', 'SANCTIONS_ACTIVE=1', 'REF:RAW:DJENT000056'),
  ('DJVER000057', 'DJENT000057', 'DJBATCH20260227', '2026-02-27 08:45:00', 'Leo Torres', 'PEP', 'PEP_ACTIVE=1', 'REF:RAW:DJENT000057'),
  ('DJVER000058', 'DJENT000058', 'DJBATCH20260227', '2026-02-27 08:45:00', 'Olivia Carter', 'SANCTIONS', 'SANCTIONS_ACTIVE=1', 'REF:RAW:DJENT000058'),
  ('DJVER000059', 'DJENT000059', 'DJBATCH20260227', '2026-02-27 08:45:00', 'Ivy Allen', 'PEP', 'PEP_ACTIVE=1', 'REF:RAW:DJENT000059'),
  ('DJVER000060', 'DJENT000060', 'DJBATCH20260227', '2026-02-27 08:45:00', 'Grace R. Jones', 'SANCTIONS', 'SANCTIONS_ACTIVE=1', 'REF:RAW:DJENT000060'),
  ('DJVER000061', 'DJENT000061', 'DJBATCH20260227', '2026-02-27 08:45:00', 'James Q. Mitchell', 'PEP', 'PEP_ACTIVE=1', 'REF:RAW:DJENT000061'),
  ('DJVER000062', 'DJENT000062', 'DJBATCH20260227', '2026-02-27 08:45:00', 'Mia M. Gonzalez', 'SANCTIONS', 'SANCTIONS_ACTIVE=1', 'REF:RAW:DJENT000062'),
  ('DJVER000063', 'DJENT000063', 'DJBATCH20260227', '2026-02-27 08:45:00', 'Elena F. Jones', 'PEP', 'PEP_ACTIVE=1', 'REF:RAW:DJENT000063'),
  ('DJVER000064', 'DJENT000064', 'DJBATCH20260227', '2026-02-27 08:45:00', 'Mia R. Garcia', 'SANCTIONS', 'SANCTIONS_ACTIVE=1', 'REF:RAW:DJENT000064'),
  ('DJVER000065', 'DJENT000065', 'DJBATCH20260227', '2026-02-27 08:45:00', 'Stella Torres', 'PEP', 'PEP_ACTIVE=1', 'REF:RAW:DJENT000065'),
  ('DJVER000066', 'DJENT000066', 'DJBATCH20260227', '2026-02-27 08:45:00', 'Julia Phillips', 'SANCTIONS', 'SANCTIONS_ACTIVE=1', 'REF:RAW:DJENT000066'),
  ('DJVER000067', 'DJENT000067', 'DJBATCH20260227', '2026-02-27 08:45:00', 'Quinn D. Moore', 'PEP', 'PEP_ACTIVE=1', 'REF:RAW:DJENT000067'),
  ('DJVER000068', 'DJENT000068', 'DJBATCH20260227', '2026-02-27 08:45:00', 'Carter D. Robinson', 'SANCTIONS', 'SANCTIONS_ACTIVE=1', 'REF:RAW:DJENT000068'),
  ('DJVER000069', 'DJENT000069', 'DJBATCH20260227', '2026-02-27 08:45:00', 'Josiah Clark', 'PEP', 'PEP_ACTIVE=1', 'REF:RAW:DJENT000069'),
  ('DJVER000070', 'DJENT000070', 'DJBATCH20260227', '2026-02-27 08:45:00', 'Maverick Walker', 'SANCTIONS', 'SANCTIONS_ACTIVE=1', 'REF:RAW:DJENT000070');

COMMIT;
