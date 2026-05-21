package com.blackbox.runtime.config;

import java.io.IOException;
import java.io.InputStream;
import java.nio.file.Path;
import java.util.LinkedHashMap;
import java.util.Map;
import java.util.Properties;
import java.util.logging.Level;

/**
 * Loads simple properties-based runtime configuration.
 *
 * The core runtime deliberately avoids project-specific assumptions here. It
 * knows about source JDBC URLs, target output paths, logging, and generic
 * execution controls. Mapping classes decide which tables and fields to use.
 */
public final class RuntimeConfig {
    private final Path configFile;
    private final Properties properties;

    private RuntimeConfig(Path configFile, Properties properties) {
        this.configFile = configFile;
        this.properties = properties;
    }

    public static RuntimeConfig load(Path configFile) {
        Properties properties = new Properties();
        try (InputStream input = java.nio.file.Files.newInputStream(configFile)) {
            properties.load(input);
        } catch (IOException ex) {
            throw new IllegalStateException("Unable to load runtime config " + configFile, ex);
        }
        return new RuntimeConfig(configFile.toAbsolutePath().normalize(), properties);
    }

    public Path configFile() {
        return configFile;
    }

    public Level loggingLevel() {
        return Level.parse(value("logging.level", "INFO").trim().toUpperCase());
    }

    public String required(String key) {
        String value = properties.getProperty(key);
        if (value == null || value.isBlank()) {
            throw new IllegalArgumentException("Missing required runtime config key " + key);
        }
        return value.trim();
    }

    public String value(String key, String defaultValue) {
        String value = properties.getProperty(key);
        return value == null || value.isBlank() ? defaultValue : value.trim();
    }

    public boolean booleanValue(String key, boolean defaultValue) {
        String value = properties.getProperty(key);
        return value == null || value.isBlank() ? defaultValue : Boolean.parseBoolean(value.trim());
    }

    public int intValue(String key, int defaultValue) {
        String value = properties.getProperty(key);
        if (value == null || value.isBlank()) {
            return defaultValue;
        }
        return Integer.parseInt(value.trim());
    }

    public Path pathValue(String key) {
        return resolvePath(required(key));
    }

    public Path pathValue(String key, String defaultValue) {
        return resolvePath(value(key, defaultValue));
    }

    public Map<String, String> sourceUrls() {
        Map<String, String> urls = new LinkedHashMap<>();
        String prefix = "source.";
        String suffix = ".url";
        for (String key : properties.stringPropertyNames()) {
            if (key.startsWith(prefix) && key.endsWith(suffix)) {
                String sourceName = key.substring(prefix.length(), key.length() - suffix.length());
                urls.put(sourceName, resolveJdbcUrl(required(key)));
            }
        }
        return urls;
    }

    private String resolveJdbcUrl(String raw) {
        String sqlitePrefix = "jdbc:sqlite:";
        if (!raw.startsWith(sqlitePrefix)) {
            return raw;
        }
        String sqlitePath = raw.substring(sqlitePrefix.length());
        if (sqlitePath.isBlank() || sqlitePath.equals(":memory:") || sqlitePath.startsWith("file:")) {
            return raw;
        }
        Path path = Path.of(sqlitePath);
        if (path.isAbsolute()) {
            return sqlitePrefix + path.normalize();
        }
        return sqlitePrefix + resolvePath(sqlitePath);
    }

    private Path resolvePath(String raw) {
        Path path = Path.of(raw);
        if (path.isAbsolute()) {
            return path.normalize();
        }
        Path configDir = configFile.getParent();
        return configDir.resolve(path).normalize();
    }
}
