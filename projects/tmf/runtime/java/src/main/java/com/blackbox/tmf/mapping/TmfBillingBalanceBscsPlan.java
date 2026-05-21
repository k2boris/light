package com.blackbox.tmf.mapping;

import com.blackbox.runtime.mapping.MappingContext;
import com.blackbox.runtime.mapping.MappingPlan;
import com.blackbox.runtime.mapping.ReverseMappingContext;
import com.blackbox.runtime.mapping.ReverseMappingPlan;
import java.sql.PreparedStatement;
import java.sql.ResultSet;
import java.sql.SQLException;
import java.util.logging.Logger;

/**
 * Project-scoped BSCS open-item balance mapping for TMF billing accounts.
 */
public final class TmfBillingBalanceBscsPlan implements MappingPlan, ReverseMappingPlan {
    private static final Logger LOG = Logger.getLogger(TmfBillingBalanceBscsPlan.class.getName());

    @Override
    public String planId() {
        return "TC_BA_BAL__BSCS__BSCS_AR_OPEN_ITEM";
    }

    @Override
    public void execute(MappingContext context) throws Exception {
        String customerId = context.instanceValue("customer_id");
        if (customerId == null || customerId.isBlank()) {
            LOG.warning("No customer_id resolved; skipping BSCS balance mapping");
            return;
        }
        String sql = """
                select chosen.billing_account_id,
                       chosen.status,
                       sum(chosen.open_amount) as amount,
                       max(chosen.due_dt) as as_of_dt
                from BSCS_BILLING_ACCOUNT b
                join (
                    select a.billing_account_id, a.open_amount, a.status, i.due_dt
                    from BSCS_AR_OPEN_ITEM a
                    left join BSCS_INVOICE i on i.invoice_id = a.source_invoice_id
                    where a.status = (
                        select a2.status
                        from BSCS_AR_OPEN_ITEM a2
                        where a2.billing_account_id = a.billing_account_id
                          and a2.status in ('OPEN', 'PAST_DUE')
                        order by case when a2.status = 'OPEN' then 0 else 1 end
                        limit 1
                    )
                ) chosen on chosen.billing_account_id = b.billing_account_id
                where b.customer_id = ?
                group by chosen.billing_account_id, chosen.status
                order by chosen.billing_account_id
                """;
        int rows = 0;
        try (PreparedStatement statement = context.sources().connection("BSCS_SYSTEM").prepareStatement(sql)) {
            statement.setString(1, customerId);
            try (ResultSet rs = statement.executeQuery()) {
                while (rs.next()) {
                    rows += upsertBalance(context, rs);
                }
            }
        }
        LOG.finer("Mapped BSCS open balances rows=" + rows + " customer_id=" + customerId);
    }

    private static int upsertBalance(MappingContext context, ResultSet rs) throws SQLException {
        String sql = """
                insert into TC_BA_BAL (bill_acct_id, bal_type, amount, units, as_of_dt)
                values (?, ?, ?, 'USD', ?)
                on conflict(bill_acct_id, bal_type, as_of_dt) do update set
                  amount = excluded.amount,
                  units = excluded.units
                """;
        try (PreparedStatement statement = context.target().prepareStatement(sql)) {
            statement.setString(1, rs.getString("billing_account_id"));
            statement.setString(2, rs.getString("status"));
            statement.setString(3, formatDecimal(rs.getString("amount")));
            statement.setString(4, valueOrDefault(rs.getString("as_of_dt"), "1970-01-01"));
            return statement.executeUpdate();
        }
    }

    @Override
    public void reverse(ReverseMappingContext context) throws Exception {
        LOG.finer("Reverse mapping no-op for " + planId() + "; balances are validated target-side only");
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
}
