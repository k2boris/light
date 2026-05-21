package com.blackbox.runtime.mapping;

import java.sql.Connection;
import java.util.Map;

/**
 * Runtime context passed to reverse mapping plans.
 *
 * Reverse plans read one target instance database and write mapped columns into
 * reconstructed source databases. Connection lifecycle stays with the runtime.
 */
public record ReverseMappingContext(Connection target, Map<String, Connection> sources) {
    public Connection source(String name) {
        Connection connection = sources.get(name);
        if (connection == null) {
            throw new IllegalArgumentException("Source connection not available: " + name);
        }
        return connection;
    }
}
