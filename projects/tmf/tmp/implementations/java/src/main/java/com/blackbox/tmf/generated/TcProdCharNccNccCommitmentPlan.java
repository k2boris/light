package com.blackbox.tmf.generated;

import com.blackbox.runtime.mapping.MappingContext;
import com.blackbox.runtime.mapping.MappingPlan;
import com.blackbox.runtime.mapping.ReverseMappingContext;
import com.blackbox.runtime.mapping.ReverseMappingPlan;
import java.sql.PreparedStatement;
import java.sql.ResultSet;
import java.sql.SQLException;
import java.util.logging.Logger;

/** Auto-generated Java mapping from Blackbox IR. */
public final class TcProdCharNccNccCommitmentPlan implements MappingPlan, ReverseMappingPlan {
    private static final Logger LOG = Logger.getLogger(TcProdCharNccNccCommitmentPlan.class.getName());

    @Override
    public String planId() { return "TC_PROD_CHAR__NCC__NCC_COMMITMENT"; }

    @Override
    public void execute(MappingContext context) throws Exception {
        String customerId = context.instanceValue("customer_id");
        int rows = 0;
        try (PreparedStatement statement = context.sources().connection("NCC_SYSTEM").prepareStatement("select c.product_id, c.commitment_type, c.start_dt, c.end_dt, c.early_term_fee_usd from NCC_SUBSCRIPTION s join NCC_PRODUCT p on s.subscription_id = p.subscription_id join NCC_COMMITMENT c on p.product_id = c.product_id where s.customer_id = ? and p.status = 'ACTIVE' and c.product_id = (select min(p2.product_id) from NCC_SUBSCRIPTION s2 join NCC_PRODUCT p2 on s2.subscription_id = p2.subscription_id join NCC_COMMITMENT c3 on c3.product_id = p2.product_id where s2.customer_id = s.customer_id and p2.status = 'ACTIVE') and c.commitment_type = (select c2.commitment_type from NCC_COMMITMENT c2 where c2.product_id = c.product_id order by case when c2.commitment_type = 'CONTRACT' then 0 else 1 end, c2.commitment_type limit 1)")) {
            statement.setString(1, customerId);
            try (ResultSet rs = statement.executeQuery()) {
                while (rs.next()) {

                    String valueType = rs.getString("commitment_type");
                    rows += insertCharacteristic(context, rs.getString("product_id"), "commitmentEndDt", rs.getString("end_dt"), valueType);
                    rows += insertCharacteristic(context, rs.getString("product_id"), "earlyTermFeeUsd", formatDecimal(rs.getString("early_term_fee_usd")), valueType);

                }
            }
        }
        LOG.finer("Generated mapping wrote TC_PROD_CHAR rows=" + rows + " plan=" + planId() + " customer_id=" + customerId);
    }

    private static int insertCharacteristic(MappingContext context, String productId, String name, String value, String valueType) throws SQLException {
        if (value == null || value.isBlank()) {
            return 0;
        }
        String sql = """
                insert into TC_PROD_CHAR (product_id, name, value, value_type)
                values (?, ?, ?, ?)
                on conflict(product_id, name, value_type) do update set value = excluded.value
                """;
        try (PreparedStatement statement = context.target().prepareStatement(sql)) {
            statement.setString(1, productId);
            statement.setString(2, name);
            statement.setString(3, value);
            statement.setString(4, valueType);
            return statement.executeUpdate();
        }
    }

    private static String prodCharValue(MappingContext context, String productId, String name, String valueType) {
        throw new UnsupportedOperationException("Forward context cannot read reverse values");
    }

    private static String prodCharValue(ReverseMappingContext context, String productId, String name, String valueType) throws SQLException {
        String sql = "select value from TC_PROD_CHAR where product_id = ? and name = ? and value_type = ? limit 1";
        try (PreparedStatement statement = context.target().prepareStatement(sql)) {
            statement.setString(1, productId);
            statement.setString(2, name);
            statement.setString(3, valueType);
            try (ResultSet rs = statement.executeQuery()) {
                return rs.next() ? rs.getString("value") : null;
            }
        }
    }

    private static void executeUpdate(java.sql.Connection connection, String sql, String... values) throws SQLException {
        try (PreparedStatement statement = connection.prepareStatement(sql)) {
            for (int i = 0; i < values.length; i++) {
                statement.setString(i + 1, values[i]);
            }
            statement.executeUpdate();
        }
    }

    private static String valueOrDefault(String value, String defaultValue) {
        return value == null || value.isBlank() ? defaultValue : value;
    }

    private static String formatDecimal(String value) {
        if (value == null || value.isBlank()) {
            return value;
        }
        if (value.endsWith(".0")) {
            return value.substring(0, value.length() - 2);
        }
        return value;
    }

    @Override
    public void reverse(ReverseMappingContext context) throws Exception {
        String sql = """
                select product_id, value_type
                from TC_PROD_CHAR
                where name in ('commitmentEndDt', 'earlyTermFeeUsd')
                group by product_id, value_type
                order by product_id, value_type
                """;
        try (PreparedStatement statement = context.target().prepareStatement(sql);
                ResultSet rs = statement.executeQuery()) {
            while (rs.next()) {
                String[] parts = rs.getString("value_type").split(":", 2);
                if (parts.length != 2) {
                    continue;
                }
                executeUpdate(context.source("NCC_SYSTEM"),
                        "insert into NCC_COMMITMENT (product_id, commitment_type, start_dt, end_dt, early_term_fee_usd) "
                                + "values (?, ?, ?, ?, ?) on conflict(product_id, commitment_type) do update set "
                                + "start_dt = excluded.start_dt, end_dt = excluded.end_dt, early_term_fee_usd = excluded.early_term_fee_usd",
                        rs.getString("product_id"),
                        parts[0],
                        parts[1],
                        valueOrDefault(prodCharValue(context, rs.getString("product_id"), "commitmentEndDt", rs.getString("value_type")), "2999-12-31"),
                        valueOrDefault(prodCharValue(context, rs.getString("product_id"), "earlyTermFeeUsd", rs.getString("value_type")), "0"));
            }
        }
    }

}
