# Blackbox Java Runtime Core

This module contains common Java runtime code for Blackbox executable targets.

It intentionally excludes project-specific config, scripts, source databases,
and mapping classes. Those live under each project, for example:

```text
projects/tmf/runtime/java/
```

The durable runtime code lives under `com.blackbox.runtime` and covers:

```
config loading
logging
source JDBC registry
target instance database creation
target schema loading
mapping-plan contracts
```

Build/install from the repository root:

```bash
mvn -q -f runtime/java/pom.xml clean install
```
