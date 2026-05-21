package com.blackbox.runtime.schema;

import java.io.IOException;
import java.nio.file.Path;
import java.sql.Connection;
import java.sql.SQLException;
import java.sql.Statement;
import java.util.ArrayList;
import java.util.List;
import java.util.logging.Logger;
import java.util.regex.Pattern;

/**
 * Creates target schema inside a target instance database.
 *
 * The schema file is project-owned. The runtime executes it statement by
 * statement and applies a small SQLite compatibility normalization for legacy
 * DDL that declares both an inline and table-level primary key in one table.
 */
public final class TargetSchemaManager {
    private static final Logger LOG = Logger.getLogger(TargetSchemaManager.class.getName());
    private static final Pattern INLINE_PRIMARY_KEY = Pattern.compile("(?i)\\s+PRIMARY\\s+KEY\\b");

    private final Path schemaPath;

    public TargetSchemaManager(Path schemaPath) {
        this.schemaPath = schemaPath;
    }

    public void createSchema(Connection target) {
        LOG.info(() -> "Creating target schema from " + schemaPath);
        for (String statement : loadStatements()) {
            String normalized = normalizeForSqlite(statement);
            if (normalized.isBlank()) {
                continue;
            }
            LOG.finest(() -> "Executing schema statement: " + normalized);
            try (Statement sql = target.createStatement()) {
                sql.execute(normalized);
            } catch (SQLException ex) {
                throw new IllegalStateException("Failed to execute schema statement from " + schemaPath + ": " + normalized, ex);
            }
        }
    }

    private List<String> loadStatements() {
        String ddl;
        try {
            ddl = java.nio.file.Files.readString(schemaPath);
        } catch (IOException ex) {
            throw new IllegalStateException("Unable to read target schema " + schemaPath, ex);
        }
        List<String> statements = new ArrayList<>();
        StringBuilder current = new StringBuilder();
        for (String rawLine : ddl.split("\\R")) {
            String line = stripLineComment(rawLine);
            if (line.isBlank()) {
                continue;
            }
            current.append(line).append('\n');
            if (line.trim().endsWith(";")) {
                statements.add(current.toString().trim());
                current.setLength(0);
            }
        }
        if (!current.isEmpty()) {
            statements.add(current.toString().trim());
        }
        return statements;
    }

    private static String stripLineComment(String rawLine) {
        int index = rawLine.indexOf("--");
        return index >= 0 ? rawLine.substring(0, index) : rawLine;
    }

    private static String normalizeForSqlite(String statement) {
        if (!statement.toUpperCase().contains("CREATE TABLE") || !statement.toUpperCase().contains("PRIMARY KEY (")) {
            return statement;
        }
        String[] lines = statement.split("\\R");
        StringBuilder out = new StringBuilder();
        for (String line : lines) {
            if (!line.toUpperCase().contains("PRIMARY KEY (")) {
                out.append(INLINE_PRIMARY_KEY.matcher(line).replaceFirst("")).append('\n');
            } else {
                out.append(line).append('\n');
            }
        }
        return out.toString().trim();
    }
}
