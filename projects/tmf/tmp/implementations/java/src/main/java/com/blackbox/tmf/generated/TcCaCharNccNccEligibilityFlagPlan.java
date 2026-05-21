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
 * Plan: TC_CA_CHAR__NCC__NCC_ELIGIBILITY_FLAG
 * Template: TPL_EAV_PARENT_SCOPED
 *
 * Generated as build output. Do not edit by hand.
 */
public final class TcCaCharNccNccEligibilityFlagPlan implements MappingPlan, ReverseMappingPlan {
    private static final Logger LOG = Logger.getLogger(TcCaCharNccNccEligibilityFlagPlan.class.getName());

    @Override
    public String planId() {
        return "TC_CA_CHAR__NCC__NCC_ELIGIBILITY_FLAG";
    }

    @Override
    public void execute(MappingContext context) throws Exception {
        String customerId = context.instanceValue("customer_id");
        String custAcctId = "CA_" + customerId;
        int rows = 0;
        try (PreparedStatement statement = context.sources().connection("NCC_SYSTEM").prepareStatement("""
                select customer_id, flag_value, flag_code, effective_dt from NCC_ELIGIBILITY_FLAG where customer_id = ?
                """)) {
            statement.setString(1, customerId);
            try (ResultSet rs = statement.executeQuery()) {
                while (rs.next()) {
                    SourceRow row = new SourceRow(rs.getString("customer_id"), rs.getString("flag_value"), rs.getString("flag_code"), rs.getString("effective_dt"));
                    rows += insertRows(context.target(), custAcctId, row);
                }
            }
        }
        LOG.finer("Generated mapping wrote TC_CA_CHAR rows=" + rows + " plan=" + planId() + " customer_id=" + customerId);
    }

    private static int insertRows(Connection target, String custAcctId, SourceRow row) throws SQLException {
        int rows = 0;
            if (!isBlank(row.flagValue())) {
                rows += insertCharacteristic(target, custAcctId, "NCC_ELIGIBILITY_FLAG", "flag." + row.flagCode() + "." + row.effectiveDt(), row.flagValue());
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

    private record SourceRow(String customerId, String flagValue, String flagCode, String effectiveDt) {
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
        try (PreparedStatement statement = context.target().prepareStatement(
                "select name, value from TC_CA_CHAR where value_type = 'NCC_ELIGIBILITY_FLAG'")) {
            try (ResultSet rs = statement.executeQuery()) {
                while (rs.next()) {
                    String[] parts = rs.getString("name").split("\\.", 3);
                    if (parts.length != 3 || !"flag".equals(parts[0])) {
                        continue;
                    }
                    executeUpdate(context.source("NCC_SYSTEM"),
                            "insert into NCC_ELIGIBILITY_FLAG (customer_id, flag_code, flag_value, effective_dt, end_dt) "
                                    + "values (?, ?, ?, ?, ?) on conflict(customer_id, flag_code, effective_dt) do update set "
                                    + "flag_value = excluded.flag_value",
                            customerId, parts[1], rs.getString("value"), parts[2], null);
                }
            }
        }
    }

}
