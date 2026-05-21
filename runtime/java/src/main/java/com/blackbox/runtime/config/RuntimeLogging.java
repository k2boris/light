package com.blackbox.runtime.config;

import java.util.logging.ConsoleHandler;
import java.util.logging.Handler;
import java.util.logging.Level;
import java.util.logging.Logger;
import java.util.logging.SimpleFormatter;

/**
 * Central logging setup for the Java runtime.
 *
 * Uses java.util.logging so the runtime remains dependency-light. Fine-grained
 * messages use FINE, FINER, and FINEST around connection lifecycle, SQL work,
 * row handling, and mapping decisions.
 */
public final class RuntimeLogging {
    private RuntimeLogging() {
    }

    public static void configure(Level level) {
        Logger root = Logger.getLogger("");
        for (Handler handler : root.getHandlers()) {
            root.removeHandler(handler);
        }
        ConsoleHandler console = new ConsoleHandler();
        console.setLevel(level);
        console.setFormatter(new SimpleFormatter());
        root.addHandler(console);
        root.setLevel(level);
    }
}
