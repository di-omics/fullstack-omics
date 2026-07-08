"""Build the Bill of Materials, scaled to N cells, from reagents.yaml + protocol_params.yaml.

Scaling rules (all quantities trace to the protocol):
  by_volume  -> total uL consumed = per-well volume (scaled to plate format) x
                wells x (1 + overage). Reported as consumed volume; pack counts
                are left null because pack sizes are not in the protocol.
  per_plate  -> one unit per plate (plate = plate_format wells).
  per_sample -> one unit per cell.
  per_run    -> one bulk unit (note: covers many runs).
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from typing import Any, Optional

from ..params import Params


@dataclass
class BomItem:
    name: str
    vendor: str
    catalog: str
    category: str
    scale: str
    quantity: str                     # human-readable quantity for this run
    required_detail: str = ""         # e.g. "3.30 uL consumed (0.240 uL/well x ...)"
    channel: Optional[str] = None     # filled by channels.route_channels()
    channel_reason: str = ""
    verify: bool = False
    verify_note: str = ""
    optional: bool = False
    notes: str = ""


def _component_volume_384(p: Params, component_name: str) -> Optional[float]:
    """Sum a component's 384-well per-well volume across BOTH mixes.

    Shared reagents (RNase inhibitor, Betaine) appear in the lysis mix AND the
    RT-PCR mix, so their per-run consumption is the sum of both usages.
    """
    total = 0.0
    found = False
    for mix_key, comp_key in (("lysis_mix", "components"), ("rt_pcr", "mix_components")):
        for comp in p.protocol[mix_key][comp_key]:
            if comp["name"] == component_name:
                total += float(comp["volume_ul_384"])
                found = True
    return total if found else None


def _enrichment_reaction_volume_384(p: Params) -> float:
    """Total enrichment-PCR reaction volume (384 base) = sum of the added volumes.
    Used to estimate 0.8x SPRI bead usage for library cleanup, since the protocol
    cleans 'an aliquot' without fixing the aliquot volume."""
    t = p.protocol["tagmentation"]
    return (
        float(t["tagmentation_mix_total_ul_384"])
        + float(t["normalized_cdna_input_ul_384"])
        + float(t["neutralization"]["sds_volume_ul_384"])
        + float(t["indexing"]["index_adaptor_volume_ul_384"])
        + float(t["indexing"]["npm_volume_ul_384"])
    )


def _bead_volume_per_well_384(p: Params) -> tuple[float, str]:
    """Total SPRI bead volume per well (384 base): 0.6x cDNA cleanup + 0.8x library cleanup."""
    cdna_beads = float(p.protocol["cdna_cleanup"]["beads_volume_ul_384"])   # 9.0 (=0.6x of 15)
    lib_ratio = float(p.protocol["library_cleanup"]["bead_ratio"])          # 0.8
    lib_beads = round(lib_ratio * _enrichment_reaction_volume_384(p), 3)
    total = round(cdna_beads + lib_beads, 3)
    detail = (
        f"{cdna_beads} uL/well (0.6x cDNA cleanup) + {lib_beads} uL/well "
        f"(0.8x of {_enrichment_reaction_volume_384(p)} uL enrichment rxn, aliquot=full rxn assumed)"
    )
    return total, detail


def _n_plates(p: Params, n: int) -> int:
    return max(1, math.ceil(n / p.plate_format))


def _by_volume_quantity(p: Params, reagent: dict[str, Any], n: int) -> tuple[str, str]:
    mapped = reagent.get("maps_to")
    if mapped == "__beads__":
        per_well_384, detail = _bead_volume_per_well_384(p)
    else:
        per_well_384 = _component_volume_384(p, mapped) if mapped else None
        detail = ""
    if per_well_384 is None:
        return ("qty TBD", "# TODO: expert value -- no per-well volume mapped for this reagent")
    per_well = p.scale_volume(per_well_384)
    total_ul = round(per_well * p.wells_with_overage(n), 2)
    total_ml = round(total_ul / 1000.0, 3)
    detail = detail or f"{per_well} uL/well x {n} wells + {int(p.overage*100)}% overage"
    return (f"{total_ul} uL (~{total_ml} mL) consumed", detail)


def build_bom(p: Params, n_cells: Optional[int] = None) -> list[BomItem]:
    """Return the full scaled BOM as a flat list of BomItem."""
    n = p.n_cells if n_cells is None else n_cells
    n_plates = _n_plates(p, n)
    items: list[BomItem] = []

    # Reagent categories that live in reagents.yaml as lists.
    list_categories = [
        ("lysis_reagents", "Lysis mix"),
        ("rt_pcr_reagents", "RT-PCR mix"),
        ("bead_reagents", "Magnetic beads"),
        ("qc_reagents", "QC"),
        ("readiness_reagents", "Instrument readiness (Rhodamine B QC)"),
        ("tagmentation_reagents", "Tagmentation / indexing"),
        ("consumables", "Consumables"),
        ("oligos_rt_pcr", "Custom oligos (RT-PCR)"),
    ]

    for key, category in list_categories:
        for r in p.reagents.get(key, []):
            scale = r.get("scale", "per_run")
            if scale == "by_volume":
                qty, detail = _by_volume_quantity(p, r, n)
            elif scale == "per_plate":
                qty, detail = f"{n_plates} plate-unit(s)", f"{n} wells / {p.plate_format} per plate"
            elif scale == "per_sample":
                qty, detail = f"{n} unit(s)", "one per cell/sample"
            elif scale == "per_run":
                qty, detail = "1 bulk unit", "bulk reagent; one unit covers many runs"
            else:  # custom oligo synthesis
                qty, detail = "1 synthesis order", "custom oligo"
            items.append(
                BomItem(
                    name=r["name"],
                    vendor=r.get("vendor", "# TODO: expert value"),
                    catalog=r.get("catalog", "# TODO: expert value"),
                    category=category,
                    scale=scale,
                    quantity=qty,
                    required_detail=detail,
                    verify=bool(r.get("verify", False)),
                    verify_note=r.get("verify_note", ""),
                    optional=bool(r.get("optional", False)),
                    notes=r.get("note", ""),
                )
            )

    # Extra enrichment index oligos (optional, sequences omitted from OCR).
    extra = p.reagents.get("oligos_enrichment_extra")
    if extra:
        items.append(
            BomItem(
                name=f"Nextera extra index set ({extra['i7_count']} i7 + {extra['i5_count']} i5)",
                vendor="Any oligo provider (IDT)",
                catalog="custom",
                category="Custom oligos (enrichment, optional)",
                scale="once",
                quantity="1 synthesis order (optional)",
                required_detail=f"working dilution plates at {extra['working_conc_uM']} uM each",
                verify=bool(extra.get("verify", False)),
                verify_note=extra.get("verify_note", ""),
                optional=True,
            )
        )

    return items
