package com.blackbox.runtime.mapping;

/**
 * Executable mapping contract.
 *
 * The first implementation is hand-written. Later Java materialization should
 * generate classes implementing this same interface from the JSON IR.
 */
public interface MappingPlan {
    String planId();

    void execute(MappingContext context) throws Exception;
}
