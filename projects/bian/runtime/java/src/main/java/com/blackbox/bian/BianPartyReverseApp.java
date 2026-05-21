package com.blackbox.bian;

import com.blackbox.bian.generated.BianGeneratedMappings;
import com.blackbox.bian.mapping.BianGeneratedPlan.BindingSpec;
import com.blackbox.bian.mapping.BianGeneratedPlan.PlanSpec;
import com.blackbox.bian.mapping.BianGeneratedMapping;
import com.blackbox.runtime.config.RuntimeConfig;
import com.blackbox.runtime.config.RuntimeLogging;
import com.blackbox.runtime.mapping.ReverseMappingContext;
import com.blackbox.runtime.mapping.ReverseMappingPlan;
import java.io.IOException;
import java.nio.file.Files;
import java.nio.file.Path;
import java.sql.Connection;
import java.sql.DriverManager;
import java.sql.PreparedStatement;
import java.sql.ResultSet;
import java.sql.Statement;
import java.util.ArrayList;
import java.util.Collections;
import java.util.Comparator;
import java.util.HashMap;
import java.util.LinkedHashSet;
import java.util.LinkedHashMap;
import java.util.List;
import java.util.Map;
import java.util.Set;
import java.util.logging.Logger;

/**
 * BIAN reverse round-trip runtime for mapped-column equivalence.
 *
 * It reads generated per-party target databases and reconstructs one relaxed
 * SQLite database per source system. The reverse tables contain mapped source
 * columns only, which keeps the test focused on the current mapping contract.
 */
public final class BianPartyReverseApp {
    private static final Logger LOG = Logger.getLogger(BianPartyReverseApp.class.getName());

    private BianPartyReverseApp() {
    }

    public static void main(String[] args) throws Exception {
        Path configPath = args.length == 0 ? Path.of("config/bian-runtime.properties") : Path.of(args[0]);
        RuntimeConfig config = RuntimeConfig.load(configPath);
        RuntimeLogging.configure(config.loggingLevel());

        Path targetDataDir = config.pathValue("target.outputDir");
        Path reverseDir = config.pathValue("reverse.outputDir");
        Files.createDirectories(reverseDir);
        Map<String, Connection> reverseSources = openReverseSources(reverseDir);
        List<ReverseMappingPlan> plans = BianGeneratedMappings.reversePlans();

        try {
            for (Path targetDb : listTargetDbs(targetDataDir)) {
                LOG.info(() -> "Reverse materializing targetDb=" + targetDb);
                try (Connection target = openSqlite(targetDb)) {
                    ReverseMappingContext context = new ReverseMappingContext(target, reverseSources);
                    for (ReverseMappingPlan plan : plans) {
                        plan.reverse(context);
                    }
                }
            }
            for (Connection connection : reverseSources.values()) {
                connection.commit();
            }
        } finally {
            for (Connection connection : reverseSources.values()) {
                connection.close();
            }
        }

        Comparison comparison = compareMappedColumns(config, reverseDir);
        writeReport(config.pathValue("reverse.report"), reverseDir, listTargetDbs(targetDataDir).size(), comparison);
        if (!comparison.passed()) {
            throw new IllegalStateException("BIAN mapped-column consistency check failed mismatches="
                    + comparison.mismatches.size());
        }
        LOG.info(() -> "BIAN reverse runtime complete reverseDir=" + reverseDir);
    }

    private static Map<String, Connection> openReverseSources(Path reverseDir) throws Exception {
        Map<String, Connection> sources = new LinkedHashMap<>();
        for (String source : List.of("MDM_INFA_DS", "CRM_SF_DS", "AML_ORA_DS", "CORE_TMNS_DS", "DOWJONES_DS")) {
            Path path = reverseDir.resolve(source + ".db");
            deleteIfExists(path);
            Connection connection = openSqlite(path);
            connection.setAutoCommit(false);
            sources.put(source, connection);
        }
        return sources;
    }

    private static List<Path> listTargetDbs(Path targetDataDir) throws IOException {
        if (!Files.exists(targetDataDir)) {
            return List.of();
        }
        try (var stream = Files.list(targetDataDir)) {
            return stream
                    .filter(path -> path.getFileName().toString().endsWith(".db"))
                    .sorted(Comparator.comparing(path -> path.getFileName().toString()))
                    .toList();
        }
    }

    private static Connection openSqlite(Path path) throws Exception {
        Connection connection = DriverManager.getConnection("jdbc:sqlite:" + path);
        try (Statement statement = connection.createStatement()) {
            statement.execute("PRAGMA foreign_keys = OFF");
        }
        return connection;
    }

    private static void deleteIfExists(Path path) throws IOException {
        if (Files.exists(path)) {
            Files.delete(path);
        }
    }

    private static Comparison compareMappedColumns(RuntimeConfig config, Path reverseDir) throws Exception {
        Comparison comparison = new Comparison();
        Map<String, Connection> original = openOriginalSources(config);
        Map<String, Connection> generated = openGeneratedSources(reverseDir);
        try {
            Set<String> partyIds = columnSet(original.get("MDM_INFA_DS"), "select ROWID_OBJECT from C_BO_PARTY");
            Map<String, Set<String>> xrefs = Map.of(
                    "SFDC", columnSet(original.get("MDM_INFA_DS"), "select SOURCE_KEY from C_XREF_PARTY where SYSTEM_CODE = 'SFDC'"),
                    "TEMENOS", columnSet(original.get("MDM_INFA_DS"), "select SOURCE_KEY from C_XREF_PARTY where SYSTEM_CODE = 'TEMENOS'"),
                    "ORACLE_AML", columnSet(original.get("MDM_INFA_DS"), "select SOURCE_KEY from C_XREF_PARTY where SYSTEM_CODE = 'ORACLE_AML'"));
            for (ReverseMappingPlan rawPlan : BianGeneratedMappings.reversePlans()) {
                if (!(rawPlan instanceof BianGeneratedMapping plan)) {
                    continue;
                }
                comparePlan(plan.planSpec(), original, generated, partyIds, xrefs, comparison);
            }
        } finally {
            for (Connection connection : original.values()) {
                connection.close();
            }
            for (Connection connection : generated.values()) {
                connection.close();
            }
        }
        return comparison;
    }

    private static void comparePlan(
            PlanSpec spec,
            Map<String, Connection> original,
            Map<String, Connection> generated,
            Set<String> partyIds,
            Map<String, Set<String>> xrefs,
            Comparison comparison) throws Exception {
        List<BindingSpec> sourceBindings = spec.sourceBindings();
        if (sourceBindings.isEmpty()
                || skipForCurrentScope(spec)
                || "SOURCE_SYSTEM__MDM_INFA_DS__C_XREF_PARTY".equals(spec.planId())) {
            return;
        }
        Map<String, Integer> expected = rowMultiset(
                readOriginalRows(spec, original, partyIds, xrefs),
                sourceBindings);
        Map<String, Integer> actual = rowMultiset(
                readGeneratedRows(spec, generated.get(spec.sourceInterface()), sourceBindings),
                sourceBindings);
        comparison.planCompared(spec.planId(), expected.values().stream().mapToInt(Integer::intValue).sum());
        if (!expected.equals(actual)) {
            comparison.mismatch(spec.planId(), spec.sourceInterface() + "." + spec.sourceTable(),
                    expected.values().stream().mapToInt(Integer::intValue).sum(),
                    actual.values().stream().mapToInt(Integer::intValue).sum(),
                    sampleDifference(expected, actual));
        }
    }

    private static List<Map<String, String>> readOriginalRows(
            PlanSpec spec,
            Map<String, Connection> original,
            Set<String> partyIds,
            Map<String, Set<String>> xrefs) throws Exception {
        Connection connection = original.get(spec.sourceInterface());
        List<String> selectColumns = sourceColumnsForExpectedRead(spec);
        String sql = baseSql(spec, selectColumns);
        List<Map<String, String>> rows = readRows(connection, sql, selectColumns);
        Set<String> allowed = allowedValues(spec, partyIds, xrefs);
        if (allowed == null || spec.filterColumn() == null || spec.filterColumn().isBlank()) {
            return applyPlanSpecificExpectedFilters(spec, rows);
        }
        List<Map<String, String>> scopedRows = rows.stream()
                .filter(row -> allowed.contains(row.get(spec.filterColumn())))
                .toList();
        return applyPlanSpecificExpectedFilters(spec, scopedRows);
    }

    private static List<Map<String, String>> applyPlanSpecificExpectedFilters(
            PlanSpec spec,
            List<Map<String, String>> rows) {
        if ("KYC_ASSESSMENT__CRM_SF_DS__sf_kyc_check".equals(spec.planId())) {
            return rows.stream()
                    .filter(row -> "CIP_IDV".equals(row.get("check_type")))
                    .toList();
        }
        if ("CONTACT_POINT__CRM_SF_DS__sf_contact_point".equals(spec.planId())) {
            return rows.stream()
                    .filter(row -> "EMAIL".equals(row.get("contact_type"))
                            && "1".equals(row.get("is_primary")))
                    .toList();
        }
        if ("KYC_REQUIREMENT_ITEM__CRM_SF_DS__sf_consent".equals(spec.planId())) {
            return rows.stream()
                    .filter(row -> "PRIVACY_NOTICE".equals(row.get("consent_type")))
                    .toList();
        }
        if ("EVIDENCE_DOCUMENT__CRM_SF_DS__sf_consent".equals(spec.planId())) {
            return rows.stream()
                    .filter(row -> "PRIVACY_NOTICE".equals(row.get("consent_type")))
                    .toList();
        }
        return rows;
    }

    private static List<Map<String, String>> readGeneratedRows(
            PlanSpec spec,
            Connection connection,
            List<BindingSpec> sourceBindings) throws Exception {
        if (connection == null || !tableExists(connection, spec.sourceTable())) {
            return List.of();
        }
        String sql = "select " + sourceColumnList(sourceBindings)
                + " from " + spec.sourceTable()
                + " where __plan_id = ?";
        List<Map<String, String>> rows = new ArrayList<>();
        try (PreparedStatement statement = connection.prepareStatement(sql)) {
            statement.setString(1, spec.planId());
            try (ResultSet rs = statement.executeQuery()) {
                while (rs.next()) {
                    Map<String, String> row = new LinkedHashMap<>();
                    for (BindingSpec binding : sourceBindings) {
                        row.put(binding.sourceColumn(), rs.getString(binding.sourceColumn()));
                    }
                    rows.add(row);
                }
            }
        }
        return rows;
    }

    private static String baseSql(PlanSpec spec, List<String> selectColumns) {
        if (spec.joinSql() != null && !spec.joinSql().isBlank()) {
            return "select " + String.join(", ", selectColumns) + " from (" + spec.joinSql() + ")";
        }
        return "select " + String.join(", ", selectColumns) + " from " + spec.sourceTable();
    }

    private static Set<String> allowedValues(PlanSpec spec, Set<String> partyIds, Map<String, Set<String>> xrefs) {
        if ("MDM_INFA_DS".equals(spec.sourceInterface())) {
            return partyIds;
        }
        if (spec.bridgeEnabled() && spec.bridgeSystemCode() != null) {
            return xrefs.get(spec.bridgeSystemCode());
        }
        if ("CRM_SF_DS".equals(spec.sourceInterface()) && "party_id".equals(spec.filterColumn())) {
            return xrefs.get("SFDC");
        }
        if ("AML_ORA_DS".equals(spec.sourceInterface()) && "party_id".equals(spec.filterColumn())) {
            return xrefs.get("ORACLE_AML");
        }
        if ("CORE_TMNS_DS".equals(spec.sourceInterface()) && "customer_id".equals(spec.filterColumn())) {
            return xrefs.get("TEMENOS");
        }
        return null;
    }

    private static List<Map<String, String>> readRows(
            Connection connection,
            String sql,
            List<String> columns) throws Exception {
        List<Map<String, String>> rows = new ArrayList<>();
        try (PreparedStatement statement = connection.prepareStatement(sql);
                ResultSet rs = statement.executeQuery()) {
            while (rs.next()) {
                Map<String, String> row = new LinkedHashMap<>();
                for (String column : columns) {
                    row.put(column, rs.getString(column));
                }
                rows.add(row);
            }
        }
        return rows;
    }

    private static Map<String, Integer> rowMultiset(List<Map<String, String>> rows, List<BindingSpec> bindings) {
        Map<String, Integer> counts = new HashMap<>();
        for (Map<String, String> row : rows) {
            counts.merge(rowKey(row, bindings), 1, Integer::sum);
        }
        return counts;
    }

    private static String rowKey(Map<String, String> row, List<BindingSpec> bindings) {
        List<String> parts = new ArrayList<>();
        Set<String> seen = new LinkedHashSet<>();
        for (BindingSpec binding : bindings) {
            if (!seen.add(binding.sourceColumn())) {
                continue;
            }
            parts.add(binding.sourceColumn() + "=" + String.valueOf(row.get(binding.sourceColumn())));
        }
        return String.join("|", parts);
    }

    private static String sampleDifference(Map<String, Integer> expected, Map<String, Integer> actual) {
        List<String> samples = new ArrayList<>();
        for (String key : expected.keySet()) {
            if (!expected.get(key).equals(actual.getOrDefault(key, 0))) {
                samples.add("missing/changed expected[" + expected.get(key) + "] actual["
                        + actual.getOrDefault(key, 0) + "] " + key);
            }
            if (samples.size() >= 3) {
                return String.join("; ", samples);
            }
        }
        for (String key : actual.keySet()) {
            if (!actual.get(key).equals(expected.getOrDefault(key, 0))) {
                samples.add("extra expected[" + expected.getOrDefault(key, 0) + "] actual["
                        + actual.get(key) + "] " + key);
            }
            if (samples.size() >= 3) {
                return String.join("; ", samples);
            }
        }
        return "";
    }

    private static String sourceColumnList(List<BindingSpec> sourceBindings) {
        return String.join(", ", sourceBindings.stream()
                .map(BindingSpec::sourceColumn)
                .distinct()
                .toList());
    }

    private static List<String> sourceColumnsForExpectedRead(PlanSpec spec) {
        List<String> columns = new ArrayList<>(spec.sourceBindings().stream()
                .map(BindingSpec::sourceColumn)
                .distinct()
                .toList());
        if (spec.filterColumn() != null
                && !spec.filterColumn().isBlank()
                && !columns.contains(spec.filterColumn())) {
            columns.add(spec.filterColumn());
        }
        if ("KYC_ASSESSMENT__CRM_SF_DS__sf_kyc_check".equals(spec.planId())
                && !columns.contains("check_type")) {
            columns.add("check_type");
        }
        if ("CONTACT_POINT__CRM_SF_DS__sf_contact_point".equals(spec.planId())) {
            if (!columns.contains("contact_type")) {
                columns.add("contact_type");
            }
            if (!columns.contains("is_primary")) {
                columns.add("is_primary");
            }
        }
        if ("KYC_REQUIREMENT_ITEM__CRM_SF_DS__sf_consent".equals(spec.planId())
                && !columns.contains("consent_type")) {
            columns.add("consent_type");
        }
        if ("EVIDENCE_DOCUMENT__CRM_SF_DS__sf_consent".equals(spec.planId())
                && !columns.contains("consent_type")) {
            columns.add("consent_type");
        }
        return columns;
    }

    private static boolean skipForCurrentScope(PlanSpec spec) {
        return "DOWJONES_DS".equals(spec.sourceInterface())
                && ("BI_PARTY".equals(spec.targetTable())
                || "BI_PERSON".equals(spec.targetTable())
                || "BI_SOURCE_REFERENCE".equals(spec.targetTable()))
                || "SCREENING_HIT__DOWJONES_DS__dj_listing".equals(spec.planId());
    }

    private static boolean tableExists(Connection connection, String table) throws Exception {
        try (ResultSet rs = connection.getMetaData().getTables(null, null, table, null)) {
            return rs.next();
        }
    }

    private static Set<String> columnSet(Connection connection, String sql) throws Exception {
        Set<String> values = new LinkedHashSet<>();
        try (PreparedStatement statement = connection.prepareStatement(sql);
                ResultSet rs = statement.executeQuery()) {
            while (rs.next()) {
                values.add(rs.getString(1));
            }
        }
        return values;
    }

    private static Map<String, Connection> openOriginalSources(RuntimeConfig config) throws Exception {
        Map<String, Connection> sources = new LinkedHashMap<>();
        for (Map.Entry<String, String> entry : config.sourceUrls().entrySet()) {
            sources.put(entry.getKey(), DriverManager.getConnection(entry.getValue()));
        }
        return sources;
    }

    private static Map<String, Connection> openGeneratedSources(Path reverseDir) throws Exception {
        Map<String, Connection> sources = new LinkedHashMap<>();
        for (String source : List.of("MDM_INFA_DS", "CRM_SF_DS", "AML_ORA_DS", "CORE_TMNS_DS", "DOWJONES_DS")) {
            sources.put(source, openSqlite(reverseDir.resolve(source + ".db")));
        }
        return sources;
    }

    private static void writeReport(Path report, Path reverseDir, int targetDbCount, Comparison comparison) throws IOException {
        Files.createDirectories(report.getParent());
        List<String> files = new ArrayList<>();
        if (Files.exists(reverseDir)) {
            try (var stream = Files.list(reverseDir)) {
                stream.filter(path -> path.getFileName().toString().endsWith(".db"))
                        .sorted(Comparator.comparing(path -> path.getFileName().toString()))
                        .forEach(path -> files.add(path.getFileName().toString()));
            }
        }
        String json = "{\n"
                + "  \"status\": " + quote(comparison.passed() ? "passed" : "failed") + ",\n"
                + "  \"mode\": \"mapped-column-equivalence\",\n"
                + "  \"targetDbCount\": " + targetDbCount + ",\n"
                + "  \"reverseDir\": " + quote(reverseDir.toString()) + ",\n"
                + "  \"reverseDbs\": [" + String.join(", ", files.stream().map(BianPartyReverseApp::quote).toList()) + "],\n"
                + "  \"comparedPlans\": " + comparison.comparedPlans + ",\n"
                + "  \"comparedRows\": " + comparison.comparedRows + ",\n"
                + "  \"mismatchCount\": " + comparison.mismatches.size() + ",\n"
                + "  \"mismatches\": [\n"
                + String.join(",\n", comparison.mismatches.stream().map(Mismatch::toJson).toList()) + "\n"
                + "  ]\n"
                + "}\n";
        Files.writeString(report, json);
    }

    private static String quote(String value) {
        return "\"" + value.replace("\\", "\\\\").replace("\"", "\\\"") + "\"";
    }

    private static final class Comparison {
        private int comparedPlans;
        private int comparedRows;
        private final List<Mismatch> mismatches = new ArrayList<>();

        boolean passed() {
            return mismatches.isEmpty();
        }

        void planCompared(String planId, int rows) {
            comparedPlans++;
            comparedRows += rows;
            LOG.fine(() -> "Compared mapped columns plan=" + planId + " expectedRows=" + rows);
        }

        void mismatch(String planId, String source, int expectedRows, int actualRows, String sample) {
            mismatches.add(new Mismatch(planId, source, expectedRows, actualRows, sample));
            LOG.warning(() -> "Mapped-column mismatch plan=" + planId
                    + " source=" + source
                    + " expectedRows=" + expectedRows
                    + " actualRows=" + actualRows
                    + " sample=" + sample);
        }
    }

    private record Mismatch(String planId, String source, int expectedRows, int actualRows, String sample) {
        String toJson() {
            return "    {"
                    + "\"planId\": " + quote(planId)
                    + ", \"source\": " + quote(source)
                    + ", \"expectedRows\": " + expectedRows
                    + ", \"actualRows\": " + actualRows
                    + ", \"sample\": " + quote(sample)
                    + "}";
        }
    }
}
