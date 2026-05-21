DROP TABLE IF EXISTS NCC_OFFER_QUAL_REASON;
DROP TABLE IF EXISTS NCC_OFFER_QUAL_RESULT;
DROP TABLE IF EXISTS NCC_OFFER_QUAL_REQUEST;
DROP TABLE IF EXISTS NCC_OFFER_MESSAGE;
DROP TABLE IF EXISTS NCC_RETENTION_OFFER;
DROP TABLE IF EXISTS NCC_DISCOUNT;
DROP TABLE IF EXISTS NCC_PRODUCT_OFFERING;

CREATE TABLE NCC_PRODUCT_OFFERING (
  offering_id         TEXT PRIMARY KEY,
  offering_code       TEXT NOT NULL UNIQUE,
  name                TEXT NOT NULL,
  category            TEXT NOT NULL,
  base_monthly_price  REAL NOT NULL,
  status              TEXT NOT NULL,
  valid_from          TEXT NOT NULL,
  valid_to            TEXT NOT NULL
);

CREATE TABLE NCC_DISCOUNT (
  discount_id   TEXT PRIMARY KEY,
  discount_code TEXT NOT NULL UNIQUE,
  discount_type TEXT NOT NULL CHECK(discount_type IN ('PCT','AMOUNT')),
  value         REAL NOT NULL,
  valid_from    TEXT NOT NULL,
  valid_to      TEXT NOT NULL
);

CREATE TABLE NCC_RETENTION_OFFER (
  retention_offer_id   TEXT PRIMARY KEY,
  offering_id          TEXT NOT NULL REFERENCES NCC_PRODUCT_OFFERING(offering_id) ON DELETE CASCADE,
  discount_id          TEXT NOT NULL REFERENCES NCC_DISCOUNT(discount_id) ON DELETE CASCADE,
  eligibility_rule_set TEXT NOT NULL,
  priority             INTEGER NOT NULL,
  reason_tag           TEXT NOT NULL
);

CREATE TABLE NCC_OFFER_MESSAGE (
  offering_id TEXT NOT NULL REFERENCES NCC_PRODUCT_OFFERING(offering_id) ON DELETE CASCADE,
  channel     TEXT NOT NULL,
  headline    TEXT NOT NULL,
  details     TEXT NOT NULL,
  legal_text  TEXT NOT NULL,
  PRIMARY KEY (offering_id, channel)
);

CREATE TABLE NCC_OFFER_QUAL_REQUEST (
  request_id      TEXT PRIMARY KEY,
  customer_id     TEXT NOT NULL, -- shared with Siebel/BSCS customer_id
  msisdn          TEXT NOT NULL,
  context_channel TEXT NOT NULL,
  requested_dt    TEXT NOT NULL,
  rep_id          TEXT NOT NULL,
  churn_score     REAL NOT NULL,
  past_due_amount REAL NOT NULL
);

CREATE TABLE NCC_OFFER_QUAL_RESULT (
  request_id           TEXT NOT NULL REFERENCES NCC_OFFER_QUAL_REQUEST(request_id) ON DELETE CASCADE,
  offering_id          TEXT NOT NULL REFERENCES NCC_PRODUCT_OFFERING(offering_id) ON DELETE CASCADE,
  eligible_flag        INTEGER NOT NULL CHECK(eligible_flag IN (0,1)),
  rank_score           REAL NOT NULL,
  computed_discount_id TEXT REFERENCES NCC_DISCOUNT(discount_id),
  PRIMARY KEY (request_id, offering_id)
);

CREATE TABLE NCC_OFFER_QUAL_REASON (
  request_id   TEXT NOT NULL REFERENCES NCC_OFFER_QUAL_REQUEST(request_id) ON DELETE CASCADE,
  offering_id  TEXT NOT NULL REFERENCES NCC_PRODUCT_OFFERING(offering_id) ON DELETE CASCADE,
  reason_code  TEXT NOT NULL,
  message      TEXT NOT NULL,
  PRIMARY KEY (request_id, offering_id, reason_code)
);

-- ================================
-- NCC: Product specs + subscriber portfolio (added)
-- ================================

DROP TABLE IF EXISTS NCC_PRODUCT_PARAM_VALUE;
DROP TABLE IF EXISTS NCC_PRODUCT;
DROP TABLE IF EXISTS NCC_SUBSCRIPTION;
DROP TABLE IF EXISTS NCC_OFFERING_SPEC_REL;
DROP TABLE IF EXISTS NCC_SPEC_PARAM;
DROP TABLE IF EXISTS NCC_PRODUCT_SPEC;

CREATE TABLE NCC_PRODUCT_SPEC (
  spec_id   TEXT PRIMARY KEY,
  spec_code TEXT NOT NULL UNIQUE,
  name      TEXT NOT NULL,
  type      TEXT NOT NULL
);

CREATE TABLE NCC_SPEC_PARAM (
  spec_id        TEXT NOT NULL REFERENCES NCC_PRODUCT_SPEC(spec_id) ON DELETE CASCADE,
  param_name     TEXT NOT NULL,
  data_type      TEXT NOT NULL,
  unit           TEXT,
  allowed_values TEXT,
  is_required    INTEGER NOT NULL CHECK(is_required IN (0,1)),
  default_value  TEXT,
  PRIMARY KEY (spec_id, param_name)
);

CREATE TABLE NCC_OFFERING_SPEC_REL (
  offering_id TEXT NOT NULL REFERENCES NCC_PRODUCT_OFFERING(offering_id) ON DELETE CASCADE,
  spec_id     TEXT NOT NULL REFERENCES NCC_PRODUCT_SPEC(spec_id) ON DELETE CASCADE,
  PRIMARY KEY (offering_id)
);

CREATE TABLE NCC_SUBSCRIPTION (
  subscription_id TEXT PRIMARY KEY,
  customer_id     TEXT NOT NULL,
  status          TEXT NOT NULL,
  start_dt        TEXT NOT NULL,
  end_dt          TEXT
);

CREATE TABLE NCC_PRODUCT (
  product_id      TEXT PRIMARY KEY,
  subscription_id TEXT NOT NULL REFERENCES NCC_SUBSCRIPTION(subscription_id) ON DELETE CASCADE,
  offering_id     TEXT NOT NULL REFERENCES NCC_PRODUCT_OFFERING(offering_id) ON DELETE CASCADE,
  spec_id         TEXT NOT NULL REFERENCES NCC_PRODUCT_SPEC(spec_id) ON DELETE CASCADE,
  status          TEXT NOT NULL,
  start_dt        TEXT NOT NULL,
  end_dt          TEXT
);

CREATE TABLE NCC_PRODUCT_PARAM_VALUE (
  product_id  TEXT NOT NULL REFERENCES NCC_PRODUCT(product_id) ON DELETE CASCADE,
  param_name  TEXT NOT NULL,
  param_value TEXT NOT NULL,
  PRIMARY KEY (product_id, param_name)
);

-- ================================
-- NCC: Eligibility (added)
-- ================================

DROP TABLE IF EXISTS NCC_COMMITMENT;
DROP TABLE IF EXISTS NCC_ELIGIBILITY_FLAG;

-- Customer-level flags that influence eligibility / decisioning
CREATE TABLE NCC_ELIGIBILITY_FLAG (
  customer_id   TEXT NOT NULL,
  flag_code     TEXT NOT NULL,   -- PAST_DUE | FRAUD | VIP | ROAMING_RISK | PORT_OUT_REQUEST | SUPPORT_ESCALATION
  flag_value    TEXT NOT NULL,   -- Y/N or numeric or free text
  effective_dt  TEXT NOT NULL,
  end_dt        TEXT,
  PRIMARY KEY (customer_id, flag_code, effective_dt)
);

-- Product-level commitments like contract term / device finance
CREATE TABLE NCC_COMMITMENT (
  product_id        TEXT NOT NULL REFERENCES NCC_PRODUCT(product_id) ON DELETE CASCADE,
  commitment_type   TEXT NOT NULL,   -- CONTRACT | DEVICE_FINANCE
  start_dt          TEXT NOT NULL,
  end_dt            TEXT NOT NULL,
  early_term_fee_usd REAL NOT NULL,
  PRIMARY KEY (product_id, commitment_type)
);
