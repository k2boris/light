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
 * Generated mapping: SCREENING_HIT__AML_ORA_DS__aml_screening_match.
 *
 * Target: BI_SCREENING_HIT
 * Source: AML_ORA_DS.aml_screening_match
 * Target key(s): screening_hit_id
 * Source filter: source column run_id is scoped to the current party/runtime context.
 * Forward: read source rows, audit mapped source columns, project canonical row(s), then upsert target table.
 * Reverse: rebuild mapped source rows from BI_MAPPING_AUDIT and compare them with original source rows.
 */
public final class BiScreeningHit_AmlOraDsAmlScreeningMatchPlan implements MappingPlan, ReverseMappingPlan, BianGeneratedMapping {
    private static final Logger LOG = Logger.getLogger(BiScreeningHit_AmlOraDsAmlScreeningMatchPlan.class.getName());
    private static final String PLAN_ID = "SCREENING_HIT__AML_ORA_DS__aml_screening_match";
    private static final String SOURCE_INTERFACE = "AML_ORA_DS";
    private static final String SOURCE_TABLE = "aml_screening_match";
    private static final String TARGET_TABLE = "BI_SCREENING_HIT";
    private static final String FILTER_COLUMN = "run_id";
    private static final boolean BRIDGE_ENABLED = false;
    private static final String BRIDGE_SYSTEM_CODE = null;
    private static final boolean SKIP_FOR_PARTY_SCOPE = false;
    private static final String SOURCE_READ_SQL = """
select * from (
SELECT DISTINCT
    t1.match_id AS match_id,
    t2.run_id AS run_id,
    t1.match_status AS match_status,
    t1.list_id AS list_id,
    t1.matched_name AS matched_name,
    t1.match_score AS match_score,
    t1.created_at AS created_at
FROM aml_screening_match t1
JOIN aml_screening_subject t2 ON t1.subject_id = t2.subject_id
) where run_id = ?
                """;
    private static final String TARGET_DRIVER_SQL = """
select screening_run_id from BI_SCREENING_RUN where source_system_id = 'ORA-AML'
                """;
    private static final String TARGET_UPSERT_SQL = """
insert or replace into BI_SCREENING_HIT (screening_run_id, screening_hit_id, hit_type, provider_code, provider_entity_id, provider_listing_id, matched_name, match_score, hit_status, created_at) values (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """;
    private static final String JOIN_SQL = "SELECT DISTINCT\n    t1.match_id AS match_id,\n    t2.run_id AS run_id,\n    t1.match_status AS match_status,\n    t1.list_id AS list_id,\n    t1.matched_name AS matched_name,\n    t1.match_score AS match_score,\n    t1.created_at AS created_at\nFROM aml_screening_match t1\nJOIN aml_screening_subject t2 ON t1.subject_id = t2.subject_id";
    private static final List<String> TARGET_FIELDS = List.of("screening_run_id", "screening_hit_id", "hit_type", "provider_code", "provider_entity_id", "provider_listing_id", "matched_name", "match_score", "hit_status", "created_at");
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
        List<String> values = new ArrayList<>();
        LOG.finest(() -> "Reading target driver SQL for " + PLAN_ID + ": " + TARGET_DRIVER_SQL.replace("\n", " "));
        try (PreparedStatement statement = context.target().prepareStatement(TARGET_DRIVER_SQL);
                ResultSet rs = statement.executeQuery()) {
            while (rs.next()) {
                String value = rs.getString("screening_run_id");
                if (value != null && !value.isBlank()) {
                    values.add(value);
                }
            }
        }
        if (values.isEmpty()) {
            return List.of();
        }
        List<SourceRow> rows = new ArrayList<>();
        Connection source = context.sources().connection(SOURCE_INTERFACE);
        for (String value : values) {
            rows.addAll(readRows(source, SOURCE_READ_SQL, List.of(value)));
        }
        return rows;
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
                        rs.getString("match_id"),
                        rs.getString("match_status"),
                        rs.getString("list_id"),
                        rs.getString("matched_name"),
                        rs.getString("match_score"),
                        rs.getString("created_at"),
                        rs.getString("run_id")));
                }
            }
        }
        return rows;
    }


    private record SourceRow(String matchId, String matchStatus, String listId, String matchedName, String matchScore, String createdAt, String runId) {
        String value(String column) {
            return switch (column) {
            case "match_id" -> matchId;
            case "match_status" -> matchStatus;
            case "list_id" -> listId;
            case "matched_name" -> matchedName;
            case "match_score" -> matchScore;
            case "created_at" -> createdAt;
            case "run_id" -> runId;
                default -> null;
            };
        }
    }

    // ===== Source To Target Mapping =====

    private static List<Map<String, String>> projectTargetRows(MappingContext context, SourceRow sourceRow) {
        List<Map<String, String>> rows = new ArrayList<>();
        if (notBlank(sourceRow.matchId())) {
            Map<String, String> row = projectOneTargetRow(context, sourceRow);
                row.put("screening_hit_id", sourceRow.matchId());
                row.put("hit_type", sourceRow.matchStatus());
                row.put("provider_code", "ORA-AML");
                row.put("provider_entity_id", sourceRow.listId());
                row.put("provider_listing_id", sourceRow.listId());
                row.put("matched_name", sourceRow.matchedName());
                row.put("match_score", sourceRow.matchScore());
                row.put("hit_status", "OPEN");
                row.put("created_at", sourceRow.createdAt());
            rows.add(row);
        }
        if (providerEntityId(sourceRow.matchedName()) != null && providerListingId(sourceRow.matchedName()) != null) {
            Map<String, String> row = projectOneTargetRow(context, sourceRow);
                row.put("screening_hit_id", sourceRow.matchId() + ":2");
                row.put("hit_type", "WATCHLIST");
                row.put("provider_code", "DOWJONES");
                row.put("provider_entity_id", providerEntityId(sourceRow.matchedName()));
                row.put("provider_listing_id", providerListingId(sourceRow.matchedName()));
                row.put("matched_name", sourceRow.matchedName());
                row.put("match_score", sourceRow.matchScore());
                row.put("hit_status", "OPEN");
                row.put("created_at", sourceRow.createdAt());
            rows.add(row);
        }
        return rows;
    }

    private static Map<String, String> projectOneTargetRow(MappingContext context, SourceRow sourceRow) {
        Map<String, String> row = new LinkedHashMap<>();
        row.put("screening_hit_id", sourceRow.matchId());
        row.put("screening_run_id", sourceRow.runId());
        row.put("hit_type", sourceRow.matchStatus());
        row.put("provider_code", "ORA-AML");
        row.put("provider_entity_id", sourceRow.listId());
        row.put("provider_listing_id", sourceRow.listId());
        row.put("matched_name", sourceRow.matchedName());
        row.put("match_score", sourceRow.matchScore());
        row.put("hit_status", "OPEN");
        row.put("created_at", sourceRow.createdAt());
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
                BRIDGE_SYSTEM_CODE, JOIN_SQL, List.of("match_id", "run_id", "match_status", "list_id", "matched_name", "match_score", "created_at"), bindings(), emitRows());
    }
    private static List<BindingSpec> bindings() { return List.of(
            b("screening_hit_id", "source", "match_id", null, null, null),
            b("screening_run_id", "source", "run_id", null, null, null),
            b("hit_type", "source", "match_status", null, null, null),
            b("provider_code", "const", null, null, "ORA-AML", null),
            b("provider_entity_id", "source", "list_id", null, null, null),
            b("provider_listing_id", "source", "list_id", null, null, null),
            b("matched_name", "source", "matched_name", null, null, null),
            b("match_score", "source", "match_score", null, null, null),
            b("hit_status", "const", null, null, "OPEN", null),
            b("created_at", "source", "created_at", null, null, null)
        ); }
    private static List<EmitRowSpec> emitRows() { return List.of(
            emit("AML_ROW", "match_id",
                    entry("screening_hit_id", e("PATH", "AML_ORA_DS.aml_screening_match.match_id", null, null)),
                    entry("hit_type", e("PATH", "AML_ORA_DS.aml_screening_match.match_status", null, null)),
                    entry("provider_code", e("CONST", null, "ORA-AML", null)),
                    entry("provider_entity_id", e("PATH", "AML_ORA_DS.aml_screening_match.list_id", null, null)),
                    entry("provider_listing_id", e("PATH", "AML_ORA_DS.aml_screening_match.list_id", null, null)),
                    entry("matched_name", e("PATH", "AML_ORA_DS.aml_screening_match.matched_name", null, null)),
                    entry("match_score", e("PATH", "AML_ORA_DS.aml_screening_match.match_score", null, null)),
                    entry("hit_status", e("CONST", null, "OPEN", null)),
                    entry("created_at", e("PATH", "AML_ORA_DS.aml_screening_match.created_at", null, null))),
            emit("DJ_ROW", "matched_name && matched_name.indexOf(':')>=0 && matched_name.lastIndexOf(':')>matched_name.indexOf('|')",
                    entry("screening_hit_id", e("EXPR", null, null, "match_id + ':2'")),
                    entry("hit_type", e("CONST", null, "WATCHLIST", null)),
                    entry("provider_code", e("CONST", null, "DOWJONES", null)),
                    entry("provider_entity_id", e("EXPR", null, null, "(matched_name && matched_name.indexOf(':')>=0 && matched_name.indexOf('|')>matched_name.indexOf(':')) ? matched_name.substring(matched_name.indexOf(':')+1, matched_name.indexOf('|')) : null")),
                    entry("provider_listing_id", e("EXPR", null, null, "(matched_name && matched_name.lastIndexOf(':')>matched_name.indexOf('|')) ? matched_name.substring(matched_name.lastIndexOf(':')+1) : null")),
                    entry("matched_name", e("PATH", "AML_ORA_DS.aml_screening_match.matched_name", null, null)),
                    entry("match_score", e("PATH", "AML_ORA_DS.aml_screening_match.match_score", null, null)),
                    entry("hit_status", e("CONST", null, "OPEN", null)),
                    entry("created_at", e("PATH", "AML_ORA_DS.aml_screening_match.created_at", null, null)))
        ); }
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
