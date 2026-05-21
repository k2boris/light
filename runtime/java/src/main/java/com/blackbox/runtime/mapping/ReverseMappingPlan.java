package com.blackbox.runtime.mapping;

/**
 * Reverse executable mapping contract.
 *
 * Reverse mappings reconstruct mapped source columns from one target instance
 * database into fresh source databases used by round-trip tests.
 */
public interface ReverseMappingPlan {
    String planId();

    void reverse(ReverseMappingContext context) throws Exception;
}
