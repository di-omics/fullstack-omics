"""Build the Bill of Materials, scaled to N samples, from reagents.yaml.

The nice part (per the user): this workflow is KIT-based, so procurement is mostly
"buy the kit." Scaling rules:
  per_kit    -> ceil(n / plate_capacity) kits (one kit = 96 reactions)
  per_plate  -> one unit per plate
  per_sample -> one unit per sample
  per_run    -> one bulk unit (covers many runs)
  once       -> one-time purchase (e.g. magnet, instrument)
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

from ..params import Params


@dataclass
class BomItem:
    name: str
    vendor: str
    catalog: str
    category: str
    scale: str
    quantity: str
    channel: Optional[str] = None
    channel_reason: str = ""
    verify: bool = False
    verify_note: str = ""
    optional: bool = False
    notes: str = ""


# reagents.yaml list-key -> human category label.
_CATEGORIES = [
    ("wga_kit", "Single-cell WGA kit"),
    ("libprep_kit", "Library prep kit (NEBNext Ultra II)"),
    ("qc_reagents", "Sample & library QC"),
    ("readiness_reagents", "Instrument readiness (Rhodamine B QC)"),
    ("wga_accessories", "WGA accessories / consumables"),
    ("consumables", "General consumables"),
    ("sorter_consumables", "FACS Melody sorter consumables"),
]


def _quantity(p: Params, scale: str, n: int) -> str:
    if scale == "per_kit":
        k = p.n_kits(n)
        return f"{k} kit(s) (1 kit = {p.plate_capacity} rxn)"
    if scale == "per_plate":
        return f"{p.n_plates(n)} plate-unit(s)"
    if scale == "per_sample":
        return f"{n} unit(s)"
    if scale == "per_run":
        return "1 bulk unit (covers many runs)"
    if scale == "once":
        return "1 (one-time purchase)"
    return "qty TBD"


def build_bom(p: Params, n_samples: Optional[int] = None) -> list[BomItem]:
    """Return the full kit-based BOM as a flat list of BomItem."""
    n = p.n_samples if n_samples is None else n_samples
    items: list[BomItem] = []

    for key, category in _CATEGORIES:
        for r in p.reagents.get(key, []):
            scale = r.get("scale", "per_run")
            items.append(
                BomItem(
                    name=r["name"],
                    vendor=r.get("vendor", "# TODO: expert value"),
                    catalog=r.get("catalog", "# TODO: expert value"),
                    category=category,
                    scale=scale,
                    quantity=_quantity(p, scale, n),
                    channel=r.get("purchase_channel"),
                    channel_reason=(
                        "Explicit purchase channel from the reagent configuration."
                        if r.get("purchase_channel") else ""
                    ),
                    verify=bool(r.get("verify", False)),
                    verify_note=r.get("verify_note", ""),
                    optional=bool(r.get("optional", False)),
                    notes=r.get("note", ""),
                )
            )

    return items
