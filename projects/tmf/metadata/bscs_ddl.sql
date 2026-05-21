DROP TABLE IF EXISTS BSCS_PAYMENT;
DROP TABLE IF EXISTS BSCS_AR_OPEN_ITEM;
DROP TABLE IF EXISTS BSCS_INVOICE;
DROP TABLE IF EXISTS BSCS_ACCOUNT_ADDRESS;
DROP TABLE IF EXISTS BSCS_ADDRESS;
DROP TABLE IF EXISTS BSCS_BILLING_ACCOUNT;
DROP TABLE IF EXISTS BSCS_CUSTOMER;

CREATE TABLE BSCS_CUSTOMER (
  customer_id  TEXT PRIMARY KEY,   -- shared with Siebel customer_id
  msisdn       TEXT NOT NULL UNIQUE,
  credit_class TEXT NOT NULL,
  risk_flag    TEXT NOT NULL CHECK(risk_flag IN ('Y','N'))
);

CREATE TABLE BSCS_BILLING_ACCOUNT (
  billing_account_id TEXT PRIMARY KEY,
  customer_id        TEXT NOT NULL REFERENCES BSCS_CUSTOMER(customer_id) ON DELETE CASCADE,
  bill_cycle         TEXT NOT NULL,
  currency           TEXT NOT NULL,
  status             TEXT NOT NULL
);

CREATE TABLE BSCS_ADDRESS (
  address_id   TEXT PRIMARY KEY,
  line1        TEXT NOT NULL,
  city         TEXT NOT NULL,
  state        TEXT NOT NULL,
  postal_code  TEXT NOT NULL,
  country      TEXT NOT NULL
);

CREATE TABLE BSCS_ACCOUNT_ADDRESS (
  billing_account_id TEXT NOT NULL REFERENCES BSCS_BILLING_ACCOUNT(billing_account_id) ON DELETE CASCADE,
  address_id         TEXT NOT NULL REFERENCES BSCS_ADDRESS(address_id) ON DELETE CASCADE,
  address_role       TEXT NOT NULL,
  is_primary         INTEGER NOT NULL CHECK(is_primary IN (0,1)),
  PRIMARY KEY (billing_account_id, address_role)
);

CREATE TABLE BSCS_INVOICE (
  invoice_id         TEXT PRIMARY KEY,
  billing_account_id TEXT NOT NULL REFERENCES BSCS_BILLING_ACCOUNT(billing_account_id) ON DELETE CASCADE,
  invoice_dt         TEXT NOT NULL,
  due_dt             TEXT NOT NULL,
  total_amount       REAL NOT NULL,
  status             TEXT NOT NULL
);

CREATE TABLE BSCS_AR_OPEN_ITEM (
  open_item_id       TEXT PRIMARY KEY,
  billing_account_id TEXT NOT NULL REFERENCES BSCS_BILLING_ACCOUNT(billing_account_id) ON DELETE CASCADE,
  source_invoice_id  TEXT NOT NULL REFERENCES BSCS_INVOICE(invoice_id) ON DELETE CASCADE,
  open_amount        REAL NOT NULL,
  aging_bucket       TEXT NOT NULL,
  status             TEXT NOT NULL
);

CREATE TABLE BSCS_PAYMENT (
  payment_id         TEXT PRIMARY KEY,
  billing_account_id TEXT NOT NULL REFERENCES BSCS_BILLING_ACCOUNT(billing_account_id) ON DELETE CASCADE,
  payment_dt         TEXT NOT NULL,
  amount             REAL NOT NULL,
  method             TEXT NOT NULL,
  status             TEXT NOT NULL
);
