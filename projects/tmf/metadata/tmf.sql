-- =========================
-- Customer360 (TMF-aligned) - SQLite DDL
-- Table names <= 19 chars, prefix TC_
-- =========================
PRAGMA foreign_keys = ON;

-- --------
-- TMF632: Party (Individual / Organization)
-- --------
DROP TABLE IF EXISTS TC_PTY_EXT_REF;
DROP TABLE IF EXISTS TC_PTY_CNT_MED;
DROP TABLE IF EXISTS TC_PARTY;

CREATE TABLE TC_PARTY (
  party_id     TEXT PRIMARY KEY,               -- TMF: Party.id
  party_type   TEXT NOT NULL,                  -- 'Individual' | 'Organization'
  status       TEXT NOT NULL DEFAULT 'active',
  given_name   TEXT,
  family_name  TEXT,
  org_name     TEXT,
  created_dt   TEXT DEFAULT (datetime('now'))
);

CREATE TABLE TC_PTY_CNT_MED (
  party_id            TEXT NOT NULL REFERENCES TC_PARTY(party_id) ON DELETE CASCADE,
  medium_type         TEXT NOT NULL,               -- 'telephoneNumber' | 'emailAddress' | 'postalAddress'
  preferred_flag      INTEGER NOT NULL DEFAULT 0 CHECK(preferred_flag IN (0,1)),
  characteristic_json TEXT NOT NULL,
  PRIMARY KEY (party_id, medium_type, characteristic_json)
);

CREATE TABLE TC_PTY_EXT_REF (
  party_id               TEXT NOT NULL REFERENCES TC_PARTY(party_id) ON DELETE CASCADE,
  external_ref_type      TEXT NOT NULL,      -- 'SIEBEL_PARTY_ID', 'MDM_ID', etc.
  external_id            TEXT NOT NULL,
  PRIMARY KEY (party_id, external_ref_type, external_id)
);

-- --------
-- TMF629: Customer
-- --------
DROP TABLE IF EXISTS TC_CUSTOMER;

CREATE TABLE TC_CUSTOMER (
  customer_id      TEXT PRIMARY KEY,             -- TMF: Customer.id
  status           TEXT NOT NULL DEFAULT 'active',
  engaged_party_id TEXT NOT NULL REFERENCES TC_PARTY(party_id),
  created_dt       TEXT DEFAULT (datetime('now'))
);

-- --------
-- TMF629: CustomerAccount
-- --------
DROP TABLE IF EXISTS TC_CA_CHAR;
DROP TABLE IF EXISTS TC_CUST_ACCT;

CREATE TABLE TC_CUST_ACCT (
  cust_acct_id  TEXT PRIMARY KEY,        -- TMF: CustomerAccount.id
  customer_id   TEXT NOT NULL REFERENCES TC_CUSTOMER(customer_id) ON DELETE CASCADE,
  account_type  TEXT,
  status        TEXT NOT NULL DEFAULT 'active',
  created_dt    TEXT DEFAULT (datetime('now'))
);

CREATE TABLE TC_CA_CHAR (
  cust_acct_id TEXT NOT NULL REFERENCES TC_CUST_ACCT(cust_acct_id) ON DELETE CASCADE,
  name         TEXT NOT NULL,
  value        TEXT NOT NULL,
  value_type   TEXT,
  PRIMARY KEY (cust_acct_id, name, value)
);

-- --------
-- TMF666: BillingAccount
-- --------
DROP TABLE IF EXISTS TC_BA_BAL;
DROP TABLE IF EXISTS TC_CA_BILL_MAP;
DROP TABLE IF EXISTS TC_BILL_ACCT;

CREATE TABLE TC_BILL_ACCT (
  bill_acct_id TEXT PRIMARY KEY,         -- TMF: BillingAccount.id
  state        TEXT NOT NULL DEFAULT 'active',
  currency     TEXT NOT NULL DEFAULT 'USD',
  bill_cycle   TEXT,
  credit_class TEXT,
  created_dt   TEXT DEFAULT (datetime('now'))
);

CREATE TABLE TC_CA_BILL_MAP (
  cust_acct_id TEXT NOT NULL REFERENCES TC_CUST_ACCT(cust_acct_id) ON DELETE CASCADE,
  bill_acct_id TEXT NOT NULL REFERENCES TC_BILL_ACCT(bill_acct_id) ON DELETE CASCADE,
  rel_type     TEXT NOT NULL DEFAULT 'billTo',
  PRIMARY KEY (cust_acct_id, bill_acct_id)
);

CREATE TABLE TC_BA_BAL (
  bill_acct_id TEXT NOT NULL REFERENCES TC_BILL_ACCT(bill_acct_id) ON DELETE CASCADE,
  bal_type     TEXT NOT NULL,            -- 'openReceivables','credit','deposit'
  amount       REAL NOT NULL,
  units        TEXT NOT NULL DEFAULT 'USD',
  as_of_dt     TEXT NOT NULL DEFAULT (datetime('now')),
  PRIMARY KEY (bill_acct_id, bal_type, as_of_dt)
);

-- --------
-- TMF637: Product Inventory
-- --------
DROP TABLE IF EXISTS TC_PROD_CHAR;
DROP TABLE IF EXISTS TC_CA_PROD_MAP;
DROP TABLE IF EXISTS TC_PRODUCT;

CREATE TABLE TC_PRODUCT (
  product_id          TEXT PRIMARY KEY,        -- TMF: Product.id
  status              TEXT NOT NULL,
  start_date          TEXT,
  termination_date    TEXT,
  product_offering_id TEXT,                    -- TMF620 ref
  created_dt          TEXT DEFAULT (datetime('now')),
  PRIMARY KEY (product_id, start_date)
);

CREATE TABLE TC_CA_PROD_MAP (
  cust_acct_id TEXT NOT NULL REFERENCES TC_CUST_ACCT(cust_acct_id) ON DELETE CASCADE,
  product_id   TEXT NOT NULL REFERENCES TC_PRODUCT(product_id) ON DELETE CASCADE,
  rel_type     TEXT NOT NULL DEFAULT 'owns',
  PRIMARY KEY (cust_acct_id, product_id)
);

CREATE TABLE TC_PROD_CHAR (
  product_id  TEXT NOT NULL REFERENCES TC_PRODUCT(product_id) ON DELETE CASCADE,
  name        TEXT NOT NULL,
  value       TEXT NOT NULL,
  value_type  TEXT,
  PRIMARY KEY (product_id, name, value_type)
);

