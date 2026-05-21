"""Template instantiation.

Templates define an IR skeleton JSON. This module:
- loads the skeleton
- computes template parameters using Template_Params rules
- injects plan expressions and policies
- returns concrete nodes/edges/params for PlanIR

This file is a stub but includes the intended structure.
"""

from __future__ import annotations
import json
import logging
from typing import Any, Dict, List, Tuple

from ..spec.spec_model import WorkbookSpec, EntityPlan
from .ir_model import Node, Edge
from .template_params_resolver import resolve_template_params

logger = logging.getLogger(__name__)

def instantiate_template(spec: WorkbookSpec, ep: EntityPlan, project_map: Dict[str, Any]) -> Tuple[Dict[str, Any], List[Node], List[Edge]]:
    """Instantiate template skeleton for a plan.

    Args:
      spec: full workbook spec (includes Templates, Template_Params)
      ep: the EntityPlan row
      project_map: mapping of target_field -> Expression serialized form

    Returns:
      (params, nodes, edges) ready to attach to PlanIR.
    """
    tdef = spec.templates[ep.template_id]
    skeleton = json.loads(tdef.ir_skeleton_json or "{}")

    params = resolve_template_params(spec, ep, spec.field_maps_by_plan.get(ep.plan_id, []), project_map)

    # Build graph from template skeleton when valid; otherwise fall back to a minimal default graph.
    nodes: List[Node] = []
    edges: List[Edge] = []
    if "nodes" in skeleton and "edges" in skeleton:
        for n in skeleton.get("nodes", []):
            node_id = n.get("node_id") or n.get("id")
            kind = n.get("kind") or n.get("op")
            reserved = {"node_id", "id", "kind", "op", "params"}
            node_params = dict(n.get("params", {}))
            for k, v in n.items():
                if k not in reserved:
                    node_params[k] = v
            if node_id and kind:
                nodes.append(Node(node_id=node_id, kind=kind, params=node_params))

        for e in skeleton.get("edges", []):
            src = e.get("src") or e.get("from")
            dst = e.get("dst") or e.get("to")
            if src and dst:
                edges.append(Edge(src=src, dst=dst))

    if not nodes or not edges:
        nodes = [
            Node(node_id="src", kind="SOURCE", params={"entity": ep.source_entity}),
            Node(node_id="proj", kind="PROJECT", params={"fields": project_map}),
            Node(node_id="load", kind="LOAD", params={"table": ep.target_table, "mode": "UPSERT"}),
        ]
        edges = [Edge(src="src", dst="proj"), Edge(src="proj", dst="load")]

    return params, nodes, edges
