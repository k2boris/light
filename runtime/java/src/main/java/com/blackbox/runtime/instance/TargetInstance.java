package com.blackbox.runtime.instance;

import java.nio.file.Path;
import java.sql.Connection;
import java.sql.SQLException;
import java.util.logging.Logger;

/**
 * Open target database for one logical instance.
 */
public final class TargetInstance implements AutoCloseable {
    private static final Logger LOG = Logger.getLogger(TargetInstance.class.getName());

    private final InstanceKey key;
    private final Path path;
    private final Connection connection;

    TargetInstance(InstanceKey key, Path path, Connection connection) {
        this.key = key;
        this.path = path;
        this.connection = connection;
    }

    public InstanceKey key() {
        return key;
    }

    public Path path() {
        return path;
    }

    public Connection connection() {
        return connection;
    }

    public void commit() {
        try {
            connection.commit();
            LOG.info(() -> "Committed target instance db=" + path + " instance=" + key);
        } catch (SQLException ex) {
            throw new IllegalStateException("Unable to commit target instance " + key, ex);
        }
    }

    @Override
    public void close() {
        try {
            connection.close();
            LOG.finer(() -> "Closed target instance db=" + path + " instance=" + key);
        } catch (SQLException ex) {
            LOG.warning("Failed to close target instance " + key + " error=" + ex.getMessage());
        }
    }
}
