"""QC gates + tacit guards, traced to the WGA [A] and NEBNext [B] protocols.

Gates evaluate simulated (or, on hardware, measured) values and return PASS / FLAG /
FAIL. Guards enforce the protocols' unwritten-but-critical rules -- exact bead ratios,
do-not-overdry beads, on-ice handling, do-not-vortex R2, thermal-mix-not-vortex for
plates with cells, pipet-on-the-wall -- by checking the workflow's parameters and
raising if they drift.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import List

PASS = "PASS"
FLAG = "FLAG"
FAIL = "FAIL"


@dataclass
class QCResult:
    gate: str
    status: str
    detail: str
    flagged_wells: List[str] = field(default_factory=list)

    @property
    def ok(self) -> bool:
        return self.status != FAIL


class GuardViolation(RuntimeError):
    """Raised when a workflow parameter violates a protocol guard (fail closed)."""


# -- Guards (fail closed on protocol violations) ------------------------------

def guard_bead_ratio(stage: str, expected: float, actual: float, tol: float = 1e-6) -> None:
    """SPRI ratios are exact: NEBNext size-selection 0.4X/0.2X, cleanup 0.7X, PCR
    cleanup 0.8X (src: [B]); WGA workflow final pool 0.75X (src: [A])."""
    if abs(expected - actual) > tol:
        raise GuardViolation(
            f"{stage}: SPRI bead ratio {actual} != protocol {expected}. "
            "Bead ratio sets the size cutoff; do not deviate without re-validating."
        )


def guard_no_overdry(stage: str, air_dry_min: float, max_min: float = 5.0) -> str:
    """NEBNext 3A.11/3B.8/5.8: air-dry <= 5 min; elute while beads are dark brown and
    glossy. Over-dried (cracked, light-brown) beads lose yield."""
    if air_dry_min > max_min:
        raise GuardViolation(
            f"{stage}: air-dry {air_dry_min} min exceeds {max_min} min. "
            "Elute while beads are dark brown and glossy; cracked beads lose DNA."
        )
    return (f"{stage}: air-dry <= {max_min} min; elute while beads dark brown + glossy "
            "(do NOT over-dry -- src: [B] cautions).")


def guard_on_ice(step: str) -> str:
    return f"ON ICE: {step} (src: [A] 'Always keep reactions and reagents on ice unless instructed')."


def guard_no_vortex_r2(step: str) -> str:
    return (f"DO NOT vortex R2 Reagent: {step} "
            "(src: [A] Before You Begin -- 'mix all reagents ... except R2').")


def guard_thermal_mix_not_vortex(step: str) -> str:
    return (f"USE THERMAL PLATE MIXER, not a vortex, for plates with cells/lysate: {step} "
            "(src: [A] Best Practices -- gentle/thorough mixing; seal-spin-mix-spin).")


def guard_pipet_on_wall(step: str) -> str:
    return (f"PIPETTE ON THE WELL WALL (avoid touching the cell suspension): {step} "
            "(src: [A] Fig 4 -- dispense droplet on tube wall to avoid material loss).")


# -- Gates (evaluate values) --------------------------------------------------

def gate_wga_yield(yields_ng: dict, p) -> QCResult:
    """Post-WGA QC (src: [A]): flag sample wells below the yield floor.
    yields_ng maps well -> WGA yield (ng). Typical single-cell yield >800 ng."""
    floor = float(p.protocol["wga_qc"]["gates"]["min_yield_ng"])
    flagged = [w for w, y in yields_ng.items() if y < floor]
    status = FLAG if flagged else PASS
    return QCResult(
        gate="WGA yield (Qubit dsDNA)",
        status=status,
        detail=(f"floor {floor} ng; {len(flagged)}/{len(yields_ng)} sample wells below "
                f"(low/failed amplification -- drop or re-run)."),
        flagged_wells=flagged,
    )


def gate_ntc(ntc_yields_ng: dict, p) -> QCResult:
    """NTC contamination gate (src: [A] Best Practices). NTC above the ceiling means
    carryover/contamination -- this FAILS the run (it is the whole point of the NTC)."""
    ceiling = float(p.protocol["wga_qc"]["gates"]["ntc_max_ng"])
    hot = [w for w, y in ntc_yields_ng.items() if y > ceiling]
    status = FAIL if hot else PASS
    return QCResult(
        gate="NTC contamination",
        status=status,
        detail=(f"NTC ceiling {ceiling} ng; {len(hot)}/{len(ntc_yields_ng)} NTC wells above "
                f"(contamination/carryover -- investigate before trusting results)."),
        flagged_wells=hot,
    )


def gate_wga_fragment_size(sizes_bp: dict, p) -> QCResult:
    """WGA product size (src: [A] Appendix A): WGA fragments ~250-3500 bp, avg ~1275 bp.
    Flag wells outside the expected range."""
    lo, hi = [float(x) for x in p.protocol["wga_qc"]["sizing"]["fragment_range_bp"]]
    flagged = [w for w, s in sizes_bp.items() if not (lo <= s <= hi)]
    status = FLAG if flagged else PASS
    return QCResult(
        gate="WGA fragment size (Tapestation HS D5000)",
        status=status,
        detail=(f"expected {int(lo)}-{int(hi)} bp (avg ~1275 bp); "
                f"{len(flagged)}/{len(sizes_bp)} wells out of range."),
        flagged_wells=flagged,
    )


def gate_library_yield(yields_ng: dict, p) -> QCResult:
    """Final library yield (src: [A] Appendix B: 'Lower yields are sufficient for
    successful sequencing'). Flag only near-zero (failed) libraries."""
    flagged = [w for w, y in yields_ng.items() if y < 1.0]
    status = FLAG if flagged else PASS
    return QCResult(
        gate="Library yield (Qubit HS dsDNA)",
        status=status,
        detail=(f"{len(flagged)}/{len(yields_ng)} libraries near-zero (failed); "
                "lower yields are otherwise sufficient for sequencing."),
        flagged_wells=flagged,
    )


@dataclass
class QCReport:
    results: List[QCResult] = field(default_factory=list)
    guards: List[str] = field(default_factory=list)

    def add(self, r: QCResult) -> QCResult:
        self.results.append(r)
        return r

    def note_guard(self, msg: str) -> None:
        self.guards.append(msg)

    @property
    def any_fail(self) -> bool:
        return any(r.status == FAIL for r in self.results)
