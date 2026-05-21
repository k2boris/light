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
public final class TcProductNccNccProductPlan implements MappingPlan, ReverseMappingPlan {
    private static final Logger LOG = Logger.getLogger(TcProductNccNccProductPlan.class.getName());

    @Override
    public String planId() { return "TC_PRODUCT__NCC__NCC_PRODUCT"; }

    @Override
    public void execute(MappingContext context) throws Exception {
        String customerId = context.instanceValue("customer_id");
        int rows = 0;
        try (PreparedStatement statement = context.sources().connection("NCC_SYSTEM").prepareStatement("select p.product_id, p.status, p.start_dt, null as end_dt, p.offering_id from NCC_SUBSCRIPTION s join NCC_PRODUCT p on s.subscription_id = p.subscription_id where s.customer_id = ? and p.status = 'ACTIVE'")) {
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
        String subscriptionId = "SUB_REV_" + customerId;
        executeUpdate(context.source("NCC_SYSTEM"),
                "insert into NCC_SUBSCRIPTION (subscription_id, customer_id, status, start_dt, end_dt) "
                        + "values (?, ?, ?, ?, ?) on conflict(subscription_id) do update set customer_id = excluded.customer_id",
                subscriptionId, customerId, "ACTIVE", "1970-01-01", null);
        String sql = """
                select product_id, status, start_date, termination_date, product_offering_id
                from TC_PRODUCT
                where exists (
                    select 1 from TC_PROD_CHAR pc where pc.product_id = TC_PRODUCT.product_id
                )
                and (
                    termination_date is null or trim(termination_date) = ''
                    or not exists (
                        select 1
                        from TC_PRODUCT tp2
                        where tp2.product_id = TC_PRODUCT.product_id
                          and (tp2.termination_date is null or trim(tp2.termination_date) = '')
                    )
                )
                order by product_id, start_date
                """;
        try (PreparedStatement statement = context.target().prepareStatement(sql);
                ResultSet rs = statement.executeQuery()) {
            while (rs.next()) {
                String productId = rs.getString("product_id");
                String offeringId = valueOrDefault(rs.getString("product_offering_id"), "OFF_REV_" + productId);
                String specId = "SPEC_REV_" + productId;
                ensureNccProductRefs(context.source("NCC_SYSTEM"), offeringId, specId);
                executeUpdate(context.source("NCC_SYSTEM"),
                        "insert into NCC_PRODUCT (product_id, subscription_id, offering_id, spec_id, status, start_dt, end_dt) "
                                + "values (?, ?, ?, ?, ?, ?, ?) on conflict(product_id) do update set "
                                + "subscription_id = excluded.subscription_id, offering_id = excluded.offering_id, spec_id = excluded.spec_id, "
                                + "status = excluded.status, start_dt = excluded.start_dt, end_dt = excluded.end_dt",
                        productId,
                        subscriptionId,
                        offeringId,
                        specId,
                        valueOrDefault(rs.getString("status"), "ACTIVE"),
                        rs.getString("start_date"),
                        rs.getString("termination_date"));
            }
        }
    }

}
