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
 * Plan: TC_PTY_EXT_REF__Siebel__SBL_CUSTOMER
 * Template: TPL_COLUMNS_PARENT_SCOPED
 *
 * Generated as build output. Do not edit by hand.
 */
public final class TcPtyExtRefSiebelSblCustomerPlan implements MappingPlan, ReverseMappingPlan {
    private static final Logger LOG = Logger.getLogger(TcPtyExtRefSiebelSblCustomerPlan.class.getName());

    @Override
    public String planId() {
        return "TC_PTY_EXT_REF__Siebel__SBL_CUSTOMER";
    }

    @Override
    public void execute(MappingContext context) throws Exception {
        String instanceId = context.instanceValue("party_id");
        LOG.fine(() -> "Executing generated plan " + planId() + " party_id=" + instanceId);
        SourceRow source = readSource(context.sources().connection("SIEBEL_SYSTEM"), instanceId);
        if (source == null) {
            LOG.warning("No SBL_CUSTOMER row found for party_id=" + instanceId + "; skipping TC_PTY_EXT_REF insert");
            return;
        }
        insertTarget(context.target(), source);
        LOG.finer(() -> "Generated mapping wrote TC_PTY_EXT_REF party_id=" + source.partyId());
    }

    private static SourceRow readSource(Connection source, String instanceId) throws SQLException {
        String sql = """
                select party_id, customer_id from SBL_CUSTOMER where party_id = ?
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
                        rs.getString("customer_id"));
            }
        }
    }

    private static void insertTarget(Connection target, SourceRow source) throws SQLException {
        String sql = """
                insert into TC_PTY_EXT_REF (party_id, external_ref_type, external_id)
                values (?, ?, ?)
                on conflict(party_id, external_ref_type, external_id) do nothing
                """;
        LOG.finest(() -> "Writing target SQL: " + sql.replace('\n', ' '));
        try (PreparedStatement statement = target.prepareStatement(sql)) {
            statement.setString(1, source.partyId());
            statement.setString(2, "SIEBEL_CUSTOMER_ID");
            statement.setString(3, source.customerId());
            statement.executeUpdate();

            statement.setString(1, source.partyId());
            statement.setString(2, "SIEBEL_PARTY_ID");
            statement.setString(3, source.partyId());
            statement.executeUpdate();

        }
    }

    private record SourceRow(String partyId, String customerId) {
    }

    @Override
    public void reverse(ReverseMappingContext context) throws Exception {
        LOG.finer("Reverse mapping no-op for " + planId() + "; mapped source columns are reconstructed by peer plans");
    }

}
