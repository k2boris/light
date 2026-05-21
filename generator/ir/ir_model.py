"""IR model (COM + execution plans).

The canonical IR in this project is COM-like and runtime-agnostic.
Runtime execution plans (Broadway/Python) are compiled artifacts emitted alongside COM.
"""

from __future__ import annotations
from dataclasses import dataclass, field
from typing import Any, Dict, List
import json

@dataclass
class Expression:
    op: str
    args: Dict[str, Any] = field(default_factory=dict)

@dataclass
class COMOperation:
    op_id: str
    kind: str
    params: Dict[str, Any] = field(default_factory=dict)


@dataclass
class Node:
    node_id: str
    kind: str
    params: Dict[str, Any] = field(default_factory=dict)


@dataclass
class Edge:
    src: str
    dst: str

@dataclass
class COMPlan:
    plan_id: str
    template_id: str
    target: Dict[str, Any] = field(default_factory=dict)
    source: Dict[str, Any] = field(default_factory=dict)
    contract: Dict[str, Any] = field(default_factory=dict)
    params: Dict[str, Any] = field(default_factory=dict)
    operations: List[COMOperation] = field(default_factory=list)
    lineage: Dict[str, Any] = field(default_factory=dict)

@dataclass
class ExecutionPlan:
    runtime: str
    plan_id: str
    template_id: str
    spec: Dict[str, Any] = field(default_factory=dict)

@dataclass
class IRBundle:
    meta: Dict[str, Any] = field(default_factory=dict)
    plans: List[COMPlan] = field(default_factory=list)
    execution_plans: List[ExecutionPlan] = field(default_factory=list)
    dictionaries: Dict[str, Any] = field(default_factory=dict)
    warnings: List[Dict[str, Any]] = field(default_factory=list)
    errors: List[Dict[str, Any]] = field(default_factory=list)

    def to_json(self, indent: int = 2) -> str:
        def ser(o):
            if isinstance(o, Expression):
                return {"op": o.op, **o.args}
            if isinstance(o, COMOperation):
                return {"op_id": o.op_id, "kind": o.kind, "params": o.params}
            if isinstance(o, COMPlan):
                return {
                    "plan_id": o.plan_id,
                    "template_id": o.template_id,
                    "target": o.target,
                    "source": o.source,
                    "contract": o.contract,
                    "params": o.params,
                    "operations": [ser(op) for op in o.operations],
                    "lineage": o.lineage,
                }
            if isinstance(o, ExecutionPlan):
                return {
                    "plan_id": o.plan_id,
                    "template_id": o.template_id,
                    "spec": o.spec,
                }
            raise TypeError(type(o))

        grouped_exec: Dict[str, List[Dict[str, Any]]] = {}
        for ep in self.execution_plans:
            grouped_exec.setdefault(ep.runtime, []).append(ser(ep))

        data = {
            "meta": self.meta,
            "ir": {"plans": [ser(p) for p in self.plans]},
            "execution_plans": grouped_exec,
            "dictionaries": self.dictionaries,
            "warnings": self.warnings,
            "errors": self.errors,
        }
        return json.dumps(data, indent=indent)
