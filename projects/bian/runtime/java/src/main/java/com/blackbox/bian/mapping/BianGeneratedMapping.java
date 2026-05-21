package com.blackbox.bian.mapping;

import com.blackbox.bian.mapping.BianGeneratedPlan.PlanSpec;

/**
 * Metadata contract implemented by generated BIAN mapping classes.
 *
 * The reverse consistency checker uses this to compare original and generated
 * mapped source rows without depending on a specific generated class hierarchy.
 */
public interface BianGeneratedMapping {
    PlanSpec planSpec();
}
