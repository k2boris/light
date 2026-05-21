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

/** Auto-generated Java mapping from Blackbox IR. */
public final class TcProductSiebelSblAssetPlan implements MappingPlan, ReverseMappingPlan {
    private static final Logger LOG = Logger.getLogger(TcProductSiebelSblAssetPlan.class.getName());

    @Override
    public String planId() { return "TC_PRODUCT__Siebel__SBL_ASSET"; }

    @Override
    public void execute(MappingContext context) throws Exception {
        String customerId = context.instanceValue("customer_id");
        int rows = 0;
        try (PreparedStatement statement = context.sources().connection("SIEBEL_SYSTEM").prepareStatement("select product_id, status, start_dt, contract_end_dt as end_dt, offering_id from SBL_ASSET where customer_id = ? and 1 = 0")) {
            statement.setString(1, customerId);
            try (ResultSet rs = statement.executeQuery()) {
                while (rs.next()) {
                    rows += insertProduct(context.target(), rs);
                }
            }
        }
        LOG.finer("Generated mapping wrote TC_PRODUCT rows=" + rows + " plan=" + planId() + " customer_id=" + customerId);
    }

    private static int insertProduct(Connection target, ResultSet rs) throws SQLException {
        String sql = """
                insert into TC_PRODUCT (product_id, status, start_date, termination_date, product_offering_id, created_dt)
                values (?, ?, ?, ?, ?, datetime('now'))
                on conflict(product_id, start_date) do update set
                  status = excluded.status,
                  termination_date = excluded.termination_date,
                  product_offering_id = excluded.product_offering_id
                """;
        try (PreparedStatement statement = target.prepareStatement(sql)) {
            statement.setString(1, rs.getString("product_id"));
            statement.setString(2, rs.getString("status"));
            statement.setString(3, rs.getString("start_dt"));
            statement.setString(4, rs.getString("end_dt"));
            statement.setString(5, rs.getString("offering_id"));
            return statement.executeUpdate();
        }
    }

    private static String customerId(Connection target) throws SQLException {
        try (PreparedStatement statement = target.prepareStatement("select customer_id from TC_CUSTOMER limit 1");
                ResultSet rs = statement.executeQuery()) {
            return rs.next() ? rs.getString("customer_id") : null;
        }
    }

    private static void ensureNccProductRefs(Connection ncc, String offeringId, String specId) throws SQLException {
        executeUpdate(ncc,
                "insert into NCC_PRODUCT_SPEC (spec_id, spec_code, name, type) values (?, ?, ?, ?) on conflict(spec_id) do nothing",
                specId, specId, "Generated spec", "UNKNOWN");
        executeUpdate(ncc,
                "insert into NCC_PRODUCT_OFFERING (offering_id, offering_code, name, category, base_monthly_price, status, valid_from, valid_to) "
                        + "values (?, ?, ?, ?, ?, ?, ?, ?) on conflict(offering_id) do nothing",
                offeringId, offeringId, "Generated offering", "UNKNOWN", "0", "ACTIVE", "1970-01-01", "2999-12-31");
    }

    private static void executeUpdate(Connection connection, String sql, String... values) throws SQLException {
        try (PreparedStatement statement = connection.prepareStatement(sql)) {
            for (int i = 0; i < values.length; i++) {
                statement.setString(i + 1, values[i]);
            }
            statement.executeUpdate();
        }
    }

    private static boolean isBlank(String value) {
        return value == null || value.isBlank();
    }

    private static String valueOrDefault(String value, String defaultValue) {
        return isBlank(value) ? defaultValue : value;
    }

    @Override
    public void reverse(ReverseMappingContext context) throws Exception {
        String customerId = customerId(context.target());
        if (isBlank(customerId)) {
            return;
        }
        String sql = """
                select product_id, status, start_date, termination_date, product_offering_id
                from TC_PRODUCT
                where termination_date is not null and trim(termination_date) <> ''
                order by product_id, start_date
                """;
        int index = 0;
        try (PreparedStatement statement = context.target().prepareStatement(sql);
                ResultSet rs = statement.executeQuery()) {
            while (rs.next()) {
                index++;
                executeUpdate(context.source("SIEBEL_SYSTEM"),
                        "insert into SBL_ASSET (asset_id, customer_id, product_id, offering_id, start_dt, status, contract_end_dt) "
                                + "values (?, ?, ?, ?, ?, ?, ?) on conflict(asset_id) do update set "
                                + "customer_id = excluded.customer_id, product_id = excluded.product_id, offering_id = excluded.offering_id, "
                                + "start_dt = excluded.start_dt, status = excluded.status, contract_end_dt = excluded.contract_end_dt",
                        "AST_REV_" + customerId + "_" + index,
                        customerId,
                        rs.getString("product_id"),
                        valueOrDefault(rs.getString("product_offering_id"), "UNKNOWN"),
                        rs.getString("start_date"),
                        valueOrDefault(rs.getString("status"), "ACTIVE"),
                        rs.getString("termination_date"));
            }
        }
    }

}
