package com.blackbox.tmf;

import com.blackbox.runtime.config.RuntimeConfig;
import com.blackbox.runtime.config.RuntimeLogging;
import com.blackbox.runtime.instance.InstanceEnumerator;
import com.blackbox.runtime.instance.InstanceKey;
import com.blackbox.runtime.instance.TargetInstance;
import com.blackbox.runtime.instance.TargetInstanceFactory;
import com.blackbox.runtime.jdbc.SourceRegistry;
import com.blackbox.runtime.mapping.MappingContext;
import com.blackbox.runtime.mapping.MappingPlan;
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
import com.blackbox.tmf.source.TmfPartyEnumerator;
import java.nio.file.Path;
import java.util.List;
import java.util.logging.Logger;

/**
 * First executable Java runtime slice for Blackbox TMF.
 *
 * The app is intentionally simple:
 * 1. Load top-level runtime configuration.
 * 2. Open source JDBC connections.
 * 3. Enumerate TC_PARTY instances.
 * 4. Create one target SQLite DB per party.
 * 5. Create the full TMF canonical schema in each DB.
 * 6. Run generated Java mapping plans materialized from IR.
 */
public final class TmfPartyRuntimeApp {
    private static final Logger LOG = Logger.getLogger(TmfPartyRuntimeApp.class.getName());

    private TmfPartyRuntimeApp() {
    }

    public static void main(String[] args) throws Exception {
        Path configPath = args.length == 0 ? Path.of("config/tmf-runtime.properties") : Path.of(args[0]);
        RuntimeConfig config = RuntimeConfig.load(configPath);
        RuntimeLogging.configure(config.loggingLevel());

        LOG.info(() -> "Starting TMF Java runtime config=" + config.configFile());
        LOG.fine(() -> "Target output dir=" + config.pathValue("target.outputDir"));
        LOG.fine(() -> "Target schema=" + config.pathValue("target.schema"));

        TargetSchemaManager schemaManager = new TargetSchemaManager(config.pathValue("target.schema"));
        TargetInstanceFactory targetFactory = new TargetInstanceFactory(
                config.pathValue("target.outputDir"),
                config.booleanValue("target.overwrite", true),
                schemaManager);
        InstanceEnumerator enumerator = new TmfPartyEnumerator(config.intValue("runtime.maxInstances", 0));
        List<MappingPlan> plans = List.of(
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
        plans.forEach(plan -> LOG.info(() -> "Loaded mapping plan " + plan.planId()
                + " class=" + plan.getClass().getName()));

        int completed = 0;
        try (SourceRegistry sources = SourceRegistry.open(config.sourceUrls())) {
            List<InstanceKey> instances = enumerator.enumerate(sources);
            for (InstanceKey instance : instances) {
                LOG.info(() -> "Instance start " + instance);
                try (TargetInstance target = targetFactory.open(instance)) {
                    MappingContext context = new MappingContext(instance, sources, target.connection());
                    for (MappingPlan plan : plans) {
                        LOG.info(() -> "Mapping start instance=" + instance
                                + " plan=" + plan.planId()
                                + " class=" + plan.getClass().getName()
                                + " db=" + target.path());
                        plan.execute(context);
                        LOG.info(() -> "Mapping complete instance=" + instance
                                + " plan=" + plan.planId()
                                + " db=" + target.path());
                    }
                    target.commit();
                    completed++;
                    LOG.info(() -> "Instance complete " + instance + " db=" + target.path());
                }
            }
        }

        LOG.info("TMF Java runtime complete instances=" + completed);
    }
}
