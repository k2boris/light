package com.blackbox.bian;

import com.blackbox.bian.generated.BianGeneratedMappings;
import com.blackbox.bian.source.BianPartyEnumerator;
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
import java.nio.file.Path;
import java.util.List;
import java.util.logging.Logger;

/**
 * Executable BIAN forward runtime.
 *
 * The runtime creates one SQLite target database per MDM golden party, creates
 * the full BIAN canonical schema, then runs the generated mapping plans
 * sequentially for that party instance.
 */
public final class BianPartyRuntimeApp {
    private static final Logger LOG = Logger.getLogger(BianPartyRuntimeApp.class.getName());

    private BianPartyRuntimeApp() {
    }

    public static void main(String[] args) throws Exception {
        Path configPath = args.length == 0 ? Path.of("config/bian-runtime.properties") : Path.of(args[0]);
        RuntimeConfig config = RuntimeConfig.load(configPath);
        RuntimeLogging.configure(config.loggingLevel());

        LOG.info(() -> "Starting BIAN Java runtime config=" + config.configFile());
        TargetSchemaManager schemaManager = new TargetSchemaManager(config.pathValue("target.schema"));
        TargetInstanceFactory targetFactory = new TargetInstanceFactory(
                config.pathValue("target.outputDir"),
                config.booleanValue("target.overwrite", true),
                schemaManager);
        InstanceEnumerator enumerator = new BianPartyEnumerator(config.intValue("runtime.maxInstances", 0));
        List<MappingPlan> plans = BianGeneratedMappings.forwardPlans();
        plans.forEach(plan -> LOG.info(() -> "Loaded BIAN mapping plan " + plan.planId()
                + " class=" + plan.getClass().getName()));

        int completed = 0;
        try (SourceRegistry sources = SourceRegistry.open(config.sourceUrls())) {
            for (InstanceKey instance : enumerator.enumerate(sources)) {
                LOG.info(() -> "Instance start " + instance);
                try (TargetInstance target = targetFactory.open(instance)) {
                    MappingContext context = new MappingContext(instance, sources, target.connection());
                    for (MappingPlan plan : plans) {
                        LOG.info(() -> "Mapping start instance=" + instance
                                + " plan=" + plan.planId()
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
        LOG.info("BIAN Java runtime complete instances=" + completed);
    }
}
