package com.blackbox.runtime.mapping;

import com.blackbox.runtime.instance.InstanceKey;
import com.blackbox.runtime.jdbc.SourceRegistry;
import java.sql.Connection;

/**
 * Runtime context passed to a mapping plan.
 *
 * Core runtime components supply connections and the current instance key.
 * Generated or hand-written mapping plans use this context to read source rows
 * and write target rows without owning connection lifecycle.
 */
public record MappingContext(InstanceKey instanceKey, SourceRegistry sources, Connection target) {
    public String instanceValue(String name) {
        return instanceKey.attribute(name);
    }
}
