"""Schema model produced from DDL parsing.

This is intentionally simplified and engine-neutral:
- Tables
- Columns
- Primary keys
- (Optional) foreign keys and unique constraints

The validator uses this model to confirm that the Excel spec references real tables/columns.
"""

from __future__ import annotations
from dataclasses import dataclass, field
from typing import Dict, List, Optional

@dataclass(frozen=True)
class Column:
    name: str
    datatype: str
    nullable: bool = True

@dataclass(frozen=True)
class PrimaryKey:
    columns: List[str] = field(default_factory=list)

@dataclass(frozen=True)
class ForeignKey:
    from_column: str
    to_table: str
    to_column: str

@dataclass
class Table:
    name: str
    columns: Dict[str, Column] = field(default_factory=dict)
    primary_key: PrimaryKey = field(default_factory=PrimaryKey)
    foreign_keys: List[ForeignKey] = field(default_factory=list)

    def has_column(self, col: str) -> bool:
        return col.lower() in {c.lower() for c in self.columns.keys()}

    def get_column(self, col: str) -> Column | None:
        for k, v in self.columns.items():
            if k.lower() == col.lower():
                return v
        return None

@dataclass
class Schema:
    """A parsed schema: a registry of tables by name."""
    name: str
    tables: Dict[str, Table] = field(default_factory=dict)

    def get_table(self, name: str) -> Table | None:
        for k, v in self.tables.items():
            if k.lower() == name.lower():
                return v
        return None
