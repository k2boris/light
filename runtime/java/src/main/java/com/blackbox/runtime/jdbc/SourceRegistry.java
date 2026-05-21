package com.blackbox.runtime.jdbc;

import java.sql.Connection;
import java.sql.DriverManager;
import java.sql.SQLException;
import java.util.LinkedHashMap;
import java.util.Map;
import java.util.logging.Logger;

/**
 * Owns source JDBC connections for one runtime execution.
 *
 * Source names must match project.yaml source_ddls keys, for example
 * SIEBEL_SYSTEM. Mapping plans address sources by these stable names.
 */
public final class SourceRegistry implements AutoCloseable {
    private static final Logger LOG = Logger.getLogger(SourceRegistry.class.getName());

    private final Map<String, Connection> connections = new LinkedHashMap<>();

    public static SourceRegistry open(Map<String, String> sourceUrls) {
        SourceRegistry registry = new SourceRegistry();
        for (Map.Entry<String, String> entry : sourceUrls.entrySet()) {
            registry.openSource(entry.getKey(), entry.getValue());
        }
        return registry;
    }

    public Connection connection(String sourceName) {
        Connection connection = connections.get(sourceName);
        if (connection == null) {
            throw new IllegalArgumentException("No source connection registered for " + sourceName);
        }
        return connection;
    }

    private void openSource(String sourceName, String jdbcUrl) {
        try {
            LOG.info(() -> "Opening source connection source=" + sourceName + " url=" + jdbcUrl);
            Connection connection = DriverManager.getConnection(jdbcUrl);
            connections.put(sourceName, connection);
            LOG.fine(() -> "Source connection opened source=" + sourceName);
        } catch (SQLException ex) {
            throw new IllegalStateException("Unable to open source " + sourceName + " at " + jdbcUrl, ex);
        }
    }

    @Override
    public void close() {
        for (Map.Entry<String, Connection> entry : connections.entrySet()) {
            try {
                LOG.finer(() -> "Closing source connection source=" + entry.getKey());
                entry.getValue().close();
            } catch (SQLException ex) {
                LOG.warning("Failed to close source connection source=" + entry.getKey() + " error=" + ex.getMessage());
            }
        }
    }
}
