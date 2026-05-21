package com.blackbox.tmf.generated;

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
 * Auto-generated Java mapping from Blackbox IR.
 *
 * Plan: TC_CUST_ACCT__Siebel__SBL_CUSTOMER
 * Template: TPL_COLUMNS_PARENT_SCOPED
 *
 * Generated as build output. Do not edit by hand.
 */
public final class TcCustAcctSiebelSblCustomerPlan implements MappingPlan, ReverseMappingPlan {
    private static final Logger LOG = Logger.getLogger(TcCustAcctSiebelSblCustomerPlan.class.getName());

    @Override
    public String planId() {
        return "TC_CUST_ACCT__Siebel__SBL_CUSTOMER";
    }

    @Override
    public void execute(MappingContext context) throws Exception {
        String instanceId = context.instanceValue("customer_id");
        LOG.fine(() -> "Executing generated plan " + planId() + " customer_id=" + instanceId);
        SourceRow source = readSource(context.sources().connection("SIEBEL_SYSTEM"), instanceId);
        if (source == null) {
            LOG.warning("No SBL_CUSTOMER row found for customer_id=" + instanceId + "; skipping TC_CUST_ACCT insert");
            return;
        }
        insertTarget(context.target(), source);
        LOG.finer(() -> "Generated mapping wrote TC_CUST_ACCT customer_id=" + source.customerId());
    }

    private static SourceRow readSource(Connection source, String instanceId) throws SQLException {
        String sql = """
                select customer_id, status from SBL_CUSTOMER where customer_id = ?
                """;
        LOG.finest(() -> "Reading source SQL: " + sql.replace('\n', ' '));
        try (PreparedStatement statement = source.prepareStatement(sql)) {
            statement.setString(1, instanceId);
            try (ResultSet rs = statement.executeQuery()) {
                if (!rs.next()) {
                    return null;
                }
                return new SourceRow(
                        rs.getString("customer_id"),
                        rs.getString("status"));
            }
        }
    }

    private static void insertTarget(Connection target, SourceRow source) throws SQLException {
        String sql = """
                insert into TC_CUST_ACCT (cust_acct_id, customer_id, account_type, status, created_dt)
                values (?, ?, ?, ?, datetime('now'))
                on conflict(cust_acct_id) do update set
                  customer_id = excluded.customer_id,
                  account_type = excluded.account_type,
                  status = excluded.status
                """;
        LOG.finest(() -> "Writing target SQL: " + sql.replace('\n', ' '));
        try (PreparedStatement statement = target.prepareStatement(sql)) {
            statement.setString(1, "CA_" + source.customerId());
            statement.setString(2, source.customerId());
            statement.setString(3, "consumer");
            statement.setString(4, source.status());
            statement.executeUpdate();

        }
    }

    private record SourceRow(String customerId, String status) {
    }

    @Override
    public void reverse(ReverseMappingContext context) throws Exception {
        LOG.finer("Reverse mapping no-op for " + planId() + "; mapped source columns are reconstructed by peer plans");
    }

}
