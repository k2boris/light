# TMF Java Runtime

TMF-specific Java executable target. The current project-level status and latest
validation results are summarized in `projects/tmf/README.md`.

Useful commands from the repository root:

```bash
projects/tmf/runtime/java/scripts/clean-party.sh
mvn -q test -f projects/tmf/runtime/java/pom.xml
projects/tmf/runtime/java/scripts/run-party.sh
projects/tmf/runtime/java/scripts/reverse-party.sh
projects/tmf/runtime/java/scripts/smoke-party.sh
PYTHONDONTWRITEBYTECODE=1 projects/tmf/runtime/java/scripts/validate-golden-targets.sh
```

Runtime outputs:

```text
projects/tmf/tmp/java-runtime/data
projects/tmf/tmp/java-runtime/logs
projects/tmf/tmp/java-runtime/reverse-sources
projects/tmf/tmp/java-runtime/reverse-compare.json
projects/tmf/tmp/java-runtime/golden-target-compare.json
```

Default configuration:

```text
projects/tmf/runtime/java/config/tmf-runtime.properties
```
