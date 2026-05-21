"""Join-key notation parser/validator helpers.

Supported operators:
- '->'   : intra-system join intent
- '-->'  : cross-system bridge intent
"""

from __future__ import annotations

from collections import deque
import re
from typing import Dict, Any, List, Optional, Tuple

from .ddl.schema_model import Schema, Table

_JOIN_OP_RE = re.compile(r"\s*(-->|->)\s*")


def normalize_system_name(name: Optional[str]) -> Optional[str]:
    if not name:
        return None
    s = str(name).strip()
    if not s:
        return None
    u = s.upper()
    return u[:-7] if u.endswith("_SYSTEM") else u


def parse_join_key(join_key: str) -> Dict[str, Any]:
    raw = (join_key or "").strip().replace("→", "->")
    parts = _JOIN_OP_RE.split(raw)
    if not parts or not parts[0].strip():
        return {"nodes": [], "ops": [], "errors": ["empty join_key"]}
    nodes_raw = parts[0::2]
    ops = parts[1::2]
    nodes = [parse_join_node(x.strip()) for x in nodes_raw]
    errors: List[str] = []
    if len(nodes) < 2:
        errors.append("join_key must contain at least two nodes")
    if len(ops) != len(nodes) - 1:
        errors.append("invalid operator/node sequence")
    return {"nodes": nodes, "ops": ops, "errors": errors}


def parse_join_node(token: str) -> Dict[str, Any]:
    parts = [p.strip() for p in token.split(".") if p.strip()]
    if len(parts) == 3:
        return {"kind": "qualified", "system": parts[0], "table": parts[1], "column": parts[2], "raw": token}
    if len(parts) == 2:
        return {"kind": "table_col", "system": None, "table": parts[0], "column": parts[1], "raw": token}
    if len(parts) == 1:
        return {"kind": "context_col", "system": None, "table": None, "column": parts[0], "raw": token}
    return {"kind": "invalid", "system": None, "table": None, "column": None, "raw": token}


def resolve_node(node: Dict[str, Any], ep_source_system: str, sources: Dict[str, Schema]) -> Dict[str, Any]:
    if node["kind"] == "context_col":
        return {"ok": True, "system": None, "table": None, "column": node["column"], "node": node}
    if node["kind"] == "invalid":
        return {"ok": False, "error": f"invalid node '{node.get('raw')}'", "node": node}

    nsys = normalize_system_name(node.get("system"))
    if nsys:
        schema = _schema_by_system(sources, nsys)
        if not schema:
            return {"ok": False, "error": f"unknown system '{node.get('system')}'", "node": node}
        table = schema.get_table(node["table"])
        if not table:
            return {"ok": False, "error": f"table '{node['table']}' not found in system '{nsys}'", "node": node}
        if not table.get_column(node["column"]):
            return {"ok": False, "error": f"column '{node['column']}' not found in {nsys}.{table.name}", "node": node}
        return {"ok": True, "system": nsys, "table": table.name, "column": node["column"], "node": node}

    ep_sys = normalize_system_name(ep_source_system) or ""
    ep_schema = _schema_by_system(sources, ep_sys)
    if ep_schema:
        table = ep_schema.get_table(node["table"])
        if table and table.get_column(node["column"]):
            return {"ok": True, "system": ep_sys, "table": table.name, "column": node["column"], "node": node}

    for k, schema in sources.items():
        sk = normalize_system_name(k) or ""
        table = schema.get_table(node["table"])
        if table and table.get_column(node["column"]):
            return {"ok": True, "system": sk, "table": table.name, "column": node["column"], "node": node}

    return {"ok": False, "error": f"could not resolve node '{node.get('raw')}'", "node": node}


def table_path_exists(schema: Schema, start_table: str, end_table: str) -> bool:
    return bool(find_table_path(schema, start_table, end_table))


def find_table_path(schema: Schema, start_table: str, end_table: str) -> List[str]:
    if start_table.lower() == end_table.lower():
        return [start_table]
    graph = _build_table_graph(schema)
    st = _norm_table_name(schema, start_table)
    en = _norm_table_name(schema, end_table)
    if not st or not en:
        return []
    q = deque([st])
    prev: Dict[str, Optional[str]] = {st: None}
    while q:
        cur = q.popleft()
        if cur.lower() == en.lower():
            break
        for nxt in graph.get(cur, []):
            if nxt not in prev:
                prev[nxt] = cur
                q.append(nxt)
    if en not in prev:
        return []
    out: List[str] = []
    cur: Optional[str] = en
    while cur is not None:
        out.append(cur)
        cur = prev[cur]
    out.reverse()
    return out


def join_condition(schema: Schema, left_table: str, right_table: str) -> Optional[Tuple[str, str]]:
    lt = schema.get_table(left_table)
    rt = schema.get_table(right_table)
    if not lt or not rt:
        return None
    for fk in lt.foreign_keys:
        if fk.to_table.lower() == rt.name.lower():
            return (f"{lt.name}.{fk.from_column}", f"{rt.name}.{fk.to_column}")
    for fk in rt.foreign_keys:
        if fk.to_table.lower() == lt.name.lower():
            return (f"{lt.name}.{fk.to_column}", f"{rt.name}.{fk.from_column}")

    # Fallback: common column names.
    lcols = {c.lower(): c for c in lt.columns.keys()}
    rcols = {c.lower(): c for c in rt.columns.keys()}
    common = sorted(set(lcols.keys()) & set(rcols.keys()))
    if common:
        c = common[0]
        return (f"{lt.name}.{lcols[c]}", f"{rt.name}.{rcols[c]}")
    return None


def _build_table_graph(schema: Schema) -> Dict[str, List[str]]:
    graph: Dict[str, List[str]] = {t.name: [] for t in schema.tables.values()}
    for t in schema.tables.values():
        for fk in t.foreign_keys:
            rt = schema.get_table(fk.to_table)
            if not rt:
                continue
            if rt.name not in graph[t.name]:
                graph[t.name].append(rt.name)
            if t.name not in graph[rt.name]:
                graph[rt.name].append(t.name)
    return graph


def _norm_table_name(schema: Schema, table_name: str) -> Optional[str]:
    t = schema.get_table(table_name)
    return t.name if t else None


def _schema_by_system(sources: Dict[str, Schema], system: str) -> Optional[Schema]:
    ns = normalize_system_name(system)
    for k, s in sources.items():
        if normalize_system_name(k) == ns:
            return s
    return None
