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