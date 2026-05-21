package com.blackbox.bian.source;

import com.blackbox.runtime.instance.InstanceEnumerator;
import com.blackbox.runtime.instance.InstanceKey;
import com.blackbox.runtime.jdbc.SourceRegistry;
import java.sql.Connection;
import java.sql.PreparedStatement;
import java.sql.ResultSet;
import java.util.ArrayList;
import java.util.LinkedHashMap;
import java.util.List;
import java.util.Map;
import java.util.logging.Logger;

/**
 * Enumerates BIAN target instances from Informatica MDM golden parties.
 *
 * ROWID_OBJECT is the canonical BI_PARTY id. Peer source keys are copied into
 * attributes for trace logging and for simple mappings that need source keys
 * without re-querying the xref table.
 */
public final class BianPartyEnumerator implements InstanceEnumerator {
    private static final Logger LOG = Logger.getLogger(BianPartyEnumerator.class.getName());

    private final int maxInstances;

    public BianPartyEnumerator(int maxInstances) {
        this.maxInstances = maxInstances;
    }

    @Override
    public List<InstanceKey> enumerate(SourceRegistry sources) throws Exception {
        Connection mdm = sources.connection("MDM_INFA_DS");
        String sql = """
                select ROWID_OBJECT
                from C_BO_PARTY
                order by ROWID_OBJECT
                """;
        List<InstanceKey> instances = new ArrayList<>();
        try (PreparedStatement statement = mdm.prepareStatement(sql);
                ResultSet rs = statement.executeQuery()) {
            while (rs.next()) {
                String partyId = rs.getString("ROWID_OBJECT");
                Map<String, String> attributes = new LinkedHashMap<>();
                attributes.put("party_id", partyId);
                attributes.putAll(sourceKeys(mdm, partyId));
                instances.add(new InstanceKey("BI_PARTY", partyId, attributes));
                if (maxInstances > 0 && instances.size() >= maxInstances) {
                    break;
                }
            }
        }
        LOG.info(() -> "Enumerated BIAN party instances count=" + instances.size());
        return instances;
    }

    private static Map<String, String> sourceKeys(Connection mdm, String partyId) throws Exception {
        String sql = """
                select SYSTEM_CODE, SOURCE_KEY
                from C_XREF_PARTY
                where ROWID_OBJECT = ?
                order by SYSTEM_CODE, SOURCE_ENTITY
                """;
        Map<String, String> attributes = new LinkedHashMap<>();
        try (PreparedStatement statement = mdm.prepareStatement(sql)) {
            statement.setString(1, partyId);
            try (ResultSet rs = statement.executeQuery()) {
                while (rs.next()) {
                    attributes.put(rs.getString("SYSTEM_CODE"), rs.getString("SOURCE_KEY"));
                }
            }
        }
        return attributes;
    }
}
