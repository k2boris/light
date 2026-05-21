package com.blackbox.runtime.instance;

import com.blackbox.runtime.jdbc.SourceRegistry;
import java.util.List;

/**
 * Finds the root instances to materialize.
 */
public interface InstanceEnumerator {
    List<InstanceKey> enumerate(SourceRegistry sources) throws Exception;
}
