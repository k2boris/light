package com.blackbox.tmf;

import com.blackbox.runtime.config.RuntimeConfig;
import com.blackbox.runtime.config.RuntimeLogging;
import com.blackbox.runtime.mapping.ReverseMappingContext;
import com.blackbox.runtime.mapping.ReverseMappingPlan;
import com.blackbox.runtime.schema.TargetSchemaManager;
import com.blackbox.tmf.generated.TcCaCharBscsBscsCustomerPlan;
import com.blackbox.tmf.generated.TcCaCharNccNccEligibilityFlagPlan;
import com.blackbox.tmf.generated.TcCaCharNccNccOfferQualRequestPlan;
import com.blackbox.tmf.generated.TcCaCharSiebelSblChurnScorePlan;
import com.blackbox.tmf.generated.TcCaCharSiebelSblCustomerPlan;
import com.blackbox.tmf.generated.TcCaCharSiebelSblInteractionPlan;
import com.blackbox.tmf.generated.TcCaProdMapNccJoinedPlan;
import com.blackbox.tmf.generated.TcCustAcctSiebelSblCustomerPlan;
import com.blackbox.tmf.generated.TcCustomerSiebelSblCustomerPlan;
import com.blackbox.tmf.generated.TcPartySiebelSblCustomerPlan;
import com.blackbox.tmf.generated.TcProdCharNccNccCommitmentPlan;
import com.blackbox.tmf.generated.TcProdCharNccNccProductParamValuePlan;
import com.blackbox.tmf.generated.TcProductNccNccProductPlan;
import com.blackbox.tmf.generated.TcProductSiebelSblAssetPlan;
import com.blackbox.tmf.generated.TcPtyCntMedBscsBillingAddressPlan;
import com.blackbox.tmf.generated.TcPtyCntMedSiebelCustomerContactPlan;
import com.blackbox.tmf.generated.TcPtyExtRefBscsBscsCustomerPlan;
import com.blackbox.tmf.generated.TcPtyExtRefSiebelSblCustomerPlan;
import com.blackbox.tmf.mapping.TmfBillingAccountBscsPlan;
import com.blackbox.tmf.mapping.TmfBillingBalanceBscsPlan;
import java.io.IOException;
import java.nio.file.Files;
import java.nio.file.Path;
import java.sql.Connection;
import java.sql.DriverManager;
import java.sql.PreparedStatement;
import java.sql.ResultSet;
import java.sql.SQLException;
import java.sql.Statement;
import java.util.ArrayList;
import java.util.LinkedHashSet;
import java.util.List;
import java.util.Map;
import java.util.Objects;
import java.util.Set;
import java.util.logging.Logger;

/**
 * Reverse round-trip test runtime for the current TMF Java slice.
 *
 * This is not live synchronization. It reads generated entity-level target DBs
 * and reconstructs a fresh set of source SQLite DBs containing mapped columns.
 * The comparison report checks mapped-column equivalence against the original
 * source DBs.
 */
public final class TmfPartyReverseApp {
    private static final Logger LOG = Logger.getLogger(TmfPartyReverseApp.class.getName());

    private TmfPartyReverseApp() {
    }

    public static void main(String[] args) throws Exception {
        Path configPath = args.length == 0 ? Path.of("config/tmf-runtime.properties") : Path.of(args[0]);
        RuntimeConfig config = RuntimeConfig.load(configPath);
        RuntimeLogging.configure(config.loggingLevel());

        Path targetDataDir = config.pathValue("target.outputDir");
        Path reverseDir = config.pathValue("reverse.outputDir");
        Path reverseSiebel = reverseDir.resolve("siebel.db");
        Path reverseBscs = reverseDir.resolve("bscs.db");
        Path reverseNcc = reverseDir.resolve("ncc.db");
        Files.createDirectories(reverseDir);
        deleteIfExists(reverseSiebel);
        deleteIfExists(reverseBscs);
        deleteIfExists(reverseNcc);

        LOG.info(() -> "Starting TMF reverse runtime targetDataDir=" + targetDataDir + " reverseDir=" + reverseDir);
        try (Connection siebel = openSqlite(reverseSiebel);
                Connection bscs = openSqlite(reverseBscs);
                Connection ncc = openSqlite(reverseNcc)) {
            new TargetSchemaManager(config.pathValue("reverse.siebel.schema")).createSchema(siebel);
            new TargetSchemaManager(config.pathValue("reverse.bscs.schema")).createSchema(bscs);
            new TargetSchemaManager(config.pathValue("reverse.ncc.schema")).createSchema(ncc);

            List<ReverseMappingPlan> reversePlans = List.of(
                    new TcPartySiebelSblCustomerPlan(),
                    new TcCustomerSiebelSblCustomerPlan(),
                    new TcCustAcctSiebelSblCustomerPlan(),
                    new TcCaCharBscsBscsCustomerPlan(),
                    new TcCaCharNccNccEligibilityFlagPlan(),
                    new TcCaCharNccNccOfferQualRequestPlan(),
                    new TcCaCharSiebelSblChurnScorePlan(),
                    new TcCaCharSiebelSblCustomerPlan(),
                    new TcCaCharSiebelSblInteractionPlan(),
                    new TcProductNccNccProductPlan(),
                    new TcProductSiebelSblAssetPlan(),
                    new TcCaProdMapNccJoinedPlan(),
                    new TcProdCharNccNccCommitmentPlan(),
                    new TcProdCharNccNccProductParamValuePlan(),
                    new TcPtyCntMedSiebelCustomerContactPlan(),
                    new TcPtyCntMedBscsBillingAddressPlan(),
                    new TmfBillingAccountBscsPlan(),
                    new TmfBillingBalanceBscsPlan(),
                    new TcPtyExtRefSiebelSblCustomerPlan(),
                    new TcPtyExtRefBscsBscsCustomerPlan());
            reversePlans.forEach(plan -> LOG.info(() -> "Loaded reverse mapping plan " + plan.planId()
                    + " class=" + plan.getClass().getName()));

            List<Path> targetDbs = listTargetDbs(targetDataDir);
            LOG.info(() -> "Reverse materializing source rows from target DB count=" + targetDbs.size());
            Map<String, Connection> reverseSources = Map.of(
                    "SIEBEL_SYSTEM", siebel,
                    "BSCS_SYSTEM", bscs,
                    "NCC_SYSTEM", ncc);
            for (Path targetDb : targetDbs) {
                reverseOneTargetDb(targetDb, reverseSources, reversePlans);
            }
            siebel.commit();
            bscs.commit();
            ncc.commit();
        }

        Comparison comparison = compare(config, reverseSiebel, reverseBscs, reverseNcc);
        writeReport(config.pathValue("reverse.report"), comparison, reverseSiebel, reverseBscs, reverseNcc);
        if (!comparison.passed()) {
            throw new IllegalStateException("Reverse mapped-column comparison failed mismatches=" + comparison.mismatches());
        }
        LOG.info(() -> "TMF reverse runtime complete comparedRows=" + comparison.comparedRows());
    }

    private static void reverseOneTargetDb(
            Path targetDb,
            Map<String, Connection> reverseSources,
            List<ReverseMappingPlan> reversePlans) throws Exception {
        LOG.info(() -> "Reverse materializing targetDb=" + targetDb);
        try (Connection target = openSqlite(targetDb)) {
            ReverseMappingContext context = new ReverseMappingContext(target, reverseSources);
            for (ReverseMappingPlan plan : reversePlans) {
                LOG.info(() -> "Reverse mapping start plan=" + plan.planId() + " targetDb=" + targetDb);
                plan.reverse(context);
                LOG.info(() -> "Reverse mapping complete plan=" + plan.planId() + " targetDb=" + targetDb);
            }
        }
    }

    private static Comparison compare(RuntimeConfig config, Path reverseSiebel, Path reverseBscs, Path reverseNcc) throws SQLException {
        Comparison comparison = new Comparison();
        try (Connection originalSiebel = openSqlite(jdbcSqlitePath(config.sourceUrls().get("SIEBEL_SYSTEM")));
                Connection generatedSiebel = openSqlite(reverseSiebel);
                Connection originalBscs = openSqlite(jdbcSqlitePath(config.sourceUrls().get("BSCS_SYSTEM")));
                Connection generatedBscs = openSqlite(reverseBscs);
                Connection originalNcc = openSqlite(jdbcSqlitePath(config.sourceUrls().get("NCC_SYSTEM")));
                Connection generatedNcc = openSqlite(reverseNcc)) {
            compareSiebel(originalSiebel, generatedSiebel, comparison);
            compareBscs(originalBscs, generatedBscs, comparison);
            compareNcc(originalNcc, generatedNcc, comparison);
        }
        return comparison;
    }

    private static void compareSiebel(Connection original, Connection generated, Comparison comparison) throws SQLException {
        String sql = """
                select customer_id, party_id, first_name, last_name, status, email, msisdn, segment_code
                from SBL_CUSTOMER
                order by customer_id
                """;
        try (Statement statement = original.createStatement();
                ResultSet rs = statement.executeQuery(sql)) {
            while (rs.next()) {
                String customerId = rs.getString("customer_id");
                try (PreparedStatement gen = generated.prepareStatement(sql.replace("order by customer_id", "where customer_id = ?"))) {
                    gen.setString(1, customerId);
                    try (ResultSet grs = gen.executeQuery()) {
                        if (!grs.next()) {
                            comparison.mismatch("SIEBEL", customerId, "missing generated row");
                            continue;
                        }
                        compareField(comparison, "SIEBEL", customerId, "party_id", rs.getString("party_id"), grs.getString("party_id"));
                        compareField(comparison, "SIEBEL", customerId, "first_name", rs.getString("first_name"), grs.getString("first_name"));
                        compareField(comparison, "SIEBEL", customerId, "last_name", rs.getString("last_name"), grs.getString("last_name"));
                        compareField(comparison, "SIEBEL", customerId, "status", rs.getString("status"), grs.getString("status"));
                        compareField(comparison, "SIEBEL", customerId, "email", rs.getString("email"), grs.getString("email"));
                        compareField(comparison, "SIEBEL", customerId, "msisdn", rs.getString("msisdn"), grs.getString("msisdn"));
                        compareField(comparison, "SIEBEL", customerId, "segment_code", rs.getString("segment_code"), grs.getString("segment_code"));
                    }
                }
                compareSiebelChurnScore(original, generated, comparison, customerId);
                compareSiebelInteraction(original, generated, comparison, customerId);
            }
        }
    }

    private static void compareSiebelChurnScore(
            Connection original,
            Connection generated,
            Comparison comparison,
            String customerId) throws SQLException {
        String sql = "select churn_score, risk_band, model_version, scored_dt, top_driver from SBL_CHURN_SCORE where customer_id = ?";
        try (PreparedStatement orig = original.prepareStatement(sql);
                PreparedStatement gen = generated.prepareStatement(sql)) {
            orig.setString(1, customerId);
            gen.setString(1, customerId);
            try (ResultSet ors = orig.executeQuery();
                    ResultSet grs = gen.executeQuery()) {
                if (!ors.next()) {
                    return;
                }
                if (!grs.next()) {
                    comparison.mismatch("SIEBEL_CHURN_SCORE", customerId, "missing generated row");
                    return;
                }
                compareField(comparison, "SIEBEL_CHURN_SCORE", customerId, "churn_score", ors.getString("churn_score"), grs.getString("churn_score"));
                compareField(comparison, "SIEBEL_CHURN_SCORE", customerId, "risk_band", ors.getString("risk_band"), grs.getString("risk_band"));
                compareField(comparison, "SIEBEL_CHURN_SCORE", customerId, "model_version", ors.getString("model_version"), grs.getString("model_version"));
                compareField(comparison, "SIEBEL_CHURN_SCORE", customerId, "scored_dt", ors.getString("scored_dt"), grs.getString("scored_dt"));
                compareField(comparison, "SIEBEL_CHURN_SCORE", customerId, "top_driver", ors.getString("top_driver"), grs.getString("top_driver"));
            }
        }
    }

    private static void compareSiebelInteraction(
            Connection original,
            Connection generated,
            Comparison comparison,
            String customerId) throws SQLException {
        String sql = "select outcome_code, end_ts from SBL_INTERACTION where customer_id = ? order by end_ts desc limit 1";
        try (PreparedStatement orig = original.prepareStatement(sql);
                PreparedStatement gen = generated.prepareStatement(sql)) {
            orig.setString(1, customerId);
            gen.setString(1, customerId);
            try (ResultSet ors = orig.executeQuery();
                    ResultSet grs = gen.executeQuery()) {
                if (!ors.next()) {
                    return;
                }
                if (!grs.next()) {
                    comparison.mismatch("SIEBEL_INTERACTION", customerId, "missing generated row");
                    return;
                }
                compareField(comparison, "SIEBEL_INTERACTION", customerId, "outcome_code", ors.getString("outcome_code"), grs.getString("outcome_code"));
            }
        }
    }

    private static void compareSiebelAssets(
            Connection original,
            Connection generated,
            Comparison comparison,
            String customerId) throws SQLException {
        Set<String> expected = rowSet(original, """
                select product_id, offering_id, start_dt, status, contract_end_dt
                from SBL_ASSET
                where customer_id = ?
                order by product_id, start_dt, offering_id
                """, customerId);
        Set<String> actual = rowSet(generated, """
                select product_id, offering_id, start_dt, status, contract_end_dt
                from SBL_ASSET
                where customer_id = ?
                order by product_id, start_dt, offering_id
                """, customerId);
        comparison.comparedRows++;
        if (!expected.equals(actual)) {
            comparison.mismatch("SIEBEL_ASSET", customerId, "asset_set expected=" + expected + " actual=" + actual);
        }
    }

    private static void compareBscs(Connection original, Connection generated, Comparison comparison) throws SQLException {
        String customerSql = "select customer_id, msisdn, credit_class, risk_flag from BSCS_CUSTOMER order by customer_id";
        try (Statement statement = original.createStatement();
                ResultSet rs = statement.executeQuery(customerSql)) {
            while (rs.next()) {
                String customerId = rs.getString("customer_id");
                try (PreparedStatement gen = generated.prepareStatement(
                        "select customer_id, msisdn, credit_class, risk_flag from BSCS_CUSTOMER where customer_id = ?")) {
                    gen.setString(1, customerId);
                    try (ResultSet grs = gen.executeQuery()) {
                        if (!grs.next()) {
                            comparison.mismatch("BSCS", customerId, "missing generated customer row");
                            continue;
                        }
                        compareField(comparison, "BSCS", customerId, "msisdn", rs.getString("msisdn"), grs.getString("msisdn"));
                        compareField(comparison, "BSCS", customerId, "credit_class", rs.getString("credit_class"), grs.getString("credit_class"));
                        compareField(comparison, "BSCS", customerId, "risk_flag", rs.getString("risk_flag"), grs.getString("risk_flag"));
                    }
                }
            }
        }
    }

    private static Set<String> bscsAddressSet(Connection connection, String customerId) throws SQLException {
        String sql = """
                select t1.customer_id, t2.is_primary, t3.line1
                from BSCS_BILLING_ACCOUNT t1
                join BSCS_ACCOUNT_ADDRESS t2 on t1.billing_account_id = t2.billing_account_id
                join BSCS_ADDRESS t3 on t2.address_id = t3.address_id
                where t1.customer_id = ?
                order by t3.line1, t2.is_primary
                """;
        Set<String> rows = new LinkedHashSet<>();
        try (PreparedStatement statement = connection.prepareStatement(sql)) {
            statement.setString(1, customerId);
            try (ResultSet rs = statement.executeQuery()) {
                while (rs.next()) {
                    rows.add(rs.getString("is_primary") + "|" + rs.getString("line1"));
                }
            }
        }
        return rows;
    }

    private static void compareNcc(Connection original, Connection generated, Comparison comparison) throws SQLException {
        compareNccEligibilityFlags(original, generated, comparison);
        compareNccOfferQualRequests(original, generated, comparison);
        compareNccProducts(original, generated, comparison);
        compareNccProductParams(original, generated, comparison);
    }

    private static void compareNccEligibilityFlags(Connection original, Connection generated, Comparison comparison) throws SQLException {
        String sql = "select customer_id, flag_code, flag_value, effective_dt from NCC_ELIGIBILITY_FLAG order by customer_id, flag_code, effective_dt";
        try (Statement statement = original.createStatement();
                ResultSet rs = statement.executeQuery(sql)) {
            while (rs.next()) {
                String key = rs.getString("customer_id") + "|" + rs.getString("flag_code") + "|" + rs.getString("effective_dt");
                try (PreparedStatement gen = generated.prepareStatement(
                        "select flag_value from NCC_ELIGIBILITY_FLAG where customer_id = ? and flag_code = ? and effective_dt = ?")) {
                    gen.setString(1, rs.getString("customer_id"));
                    gen.setString(2, rs.getString("flag_code"));
                    gen.setString(3, rs.getString("effective_dt"));
                    try (ResultSet grs = gen.executeQuery()) {
                        if (!grs.next()) {
                            comparison.mismatch("NCC_ELIGIBILITY_FLAG", key, "missing generated row");
                            continue;
                        }
                        compareField(comparison, "NCC_ELIGIBILITY_FLAG", key, "flag_value", rs.getString("flag_value"), grs.getString("flag_value"));
                    }
                }
            }
        }
    }

    private static void compareNccOfferQualRequests(Connection original, Connection generated, Comparison comparison) throws SQLException {
        String sql = "select customer_id, past_due_amount from NCC_OFFER_QUAL_REQUEST order by customer_id";
        try (Statement statement = original.createStatement();
                ResultSet rs = statement.executeQuery(sql)) {
            while (rs.next()) {
                String customerId = rs.getString("customer_id");
                try (PreparedStatement gen = generated.prepareStatement(
                        "select past_due_amount from NCC_OFFER_QUAL_REQUEST where customer_id = ?")) {
                    gen.setString(1, customerId);
                    try (ResultSet grs = gen.executeQuery()) {
                        if (!grs.next()) {
                            comparison.mismatch("NCC_OFFER_QUAL_REQUEST", customerId, "missing generated row");
                            continue;
                        }
                        compareField(comparison, "NCC_OFFER_QUAL_REQUEST", customerId, "past_due_amount", rs.getString("past_due_amount"), grs.getString("past_due_amount"));
                    }
                }
            }
        }
    }

    private static void compareNccProducts(Connection original, Connection generated, Comparison comparison) throws SQLException {
                String sql = """
                select s.customer_id, p.product_id, p.offering_id, p.status, p.start_dt
                from NCC_SUBSCRIPTION s
                join NCC_PRODUCT p on s.subscription_id = p.subscription_id
                order by s.customer_id, p.product_id, p.start_dt
                """;
        try (Statement statement = original.createStatement();
                ResultSet rs = statement.executeQuery(sql)) {
            while (rs.next()) {
                String key = rs.getString("customer_id") + "|" + rs.getString("product_id");
                try (PreparedStatement gen = generated.prepareStatement("""
                        select s.customer_id, p.product_id, p.offering_id, p.status, p.start_dt
                        from NCC_SUBSCRIPTION s
                        join NCC_PRODUCT p on s.subscription_id = p.subscription_id
                        where s.customer_id = ? and p.product_id = ?
                        """)) {
                    gen.setString(1, rs.getString("customer_id"));
                    gen.setString(2, rs.getString("product_id"));
                    try (ResultSet grs = gen.executeQuery()) {
                        if (!grs.next()) {
                            comparison.mismatch("NCC_PRODUCT", key, "missing generated row");
                            continue;
                        }
                        compareField(comparison, "NCC_PRODUCT", key, "offering_id", rs.getString("offering_id"), grs.getString("offering_id"));
                        compareField(comparison, "NCC_PRODUCT", key, "status", rs.getString("status"), grs.getString("status"));
                        compareField(comparison, "NCC_PRODUCT", key, "start_dt", rs.getString("start_dt"), grs.getString("start_dt"));
                    }
                }
            }
        }
    }

    private static void compareNccProductParams(Connection original, Connection generated, Comparison comparison) throws SQLException {
        Set<String> expected = rowSet(original, """
                select v.product_id, v.param_name, v.param_value
                from NCC_PRODUCT_PARAM_VALUE v
                join NCC_PRODUCT p on p.product_id = v.product_id
                where p.status = 'ACTIVE'
                order by v.product_id, v.param_name
                """);
        Set<String> actual = rowSet(generated, """
                select product_id, param_name, param_value
                from NCC_PRODUCT_PARAM_VALUE
                order by product_id, param_name
                """);
        comparison.comparedRows++;
        if (!expected.equals(actual)) {
            comparison.mismatch("NCC_PRODUCT_PARAM_VALUE", "all", "param_set expected=" + expected + " actual=" + actual);
        }
    }

    private static void compareNccCommitments(Connection original, Connection generated, Comparison comparison) throws SQLException {
        Set<String> expected = rowSet(original, """
                select product_id, commitment_type, start_dt, end_dt, early_term_fee_usd
                from NCC_COMMITMENT
                order by product_id, commitment_type
                """);
        Set<String> actual = rowSet(generated, """
                select product_id, commitment_type, start_dt, end_dt, early_term_fee_usd
                from NCC_COMMITMENT
                order by product_id, commitment_type
                """);
        comparison.comparedRows++;
        if (!expected.equals(actual)) {
            comparison.mismatch("NCC_COMMITMENT", "all", "commitment_set expected=" + expected + " actual=" + actual);
        }
    }

    private static Set<String> rowSet(Connection connection, String sql, String... params) throws SQLException {
        Set<String> rows = new LinkedHashSet<>();
        try (PreparedStatement statement = connection.prepareStatement(sql)) {
            for (int i = 0; i < params.length; i++) {
                statement.setString(i + 1, params[i]);
            }
            try (ResultSet rs = statement.executeQuery()) {
                int columns = rs.getMetaData().getColumnCount();
                while (rs.next()) {
                    List<String> values = new ArrayList<>();
                    for (int i = 1; i <= columns; i++) {
                        String value = rs.getString(i);
                        values.add(value == null ? "" : value);
                    }
                    rows.add(String.join("|", values));
                }
            }
        }
        return rows;
    }

    private static void compareField(Comparison comparison, String source, String key, String field, String expected, String actual) {
        comparison.comparedRows++;
        if (!Objects.equals(expected, actual)) {
            comparison.mismatch(source, key, field + " expected=" + expected + " actual=" + actual);
        }
    }

    private static void writeReport(Path reportPath, Comparison comparison, Path reverseSiebel, Path reverseBscs, Path reverseNcc) throws IOException {
        Files.createDirectories(reportPath.getParent());
        StringBuilder json = new StringBuilder();
        json.append("{\n");
        json.append("  \"passed\": ").append(comparison.passed()).append(",\n");
        json.append("  \"comparedRows\": ").append(comparison.comparedRows()).append(",\n");
        json.append("  \"mismatchCount\": ").append(comparison.mismatches().size()).append(",\n");
        json.append("  \"reverseSiebel\": ").append(jsonString(reverseSiebel.toString())).append(",\n");
        json.append("  \"reverseBscs\": ").append(jsonString(reverseBscs.toString())).append(",\n");
        json.append("  \"reverseNcc\": ").append(jsonString(reverseNcc.toString())).append(",\n");
        json.append("  \"mismatches\": [\n");
        for (int i = 0; i < comparison.mismatches().size(); i++) {
            json.append("    ").append(jsonString(comparison.mismatches().get(i)));
            json.append(i + 1 == comparison.mismatches().size() ? "\n" : ",\n");
        }
        json.append("  ]\n");
        json.append("}\n");
        Files.writeString(reportPath, json.toString());
    }

    private static List<Path> listTargetDbs(Path targetDataDir) throws IOException {
        try (var stream = Files.list(targetDataDir)) {
            return stream.filter(path -> path.getFileName().toString().endsWith(".db"))
                    .sorted()
                    .toList();
        }
    }

    private static Connection openSqlite(Path path) throws SQLException {
        Connection connection = DriverManager.getConnection("jdbc:sqlite:" + path);
        connection.setAutoCommit(false);
        try (Statement statement = connection.createStatement()) {
            statement.execute("PRAGMA foreign_keys = ON");
        }
        return connection;
    }

    private static void deleteIfExists(Path path) throws IOException {
        if (Files.exists(path)) {
            Files.delete(path);
        }
    }

    private static Path jdbcSqlitePath(String jdbcUrl) {
        return Path.of(jdbcUrl.replaceFirst("^jdbc:sqlite:", ""));
    }

    private static String jsonString(String value) {
        return "\"" + value.replace("\\", "\\\\").replace("\"", "\\\"") + "\"";
    }

    private static final class Comparison {
        private final List<String> mismatches = new ArrayList<>();
        private int comparedRows;

        boolean passed() {
            return mismatches.isEmpty();
        }

        int comparedRows() {
            return comparedRows;
        }

        List<String> mismatches() {
            return mismatches;
        }

        void mismatch(String source, String key, String message) {
            mismatches.add(source + " " + key + " " + message);
        }
    }
}
