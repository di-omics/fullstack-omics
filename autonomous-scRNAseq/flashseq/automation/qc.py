"""QC gates + tacit guards, all traced to the protocol.

Gates evaluate simulated (or, on hardware, measured) values and return PASS / FLAG /
FAIL. Guards enforce the protocol's unwritten-but-critical rules -- exact bead
ratios, do-not-overdry beads, on-ice handling, do-not-re-chill after SDS -- by
checking the workflow's own parameters and raising if they drift from the protocol.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import List, Optional

PASS = "PASS"
FLAG = "FLAG"
FAIL = "FAIL"


@dataclass
class QCResult:
    gate: str
    status: str
    detail: str
    flagged_wells: List[int] = field(default_factory=list)

    @property
    def ok(self) -> bool:
        return self.status != FAIL


class GuardViolation(RuntimeError):
    """Raised when a workflow parameter violates a protocol guard (fail closed)."""


# -- Guards (fail closed on protocol violations) ------------------------------

def guard_bead_ratio(stage: str, expected: float, actual: float, tol: float = 1e-6) -> None:
    """SPRI ratios are exact in this protocol: 0.6x cDNA cleanup, 0.8x library cleanup."""
    if abs(expected - actual) > tol:
        raise GuardViolation(
            f"{stage}: SPRI bead ratio {actual} != protocol {expected}. "
            "Bead ratio sets the size cutoff; do not deviate without re-validating."
        )


def guard_no_overdry(stage: str, ethanol_wash: bool, dry_min: Optional[float]) -> str:
    """cDNA cleanup: NO ethanol wash, resuspend before the pellet dries (Stage 5).
    Library cleanup: dry only ~2 min 'until small cracks appear' (Stage 10)."""
    if not ethanol_wash:
        return (f"{stage}: no ethanol wash; resuspend immediately -- "
                "'Do not let the bead pellet dry completely' (over-drying lowers yield).")
    if dry_min is not None and dry_min > 3:
        raise GuardViolation(
            f"{stage}: dry time {dry_min} min is too long. Protocol dries ~2 min "
            "'until small cracks appear'; over-dried beads crack and lose library."
        )
    return f"{stage}: ethanol wash then dry ~{dry_min} min until small cracks (do not over-dry)."


def guard_on_ice(step: str) -> str:
    return f"ON ICE / cool rack: {step} (keep cold to preserve RNA / RT activity)."


def guard_no_rechill(step: str) -> str:
    return f"DO NOT re-chill after SDS neutralization: {step} (Stage 9 -- keep at RT)."


# -- Gates (evaluate values) --------------------------------------------------

def gate_cdna_size(avg_sizes_kb: List[float], p) -> QCResult:
    """Stage 6: cDNA average 1.8-2.2 kb; flag wells with size < 400 bp."""
    g = p.protocol["cdna_qc"]["gates"]
    lo, hi = float(g["cdna_size_kb_min"]), float(g["cdna_size_kb_max"])
    below_bp = float(g["flag_below_bp"])
    flagged = [i for i, s in enumerate(avg_sizes_kb) if s * 1000.0 < below_bp]
    in_range = [lo <= s <= hi for s in avg_sizes_kb]
    n_ok = sum(in_range)
    status = FLAG if flagged or n_ok < len(avg_sizes_kb) else PASS
    return QCResult(
        gate="cDNA size (Bioanalyzer HS)",
        status=status,
        detail=(f"{n_ok}/{len(avg_sizes_kb)} wells in {lo}-{hi} kb; "
                f"{len(flagged)} wells <{int(below_bp)} bp (degraded/failed)."),
        flagged_wells=flagged,
    )


def gate_picogreen(concentrations_pg_per_ul: List[float], p) -> QCResult:
    """Stage 7/8: need >= 100 pg/uL to normalize down to the 100 pg/uL target.
    Wells below target cannot be normalized up and are flagged as insufficient."""
    target = float(p.protocol["normalization"]["target_concentration_pg_per_ul"])
    flagged = [i for i, c in enumerate(concentrations_pg_per_ul) if c < target]
    status = FLAG if flagged else PASS
    return QCResult(
        gate="PicoGreen cDNA quant",
        status=status,
        detail=(f"target {target} pg/uL; {len(flagged)}/{len(concentrations_pg_per_ul)} "
                f"wells below target (cannot normalize up -- drop or re-amplify)."),
        flagged_wells=flagged,
    )


def gate_library_size(avg_sizes_bp: List[float], p) -> QCResult:
    """Stage 9/10: libraries ~700-1000 bp (target ~800); flag > 1000 bp (won't bind flow cell)."""
    lc = p.protocol["library_cleanup"]["qc"]
    lo, hi = [float(x) for x in lc["library_size_bp_range"]]
    flag_above = float(lc["flag_above_bp"])
    flagged = [i for i, s in enumerate(avg_sizes_bp) if s > flag_above]
    in_range = sum(lo <= s <= hi for s in avg_sizes_bp)
    status = FLAG if flagged or in_range < len(avg_sizes_bp) else PASS
    return QCResult(
        gate="Library size (Bioanalyzer HS)",
        status=status,
        detail=(f"{in_range}/{len(avg_sizes_bp)} wells in {int(lo)}-{int(hi)} bp; "
                f"{len(flagged)} wells >{int(flag_above)} bp (poor flow-cell binding)."),
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
