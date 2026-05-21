"""Runtime compiler registry.

Build runtime-specific artifacts from template implementation declarations.
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional

from ..spec.spec_model import WorkbookSpec, EntityPlan, FieldMap
from ..ddl.schema_model import Schema
from .broadway_compiler import compile_broadway_plan
from .python_compiler import compile_python_plan


def compile_runtimes(
    spec: WorkbookSpec,
    ep: EntityPlan,
    field_maps: List[FieldMap],
    template_params: Dict[str, Any],
    sources: Optional[Dict[str, Schema]] = None,
) -> Dict[str, Any]:
    runtimes: Dict[str, Any] = {}
    broadway = compile_broadway_plan(spec, ep, field_maps, template_params, sources=sources)
    if broadway:
        runtimes["broadway"] = broadway

    py_runtime = compile_python_plan(spec, ep, field_maps, template_params, sources=sources)
    if py_runtime:
        runtimes["python"] = py_runtime

    return runtimes
