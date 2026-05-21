"""Validation report model.

We keep errors and warnings as structured records with stable codes.
This allows deterministic gating (fail build) and reporting.
"""

from __future__ import annotations
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

@dataclass(frozen=True)
class Issue:
    level: str  # ERROR or WARN
    code: str
    message: str
    phase: str
    tab: str
    row: int
    plan_id: str | None = None
    details: Dict[str, Any] = field(default_factory=dict)

@dataclass
class ValidationReport:
    errors: List[Issue] = field(default_factory=list)
    warnings: List[Issue] = field(default_factory=list)
    meta: Dict[str, Any] = field(default_factory=dict)

    @property
    def has_errors(self) -> bool:
        return len(self.errors) > 0

    def add_error(self, **kwargs) -> None:
        self.errors.append(Issue(level="ERROR", **kwargs))

    def add_warning(self, **kwargs) -> None:
        self.warnings.append(Issue(level="WARN", **kwargs))

    def to_dict(self) -> Dict[str, Any]:
        def iss(i: Issue) -> Dict[str, Any]:
            return {
                "level": i.level, "code": i.code, "message": i.message,
                "phase": i.phase, "tab": i.tab, "row": i.row,
                "plan_id": i.plan_id, "details": i.details
            }
        return {
            "meta": self.meta,
            "errors": [iss(i) for i in self.errors],
            "warnings": [iss(i) for i in self.warnings],
        }
