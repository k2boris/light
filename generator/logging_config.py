"""Logging configuration helpers.

We standardize on INFO/DEBUG/ERROR with structured context fields.
This keeps validation errors actionable across environments.
"""

from __future__ import annotations

import logging
import sys
from typing import Optional

LOG_FORMAT = (
    "%(asctime)s | %(levelname)s | %(name)s | "
    "phase=%(phase)s tab=%(tab)s row=%(row)s plan_id=%(plan_id)s "
    "msg=%(message)s"
)

class ContextFilter(logging.Filter):
    """Inject default context keys so formatters never KeyError.

    We keep the core formatter stable, and attach contextual fields via `extra=`.
    """
    def filter(self, record: logging.LogRecord) -> bool:
        for k, v in {
            "phase": "-",
            "tab": "-",
            "row": "-",
            "plan_id": "-",
        }.items():
            if not hasattr(record, k):
                setattr(record, k, v)
        return True

def configure_logging(level: str = "INFO") -> None:
    lvl = getattr(logging, level.upper(), logging.INFO)
    context_filter = ContextFilter()

    handler = logging.StreamHandler(sys.stdout)
    handler.setLevel(lvl)
    # Ensure all records formatted by this handler include required context fields.
    handler.addFilter(context_filter)

    formatter = logging.Formatter(LOG_FORMAT)
    handler.setFormatter(formatter)

    root = logging.getLogger()
    root.handlers.clear()
    root.setLevel(lvl)
    root.addHandler(handler)
    root.filters.clear()
    root.addFilter(context_filter)

    # Make noisy libs quieter by default
    logging.getLogger("openpyxl").setLevel(max(lvl, logging.WARNING))
