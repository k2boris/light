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
 * Plan: TC_CUSTOMER__Siebel__SBL_CUSTOMER
 * Template: TPL_COLUMNS_PARENT_SCOPED
 *
 * Generated as build output. Do not edit by hand.
 */
public final class TcCustomerSiebelSblCustomerPlan implements MappingPlan, ReverseMappingPlan {
    private static final Logger LOG = Logger.getLogger(TcCustomerSiebelSblCustomerPlan.class.getName());

    @Override
    public String planId() {
        return "TC_CUSTOMER__Siebel__SBL_CUSTOMER";
    }

    @Override
    public void execute(MappingContext context) throws Exception {
        String instanceId = context.instanceValue("customer_id");
        LOG.fine(() -> "Executing generated plan " + planId() + " customer_id=" + instanceId);
        SourceRow source = readSource(context.sources().connection("SIEBEL_SYSTEM"), instanceId);
        if (source == null) {
            LOG.warning("No SBL_CUSTOMER row found for customer_id=" + instanceId + "; skipping TC_CUSTOMER insert");
            return;
        }
        insertTarget(context.target(), source);
        LOG.finer(() -> "Generated mapping wrote TC_CUSTOMER customer_id=" + source.customerId());
    }

    private static SourceRow readSource(Connection source, String instanceId) throws SQLException {
        String sql = """
                select customer_id, status, party_id from SBL_CUSTOMER where customer_id = ?
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
                        rs.getString("status"),
                        rs.getString("party_id"));
            }
        }
    }

    private static void insertTarget(Connection target, SourceRow source) throws SQLException {
        String sql = """
                insert into TC_CUSTOMER (customer_id, status, engaged_party_id, created_dt)
                values (?, ?, ?, datetime('now'))
                on conflict(customer_id) do update set
                  status = excluded.status,
                  engaged_party_id = excluded.engaged_party_id
                """;
        LOG.finest(() -> "Writing target SQL: " + sql.replace('\n', ' '));
        try (PreparedStatement statement = target.prepareStatement(sql)) {
            statement.setString(1, source.customerId());
            statement.setString(2, source.status());
            statement.setString(3, source.partyId());
            statement.executeUpdate();

        }
    }

    private record SourceRow(String customerId, String status, String partyId) {
    }

    @Override
    public void reverse(ReverseMappingContext context) throws Exception {
        String sql = "select customer_id, status, engaged_party_id from TC_CUSTOMER limit 1";
        try (PreparedStatement statement = context.target().prepareStatement(sql);
                ResultSet rs = statement.executeQuery()) {
            if (!rs.next()) {
                return;
            }
            upsertSiebelCustomer(
                    context.source("SIEBEL_SYSTEM"),
                    rs.getString("customer_id"),
                    rs.getString("engaged_party_id"),
                    rs.getString("status"));
        }
    }

    private static void upsertSiebelCustomer(Connection siebel, String customerId, String partyId, String status) throws SQLException {
        String sql = """
                insert into SBL_CUSTOMER
                  (customer_id, party_id, msisdn, first_name, last_name, email, segment_code, status)
                values (?, ?, ?, ?, ?, ?, ?, ?)
                on conflict(customer_id) do update set
                  party_id = excluded.party_id,
                  status = excluded.status
                """;
        try (PreparedStatement statement = siebel.prepareStatement(sql)) {
            statement.setString(1, customerId);
            statement.setString(2, partyId);
            statement.setString(3, "UNKNOWN_" + customerId);
            statement.setString(4, "");
            statement.setString(5, "");
            statement.setString(6, customerId + "@example.invalid");
            statement.setString(7, "UNKNOWN");
            statement.setString(8, status == null || status.isBlank() ? "ACTIVE" : status);
            statement.executeUpdate();
        }
    }

}
