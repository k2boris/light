-- ============================================================
-- Minimal "Informatica MDM-style" Party Hub - SQLite DDL (3 tables)
-- Goal: absolute minimal MDM for retail Party mastering:
--   1) Golden Party (ROWID_OBJECT)
--   2) XREF (source keys -> ROWID_OBJECT)
--   3) Merge history (lineage)   [optional but very typical in Informatica]
-- If you want the *absolute* minimum, drop C_MERGE_HISTORY and keep 2 tables.
-- ============================================================

PRAGMA foreign_keys = ON;

-- 1) Golden Party (Base Object)
CREATE TABLE IF NOT EXISTS C_BO_PARTY (
  ROWID_OBJECT   TEXT PRIMARY KEY,                 -- golden party id
  PARTY_TYPE_CD  TEXT NOT NULL DEFAULT 'PERSON',   -- PERSON|ORG
  FIRST_NM       TEXT,
  LAST_NM        TEXT,
  BIRTH_DT       TEXT,                             -- YYYY-MM-DD
  STATUS_CD      TEXT NOT NULL DEFAULT 'ACTIVE',   -- ACTIVE|INACTIVE|DECEASED|UNKNOWN
  CREATED_DT     TEXT NOT NULL DEFAULT (datetime('now')),
  UPDATED_DT     TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE INDEX IF NOT EXISTS IDX_PARTY_NAME ON C_BO_PARTY(LAST_NM, FIRST_NM);
CREATE INDEX IF NOT EXISTS IDX_PARTY_DOB  ON C_BO_PARTY(BIRTH_DT);

-- 2) Cross-reference (XREF): map each source system's ID to the golden party
CREATE TABLE IF NOT EXISTS C_XREF_PARTY (
  ROWID_XREF     TEXT PRIMARY KEY,
  ROWID_OBJECT   TEXT NOT NULL,
  SYSTEM_CODE    TEXT NOT NULL,                    -- "SFDC","TEMENOS","CARDS","AML","SCREENING"
  SOURCE_ENTITY  TEXT NOT NULL,                    -- "APPLICANT","CUSTOMER","CARDHOLDER","SCREENED_ENTITY"
  SOURCE_KEY     TEXT NOT NULL,                    -- source id (e.g., Salesforce ContactId)
  BEST_REC_IND   INTEGER NOT NULL DEFAULT 1,        -- 1=best xref in that system/entity
  CREATED_DT     TEXT NOT NULL DEFAULT (datetime('now')),
  FOREIGN KEY (ROWID_OBJECT) REFERENCES C_BO_PARTY(ROWID_OBJECT) ON DELETE CASCADE
);

CREATE UNIQUE INDEX IF NOT EXISTS UX_XREF_UNQ
  ON C_XREF_PARTY(SYSTEM_CODE, SOURCE_ENTITY, SOURCE_KEY);

CREATE INDEX IF NOT EXISTS IDX_XREF_OBJECT ON C_XREF_PARTY(ROWID_OBJECT);

-- 3) Merge lineage (very common in Informatica hubs; optional)
CREATE TABLE IF NOT EXISTS C_MERGE_HISTORY (
  MERGE_ID       TEXT PRIMARY KEY,
  SURVIVOR_ROWID TEXT NOT NULL,                    -- survivor ROWID_OBJECT
  MERGED_ROWID   TEXT NOT NULL,                    -- merged (inactive) ROWID_OBJECT
  MERGED_DT      TEXT NOT NULL DEFAULT (datetime('now')),
  MERGE_REASON   TEXT,                             -- "MATCH","MANUAL","BATCH"
  FOREIGN KEY (SURVIVOR_ROWID) REFERENCES C_BO_PARTY(ROWID_OBJECT),
  FOREIGN KEY (MERGED_ROWID)   REFERENCES C_BO_PARTY(ROWID_OBJECT)
);

CREATE INDEX IF NOT EXISTS IDX_MERGE_SURV ON C_MERGE_HISTORY(SURVIVOR_ROWID);
CREATE INDEX IF NOT EXISTS IDX_MERGE_OLD  ON C_MERGE_HISTORY(MERGED_ROWID);

-- ============================================================
-- End Minimal Informatica MDM-style schema
-- ============================================================