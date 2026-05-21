package com.blackbox.tmf.source;

import com.blackbox.runtime.instance.InstanceEnumerator;
import com.blackbox.runtime.instance.InstanceKey;
import com.blackbox.runtime.jdbc.SourceRegistry;
import java.sql.Connection;
import java.sql.PreparedStatement;
import java.sql.ResultSet;
import java.util.ArrayList;
import java.util.List;
import java.util.Map;
import java.util.logging.Logger;

/**
 * TMF root-instance enumerator.
 *
 * The target database is scoped by party_id. The enumerator also resolves peer
 * source identifiers, such as customer_id, once at the root instance boundary.
 */
public final class TmfPartyEnumerator implements InstanceEnumerator {
    private static final Logger LOG = Logger.getLogger(TmfPartyEnumerator.class.getName());

    private final int maxInstances;

    public TmfPartyEnumerator(int maxInstances) {
        this.maxInstances = maxInstances;
    }

    @Override
    public List<InstanceKey> enumerate(SourceRegistry sources) throws Exception {
        String sql = """
                select party_id, customer_id
                from SBL_CUSTOMER
                where party_id is not null and trim(party_id) <> ''
                order by party_id
                """;
        if (maxInstances > 0) {
            sql = sql + " limit ?";
        }
        String enumerationSql = sql;
        LOG.info("Enumerating TC_PARTY instances from SIEBEL_SYSTEM.SBL_CUSTOMER");
        LOG.finer(() -> "Instance enumeration SQL: " + enumerationSql);
        List<InstanceKey> keys = new ArrayList<>();
        Connection connection = sources.connection("SIEBEL_SYSTEM");
        try (PreparedStatement statement = connection.prepareStatement(enumerationSql)) {
            if (maxInstances > 0) {
                statement.setInt(1, maxInstances);
            }
            try (ResultSet rs = statement.executeQuery()) {
                while (rs.next()) {
                    String partyId = rs.getString("party_id");
                    String customerId = rs.getString("customer_id");
                    keys.add(new InstanceKey("TC_PARTY", partyId, Map.of(
                            "party_id", partyId,
                            "customer_id", customerId)));
                    LOG.finest(() -> "Discovered TC_PARTY instance party_id=" + partyId
                            + " customer_id=" + customerId);
                }
            }
        }
        LOG.info(() -> "Discovered " + keys.size() + " TC_PARTY instances");
        return keys;
    }
}
