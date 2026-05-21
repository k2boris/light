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
 * Plan: TC_PARTY__Siebel__SBL_CUSTOMER
 * Template: TPL_COLUMNS_PARENT_SCOPED
 *
 * Generated as build output. Do not edit by hand.
 */
public final class TcPartySiebelSblCustomerPlan implements MappingPlan, ReverseMappingPlan {
    private static final Logger LOG = Logger.getLogger(TcPartySiebelSblCustomerPlan.class.getName());

    @Override
    public String planId() {
        return "TC_PARTY__Siebel__SBL_CUSTOMER";
    }

    @Override
    public void execute(MappingContext context) throws Exception {
        String instanceId = context.instanceValue("party_id");
        LOG.fine(() -> "Executing generated plan " + planId() + " party_id=" + instanceId);
        SourceRow source = readSource(context.sources().connection("SIEBEL_SYSTEM"), instanceId);
        if (source == null) {
            LOG.warning("No SBL_CUSTOMER row found for party_id=" + instanceId + "; skipping TC_PARTY insert");
            return;
        }
        insertTarget(context.target(), source);
        LOG.finer(() -> "Generated mapping wrote TC_PARTY party_id=" + source.partyId());
    }

    private static SourceRow readSource(Connection source, String instanceId) throws SQLException {
        String sql = """
                select party_id, status, first_name, last_name from SBL_CUSTOMER where party_id = ?
                """;
        LOG.finest(() -> "Reading source SQL: " + sql.replace('\n', ' '));
        try (PreparedStatement statement = source.prepareStatement(sql)) {
            statement.setString(1, instanceId);
            try (ResultSet rs = statement.executeQuery()) {
                if (!rs.next()) {
                    return null;
                }
                return new SourceRow(
                        rs.getString("party_id"),
                        rs.getString("status"),
                        rs.getString("first_name"),
                        rs.getString("last_name"));
            }
        }
    }

    private static void insertTarget(Connection target, SourceRow source) throws SQLException {
        String sql = """
                insert into TC_PARTY (party_id, party_type, status, given_name, family_name, org_name, created_dt)
                values (?, ?, ?, ?, ?, ?, datetime('now'))
                on conflict(party_id) do update set
                  party_type = excluded.party_type,
                  status = excluded.status,
                  given_name = excluded.given_name,
                  family_name = excluded.family_name,
                  org_name = excluded.org_name
                """;
        LOG.finest(() -> "Writing target SQL: " + sql.replace('\n', ' '));
        try (PreparedStatement statement = target.prepareStatement(sql)) {
            statement.setString(1, source.partyId());
            statement.setString(2, "Individual");
            statement.setString(3, source.status());
            statement.setString(4, source.firstName());
            statement.setString(5, source.lastName());
            statement.setNull(6, java.sql.Types.VARCHAR);
            statement.executeUpdate();

        }
    }

    private record SourceRow(String partyId, String status, String firstName, String lastName) {
    }

    @Override
    public void reverse(ReverseMappingContext context) throws Exception {
        String sql = """
                select p.party_id, p.given_name, p.family_name, p.status,
                       c.customer_id
                from TC_PARTY p
                left join TC_CUSTOMER c on c.engaged_party_id = p.party_id
                limit 1
                """;
        try (PreparedStatement statement = context.target().prepareStatement(sql);
                ResultSet rs = statement.executeQuery()) {
            if (!rs.next()) {
                return;
            }
            String customerId = valueOrDefault(rs.getString("customer_id"), "UNKNOWN_" + rs.getString("party_id"));
            upsertSiebelCustomer(
                    context.source("SIEBEL_SYSTEM"),
                    customerId,
                    rs.getString("party_id"),
                    "UNKNOWN_" + customerId,
                    rs.getString("given_name"),
                    rs.getString("family_name"),
                    customerId + "@example.invalid",
                    rs.getString("status"));
        }
    }

    private static void upsertSiebelCustomer(
            Connection siebel,
            String customerId,
            String partyId,
            String msisdn,
            String firstName,
            String lastName,
            String email,
            String status) throws SQLException {
        String sql = """
                insert into SBL_CUSTOMER
                  (customer_id, party_id, msisdn, first_name, last_name, email, segment_code, status)
                values (?, ?, ?, ?, ?, ?, ?, ?)
                on conflict(customer_id) do update set
                  party_id = excluded.party_id,
                  first_name = excluded.first_name,
                  last_name = excluded.last_name,
                  status = excluded.status
                """;
        try (PreparedStatement statement = siebel.prepareStatement(sql)) {
            statement.setString(1, customerId);
            statement.setString(2, partyId);
            statement.setString(3, valueOrDefault(msisdn, "UNKNOWN_" + customerId));
            statement.setString(4, valueOrDefault(firstName, ""));
            statement.setString(5, valueOrDefault(lastName, ""));
            statement.setString(6, valueOrDefault(email, customerId + "@example.invalid"));
            statement.setString(7, "UNKNOWN");
            statement.setString(8, valueOrDefault(status, "ACTIVE"));
            statement.executeUpdate();
        }
    }

    private static String valueOrDefault(String value, String defaultValue) {
        return value == null || value.isBlank() ? defaultValue : value;
    }

}
