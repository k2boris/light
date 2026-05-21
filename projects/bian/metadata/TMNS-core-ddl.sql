-- ============================================================================
-- TEMENOS TRANSACT (T24) - PAYMENTS DOMAIN (DDL, PostgreSQL DIALECT)
-- ----------------------------------------------------------------------------
-- This DDL approximates common T24 "applications" used in payments flows.
-- Names and fields vary by version and localization; these structures are
-- pragmatic for integration mapping. All documentation is inline via "--".
-- ============================================================================

-- Choose a schema for clarity (optional)
-- ============================================================================
-- 1) FUNDS.TRANSFER (FT): core payment contract (single instruction)
-- ============================================================================
CREATE TABLE funds_transfer (
  ft_id               TEXT PRIMARY KEY,        -- Unique contract identifier (e.g., @ID)
  debit_account_id    TEXT NOT NULL,           -- Debtor account ID/number (local or IBAN)
  credit_account_id   TEXT NOT NULL,           -- Beneficiary account ID/number (local or IBAN)
  amount              NUMERIC(18,2) NOT NULL,         -- Payment amount in transaction currency
  currency            CHAR(3)     NOT NULL,           -- ISO 4217 currency code for the amount
  value_date          DATE        NOT NULL,           -- Requested value date for funds movement
  booking_date        TEXT,                    -- Booking TEXT when posted to ledger
  charges_code        TEXT,                      -- OUR/SHA/BEN or bank-specific charge arrangement
  charge_amount       NUMERIC(18,2),                  -- Total charges applied (if precomputed)
  exchange_rate       NUMERIC(14,8),                  -- Applied FX rate when cross-currency
  rate_source         TEXT,                    -- FX source identifier/table
  remittance_info     TEXT,                   -- Unstructured remittance/reference information
  structured_remit    TEXT,                          -- Structured remittance (ISO 20022 fields if applicable)
  channel_code        TEXT,                    -- Channel initiating the payment (BRANCH, ONLINE, API, FILE)
  purpose_code        TEXT,                    -- Purpose/category (e.g., SALA, SUPP, GDSV) if required
  status              TEXT  NOT NULL,          -- Lifecycle: ENTERED|VERIFIED|AUTHORIZED|POSTED|REVERSED|CANCELLED
  auth_required       INTEGER      DEFAULT 0,     -- TRUE if dual-control authorization is required
  auth_completed      INTEGER      DEFAULT 0,     -- TRUE when authorization achieved
  created_at          TEXT  DEFAULT CURRENT_TIMESTAMP,     -- Creation TEXT
  updated_at          TEXT                       -- Last modification TEXT
);

-- ============================================================================
-- 2) FUNDS.TRANSFER.HIS: lifecycle history for FT
-- ============================================================================
CREATE TABLE funds_transfer_his (
  his_id              TEXT PRIMARY KEY,        -- Unique history event ID
  ft_id               TEXT NOT NULL,           -- Parent FT contract ID
  event_type          TEXT  NOT NULL,          -- ENTERED|VERIFIED|AUTHORIZED|POSTED|AMENDED|REVERSED|CANCELLED
  event_time          TEXT  NOT NULL,          -- TEXT of the lifecycle event
  user_id             TEXT,                    -- Operator or system user generating the event
  notes               TEXT                    -- Additional narrative about the change
);

CREATE INDEX idx_ft_his_ft ON t24.funds_transfer_his(ft_id, event_time);

-- ============================================================================
-- 3) FT.BULK.MASTER: batch/header for bulk payment submissions
-- ============================================================================
CREATE TABLE ft_bulk_master (
  bulk_id             TEXT PRIMARY KEY,        -- Bulk batch identifier
  submitted_by        TEXT,                    -- Submitting user/system
  submission_time     TEXT NOT NULL,           -- Time the bulk was submitted
  total_items         INTEGER      NOT NULL,          -- Count of items in the batch
  total_amount        NUMERIC(18,2) NOT NULL,         -- Sum of item amounts (in batch currency)
  currency            CHAR(3)      NOT NULL,          -- Currency context for totals/checks
  cutoff_code         TEXT,                    -- Cut-off profile applied (scheme dependent)
  status              TEXT  NOT NULL,          -- CREATED|VALIDATED|AUTHORIZED|PARTIAL|SENT|FAILED|COMPLETED
  remarks             TEXT                     -- Any free-form comments for operators
);

-- ============================================================================
-- 4) FT.BULK.ITEM: items within a bulk payment
-- ============================================================================
CREATE TABLE ft_bulk_item (
  item_id             TEXT PRIMARY KEY,        -- Unique bulk item identifier
  bulk_id             TEXT NOT NULL,           -- FK to bulk master
  debtor_account_id   TEXT NOT NULL,           -- Source account
  creditor_account_id TEXT NOT NULL,           -- Destination account
  amount              NUMERIC(18,2) NOT NULL,         -- Item amount
  currency            CHAR(3)      NOT NULL,          -- Item currency
  remittance_info     TEXT,                   -- Remittance narrative
  ft_id               TEXT,                    -- Generated FT contract ID (post-creation)
  item_status         TEXT  NOT NULL,          -- PENDING|VALID|ERROR|AUTHORIZED|POSTED|SKIPPED
  error_code          TEXT,                    -- Validation/processing error code if any
  error_text          TEXT                     -- Human-readable error text
);

CREATE INDEX idx_bulk_item_master ON t24.ft_bulk_item(bulk_id);
CREATE INDEX idx_bulk_item_ft ON t24.ft_bulk_item(ft_id);

-- ============================================================================
-- 5) STANDING.ORDER: recurring instructions
-- ============================================================================
CREATE TABLE standing_order (
  so_id               TEXT PRIMARY KEY,        -- Standing order identifier
  debtor_account_id   TEXT NOT NULL,           -- Account to debit per schedule
  creditor_account_id TEXT NOT NULL,           -- Beneficiary account
  schedule_rule       TEXT NOT NULL,          -- RRULE/cron-like definition of recurrence
  amount_rule         TEXT  NOT NULL,          -- FIXED|MAX|VARIABLE
  fixed_amount        NUMERIC(18,2),                  -- Amount when amount_rule=FIXED
  currency            CHAR(3),                        -- Currency for FIXED amounts
  next_due_date       DATE,                           -- Next scheduled run date
  last_run_at         TEXT,                    -- Last time the SO produced a payment
  status              TEXT  NOT NULL,          -- ACTIVE|SUSPENDED|ENDED
  remarks             TEXT                     -- Operational notes
);

-- ============================================================================
-- 6) CUSTOMER: party master referenced by payments
-- ============================================================================
CREATE TABLE customer (
  customer_id         TEXT PRIMARY KEY,        -- Core customer identifier
  legal_name          TEXT NOT NULL,          -- Legal/customer name (person or organization)
  residency_country   CHAR(2),                        -- ISO country code of residency
  segment_code        TEXT,                    -- Segment classification used in pricing/policy
  kyc_status          TEXT,                    -- PENDING|VERIFIED|EXPIRED (integration hint)
  created_at          TEXT DEFAULT CURRENT_TIMESTAMP,      -- Creation TEXT
  updated_at          TEXT                      -- Last update TEXT
);

-- ============================================================================
-- 7) ACCOUNT: deposit account used by FT and postings
-- ============================================================================
CREATE TABLE account (
  account_id          TEXT PRIMARY KEY,        -- Account identifier/number (can be IBAN/local)
  customer_id         TEXT NOT NULL,           -- Owning customer reference
  product_code        TEXT,                    -- Product family/type
  currency            CHAR(3)      NOT NULL,          -- Account currency
  status              TEXT  NOT NULL,          -- ACTIVE|SUSPENDED|CLOSED
  available_balance   NUMERIC(18,2) DEFAULT 0,        -- Available funds
  current_balance     NUMERIC(18,2) DEFAULT 0,        -- Ledger balance
  overdraft_limit     NUMERIC(18,2) DEFAULT 0,        -- Authorized OD limit
  opened_on           DATE,                           -- Opening date
  closed_on           DATE                             -- Closing date (if status=CLOSED)
);

CREATE INDEX idx_account_customer ON t24.account(customer_id);

-- ============================================================================
-- 8) EXCHANGE.RATE / FX rates used in FT
-- ============================================================================
CREATE TABLE exchange_rate (
  rate_id             TEXT PRIMARY KEY,        -- Unique rate record id
  ccy_from            CHAR(3) NOT NULL,               -- Base currency
  ccy_to              CHAR(3) NOT NULL,               -- Quote currency
  buy_rate            NUMERIC(16,8),                  -- Buy rate (bank buys base currency)
  sell_rate           NUMERIC(16,8),                  -- Sell rate (bank sells base currency)
  mid_rate            NUMERIC(16,8),                  -- Mid/reference rate
  effective_from      TEXT NOT NULL,           -- Start TEXT
  effective_to        TEXT                      -- End TEXT (null=open-ended)
);

CREATE INDEX idx_fx_pair_time ON t24.exchange_rate(ccy_from, ccy_to, effective_from);

-- ============================================================================
-- 9) CHARGE.TABLE: payment fee/tariff definitions
-- ============================================================================
CREATE TABLE charge_table (
  charge_id           TEXT PRIMARY KEY,        -- Unique charge record id
  charge_code         TEXT NOT NULL,           -- Bank charge code
  payer_indicator     TEXT  NOT NULL,           -- OUR|SHA|BEN or custom
  channel_code        TEXT,                    -- Channel-specific override
  currency            CHAR(3),                        -- Currency constraint for the rule
  min_amount          NUMERIC(18,2),                  -- Minimum fee
  max_amount          NUMERIC(18,2),                  -- Maximum fee
  percentage          NUMERIC(9,6),                   -- Percentage fee (0-1)
  flat_amount         NUMERIC(18,2),                  -- Flat component
  valid_from          DATE,                           -- Start date
  valid_to            DATE                             -- End date
);

-- ============================================================================
-- 10) DELIVERY / OUTBOUND MESSAGE CONTROL (advice/dispatch)
-- ============================================================================
CREATE TABLE delivery_profile (
  profile_id          TEXT PRIMARY KEY,        -- Delivery profile id
  channel_code        TEXT NOT NULL,           -- SWIFT|LOCAL|EMAIL|PRINT
  message_format      TEXT NOT NULL,           -- MT|MX|ACH|SEPA|LOCAL
  requires_signature  INTEGER     DEFAULT 0,      -- Require operator sign-off
  retry_policy        TEXT,                    -- Retries/backoff policy
  enabled             INTEGER     DEFAULT 1,       -- Profile active flag
  created_at          TEXT DEFAULT CURRENT_TIMESTAMP,      -- Creation TEXT
  updated_at          TEXT                      -- Last update
);

-- ============================================================================
-- 11) SWIFT.MESSAGE / OUTBOUND MESSAGES
-- ============================================================================
CREATE TABLE swift_message (
  msg_id              TEXT PRIMARY KEY,        -- Message unique id
  ft_id               TEXT,                    -- Linked FT contract id
  message_type        TEXT  NOT NULL,           -- MT103, MT202, pacs.008, etc.
  direction           TEXT  NOT NULL,           -- OUT|IN
  payload             TEXT        NOT NULL,           -- Raw message payload (ISO text/XML/TEXT)
  status              TEXT NOT NULL,           -- CREATED|QUEUED|SENT|ACK|NACK|FAILED
  network_ref         TEXT,                    -- Network reference (e.g., MIR, UETR)
  created_at          TEXT DEFAULT CURRENT_TIMESTAMP,      -- Creation TEXT
  updated_at          TEXT                      -- Last update
);

CREATE INDEX idx_swift_ft ON t24.swift_message(ft_id);

-- ============================================================================
-- 12) KYC/SCREENING RESULTS (payment-time linkage)
-- ============================================================================
CREATE TABLE payment_screening (
  screening_id        TEXT PRIMARY KEY,        -- Screening event id
  ft_id               TEXT NOT NULL,           -- Payment being screened
  result_code         TEXT NOT NULL,           -- PASS|REVIEW|FAIL
  score               NUMERIC(9,4),                   -- Risk score if applicable
  reason_codes        TEXT,                   -- Codes explaining decision
  screened_at         TEXT NOT NULL,           -- When screening occurred
  analyst_user        TEXT                      -- Human reviewer (if any)
);

CREATE INDEX idx_screening_ft ON t24.payment_screening(ft_id, screened_at);

-- ============================================================================
-- 13) ACCOUNT.ENTRIES: ledger entries / statements
-- ============================================================================
CREATE TABLE account_entry (
  entry_id            TEXT PRIMARY KEY,        -- Unique posting/entry id
  account_id          TEXT NOT NULL,           -- Account impacted
  ft_id               TEXT,                    -- Related payment (if any)
  booking_time        TEXT NOT NULL,           -- Booking TEXT
  value_date          DATE        NOT NULL,           -- Value date
  debit_credit        CHAR(1)     NOT NULL,           -- D or C
  amount              NUMERIC(18,2) NOT NULL,         -- Entry amount
  currency            CHAR(3)     NOT NULL,           -- Currency
  narrative           TEXT,                   -- Statement narrative
  balance_after       NUMERIC(18,2)                    -- Balance after posting (snapshot)
);

CREATE INDEX idx_entry_account_time ON t24.account_entry(account_id, booking_time DESC);

-- ============================================================================
-- 14) NOSTRO.ACCOUNT: correspondent accounts
-- ============================================================================
CREATE TABLE nostro_account (
  nostro_id           TEXT PRIMARY KEY,        -- Nostro account id
  bank_bic            CHAR(11)    NOT NULL,           -- BIC of correspondent bank
  account_number      TEXT NOT NULL,           -- Nostro account number
  currency            CHAR(3)     NOT NULL,           -- Account currency
  status              TEXT  NOT NULL,          -- ACTIVE|SUSPENDED|CLOSED
  opening_balance     NUMERIC(18,2) DEFAULT 0,        -- Opening balance snapshot
  created_at          TEXT DEFAULT CURRENT_TIMESTAMP,      -- Creation TEXT
  updated_at          TEXT                      -- Last update
);

-- ============================================================================
-- 15) NOSTRO.MOVEMENT: movements on correspondent accounts
-- ============================================================================
CREATE TABLE nostro_movement (
  movement_id         TEXT PRIMARY KEY,        -- Movement id
  nostro_id           TEXT NOT NULL,           -- FK to nostro_account
  booking_time        TEXT NOT NULL,           -- Booking time
  value_date          DATE        NOT NULL,           -- Value date
  debit_credit        CHAR(1)     NOT NULL,           -- D or C
  amount              NUMERIC(18,2) NOT NULL,         -- Amount
  currency            CHAR(3)     NOT NULL,           -- Currency
  reference           TEXT,                    -- Network/reference id
  narrative           TEXT                     -- Narrative text
);

CREATE INDEX idx_nostro_mov_acc_time ON t24.nostro_movement(nostro_id, booking_time DESC);

-- ============================================================================
-- 16) PAYMENT.ROUTING: scheme/currency/country routing rules
-- ============================================================================
CREATE TABLE payment_routing (
  route_id            TEXT PRIMARY KEY,        -- Routing rule id
  scheme_code         TEXT NOT NULL,           -- ACH|SEPA|RTP|FEDWIRE|SWIFT etc.
  ccy                 CHAR(3),                        -- Optional currency constraint
  country             CHAR(2),                        -- Optional country constraint (ISO)
  priority            INTEGER     NOT NULL,           -- Evaluation priority (lower = earlier)
  handler_service     TEXT NOT NULL,           -- Internal service/queue handling the route
  active              INTEGER     DEFAULT 1,       -- Active flag
  valid_from          DATE,                           -- Effective date
  valid_to            DATE                             -- Expiry date
);

-- ============================================================================
-- 17) CLEARING.BATCH: outbound/inbound files/messages
-- ============================================================================
CREATE TABLE clearing_batch (
  batch_id            TEXT PRIMARY KEY,        -- Clearing batch identifier
  scheme_code         TEXT NOT NULL,           -- Payment scheme
  direction           TEXT  NOT NULL,           -- OUT|IN
  cutoff_time         TEXT,                    -- Cut-off when frozen for transmission
  settlement_date     DATE,                           -- Expected settlement date
  status              TEXT NOT NULL,           -- READY|SENT|ACK|FAILED|COMPLETED
  network_ref         TEXT,                    -- Network/file reference id
  created_at          TEXT DEFAULT CURRENT_TIMESTAMP       -- Creation TEXT
);

-- ============================================================================
-- 18) CLEARING.ITEM: items within a clearing batch
-- ============================================================================
CREATE TABLE clearing_item (
  item_id             TEXT PRIMARY KEY,        -- Clearing item id
  batch_id            TEXT NOT NULL,           -- FK to clearing_batch
  ft_id               TEXT,                    -- Related payment contract
  amount              NUMERIC(18,2) NOT NULL,         -- Amount
  currency            CHAR(3)      NOT NULL,          -- Currency
  network_ref         TEXT,                    -- Scheme/network id for the item
  response_code       TEXT,                    -- Acknowledgement/return code
  submitted_at        TEXT                      -- Submission TEXT
);

CREATE INDEX idx_clritem_batch ON t24.clearing_item(batch_id);

-- ============================================================================
-- 19) PAYMENT.RETURN: returns/exceptions from schemes
-- ============================================================================
CREATE TABLE payment_return (
  return_id           TEXT PRIMARY KEY,        -- Return event id
  ft_id               TEXT NOT NULL,           -- Original payment
  scheme_code         TEXT NOT NULL,           -- Scheme reporting the return
  return_code         TEXT NOT NULL,           -- ACH R-code / SEPA reason / SWIFT code
  return_amount       NUMERIC(18,2),                  -- Amount returned (may be partial)
  returned_at         TEXT NOT NULL,           -- When return was received
  notes               TEXT                     -- Human-readable note
);

CREATE INDEX idx_return_ft ON t24.payment_return(ft_id, returned_at);

-- ============================================================================
-- 20) STOP.PAYMENT: stop orders (checks/direct debits)
-- ============================================================================
CREATE TABLE stop_payment (
  stop_id             TEXT PRIMARY KEY,        -- Stop order id
  account_id          TEXT NOT NULL,           -- Account to which stop applies
  scope_code          TEXT NOT NULL,           -- CHECK_SERIAL|PAYEE|AMOUNT|DATE_RANGE|ALL_DEBITS
  scope_value         TEXT,                    -- Value for scope (e.g., INTEGER or payee)
  placed_at           TEXT NOT NULL,           -- When stop was placed
  expires_at          TEXT,                    -- When stop auto-expires (nullable)
  status              TEXT  NOT NULL           -- ACTIVE|RELEASED|EXPIRED
);

-- ============================================================================
-- Helpful indexes for common joins/queries
-- ============================================================================
CREATE INDEX idx_ft_accounts         ON t24.funds_transfer(debit_account_id, credit_account_id, value_date);
CREATE INDEX idx_ft_status           ON t24.funds_transfer(status, value_date);
CREATE INDEX idx_so_next_due         ON t24.standing_order(status, next_due_date);
CREATE INDEX idx_account_status_cust ON t24.account(status, customer_id);
CREATE INDEX idx_swift_status_time   ON t24.swift_message(status, created_at);
CREATE INDEX idx_entry_acct_valdate  ON t24.account_entry(account_id, value_date);
CREATE INDEX idx_route_scheme_ccy    ON t24.payment_routing(scheme_code, ccy, country);

-- ============================================================================
-- RELATIONSHIP NOTES (no hard FKs across all to keep ingestion flexible):
--   funds_transfer.ft_id         ~ funds_transfer_his.ft_id
--   ft_bulk_master.bulk_id       ~ ft_bulk_item.bulk_id
--   funds_transfer.ft_id         ~ swift_message.ft_id, account_entry.ft_id
--   clearing_batch.batch_id      ~ clearing_item.batch_id
--   funds_transfer.ft_id         ~ clearing_item.ft_id, payment_return.ft_id
--   account.account_id           ~ funds_transfer.debit_account_id / credit_account_id
-- ============================================================================