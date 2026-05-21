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
 * Plan: TC_CA_CHAR__BSCS__BSCS_CUSTOMER
 * Template: TPL_EAV_PARENT_SCOPED
 *
 * Generated as build output. Do not edit by hand.
 */
public final class TcCaCharBscsBscsCustomerPlan implements MappingPlan, ReverseMappingPlan {
    private static final Logger LOG = Logger.getLogger(TcCaCharBscsBscsCustomerPlan.class.getName());

    @Override
    public String planId() {
        return "TC_CA_CHAR__BSCS__BSCS_CUSTOMER";
    }

    @Override
    public void execute(MappingContext context) throws Exception {
        String customerId = context.instanceValue("customer_id");
        String custAcctId = "CA_" + customerId;
        int rows = 0;
        try (PreparedStatement statement = context.sources().connection("BSCS_SYSTEM").prepareStatement("""
                select customer_id, credit_class, risk_flag from BSCS_CUSTOMER where customer_id = ?
                """)) {
            statement.setString(1, customerId);
            try (ResultSet rs = statement.executeQuery()) {
                while (rs.next()) {
                    SourceRow row = new SourceRow(rs.getString("customer_id"), rs.getString("credit_class"), rs.getString("risk_flag"));
                    rows += insertRows(context.target(), custAcctId, row);
                }
            }
        }
        LOG.finer("Generated mapping wrote TC_CA_CHAR rows=" + rows + " plan=" + planId() + " customer_id=" + customerId);
    }

    private static int insertRows(Connection target, String custAcctId, SourceRow row) throws SQLException {
        int rows = 0;
            if (!isBlank(row.creditClass())) {
                rows += insertCharacteristic(target, custAcctId, "BSCS_CUSTOMER", "creditClass", row.creditClass());
            }
            if (!isBlank(row.riskFlag())) {
                rows += insertCharacteristic(target, custAcctId, "BSCS_CUSTOMER", "riskFlag", row.riskFlag());
            }
        return rows;
    }

    private static int insertCharacteristic(
            Connection target,
            String custAcctId,
            String valueType,
            String name,
            String value) throws SQLException {
        if (isBlank(value)) {
            return 0;
        }
        String sql = """
                insert into TC_CA_CHAR (cust_acct_id, value_type, name, value)
                values (?, ?, ?, ?)
                on conflict(cust_acct_id, name, value) do update set
                  value_type = excluded.value_type
                """;
        try (PreparedStatement statement = target.prepareStatement(sql)) {
            statement.setString(1, custAcctId);
            statement.setString(2, valueType);
            statement.setString(3, name);
            statement.setString(4, value);
            return statement.executeUpdate();
        }
    }

    private static boolean isBlank(String value) {
        return value == null || value.isBlank();
    }

    private record SourceRow(String customerId, String creditClass, String riskFlag) {
    }

    private static String customerId(Connection target) throws SQLException {
        try (PreparedStatement statement = target.prepareStatement("select customer_id from TC_CUSTOMER limit 1");
                ResultSet rs = statement.executeQuery()) {
            return rs.next() ? rs.getString("customer_id") : null;
        }
    }

    private static String eavValue(Connection target, String valueType, String name) throws SQLException {
        String sql = "select value from TC_CA_CHAR where value_type = ? and name = ? limit 1";
        try (PreparedStatement statement = target.prepareStatement(sql)) {
            statement.setString(1, valueType);
            statement.setString(2, name);
            try (ResultSet rs = statement.executeQuery()) {
                return rs.next() ? rs.getString("value") : null;
            }
        }
    }

    private static String latestInteractionValue(Connection target) throws SQLException {
        String sql = """
                select value
                from TC_CA_CHAR
                where value_type = 'SBL_INTERACTION' and name = 'lastInteractionOutcome'
                limit 1
                """;
        try (PreparedStatement statement = target.prepareStatement(sql);
                ResultSet rs = statement.executeQuery()) {
            return rs.next() ? rs.getString("value") : null;
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

    private static String valueOrDefault(String value, String defaultValue) {
        return isBlank(value) ? defaultValue : value;
    }

    private static String unbracket(String value) {
        if (value == null) {
            return null;
        }
        String trimmed = value.trim();
        if (trimmed.startsWith("[") && trimmed.endsWith("]") && trimmed.length() >= 2) {
            return trimmed.substring(1, trimmed.length() - 1);
        }
        return value;
    }

    @Override
    public void reverse(ReverseMappingContext context) throws Exception {
        String customerId = customerId(context.target());
        if (isBlank(customerId)) {
            return;
        }
        executeUpdate(context.source("BSCS_SYSTEM"),
                "insert into BSCS_CUSTOMER (customer_id, msisdn, credit_class, risk_flag) values (?, ?, ?, ?) "
                        + "on conflict(customer_id) do update set credit_class = excluded.credit_class, risk_flag = excluded.risk_flag",
                customerId,
                valueOrDefault(eavValue(context.target(), "BSCS_CUSTOMER", "msisdn"), "UNKNOWN_" + customerId),
                valueOrDefault(eavValue(context.target(), "BSCS_CUSTOMER", "creditClass"), "UNKNOWN"),
                valueOrDefault(eavValue(context.target(), "BSCS_CUSTOMER", "riskFlag"), "N"));
    }

}
