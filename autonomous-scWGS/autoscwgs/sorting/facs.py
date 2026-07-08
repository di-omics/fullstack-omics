"""BD FACS Melody single-cell sort -- the front of the workflow.

The whole-genome sequencing protocol starts with cells sorted into 3 uL of Cell Buffer per well
(FACS/FANS), with column 1 reserved for controls (NTC / 1 ng / 100 pg / 10 pg gDNA)
per the protocol's plate map (Figure 5). src: [A] Single-Cell Isolation + Best Practices.

The BD FACS Melody is NOT a PyLabRobot device: BD FACSChorus is a closed GUI with no
open API, so its control plane is reverse-engineered with computer vision + UI
automation of FACSChorus (di-omics/lab-cv + awesome-wetlab-cv). So:
  - `FacsMelodySimBackend` SIMULATES a sort: it deposits one cell per sample well with
    a modelled sort efficiency (some wells miss -> realistic drop-outs), and places the
    control wells exactly per the protocol map.
  - `CellSorterBackend` is the seam to drop in the real Melody control client once the
    RE is done (`sort()` raises NotImplementedError there until wired).

Nothing here invents protocol values: the control layout + buffer volume come from
protocol_params.yaml; the sort *efficiency* is a sim knob (clearly labelled), not a
protocol value.
"""

from __future__ import annotations

import random
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Dict, List, Optional

from ..params import Params

_ROWS = "ABCDEFGH"


def _well(row0: int, col1: int) -> str:
    return f"{_ROWS[row0]}{col1}"


@dataclass
class WellPlan:
    """What each well is supposed to receive before sorting."""
    controls: Dict[str, str]          # well -> control type (e.g. "NTC", "1ng")
    sample_wells: List[str]           # wells that should each receive one sorted cell
    cell_buffer_volume_ul: float

    @property
    def n_sample_wells(self) -> int:
        return len(self.sample_wells)


def plan_plate(p: Params, n_samples: Optional[int] = None) -> WellPlan:
    """Build the 96-well plan: control wells (col 1) + sample wells (cols 2-12).

    Controls come first; sample wells fill the remaining wells column-major up to
    n_samples (or the plate). src: [A] Figure 5.
    """
    sc = p.protocol["sorting"]
    cap = p.plate_capacity
    n = p.n_samples if n_samples is None else n_samples

    controls = {c["well"]: c["type"] for c in sc.get("controls", [])}
    control_wells = set(controls)

    # Column-major ordering of all wells (A1,B1,..H1,A2,..).
    all_wells = [_well(r, c) for c in range(1, 13) for r in range(8)]
    free = [w for w in all_wells if w not in control_wells]
    sample_wells = free[: max(0, min(n, cap) - 0)]
    # If the user asked for more samples than free wells, cap at free wells.
    sample_wells = sample_wells[: len(free)]

    return WellPlan(
        controls=controls,
        sample_wells=sample_wells,
        cell_buffer_volume_ul=float(sc["cell_buffer_volume_ul"]),
    )


@dataclass
class SortResult:
    mode: str
    plan: WellPlan
    wells_with_cell: List[str] = field(default_factory=list)
    missed_wells: List[str] = field(default_factory=list)
    sort_efficiency_pct: float = 0.0
    events: List[str] = field(default_factory=list)

    @property
    def n_deposited(self) -> int:
        return len(self.wells_with_cell)

    def summary(self) -> str:
        lines = [
            f"FACS Melody sort ({self.mode}) -- single-cell isolation (Stage 0 sort)",
            "-" * 64,
            f"Control wells (col 1): {', '.join(f'{w}:{t}' for w, t in self.plan.controls.items())}",
            f"Sample wells requested: {self.plan.n_sample_wells} "
            f"(3 uL Cell Buffer/well)",
            f"Cells deposited: {self.n_deposited}/{self.plan.n_sample_wells} "
            f"(sort efficiency {self.sort_efficiency_pct:.1f}%)",
        ]
        if self.missed_wells:
            preview = ", ".join(self.missed_wells[:8])
            more = "" if len(self.missed_wells) <= 8 else f" (+{len(self.missed_wells)-8} more)"
            lines.append(f"Missed wells (no cell -- expected drop-outs): {preview}{more}")
        return "\n".join(lines)


class CellSorterBackend(ABC):
    """Seam for a real BD FACS Melody control client (RE pending)."""

    name = "cell_sorter"

    @abstractmethod
    async def sort(self, plan: WellPlan) -> SortResult:
        ...


class FacsMelodySimBackend(CellSorterBackend):
    """Simulates a Melody index sort: one cell per sample well at a modelled efficiency."""

    name = "facs_melody_sim"

    def __init__(self, sort_efficiency: float = 0.9, seed: int = 0) -> None:
        # sort_efficiency is a SIM knob (fraction of target wells that actually receive
        # a viable cell). NOT a protocol value.
        self._eff = max(0.0, min(1.0, sort_efficiency))
        self._rng = random.Random(seed)

    async def sort(self, plan: WellPlan) -> SortResult:
        res = SortResult(mode="sim", plan=plan)
        res.events.append(
            f"[sim] BD FACS Melody: index-sort {plan.n_sample_wells} single cells into "
            f"{plan.cell_buffer_volume_ul} uL Cell Buffer/well (cols 2-12)."
        )
        res.events.append(
            f"[sim] control wells pre-loaded (col 1): "
            f"{', '.join(f'{w}={t}' for w, t in plan.controls.items())}"
        )
        for w in plan.sample_wells:
            if self._rng.random() <= self._eff:
                res.wells_with_cell.append(w)
            else:
                res.missed_wells.append(w)
        got = res.n_deposited
        res.sort_efficiency_pct = (100.0 * got / plan.n_sample_wells) if plan.n_sample_wells else 0.0
        res.events.append(f"[sim] deposited {got} cells; {len(res.missed_wells)} wells missed.")
        return res


class FacsMelodyHardwareBackend(CellSorterBackend):  # pragma: no cover - RE pending
    """Real BD FACS Melody -- driven by CV/UI automation of the FACSChorus GUI."""

    name = "facs_melody_hardware"

    async def sort(self, plan: WellPlan) -> SortResult:
        raise NotImplementedError(
            "FACS Melody hardware control is not wired yet. BD FACSChorus has no open API, "
            "so the plan is to drive it with computer vision + UI automation (see the "
            "di-omics CV stack: github.com/di-omics/lab-cv and github.com/di-omics/"
            "awesome-wetlab-cv). Wire that client here, then set instruments.yaml "
            "facs_melody.plr.backend_hardware."
        )


def make_sorter(mode: str = "sim", *, sort_efficiency: float = 0.9, seed: int = 0) -> CellSorterBackend:
    if mode == "sim":
        return FacsMelodySimBackend(sort_efficiency=sort_efficiency, seed=seed)
    if mode == "hardware":
        return FacsMelodyHardwareBackend()
    raise ValueError(f"Unknown sorter mode {mode!r}; expected 'sim' or 'hardware'.")


async def run_sort(p: Params, mode: str = "sim", n_samples: Optional[int] = None,
                   sort_efficiency: float = 0.9) -> SortResult:
    """Plan the plate and run (or simulate) the FACS Melody sort."""
    plan = plan_plate(p, n_samples=n_samples)
    sorter = make_sorter(mode, sort_efficiency=sort_efficiency, seed=plan.n_sample_wells)
    return await sorter.sort(plan)
