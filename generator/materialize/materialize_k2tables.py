"""K2 table descriptor materialization.

Generate one ``<CanonicalTable>.k2table.xml`` file per canonical table that has
Broadway implementation output in the current IR bundle.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any, Dict, List
import xml.etree.ElementTree as ET
from xml.dom import minidom

from ..ddl.ddl_parser import parse_ddl_file
from ..ddl.schema_model import Schema


def _default_canonical_ddl_path() -> Path:
    return Path(__file__).resolve().parents[2] / "metadata" / "tmf.sql"


def _normalize_datatype(raw: str) -> str:
    t = (raw or "").strip().upper()
    if "INT" in t:
        return "INTEGER"
    if any(x in t for x in ("CHAR", "CLOB", "TEXT")):
        return "TEXT"
    if any(x in t for x in ("REAL", "FLOA", "DOUB", "DEC", "NUM")):
        return "REAL"
    if "BLOB" in t:
        return "BLOB"
    return "TEXT"


def _pretty_xml(root: ET.Element) -> str:
    raw = ET.tostring(root, encoding="utf-8")
    doc = minidom.parseString(raw)
    pretty = doc.toprettyxml(indent="  ", encoding="utf-8")
    return pretty.decode("utf-8")


def _collect_broadway_table_meta(ir_data: Dict[str, Any]) -> Dict[str, Dict[str, Any]]:
    out: Dict[str, Dict[str, Any]] = {}
    bplans = (ir_data.get("execution_plans", {}) or {}).get("broadway", []) or []
    for p in bplans:
        spec = p.get("spec", {}) or {}
        load = spec.get("load", {}) or {}
        table = load.get("target_table")
        if not table:
            continue
        if table not in out:
            out[table] = {
                "target_interface": load.get("target_interface"),
                "target_schema": load.get("target_schema"),
            }
    return out


def _build_k2table_xml(
    table_name: str,
    canonical_schema: Schema,
    keys: List[str],
    interface_name: str,
    source_schema_name: str,
    timestamp: str,
) -> str:
    table = canonical_schema.get_table(table_name)
    if not table:
        raise ValueError(f"Canonical table '{table_name}' not found in DDL")

    root = ET.Element(
        "TableObject",
        attrib={
            "xmlns:xsi": "http://www.w3.org/2001/XMLSchema-instance",
            "xmlns:xsd": "http://www.w3.org/2001/XMLSchema",
        },
    )
    ET.SubElement(root, "Name").text = table_name
    ET.SubElement(root, "ID").text = f"tbl_{table_name}"

    columns_el = ET.SubElement(root, "Columns")
    for idx, col in enumerate(table.columns.values()):
        attrs: Dict[str, str] = {
            "name": col.name,
            "id": col.name,
            "index": str(idx),
            "datatype": _normalize_datatype(col.datatype),
        }
        is_mandatory = (col.name in keys) or (not col.nullable)
        if is_mandatory:
            attrs["mandatory"] = "true"
        ET.SubElement(columns_el, "Column", attrib=attrs)

    indexes_el = ET.SubElement(root, "IndexesList")
    if keys:
        ET.SubElement(
            indexes_el,
            "Index",
            attrib={
                "id": "1",
                "pk": "true",
                "unique": "true",
                "instanceOnly": "true",
                "columnsIdsList": ",".join(keys),
            },
        )

    ET.SubElement(root, "EnrichmentList")

    ldu = ET.SubElement(root, "LazyDataUpdate", attrib={"syncMethod": "Inherited", "performEvery": "1.00:00:00"})
    ET.SubElement(ldu, "DecisionFunction").text = ""

    ET.SubElement(root, "TriggersList")

    based_on = ET.SubElement(root, "BasedOn")
    source = ET.SubElement(
        based_on,
        "Source",
        attrib={
            "interface": interface_name,
            "schema": source_schema_name,
            "table": table_name,
            "timestamp": timestamp,
        },
    )
    ET.SubElement(source, "ColumnsList").text = ",".join([c.name for c in table.columns.values()])

    return _pretty_xml(root)


def materialize_k2tables(
    ir_data: Dict[str, Any],
    out_dir: Path,
    canonical_ddl_path: Path | None = None,
) -> List[str]:
    """Materialize K2 table descriptors for Broadway target canonical tables."""
    cddl = canonical_ddl_path or _default_canonical_ddl_path()
    canonical = parse_ddl_file(Path(cddl), "canonical")

    meta = ir_data.get("meta", {}) or {}
    generated_at = str(meta.get("generated_at") or "")
    timestamp = generated_at[:10] if len(generated_at) >= 10 else ""
    if not timestamp:
        timestamp = "1970-01-01"

    table_meta = _collect_broadway_table_meta(ir_data)
    if not table_meta:
        return []

    out_dir.mkdir(parents=True, exist_ok=True)
    for existing in out_dir.glob("*.k2table.xml"):
        if existing.is_file():
            existing.unlink()

    generated: List[str] = []
    for table_name in sorted(table_meta.keys()):
        m = table_meta[table_name]
        interface_name = str(m.get("target_interface") or "TMF_CUSTOMER_CANONICAL")
        source_schema_name = str(m.get("target_schema") or "main")
        table = canonical.get_table(table_name)
        ddl_keys = list(table.primary_key.columns) if table else []
        xml_text = _build_k2table_xml(
            table_name=table_name,
            canonical_schema=canonical,
            keys=ddl_keys,
            interface_name=interface_name,
            source_schema_name=source_schema_name,
            timestamp=timestamp,
        )
        out_file = out_dir / f"{table_name}.k2table.xml"
        out_file.write_text(xml_text, encoding="utf-8")
        generated.append(str(out_file))

    return generated
