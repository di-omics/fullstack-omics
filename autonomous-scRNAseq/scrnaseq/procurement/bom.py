"""Build a non-orderable functional checklist for scRNA-seq planning."""

from __future__ import annotations

from dataclasses import dataclass

from ..params import Params


@dataclass
class BomItem:
    name: str
    category: str = "functional requirement"
    quantity: str = "define in validated local profile"
    vendor: str = ""
    catalog: str = ""
    channel: str | None = None
    channel_reason: str = ""
    verify: bool = True
    verify_note: str = "Laboratory-controlled definition required."
    optional: bool = False


def build_bom(p: Params, n_cells: int | None = None) -> list[BomItem]:
    """Return functional requirements without suppliers, SKUs, or quantities."""
    del n_cells
    return [BomItem(name=item["name"]) for item in p.reagents["requirements"]]
