package com.blackbox.bian.mapping;

import java.util.List;
import java.util.Map;

/**
 * Metadata records shared by generated BIAN mappings and the reverse
 * consistency checker.
 *
 * Generated mapping classes own their executable SQL, source reads,
 * transformations, target writes, audit writes, and reverse reconstruction.
 * This class intentionally contains no executable mapping helper logic.
 */
public final class BianGeneratedPlan {
    private BianGeneratedPlan() {
    }

    public record PlanSpec(
            String planId,
            String sourceInterface,
            String sourceTable,
            String targetTable,
            String filterColumn,
            boolean bridgeEnabled,
            String bridgeSystemCode,
            String joinSql,
            List<String> sourceColumns,
            List<BindingSpec> bindings,
            List<EmitRowSpec> emitRows) {
        public List<BindingSpec> sourceBindings() {
            return bindings.stream()
                    .filter(binding -> "source".equals(binding.semantic()))
                    .toList();
        }
    }

    public record BindingSpec(
            String targetField,
            String semantic,
            String sourceColumn,
            String contextColumn,
            String constValue,
            String expr) {
    }

    public record EmitRowSpec(String rowId, String emitWhen, Map<String, ExprSpec> fields) {
    }

    public record ExprSpec(String op, String path, String value, String expr) {
    }
}
