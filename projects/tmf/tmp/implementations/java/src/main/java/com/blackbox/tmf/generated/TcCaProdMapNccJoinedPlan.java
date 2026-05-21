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
public final class TcCaProdMapNccJoinedPlan implements MappingPlan, ReverseMappingPlan {
    private static final Logger LOG = Logger.getLogger(TcCaProdMapNccJoinedPlan.class.getName());

    @Override
    public String planId() { return "TC_CA_PROD_MAP__NCC__JOINED"; }

    @Override
    public void execute(MappingContext context) throws Exception {
        String custAcctId = context.instanceValue("customer_id");
        String sql = """
                insert into TC_CA_PROD_MAP (cust_acct_id, product_id, rel_type)
                values (?, ?, 'owns')
                on conflict(cust_acct_id, product_id) do update set rel_type = excluded.rel_type
                """;
        int rows = 0;
        try (PreparedStatement select = context.target().prepareStatement("select distinct product_id from TC_PRODUCT");
                ResultSet rs = select.executeQuery();
                PreparedStatement insert = context.target().prepareStatement(sql)) {
            while (rs.next()) {
                insert.setString(1, custAcctId);
                insert.setString(2, rs.getString("product_id"));
                rows += insert.executeUpdate();
            }
        }
        LOG.finer("Generated mapping wrote TC_CA_PROD_MAP rows=" + rows + " cust_acct_id=" + custAcctId);
    }

    @Override
    public void reverse(ReverseMappingContext context) throws Exception {
        LOG.finer("Reverse mapping no-op for " + planId());
    }
}
