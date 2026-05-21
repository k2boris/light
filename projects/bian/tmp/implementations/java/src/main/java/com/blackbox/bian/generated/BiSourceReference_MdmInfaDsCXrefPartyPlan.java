package com.blackbox.bian.generated;

import com.blackbox.bian.mapping.BianGeneratedMapping;
import com.blackbox.bian.mapping.BianGeneratedPlan.BindingSpec;
import com.blackbox.bian.mapping.BianGeneratedPlan.EmitRowSpec;
import com.blackbox.bian.mapping.BianGeneratedPlan.ExprSpec;
import com.blackbox.bian.mapping.BianGeneratedPlan.PlanSpec;
import com.blackbox.runtime.mapping.MappingContext;
import com.blackbox.runtime.mapping.MappingPlan;
import com.blackbox.runtime.mapping.ReverseMappingContext;
import com.blackbox.runtime.mapping.ReverseMappingPlan;
import java.sql.Connection;
import java.sql.Statement;
import java.sql.DatabaseMetaData;
import java.sql.PreparedStatement;
import java.sql.ResultSet;
import java.sql.Types;
import java.util.ArrayList;
import java.util.LinkedHashMap;
import java.util.Set;
import java.util.Locale;
import java.util.LinkedHashSet;
import java.util.List;
import java.util.Map;
import java.util.logging.Logger;

/**
 * Generated mapping: SOURCE_REFERENCE__MDM_INFA_DS__C_XREF_PARTY.
 *
 * Target: BI_SOURCE_REFERENCE
 * Source: MDM_INFA_DS.C_XREF_PARTY
 * Target key(s): source_reference_id
 * Source filter: source column ROWID_OBJECT is scoped to the current party/runtime context.
 * Forward: read source rows, audit mapped source columns, project canonical row(s), then upsert target table.
 * Reverse: rebuild mapped source rows from BI_MAPPING_AUDIT and compare them with original source rows.
 */
public final class BiSourceReference_MdmInfaDsCXrefPartyPlan implements MappingPlan, ReverseMappingPlan, BianGeneratedMapping {
    private static final Logger LOG = Logger.getLogger(BiSourceReference_MdmInfaDsCXrefPartyPlan.class.getName());
    private static final String PLAN_ID = "SOURCE_REFERENCE__MDM_INFA_DS__C_XREF_PARTY";
    private static final String SOURCE_INTERFACE = "MDM_INFA_DS";
    private static final String SOURCE_TABLE = "C_XREF_PARTY";
    private static final String TARGET_TABLE = "BI_SOURCE_REFERENCE";
    private static final String FILTER_COLUMN = "ROWID_OBJECT";
    private static final boolean BRIDGE_ENABLED = false;
    private static final String BRIDGE_SYSTEM_CODE = null;
    private static final boolean SKIP_FOR_PARTY_SCOPE = false;
    private static final String SOURCE_READ_SQL = """
select * from (
select * from main.C_XREF_PARTY
) where ROWID_OBJECT = ?
                """;
    private static final String TARGET_UPSERT_SQL = """
insert or replace into BI_SOURCE_REFERENCE (source_reference_id, party_id, source_system_id, source_entity, source_key, is_primary_in_source, effective_from, created_at) values (?, ?, ?, ?, ?, ?, ?, ?)
                """;
    private static final String JOIN_SQL = null;
    private static final List<String> TARGET_FIELDS = List.of("source_reference_id", "party_id", "source_system_id", "source_entity", "source_key", "is_primary_in_source", "effective_from", "created_at");
    private static final PlanSpec SPEC = spec();
    @Override public String planId() { return PLAN_ID; }
    @Override public PlanSpec planSpec() { return SPEC; }

    @Override
    public void execute(MappingContext context) throws Exception {
        // Step 1: Identify the current target instance and the source-to-target flow.
        String instanceId = context.instanceKey().id();
        if (SKIP_FOR_PARTY_SCOPE) {
            LOG.fine(() -> "Skipping plan=" + PLAN_ID + " instance=" + instanceId);
            return;
        }
        LOG.info(() -> "Forward mapping start plan=" + PLAN_ID + " instance=" + instanceId
                + " source=" + SOURCE_INTERFACE + "." + SOURCE_TABLE + " target=" + TARGET_TABLE
                + " sourceSql=" + SOURCE_READ_SQL.replace("\n", " "));

        // Step 2: Make sure this target database can capture the source values needed for reverse mapping.
        ensureAuditTable(context.target());

        // Step 3: Read the party-scoped source records using the SQL shown in this file.
        List<SourceRow> sourceRows = readSourceRows(context);

        int sourceOrdinal = 0;
        int targetRows = 0;
        for (SourceRow sourceRow : sourceRows) {
            // Step 4: Audit the mapped source columns before transforming them.
            auditSourceRow(context.target(), sourceOrdinal, sourceRow);
            sourceOrdinal++;

            // Step 5: Map the source row into one or more target rows.
            for (Map<String, String> targetRow : projectTargetRows(context, sourceRow)) {
                // Step 6: Write the mapped target row to the entity-level target database.
                writeTargetRow(context.target(), targetRow);
                targetRows++;
            }
        }

        // Step 7: Log the source and target row counts for this flow.
        int finalTargetRows = targetRows;
        LOG.info(() -> "Forward mapping finish plan=" + PLAN_ID + " instance=" + instanceId
                + " sourceRows=" + sourceRows.size() + " targetRows=" + finalTargetRows);
    }



    // ===== Source Read Flow =====

    private static List<SourceRow> readSourceRows(MappingContext context) throws Exception {
        if (FILTER_COLUMN == null || FILTER_COLUMN.isBlank()) {
            return readRows(context.sources().connection(SOURCE_INTERFACE), SOURCE_READ_SQL, List.of());
        }
        String filterValue = resolveFilterValue(context);
        if (filterValue == null || filterValue.isBlank()) {
            LOG.finer(() -> "No source key for plan=" + PLAN_ID + " filterColumn=" + FILTER_COLUMN);
            return List.of();
        }
        return readRows(context.sources().connection(SOURCE_INTERFACE), SOURCE_READ_SQL, List.of(filterValue));
    }

    private static List<SourceRow> readRows(Connection connection, String sql, List<String> args) throws Exception {
        LOG.finest(() -> "Reading source SQL for " + PLAN_ID + ": " + sql.replace("\n", " ") + " args=" + args);
        List<SourceRow> rows = new ArrayList<>();
        try (PreparedStatement statement = connection.prepareStatement(sql)) {
            for (int i = 0; i < args.size(); i++) {
                statement.setString(i + 1, args.get(i));
            }
            try (ResultSet rs = statement.executeQuery()) {
                while (rs.next()) {
                    rows.add(new SourceRow(
                        rs.getString("ROWID_XREF"),
                        rs.getString("ROWID_OBJECT"),
                        rs.getString("SYSTEM_CODE"),
                        rs.getString("SOURCE_ENTITY"),
                        rs.getString("SOURCE_KEY"),
                        rs.getString("BEST_REC_IND"),
                        rs.getString("CREATED_DT")));
                }
            }
        }
        return rows;
    }

    private static String resolveFilterValue(MappingContext context) throws Exception {
        String partyId = context.instanceValue("party_id");
        if ("MDM_INFA_DS".equals(SOURCE_INTERFACE) && "C_BO_PARTY".equals(SOURCE_TABLE)) {
            return partyId;
        }
        if ("MDM_INFA_DS".equals(SOURCE_INTERFACE) && "C_XREF_PARTY".equals(SOURCE_TABLE)) {
            return partyId;
        }
        if (BRIDGE_ENABLED && BRIDGE_SYSTEM_CODE != null && !BRIDGE_SYSTEM_CODE.isBlank()) {
            return xref(context.sources().connection("MDM_INFA_DS"), partyId, BRIDGE_SYSTEM_CODE);
        }
        if ("CRM_SF_DS".equals(SOURCE_INTERFACE)) {
            return xref(context.sources().connection("MDM_INFA_DS"), partyId, "SFDC");
        }
        if ("AML_ORA_DS".equals(SOURCE_INTERFACE)) {
            return xref(context.sources().connection("MDM_INFA_DS"), partyId, "ORACLE_AML");
        }
        if ("CORE_TMNS_DS".equals(SOURCE_INTERFACE)) {
            return xref(context.sources().connection("MDM_INFA_DS"), partyId, "TEMENOS");
        }
        return context.instanceValue(FILTER_COLUMN);
    }

    private static String xref(Connection mdm, String partyId, String systemCode) throws Exception {
        String sql = """
                select SOURCE_KEY
                from C_XREF_PARTY
                where ROWID_OBJECT = ? and SYSTEM_CODE = ?
                order by BEST_REC_IND desc, ROWID_XREF
                limit 1
                """;
        LOG.finest(() -> "Resolving source key for " + PLAN_ID + ": " + sql.replace("\n", " ")
                + " args=[" + partyId + ", " + systemCode + "]");
        try (PreparedStatement statement = mdm.prepareStatement(sql)) {
            statement.setString(1, partyId);
            statement.setString(2, systemCode);
            try (ResultSet rs = statement.executeQuery()) {
                return rs.next() ? rs.getString("SOURCE_KEY") : null;
            }
        }
    }


    private record SourceRow(String rowidXref, String rowidObject, String systemCode, String sourceEntity, String sourceKey, String bestRecInd, String createdDt) {
        String value(String column) {
            return switch (column) {
            case "ROWID_XREF" -> rowidXref;
            case "ROWID_OBJECT" -> rowidObject;
            case "SYSTEM_CODE" -> systemCode;
            case "SOURCE_ENTITY" -> sourceEntity;
            case "SOURCE_KEY" -> sourceKey;
            case "BEST_REC_IND" -> bestRecInd;
            case "CREATED_DT" -> createdDt;
                default -> null;
            };
        }
    }

    // ===== Source To Target Mapping =====

    private static List<Map<String, String>> projectTargetRows(MappingContext context, SourceRow sourceRow) {
        return List.of(projectOneTargetRow(context, sourceRow));
    }

    private static Map<String, String> projectOneTargetRow(MappingContext context, SourceRow sourceRow) {
        Map<String, String> row = new LinkedHashMap<>();
        row.put("source_reference_id", sourceRow.rowidXref());
        row.put("party_id", sourceRow.rowidObject());
        row.put("source_system_id", sourceRow.systemCode());
        row.put("source_entity", sourceRow.sourceEntity());
        row.put("source_key", sourceRow.sourceKey());
        row.put("is_primary_in_source", sourceRow.bestRecInd());
        row.put("effective_from", sourceRow.createdDt());
        row.put("created_at", sourceRow.createdDt());
        return row;
    }

    // ===== Target Write Flow =====

    private static void writeTargetRow(Connection target, Map<String, String> row) throws Exception {
        try (PreparedStatement statement = target.prepareStatement(TARGET_UPSERT_SQL)) {
            int index = 1;
            for (String field : TARGET_FIELDS) {
                String value = row.get(field);
                if (value == null) { statement.setNull(index, Types.VARCHAR); } else { statement.setString(index, value); }
                index++;
            }
            statement.executeUpdate();
        }
    }


    // ===== Local Audit And Reverse Flow =====

    private static void ensureAuditTable(Connection target) throws Exception {
        String sql = """
                create table if not exists BI_MAPPING_AUDIT (
                  plan_id text not null,
                  source_interface text not null,
                  source_table text not null,
                  row_ordinal integer not null,
                  source_column text not null,
                  source_value text,
                  primary key (plan_id, row_ordinal, source_column)
                )
                """;
        try (Statement statement = target.createStatement()) {
            statement.execute(sql);
        }
    }

    private static void auditSourceRow(Connection target, int sourceOrdinal, SourceRow sourceRow) throws Exception {
        List<BindingSpec> sourceBindings = SPEC.sourceBindings();
        if (sourceBindings.isEmpty()) {
            return;
        }
        String sql = """
                insert or replace into BI_MAPPING_AUDIT
                  (plan_id, source_interface, source_table, row_ordinal, source_column, source_value)
                values (?, ?, ?, ?, ?, ?)
                """;
        try (PreparedStatement statement = target.prepareStatement(sql)) {
            for (BindingSpec binding : sourceBindings) {
                statement.setString(1, PLAN_ID);
                statement.setString(2, SOURCE_INTERFACE);
                statement.setString(3, SOURCE_TABLE);
                statement.setInt(4, sourceOrdinal);
                statement.setString(5, binding.sourceColumn());
                statement.setString(6, sourceRow.value(binding.sourceColumn()));
                statement.executeUpdate();
            }
        }
    }

    private static void ensureReverseTable(Connection connection) throws Exception {
        try (Statement statement = connection.createStatement()) {
            statement.execute("create table if not exists " + SOURCE_TABLE + " (__plan_id text)");
        }
        Set<String> existing = new LinkedHashSet<>();
        DatabaseMetaData metaData = connection.getMetaData();
        try (ResultSet rs = metaData.getColumns(null, null, SOURCE_TABLE, null)) {
            while (rs.next()) {
                existing.add(rs.getString("COLUMN_NAME").toLowerCase(Locale.ROOT));
            }
        }
        for (BindingSpec binding : SPEC.sourceBindings()) {
            if (!existing.contains(binding.sourceColumn().toLowerCase(Locale.ROOT))) {
                try (Statement statement = connection.createStatement()) {
                    statement.execute("alter table " + SOURCE_TABLE + " add column " + binding.sourceColumn() + " text");
                }
                existing.add(binding.sourceColumn().toLowerCase(Locale.ROOT));
            }
        }
    }

    private static boolean reverseFromAudit(Connection target, Connection generatedSource) throws Exception {
        try (ResultSet rs = target.getMetaData().getTables(null, null, "BI_MAPPING_AUDIT", null)) {
            if (!rs.next()) {
                return false;
            }
        }
        String countSql = "select count(*) from BI_MAPPING_AUDIT where plan_id = ?";
        try (PreparedStatement count = target.prepareStatement(countSql)) {
            count.setString(1, PLAN_ID);
            try (ResultSet rs = count.executeQuery()) {
                if (!rs.next() || rs.getInt(1) == 0) {
                    return true;
                }
            }
        }
        String auditSql = """
                select row_ordinal, source_column, source_value
                from BI_MAPPING_AUDIT
                where plan_id = ?
                order by row_ordinal, source_column
                """;
        Map<Integer, Map<String, String>> rows = new LinkedHashMap<>();
        try (PreparedStatement statement = target.prepareStatement(auditSql)) {
            statement.setString(1, PLAN_ID);
            try (ResultSet rs = statement.executeQuery()) {
                while (rs.next()) {
                    rows.computeIfAbsent(rs.getInt("row_ordinal"), ignored -> new LinkedHashMap<>())
                            .put(rs.getString("source_column"), rs.getString("source_value"));
                }
            }
        }
        for (Map<String, String> row : rows.values()) {
            List<String> columns = new ArrayList<>();
            columns.add("__plan_id");
            columns.addAll(row.keySet());
            String placeholders = String.join(", ", columns.stream().map(column -> "?").toList());
            String insertSql = "insert into " + SOURCE_TABLE + " (" + String.join(", ", columns) + ") values (" + placeholders + ")";
            try (PreparedStatement statement = generatedSource.prepareStatement(insertSql)) {
                statement.setString(1, PLAN_ID);
                int index = 2;
                for (String value : row.values()) {
                    statement.setString(index++, value);
                }
                statement.executeUpdate();
            }
        }
        return true;
    }

    @Override
    public void reverse(ReverseMappingContext context) throws Exception {
        if (SKIP_FOR_PARTY_SCOPE || SPEC.sourceBindings().isEmpty()) { return; }
        Connection generatedSource = context.source(SOURCE_INTERFACE);
        ensureReverseTable(generatedSource);
        reverseFromAudit(context.target(), generatedSource);
    }

    // ===== Reverse Checker Metadata =====

    private static PlanSpec spec() {
        return new PlanSpec(PLAN_ID, SOURCE_INTERFACE, SOURCE_TABLE, TARGET_TABLE, FILTER_COLUMN, BRIDGE_ENABLED,
                BRIDGE_SYSTEM_CODE, JOIN_SQL, List.of("ROWID_XREF", "ROWID_OBJECT", "SYSTEM_CODE", "SOURCE_ENTITY", "SOURCE_KEY", "BEST_REC_IND", "CREATED_DT"), bindings(), emitRows());
    }
    private static List<BindingSpec> bindings() { return List.of(
            b("source_reference_id", "source", "ROWID_XREF", null, null, null),
            b("party_id", "source", "ROWID_OBJECT", null, null, null),
            b("source_system_id", "source", "SYSTEM_CODE", null, null, null),
            b("source_entity", "source", "SOURCE_ENTITY", null, null, null),
            b("source_key", "source", "SOURCE_KEY", null, null, null),
            b("is_primary_in_source", "source", "BEST_REC_IND", null, null, null),
            b("effective_from", "source", "CREATED_DT", null, null, null),
            b("created_at", "source", "CREATED_DT", null, null, null)
        ); }
    private static List<EmitRowSpec> emitRows() { return List.of(); }
    private static BindingSpec b(String targetField, String semantic, String sourceColumn, String contextColumn, String constValue, String expr) { return new BindingSpec(targetField, semantic, sourceColumn, contextColumn, constValue, expr); }
    private static EmitRowSpec emit(String rowId, String emitWhen, Map.Entry<String, ExprSpec>... entries) { Map<String, ExprSpec> fields = new LinkedHashMap<>(); for (Map.Entry<String, ExprSpec> entry : entries) { fields.put(entry.getKey(), entry.getValue()); } return new EmitRowSpec(rowId, emitWhen, fields); }
    private static Map.Entry<String, ExprSpec> entry(String field, ExprSpec expr) { return Map.entry(field, expr); }
    private static ExprSpec e(String op, String path, String value, String expr) { return new ExprSpec(op, path, value, expr); }
    private static boolean notBlank(String value) { return value != null && !value.isBlank(); }
    private static String providerEntityId(String matchedName) { if (matchedName == null) return null; int colon = matchedName.indexOf(':'); int pipe = matchedName.indexOf('|'); return colon >= 0 && pipe > colon ? matchedName.substring(colon + 1, pipe) : null; }
    private static String providerListingId(String matchedName) { if (matchedName == null) return null; int pipe = matchedName.indexOf('|'); int colon = matchedName.lastIndexOf(':'); return pipe >= 0 && colon > pipe ? matchedName.substring(colon + 1) : null; }
    private static String sourceName(String systemCode) { return switch (String.valueOf(systemCode)) { case "SFDC" -> "Salesforce CRM"; case "TEMENOS" -> "Temenos Core"; case "ORACLE_AML", "ORA-AML" -> "Oracle AML"; case "MDM" -> "Informatica MDM"; case "DJ", "DOWJONES" -> "Dow Jones Feed"; default -> systemCode; }; }
    private static String sourceType(String systemCode) { return switch (String.valueOf(systemCode)) { case "SFDC" -> "CRM"; case "TEMENOS" -> "CORE"; case "ORACLE_AML", "ORA-AML" -> "AML"; case "MDM" -> "MDM"; case "DJ", "DOWJONES" -> "WATCHLIST"; default -> "OTHER"; }; }
}
