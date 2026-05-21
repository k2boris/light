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
 * Plan: TC_PTY_CNT_MED__Siebel__SBL_CUSTOMER
 * Template: TPL_COLUMNS_PARENT_SCOPED
 *
 * Generated as build output. Do not edit by hand.
 */
public final class TcPtyCntMedSiebelCustomerContactPlan implements MappingPlan, ReverseMappingPlan {
    private static final Logger LOG = Logger.getLogger(TcPtyCntMedSiebelCustomerContactPlan.class.getName());

    @Override
    public String planId() {
        return "TC_PTY_CNT_MED__Siebel__SBL_CUSTOMER";
    }

    @Override
    public void execute(MappingContext context) throws Exception {
        String partyId = context.instanceValue("party_id");
        SourceRow source = readSource(context.sources().connection("SIEBEL_SYSTEM"), partyId);
        if (source == null) {
            LOG.warning("No SBL_CUSTOMER contact row found for party_id=" + partyId + "; skipping TC_PTY_CNT_MED Siebel rows");
            return;
        }
        int rows = 0;
        if (hasText(source.email())) {
            insertContactMedium(context.target(), source.partyId(), "emailAddress", hasText(source.msisdn()) ? 0 : 1, source.email());
            rows++;
        }
        if (hasText(source.msisdn())) {
            insertContactMedium(context.target(), source.partyId(), "telephoneNumber", 1, source.msisdn());
            rows++;
        }
        LOG.finer("Generated mapping wrote TC_PTY_CNT_MED Siebel rows=" + rows + " party_id=" + source.partyId());
    }

    private static SourceRow readSource(Connection source, String partyId) throws SQLException {
        String sql = """
                select party_id, email, msisdn from SBL_CUSTOMER where party_id = ?
                """;
        try (PreparedStatement statement = source.prepareStatement(sql)) {
            statement.setString(1, partyId);
            try (ResultSet rs = statement.executeQuery()) {
                if (!rs.next()) {
                    return null;
                }
                return new SourceRow(rs.getString("party_id"), rs.getString("email"), rs.getString("msisdn"));
            }
        }
    }

    private static void insertContactMedium(
            Connection target,
            String partyId,
            String mediumType,
            int preferredFlag,
            String characteristicJson) throws SQLException {
        String sql = """
                insert into TC_PTY_CNT_MED (party_id, medium_type, preferred_flag, characteristic_json)
                values (?, ?, ?, ?)
                on conflict(party_id, medium_type, characteristic_json) do update set
                  preferred_flag = excluded.preferred_flag
                """;
        try (PreparedStatement statement = target.prepareStatement(sql)) {
            statement.setString(1, partyId);
            statement.setString(2, mediumType);
            statement.setInt(3, preferredFlag);
            statement.setString(4, characteristicJson);
            statement.executeUpdate();
        }
    }

    private static boolean hasText(String value) {
        return value != null && !value.isBlank();
    }

    @Override
    public void reverse(ReverseMappingContext context) throws Exception {
        String sql = """
                select c.customer_id, c.engaged_party_id,
                       email.characteristic_json as email,
                       phone.characteristic_json as msisdn
                from TC_CUSTOMER c
                left join TC_PTY_CNT_MED email
                  on email.party_id = c.engaged_party_id and email.medium_type = 'emailAddress'
                left join TC_PTY_CNT_MED phone
                  on phone.party_id = c.engaged_party_id and phone.medium_type = 'telephoneNumber'
                limit 1
                """;
        try (PreparedStatement statement = context.target().prepareStatement(sql);
                ResultSet rs = statement.executeQuery()) {
            if (!rs.next()) {
                return;
            }
            upsertSiebelContact(
                    context.source("SIEBEL_SYSTEM"),
                    rs.getString("customer_id"),
                    rs.getString("engaged_party_id"),
                    rs.getString("email"),
                    rs.getString("msisdn"));
        }
    }

    private static void upsertSiebelContact(
            Connection siebel,
            String customerId,
            String partyId,
            String email,
            String msisdn) throws SQLException {
        String sql = """
                insert into SBL_CUSTOMER
                  (customer_id, party_id, msisdn, first_name, last_name, email, segment_code, status)
                values (?, ?, ?, ?, ?, ?, ?, ?)
                on conflict(customer_id) do update set
                  msisdn = excluded.msisdn,
                  email = excluded.email
                """;
        try (PreparedStatement statement = siebel.prepareStatement(sql)) {
            statement.setString(1, customerId);
            statement.setString(2, partyId);
            statement.setString(3, hasText(msisdn) ? msisdn : "UNKNOWN_" + customerId);
            statement.setString(4, "");
            statement.setString(5, "");
            statement.setString(6, hasText(email) ? email : customerId + "@example.invalid");
            statement.setString(7, "UNKNOWN");
            statement.setString(8, "ACTIVE");
            statement.executeUpdate();
        }
    }

    private record SourceRow(String partyId, String email, String msisdn) {
    }
}
