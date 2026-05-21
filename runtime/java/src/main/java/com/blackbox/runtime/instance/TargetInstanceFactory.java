package com.blackbox.runtime.instance;

import com.blackbox.runtime.schema.TargetSchemaManager;
import java.io.IOException;
import java.nio.file.Files;
import java.nio.file.Path;
import java.sql.Connection;
import java.sql.DriverManager;
import java.sql.SQLException;
import java.sql.Statement;
import java.util.logging.Logger;

/**
 * Creates one SQLite target database for each logical instance.
 *
 * The factory owns filesystem behavior: output directory creation, overwrite
 * policy, SQLite connection creation, transaction boundaries, and schema setup.
 */
public final class TargetInstanceFactory {
    private static final Logger LOG = Logger.getLogger(TargetInstanceFactory.class.getName());

    private final Path outputDir;
    private final boolean overwrite;
    private final TargetSchemaManager schemaManager;

    public TargetInstanceFactory(Path outputDir, boolean overwrite, TargetSchemaManager schemaManager) {
        this.outputDir = outputDir;
        this.overwrite = overwrite;
        this.schemaManager = schemaManager;
    }

    public TargetInstance open(InstanceKey instanceKey) {
        try {
            Files.createDirectories(outputDir);
            Path dbPath = outputDir.resolve(instanceKey.safeFileStem() + ".db");
            if (overwrite && Files.exists(dbPath)) {
                LOG.fine(() -> "Deleting existing target DB " + dbPath);
                Files.delete(dbPath);
            }
            LOG.info(() -> "Creating target instance db=" + dbPath + " instance=" + instanceKey);
            Connection connection = DriverManager.getConnection("jdbc:sqlite:" + dbPath);
            connection.setAutoCommit(false);
            enableForeignKeys(connection);
            schemaManager.createSchema(connection);
            return new TargetInstance(instanceKey, dbPath, connection);
        } catch (IOException | SQLException ex) {
            throw new IllegalStateException("Unable to create target database for " + instanceKey, ex);
        }
    }

    private static void enableForeignKeys(Connection connection) throws SQLException {
        try (Statement statement = connection.createStatement()) {
            statement.execute("PRAGMA foreign_keys = ON");
        }
    }
}
