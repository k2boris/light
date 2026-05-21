#!/usr/bin/env bash
set -euo pipefail

PROJECT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/../../.." && pwd)"
REPO_DIR="$(cd "$PROJECT_DIR/../.." && pwd)"
RUN_DIR="$PROJECT_DIR/tmp/java-runtime"
DB_DIR="$RUN_DIR/data"
LOG_DIR="$RUN_DIR/logs"

mkdir -p "$LOG_DIR"

cd "$REPO_DIR"
"$REPO_DIR/materialize.sh" -p tmf >"$LOG_DIR/materialize.log" 2>&1
mvn -q -f "$REPO_DIR/runtime/java/pom.xml" clean install >"$LOG_DIR/core.log" 2>&1
"$PROJECT_DIR/runtime/java/scripts/run-party.sh" >"$LOG_DIR/runtime.log" 2>&1
"$PROJECT_DIR/runtime/java/scripts/reverse-party.sh" >"$LOG_DIR/reverse.log" 2>&1

DB_COUNT="$(find "$DB_DIR" -maxdepth 1 -name '*.db' | wc -l | tr -d ' ')"
PARTY_ROW="$(sqlite3 "$DB_DIR/TC_PARTY_PARTY001.db" 'select party_id, party_type, status, given_name, family_name, org_name from TC_PARTY;')"
CUSTOMER_ROW="$(sqlite3 "$DB_DIR/TC_PARTY_PARTY001.db" 'select customer_id, status, engaged_party_id from TC_CUSTOMER;')"
CUST_ACCT_ROW="$(sqlite3 "$DB_DIR/TC_PARTY_PARTY001.db" 'select cust_acct_id, customer_id, account_type, status from TC_CUST_ACCT;')"
CA_CHAR_ROWS="$(sqlite3 "$DB_DIR/TC_PARTY_PARTY001.db" 'select value_type, name, value from TC_CA_CHAR order by value_type, name, value;')"
CONTACT_ROWS="$(sqlite3 "$DB_DIR/TC_PARTY_PARTY001.db" 'select medium_type, preferred_flag, characteristic_json from TC_PTY_CNT_MED order by medium_type, characteristic_json;')"
EXT_REF_ROWS="$(sqlite3 "$DB_DIR/TC_PARTY_PARTY001.db" 'select external_ref_type, external_id from TC_PTY_EXT_REF order by external_ref_type, external_id;')"
BILL_ACCT_ROWS="$(sqlite3 "$DB_DIR/TC_PARTY_PARTY001.db" 'select bill_acct_id, state, currency, bill_cycle, credit_class from TC_BILL_ACCT order by bill_acct_id;')"
CA_BILL_ROWS="$(sqlite3 "$DB_DIR/TC_PARTY_PARTY001.db" 'select cust_acct_id, bill_acct_id, rel_type from TC_CA_BILL_MAP order by bill_acct_id;')"
BA_BAL_ROWS="$(sqlite3 "$DB_DIR/TC_PARTY_PARTY001.db" 'select bill_acct_id, bal_type, amount, units from TC_BA_BAL order by bill_acct_id, bal_type;')"
PRODUCT_ROWS="$(sqlite3 "$DB_DIR/TC_PARTY_PARTY001.db" 'select product_id, status, start_date, termination_date, product_offering_id from TC_PRODUCT order by product_id, start_date;')"
CA_PROD_ROWS="$(sqlite3 "$DB_DIR/TC_PARTY_PARTY001.db" 'select cust_acct_id, product_id, rel_type from TC_CA_PROD_MAP order by product_id;')"
PROD_CHAR_ROWS="$(sqlite3 "$DB_DIR/TC_PARTY_PARTY001.db" 'select product_id, name, value, value_type from TC_PROD_CHAR order by product_id, name, value_type;')"
TABLE_COUNT="$(sqlite3 "$DB_DIR/TC_PARTY_PARTY001.db" "select count(*) from sqlite_master where type='table' and name like 'TC_%';")"
REVERSE_PASSED="$(python -c 'import json; print(json.load(open("projects/tmf/tmp/java-runtime/reverse-compare.json"))["passed"])')"

if [[ "$DB_COUNT" != "100" ]]; then
  echo "Expected 100 target DBs, got $DB_COUNT" >&2
  exit 1
fi

if [[ "$TABLE_COUNT" != "12" ]]; then
  echo "Expected 12 TMF canonical tables, got $TABLE_COUNT" >&2
  exit 1
fi

if [[ "$PARTY_ROW" != "PARTY001|Individual|ACTIVE|Alex|Nguyen|" ]]; then
  echo "Unexpected PARTY001 row: $PARTY_ROW" >&2
  exit 1
fi

if [[ "$CUSTOMER_ROW" != "CUST001|ACTIVE|PARTY001" ]]; then
  echo "Unexpected CUST001 row: $CUSTOMER_ROW" >&2
  exit 1
fi

if [[ "$CUST_ACCT_ROW" != "CA_CUST001|CUST001|consumer|ACTIVE" ]]; then
  echo "Unexpected TC_CUST_ACCT row: $CUST_ACCT_ROW" >&2
  exit 1
fi

EXPECTED_CA_CHAR_ROWS=$'BSCS_CUSTOMER|creditClass|B\nBSCS_CUSTOMER|riskFlag|N\nNCC_ELIGIBILITY_FLAG|flag.PROFILE_COMPLETE.2025-12-23|Y\nNCC_ELIGIBILITY_FLAG|flag.VIP.2025-09-24|Y\nNCC_OFFER_QUAL_REQUEST|pastDueAmount|[0.0]\nSBL_CHURN_SCORE|churnScore|0.12\nSBL_CHURN_SCORE|modelVersion|churn_v3.2\nSBL_CHURN_SCORE|riskBand|LOW\nSBL_CHURN_SCORE|scoredDt|2026-01-20\nSBL_CHURN_SCORE|topDriver|NONE\nSBL_CUSTOMER|segmentCode|VALUE\nSBL_INTERACTION|lastInteractionOutcome|OFFER_PRESENTED'
if [[ "$CA_CHAR_ROWS" != "$EXPECTED_CA_CHAR_ROWS" ]]; then
  echo "Unexpected TC_CA_CHAR rows:" >&2
  echo "$CA_CHAR_ROWS" >&2
  exit 1
fi

EXPECTED_CONTACT_ROWS=$'emailAddress|0|alex.nguyen@example.com\npostalAddress|0|101 Main St\ntelephoneNumber|1|+13124716506'
if [[ "$CONTACT_ROWS" != "$EXPECTED_CONTACT_ROWS" ]]; then
  echo "Unexpected TC_PTY_CNT_MED rows:" >&2
  echo "$CONTACT_ROWS" >&2
  exit 1
fi

EXPECTED_EXT_REF_ROWS=$'MSISDN|+13124716506\nSIEBEL_CUSTOMER_ID|CUST001\nSIEBEL_PARTY_ID|PARTY001'
if [[ "$EXT_REF_ROWS" != "$EXPECTED_EXT_REF_ROWS" ]]; then
  echo "Unexpected TC_PTY_EXT_REF rows:" >&2
  echo "$EXT_REF_ROWS" >&2
  exit 1
fi

EXPECTED_BILL_ACCT_ROWS=$'BA001|ACTIVE|USD|2|'
if [[ "$BILL_ACCT_ROWS" != "$EXPECTED_BILL_ACCT_ROWS" ]]; then
  echo "Unexpected TC_BILL_ACCT rows:" >&2
  echo "$BILL_ACCT_ROWS" >&2
  exit 1
fi

EXPECTED_CA_BILL_ROWS=$'CUST001|BA001|billTo'
if [[ "$CA_BILL_ROWS" != "$EXPECTED_CA_BILL_ROWS" ]]; then
  echo "Unexpected TC_CA_BILL_MAP rows:" >&2
  echo "$CA_BILL_ROWS" >&2
  exit 1
fi

EXPECTED_BA_BAL_ROWS=$'BA001|OPEN|66.69|USD'
if [[ "$BA_BAL_ROWS" != "$EXPECTED_BA_BAL_ROWS" ]]; then
  echo "Unexpected TC_BA_BAL rows:" >&2
  echo "$BA_BAL_ROWS" >&2
  exit 1
fi

EXPECTED_PRODUCT_ROWS=$'NCP0001|ACTIVE|2025-03-28||OFF032\nNCP0002|ACTIVE|2025-12-23||OFF050'
if [[ "$PRODUCT_ROWS" != "$EXPECTED_PRODUCT_ROWS" ]]; then
  echo "Unexpected TC_PRODUCT rows:" >&2
  echo "$PRODUCT_ROWS" >&2
  exit 1
fi

EXPECTED_CA_PROD_ROWS=$'CUST001|NCP0001|owns\nCUST001|NCP0002|owns'
if [[ "$CA_PROD_ROWS" != "$EXPECTED_CA_PROD_ROWS" ]]; then
  echo "Unexpected TC_CA_PROD_MAP rows:" >&2
  echo "$CA_PROD_ROWS" >&2
  exit 1
fi

EXPECTED_PROD_CHAR_ROWS=$'NCP0001|streaming_service|NETFLIX|product characteristic\nNCP0001|tier|STD|product characteristic\nNCP0002|autopay_discount|1|product characteristic\nNCP0002|commitmentEndDt|2026-03-23|CONTRACT\nNCP0002|contract_months|24|product characteristic\nNCP0002|data_gb|20|product characteristic\nNCP0002|earlyTermFeeUsd|350|CONTRACT\nNCP0002|speed_mbps|100|product characteristic'
if [[ "$PROD_CHAR_ROWS" != "$EXPECTED_PROD_CHAR_ROWS" ]]; then
  echo "Unexpected TC_PROD_CHAR rows:" >&2
  echo "$PROD_CHAR_ROWS" >&2
  exit 1
fi

if [[ "$REVERSE_PASSED" != "True" ]]; then
  echo "Reverse mapped-column comparison failed" >&2
  cat "$PROJECT_DIR/tmp/java-runtime/reverse-compare.json" >&2
  exit 1
fi

echo "TMF Java runtime smoke passed"
echo "db_count=$DB_COUNT"
echo "table_count=$TABLE_COUNT"
echo "party_row=$PARTY_ROW"
echo "customer_row=$CUSTOMER_ROW"
echo "cust_acct_row=$CUST_ACCT_ROW"
printf 'ca_char_rows=%s\n' "$CA_CHAR_ROWS"
printf 'contact_rows=%s\n' "$CONTACT_ROWS"
printf 'ext_ref_rows=%s\n' "$EXT_REF_ROWS"
printf 'bill_acct_rows=%s\n' "$BILL_ACCT_ROWS"
printf 'ca_bill_rows=%s\n' "$CA_BILL_ROWS"
printf 'ba_bal_rows=%s\n' "$BA_BAL_ROWS"
printf 'product_rows=%s\n' "$PRODUCT_ROWS"
printf 'ca_prod_rows=%s\n' "$CA_PROD_ROWS"
printf 'prod_char_rows=%s\n' "$PROD_CHAR_ROWS"
echo "reverse_passed=$REVERSE_PASSED"
echo "reverse_report=$PROJECT_DIR/tmp/java-runtime/reverse-compare.json"
echo "data=$DB_DIR"
echo "logs=$LOG_DIR"
