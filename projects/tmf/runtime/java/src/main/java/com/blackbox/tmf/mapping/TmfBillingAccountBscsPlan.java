package com.blackbox.tmf.mapping;

import com.blackbox.runtime.mapping.MappingContext;
import com.blackbox.runtime.mapping.MappingPlan;
import com.blackbox.runtime.mapping.ReverseMappingContext;
import com.blackbox.runtime.mapping.ReverseMappingPlan;
import java.sql.Connection;
import java.sql.PreparedStatement;
import java.sql.ResultSet;
import java.sql.SQLException;
import java.util.logging.Logger;

/**
 * Project-scoped TMF billing account mapping.
 *
 * The generated IR does not yet contain billing-account plans, but billing
 * accounts are direct BSCS rows related to the party's customer id. Keep this
 * implementation small and explicit until the spec-driven generator owns these
 * tables too.
 */
public final class TmfBillingAccountBscsPlan implements MappingPlan, ReverseMappingPlan {
    private static final Logger LOG = Logger.getLogger(TmfBillingAccountBscsPlan.class.getName());

    @Override
    public String planId() {
        return "TC_BILL_ACCT__BSCS__BSCS_BILLING_ACCOUNT";
    }

    @Override
    public void execute(MappingContext context) throws Exception {
        String customerId = context.instanceValue("customer_id");
        if (isBlank(customerId)) {
            LOG.warning("No customer_id resolved; skipping BSCS billing account mapping");
            return;
        }

        int rows = 0;
        String sql = """
                select billing_account_id, bill_cycle, currency, status
                from BSCS_BILLING_ACCOUNT
                where customer_id = ?
                order by billing_account_id
                """;
        try (PreparedStatement statement = context.sources().connection("BSCS_SYSTEM").prepareStatement(sql)) {
            statement.setString(1, customerId);
            try (ResultSet rs = statement.executeQuery()) {
                while (rs.next()) {
                    upsertBillAccount(context.target(), rs);
                    upsertCustomerBillMap(context.target(), customerId, rs.getString("billing_account_id"));
                    rows++;
                }
            }
        }
        LOG.finer("Mapped BSCS billing accounts rows=" + rows + " customer_id=" + customerId);
    }

    private static void upsertBillAccount(Connection target, ResultSet rs) throws SQLException {
        String sql = """
                insert into TC_BILL_ACCT (bill_acct_id, state, currency, bill_cycle, credit_class)
                values (?, ?, ?, ?, null)
                on conflict(bill_acct_id) do update set
                  state = excluded.state,
                  currency = excluded.currency,
                  bill_cycle = excluded.bill_cycle
                """;
        try (PreparedStatement statement = target.prepareStatement(sql)) {
            statement.setString(1, rs.getString("billing_account_id"));
            statement.setString(2, rs.getString("status"));
            statement.setString(3, rs.getString("currency"));
            statement.setString(4, rs.getString("bill_cycle"));
            statement.executeUpdate();
        }
    }

    private static void upsertCustomerBillMap(Connection target, String custAcctId, String billAcctId) throws SQLException {
        String sql = """
                insert into TC_CA_BILL_MAP (cust_acct_id, bill_acct_id, rel_type)
                values (?, ?, 'billTo')
                on conflict(cust_acct_id, bill_acct_id) do update set rel_type = excluded.rel_type
                """;
        try (PreparedStatement statement = target.prepareStatement(sql)) {
            statement.setString(1, custAcctId);
            statement.setString(2, billAcctId);
            statement.executeUpdate();
        }
    }

    @Override
    public void reverse(ReverseMappingContext context) throws Exception {
        String sql = """
                select m.cust_acct_id as customer_id, b.bill_acct_id, b.bill_cycle, b.currency, b.state
                from TC_BILL_ACCT b
                join TC_CA_BILL_MAP m on m.bill_acct_id = b.bill_acct_id
                order by b.bill_acct_id
                """;
        int rows = 0;
        try (PreparedStatement statement = context.target().prepareStatement(sql);
                ResultSet rs = statement.executeQuery()) {
            while (rs.next()) {
                ensureBscsCustomer(context.source("BSCS_SYSTEM"), rs.getString("customer_id"));
                upsertBscsBillingAccount(context.source("BSCS_SYSTEM"), rs);
                rows++;
            }
        }
        LOG.finer("Reverse mapped BSCS billing accounts rows=" + rows);
    }

    private static void ensureBscsCustomer(Connection bscs, String customerId) throws SQLException {
        String sql = """
                insert into BSCS_CUSTOMER (customer_id, msisdn, credit_class, risk_flag)
                values (?, ?, 'UNKNOWN', 'N')
                on conflict(customer_id) do nothing
                """;
        try (PreparedStatement statement = bscs.prepareStatement(sql)) {
            statement.setString(1, customerId);
            statement.setString(2, "UNKNOWN_" + customerId);
            statement.executeUpdate();
        }
    }

    private static void upsertBscsBillingAccount(Connection bscs, ResultSet rs) throws SQLException {
        String sql = """
                insert into BSCS_BILLING_ACCOUNT (billing_account_id, customer_id, bill_cycle, currency, status)
                values (?, ?, ?, ?, ?)
                on conflict(billing_account_id) do update set
                  customer_id = excluded.customer_id,
                  bill_cycle = excluded.bill_cycle,
                  currency = excluded.currency,
                  status = excluded.status
                """;
        try (PreparedStatement statement = bscs.prepareStatement(sql)) {
            statement.setString(1, rs.getString("bill_acct_id"));
            statement.setString(2, rs.getString("customer_id"));
            statement.setString(3, valueOrDefault(rs.getString("bill_cycle"), "1"));
            statement.setString(4, valueOrDefault(rs.getString("currency"), "USD"));
            statement.setString(5, valueOrDefault(rs.getString("state"), "ACTIVE"));
            statement.executeUpdate();
        }
    }

    private static boolean isBlank(String value) {
        return value == null || value.isBlank();
    }

    private static String valueOrDefault(String value, String defaultValue) {
        return isBlank(value) ? defaultValue : value;
    }
}
