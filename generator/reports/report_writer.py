"""Report writer utilities."""

from __future__ import annotations
from pathlib import Path
import json
from ..validate.report_model import ValidationReport

def write_json_report(path: Path, report: ValidationReport) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(report.to_dict(), indent=2), encoding="utf-8")
