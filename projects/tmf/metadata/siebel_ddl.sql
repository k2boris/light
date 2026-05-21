
DROP TABLE IF EXISTS SBL_ORDER_ITEM;
DROP TABLE IF EXISTS SBL_ORDER;
DROP TABLE IF EXISTS SBL_ASSET;
DROP TABLE IF EXISTS SBL_INTERACTION;
DROP TABLE IF EXISTS SBL_CHURN_SCORE;
DROP TABLE IF EXISTS SBL_CUSTOMER;

CREATE TABLE SBL_CUSTOMER (
  customer_id      TEXT PRIMARY KEY,
  party_id         TEXT NOT NULL,
  msisdn           TEXT NOT NULL UNIQUE,
  first_name       TEXT NOT NULL,
  last_name        TEXT NOT NULL,
  email            TEXT NOT NULL,
  segment_code     TEXT NOT NULL,
  status           TEXT NOT NULL
);

CREATE TABLE SBL_CHURN_SCORE (
  customer_id   TEXT PRIMARY KEY REFERENCES SBL_CUSTOMER(customer_id) ON DELETE CASCADE,
  churn_score   REAL NOT NULL,
  risk_band     TEXT NOT NULL,
  model_version TEXT NOT NULL,
  scored_dt     TEXT NOT NULL,
  top_driver    TEXT NOT NULL
);

CREATE TABLE SBL_INTERACTION (
  interaction_id TEXT PRIMARY KEY,
  customer_id    TEXT NOT NULL REFERENCES SBL_CUSTOMER(customer_id) ON DELETE CASCADE,
  channel        TEXT NOT NULL,
  start_ts       TEXT NOT NULL,
  end_ts         TEXT NOT NULL,
  agent_id       TEXT NOT NULL,
  reason         TEXT NOT NULL,
  notes          TEXT,
  outcome_code   TEXT NOT NULL
);

CREATE TABLE SBL_ASSET (
  asset_id        TEXT PRIMARY KEY,
  customer_id     TEXT NOT NULL REFERENCES SBL_CUSTOMER(customer_id) ON DELETE CASCADE,
  product_id      TEXT NOT NULL UNIQUE,
  offering_id     TEXT NOT NULL, -- references NCC_PRODUCT_OFFERING.offering_id (in NCC db)
  start_dt        TEXT NOT NULL,
  status          TEXT NOT NULL,
  contract_end_dt TEXT
);

CREATE TABLE SBL_ORDER (
  order_id    TEXT PRIMARY KEY,
  customer_id TEXT NOT NULL REFERENCES SBL_CUSTOMER(customer_id) ON DELETE CASCADE,
  order_dt    TEXT NOT NULL,
  status      TEXT NOT NULL,
  channel     TEXT NOT NULL
);

CREATE TABLE SBL_ORDER_ITEM (
  order_item_id TEXT PRIMARY KEY,
  order_id      TEXT NOT NULL REFERENCES SBL_ORDER(order_id) ON DELETE CASCADE,
  action        TEXT NOT NULL,
  offering_id   TEXT NOT NULL, -- references NCC_PRODUCT_OFFERING.offering_id (in NCC db)
  product_id    TEXT,          -- filled for MODIFY/REMOVE actions
  discount_id   TEXT,          -- references NCC_DISCOUNT.discount_id (in NCC db)
  status        TEXT NOT NULL
);