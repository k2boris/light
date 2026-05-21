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
 * Plan: TC_PTY_EXT_REF__BSCS__BSCS_CUSTOMER
 * Template: TPL_JOIN_TO_1_PARENT_SCOPED
 *
 * Generated as build output. Do not edit by hand.
 */
public final class TcPtyExtRefBscsBscsCustomerPlan implements MappingPlan, ReverseMappingPlan {
    private static final Logger LOG = Logger.getLogger(TcPtyExtRefBscsBscsCustomerPlan.class.getName());

    @Override
    public String planId() {
        return "TC_PTY_EXT_REF__BSCS__BSCS_CUSTOMER";
    }

    @Override
    public void execute(MappingContext context) throws Exception {
        String partyId = context.instanceValue("party_id");
        String customerId = context.instanceValue("customer_id");
        if (customerId == null || customerId.isBlank()) {
            LOG.warning("No customer_id resolved for party_id=" + partyId + "; skipping TC_PTY_EXT_REF BSCS rows");
            return;
        }
        SourceRow source = readBscsCustomer(context.sources().connection("BSCS_SYSTEM"), customerId);
        if (source == null) {
            LOG.warning("No BSCS_CUSTOMER row found for customer_id=" + customerId + "; skipping TC_PTY_EXT_REF BSCS rows");
            return;
        }
        int rows = insertExternalRefs(context.target(), partyId, source);
        LOG.finer("Generated mapping wrote TC_PTY_EXT_REF BSCS rows=" + rows + " party_id=" + partyId);
    }

    private static SourceRow readBscsCustomer(Connection bscs, String customerId) throws SQLException {
        String sql = "select customer_id, msisdn from BSCS_CUSTOMER where customer_id = ?";
        LOG.finest(() -> "Reading BSCS external reference SQL: " + sql);
        try (PreparedStatement statement = bscs.prepareStatement(sql)) {
            statement.setString(1, customerId);
            try (ResultSet rs = statement.executeQuery()) {
                if (!rs.next()) {
                    return null;
                }
                return new SourceRow(rs.getString("customer_id"), rs.getString("msisdn"));
            }
        }
    }

    private static int insertExternalRefs(Connection target, String partyId, SourceRow source) throws SQLException {
        String sql = """
                insert into TC_PTY_EXT_REF (party_id, external_ref_type, external_id)
                values (?, ?, ?)
                on conflict(party_id, external_ref_type, external_id) do nothing
                """;
        int rows = 0;
        try (PreparedStatement statement = target.prepareStatement(sql)) {
            rows += insertOne(statement, partyId, "MSISDN", source.msisdn());
        }
        return rows;
    }

    private static int insertOne(
            PreparedStatement statement,
            String partyId,
            String externalRefType,
            String externalId) throws SQLException {
        if (externalId == null || externalId.isBlank()) {
            return 0;
        }
        statement.setString(1, partyId);
        statement.setString(2, externalRefType);
        statement.setString(3, externalId);
        return statement.executeUpdate();
    }

    @Override
    public void reverse(ReverseMappingContext context) throws Exception {
        String customerId = scalar(context.target(), "select customer_id from TC_CUSTOMER limit 1");
        String bscsCustomerId = scalar(
                context.target(),
                "select external_id from TC_PTY_EXT_REF where external_ref_type = 'BSCS_CUSTOMER_ID' limit 1");
        if (bscsCustomerId != null && !bscsCustomerId.isBlank()) {
            customerId = bscsCustomerId;
        }
        if (customerId == null || customerId.isBlank()) {
            return;
        }
        String msisdn = scalar(
                context.target(),
                "select external_id from TC_PTY_EXT_REF where external_ref_type = 'MSISDN' limit 1");
        upsertBscsCustomer(context.source("BSCS_SYSTEM"), customerId, msisdn);
    }

    private static String scalar(Connection connection, String sql) throws SQLException {
        try (PreparedStatement statement = connection.prepareStatement(sql);
                ResultSet rs = statement.executeQuery()) {
            return rs.next() ? rs.getString(1) : null;
        }
    }

    private static void upsertBscsCustomer(Connection bscs, String customerId, String msisdn) throws SQLException {
        String sql = """
                insert into BSCS_CUSTOMER (customer_id, msisdn, credit_class, risk_flag)
                values (?, ?, ?, ?)
                on conflict(customer_id) do update set
                  msisdn = excluded.msisdn
                """;
        try (PreparedStatement statement = bscs.prepareStatement(sql)) {
            statement.setString(1, customerId);
            statement.setString(2, valueOrDefault(msisdn, "UNKNOWN_" + customerId));
            statement.setString(3, "UNKNOWN");
            statement.setString(4, "N");
            statement.executeUpdate();
        }
    }

    private static String valueOrDefault(String value, String defaultValue) {
        return value == null || value.isBlank() ? defaultValue : value;
    }

    private record SourceRow(String customerId, String msisdn) {
    }
}
