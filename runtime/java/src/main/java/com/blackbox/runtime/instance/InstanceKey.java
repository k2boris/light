package com.blackbox.runtime.instance;

import java.util.Collections;
import java.util.LinkedHashMap;
import java.util.Map;

/**
 * Identifies one logical target instance.
 *
 * The id is the stable root id used for naming the target database. Attributes
 * carry peer-source identifiers resolved during enumeration, so generated
 * mappings do not need to query one source system only to find another source
 * system's key.
 */
public record InstanceKey(String type, String id, Map<String, String> attributes) {
    public InstanceKey {
        if (type == null || type.isBlank()) {
            throw new IllegalArgumentException("Instance type is required");
        }
        if (id == null || id.isBlank()) {
            throw new IllegalArgumentException("Instance id is required");
        }
        Map<String, String> copied = new LinkedHashMap<>();
        if (attributes != null) {
            copied.putAll(attributes);
        }
        copied.putIfAbsent("id", id);
        attributes = Collections.unmodifiableMap(copied);
    }

    public InstanceKey(String type, String id) {
        this(type, id, Map.of());
    }

    public String attribute(String name) {
        return attributes.get(name);
    }

    public String safeFileStem() {
        return (type + "_" + id).replaceAll("[^A-Za-z0-9._-]", "_");
    }
}
