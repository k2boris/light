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
 * Plan: TC_PTY_CNT_MED__BSCS__JOINED
 * Template: TPL_JOIN_TO_1_PARENT_SCOPED
 *
 * Generated as build output. Do not edit by hand.
 */
public final class TcPtyCntMedBscsBillingAddressPlan implements MappingPlan, ReverseMappingPlan {
    private static final Logger LOG = Logger.getLogger(TcPtyCntMedBscsBillingAddressPlan.class.getName());

    @Override
    public String planId() {
        return "TC_PTY_CNT_MED__BSCS__JOINED";
    }

    @Override
    public void execute(MappingContext context) throws Exception {
        String partyId = context.instanceValue("party_id");
        String customerId = context.instanceValue("customer_id");
        if (customerId == null) {
            LOG.warning("No customer_id resolved for party_id=" + partyId + "; skipping TC_PTY_CNT_MED BSCS rows");
            return;
        }
        int rows = insertPostalRows(context.target(), context.sources().connection("BSCS_SYSTEM"), partyId, customerId);
        LOG.finer("Generated mapping wrote TC_PTY_CNT_MED BSCS rows=" + rows + " party_id=" + partyId);
    }

    private static int insertPostalRows(Connection target, Connection bscs, String partyId, String customerId) throws SQLException {
        String sql = """
                select distinct t2.is_primary as is_primary, t3.line1 as line1
                from BSCS_BILLING_ACCOUNT t1
                join BSCS_ACCOUNT_ADDRESS t2 on t1.billing_account_id = t2.billing_account_id
                join BSCS_ADDRESS t3 on t2.address_id = t3.address_id
                where t1.customer_id = ?
                order by t1.billing_account_id, t2.address_role, t2.address_id
                limit 1
                """;
        int rows = 0;
        try (PreparedStatement statement = bscs.prepareStatement(sql)) {
            statement.setString(1, customerId);
            try (ResultSet rs = statement.executeQuery()) {
                while (rs.next()) {
                    String line1 = rs.getString("line1");
                    if (line1 == null || line1.isBlank()) {
                        continue;
                    }
                    insertContactMedium(target, partyId, "postalAddress", 0, line1);
                    rows++;
                }
            }
        }
        return rows;
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

    @Override
    public void reverse(ReverseMappingContext context) throws Exception {
        String customerId = readCustomerId(context.target());
        if (customerId == null) {
            return;
        }
        String billingAccountId = "BA_" + customerId;
        executeUpdate(context.source("BSCS_SYSTEM"),
                "insert into BSCS_CUSTOMER (customer_id, msisdn, credit_class, risk_flag) values (?, ?, ?, ?) "
                        + "on conflict(customer_id) do update set msisdn = excluded.msisdn",
                customerId, "UNKNOWN_" + customerId, "STANDARD", "N");
        executeUpdate(context.source("BSCS_SYSTEM"),
                "insert into BSCS_BILLING_ACCOUNT (billing_account_id, customer_id, bill_cycle, currency, status) values (?, ?, ?, ?, ?) "
                        + "on conflict(billing_account_id) do update set customer_id = excluded.customer_id",
                billingAccountId, customerId, "1", "USD", "ACTIVE");
        String sql = """
                select preferred_flag, characteristic_json
                from TC_PTY_CNT_MED
                where medium_type = 'postalAddress'
                order by characteristic_json
                """;
        int index = 0;
        try (PreparedStatement statement = context.target().prepareStatement(sql);
                ResultSet rs = statement.executeQuery()) {
            while (rs.next()) {
                index++;
                String line1 = rs.getString("characteristic_json");
                if (line1 == null || line1.isBlank()) {
                    continue;
                }
                String addressId = "ADDR_" + customerId + "_" + index;
                String addressRole = "BILL_TO_" + index;
                executeUpdate(context.source("BSCS_SYSTEM"),
                        "insert into BSCS_ADDRESS (address_id, line1, city, state, postal_code, country) values (?, ?, ?, ?, ?, ?) "
                                + "on conflict(address_id) do update set line1 = excluded.line1",
                        addressId, line1, "UNKNOWN", "NA", "00000", "US");
                executeUpdate(context.source("BSCS_SYSTEM"),
                        "insert into BSCS_ACCOUNT_ADDRESS (billing_account_id, address_id, address_role, is_primary) values (?, ?, ?, ?) "
                                + "on conflict(billing_account_id, address_role) do update set address_id = excluded.address_id, is_primary = excluded.is_primary",
                        billingAccountId, addressId, addressRole, String.valueOf(rs.getInt("preferred_flag")));
            }
        }
    }

    private static String readCustomerId(Connection target) throws SQLException {
        try (PreparedStatement statement = target.prepareStatement("select customer_id from TC_CUSTOMER limit 1");
                ResultSet rs = statement.executeQuery()) {
            return rs.next() ? rs.getString("customer_id") : null;
        }
    }

    private static void executeUpdate(Connection connection, String sql, String... values) throws SQLException {
        try (PreparedStatement statement = connection.prepareStatement(sql)) {
            for (int i = 0; i < values.length; i++) {
                statement.setString(i + 1, values[i]);
            }
            statement.executeUpdate();
        }
    }
}
