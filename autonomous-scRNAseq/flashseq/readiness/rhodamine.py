"""Rhodamine B liquid-handling readiness QC on the BioTek Synergy H1.

Why: before spending irreplaceable single cells, prove the liquid handler dispenses
precisely at the volumes the protocol actually uses. Rhodamine B is a bright, cheap
fluorophore; dispense it at known target volumes into replicate wells, top up to a
constant final volume, read fluorescence, and compute the per-well CV. Precision
(CV) is the readiness gate the user asked for; mean/SD are reported alongside.

Sim vs hardware:
  - sim: `RhodamineSimBackend` injects a modelled true pipetting CV per volume range,
    so the demo shows both READY and NEEDS_CALIBRATION. Liquid-handling ops are real
    PLR chatterbox actions.
  - hardware: swap in `SynergyH1Backend` (see instruments.yaml); the same CV math runs
    on measured RFU. Settings below are threaded to the reader.
"""

from __future__ import annotations

import math
import random
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

from pylabrobot.plate_reading import PlateReaderChatterboxBackend

from ..params import Params


# ----------------------------------------------------------------------------
# Synergy H1 read settings (from readiness.yaml).
# ----------------------------------------------------------------------------
@dataclass
class SynergyH1ReadSettings:
    read_type: str
    optics: str
    excitation_nm: int
    emission_nm: int
    gain: Any            # "extended"/"auto" or an int
    read_height_mm: float

    @staticmethod
    def from_config(cfg: dict) -> "SynergyH1ReadSettings":
        s = cfg["synergy_h1"]
        return SynergyH1ReadSettings(
            read_type=s["read_type"],
            optics=s["optics"],
            excitation_nm=int(s["excitation_nm"]),
            emission_nm=int(s["emission_nm"]),
            gain=s["gain"],
            read_height_mm=float(s["read_height_mm"]),
        )


# ----------------------------------------------------------------------------
# Statistics (no numpy dependency).
# ----------------------------------------------------------------------------
def _mean(xs: List[float]) -> float:
    return sum(xs) / len(xs) if xs else 0.0


def _sd(xs: List[float]) -> float:
    if len(xs) < 2:
        return 0.0
    m = _mean(xs)
    return math.sqrt(sum((x - m) ** 2 for x in xs) / (len(xs) - 1))  # sample SD


def _cv_pct(xs: List[float]) -> float:
    m = _mean(xs)
    return (100.0 * _sd(xs) / m) if m else float("inf")


# ----------------------------------------------------------------------------
# Rhodamine signal model (simulation).
# ----------------------------------------------------------------------------
class RhodamineSimBackend(PlateReaderChatterboxBackend):
    """Plate reader that emits Rhodamine-like RFU from per-well dispensed volume.

    RFU = blank + slope * effective_volume, where effective_volume carries the
    handler's true pipetting error (target * (1 + N(0, true_cv))). slope is scaled
    so the highest target volume lands ~60% of full scale (in-range, not saturating).
    """

    def __init__(
        self,
        high_target_ul: float,
        rfu_full_scale: float = 100000.0,
        rfu_blank: float = 200.0,
        reader_noise_pct: float = 0.5,
        seed: int = 0,
    ) -> None:
        super().__init__()
        self._blank = rfu_blank
        self._slope = (0.60 * rfu_full_scale) / high_target_ul if high_target_ul else 0.0
        self._reader_noise = reader_noise_pct / 100.0
        self._rng = random.Random(seed)
        self._eff_volume: Dict[tuple[int, int], float] = {}  # (row,col0) -> effective uL

    def seed_dispenses(self, well_targets: Dict[tuple[int, int], tuple[float, float]]) -> None:
        """well_targets: (row, col0) -> (target_ul, true_cv_fraction)."""
        for (row, col), (target, cv) in well_targets.items():
            self._eff_volume[(row, col)] = max(0.0, target * (1.0 + self._rng.gauss(0.0, cv)))

    def _rfu(self, row: int, col: int) -> float:
        vol = self._eff_volume.get((row, col))
        if vol is None:
            return self._blank + self._rng.uniform(-2, 2)
        noise = 1.0 + self._rng.gauss(0.0, self._reader_noise)
        return (self._blank + self._slope * vol) * noise

    async def read_fluorescence(  # type: ignore[override]
        self, plate: Any, wells: Any,
        excitation_wavelength: int, emission_wavelength: int, focal_height: float,
    ) -> List[dict]:
        data = [[self._rfu(r, c) for c in range(12)] for r in range(8)]
        return [{"time": 0.0, "temperature": float("nan"), "data": data,
                 "ex_wavelength": excitation_wavelength, "em_wavelength": emission_wavelength}]


# ----------------------------------------------------------------------------
# Report types.
# ----------------------------------------------------------------------------
@dataclass
class RangeResult:
    name: str
    target_ul: float
    n_wells: int
    mean_rfu: float
    sd_rfu: float
    cv_pct: float
    cv_threshold_pct: float
    represents: str

    @property
    def passed(self) -> bool:
        return self.cv_pct <= self.cv_threshold_pct


@dataclass
class ReadinessReport:
    mode: str
    handler_state: str
    settings: SynergyH1ReadSettings
    ranges: List[RangeResult] = field(default_factory=list)

    @property
    def ready(self) -> bool:
        return bool(self.ranges) and all(r.passed for r in self.ranges)

    @property
    def verdict(self) -> str:
        return "READY" if self.ready else "NEEDS_CALIBRATION"

    def summary(self) -> str:
        s = self.settings
        lines = [
            f"Instrument readiness -- Rhodamine B liquid-handling QC ({self.mode})",
            f"Synergy H1: ex {s.excitation_nm} / em {s.emission_nm} nm, gain={s.gain}, "
            f"{s.optics} optics, height {s.read_height_mm} mm",
            "-" * 68,
            f"{'range':8} {'target':>8} {'wells':>6} {'mean RFU':>10} {'CV%':>7} {'thr%':>6}  verdict",
        ]
        for r in self.ranges:
            mark = "PASS" if r.passed else "FAIL"
            lines.append(
                f"{r.name:8} {r.target_ul:>7.2f}u {r.n_wells:>6} {r.mean_rfu:>10.0f} "
                f"{r.cv_pct:>6.2f} {r.cv_threshold_pct:>6.1f}  [{mark}] ({r.represents})"
            )
        lines.append("-" * 68)
        lines.append(f"VERDICT: {self.verdict}")
        if not self.ready:
            lines.append("=> Physical calibration required before running the protocol. "
                         "Check tips, teach points, aspirate/dispense speeds, and channel health.")
        return "\n".join(lines)


# ----------------------------------------------------------------------------
# The readiness check.
# ----------------------------------------------------------------------------
async def _build_setup(p: Params, mode: str, sim_backend: Optional[RhodamineSimBackend]):
    """Minimal deck: tips + a black plate on the Synergy H1."""
    from pylabrobot.liquid_handling import LiquidHandler
    from pylabrobot.plate_reading import PlateReader
    from pylabrobot.resources import (
        PLT_CAR_L5AC_A00, TIP_CAR_480_A00, Cor_96_wellplate_360ul_Fb,
        Microplate_96_Well, hamilton_96_tiprack_50uL,
    )

    from ..automation.backends import make_backends
    bundle = make_backends(p, mode=mode)
    lh = LiquidHandler(backend=bundle.lh_backend, deck=bundle.deck)
    await lh.setup()

    tip_car = TIP_CAR_480_A00(name="rdqc_tips")
    tip_car[0] = tips = hamilton_96_tiprack_50uL(name="rdqc_tips_50")
    bundle.deck.assign_child_resource(tip_car, rails=1)
    plt_car = PLT_CAR_L5AC_A00(name="rdqc_plate_car")
    plt_car[0] = source = Cor_96_wellplate_360ul_Fb(name="rdqc_source")
    bundle.deck.assign_child_resource(plt_car, rails=8)

    if mode == "hardware":
        from pylabrobot.plate_reading import SynergyH1Backend
        pr_backend = SynergyH1Backend()
    else:
        pr_backend = sim_backend
    pr = PlateReader(name="synergy_h1_rdqc", size_x=140, size_y=90, size_z=60, backend=pr_backend)
    await pr.setup()
    black = Microplate_96_Well(name="rdqc_black_plate")
    pr.assign_child_resource(black)
    return lh, tips, source, pr, black


async def run_readiness_check(
    p: Params, mode: str = "sim", handler_state: Optional[str] = None,
) -> ReadinessReport:
    """Run the Rhodamine B liquid-handling readiness QC. REQUIRED before a real run."""
    cfg = p.readiness
    if not cfg:
        raise RuntimeError("readiness.yaml not loaded; instrument-readiness QC config is required.")

    settings = SynergyH1ReadSettings.from_config(cfg)
    sim = cfg.get("simulation", {})
    state = handler_state or sim.get("handler_state", "calibrated")
    true_cv = sim.get("true_cv_pct", {})
    bad_mult = float(sim.get("needs_calibration_multiplier", 3.0))
    ranges_cfg = cfg["volume_ranges"]
    high_target = max(float(r["target_ul"]) for r in ranges_cfg)

    sim_backend = None
    if mode == "sim":
        sim_backend = RhodamineSimBackend(
            high_target_ul=high_target,
            rfu_full_scale=float(sim.get("rfu_full_scale", 100000.0)),
            rfu_blank=float(sim.get("rfu_blank", 200.0)),
            reader_noise_pct=float(sim.get("reader_noise_pct", 0.5)),
            seed=hash(state) & 0xFFFF,
        )
        # Seed per-well effective volumes with the modelled true CV per range.
        well_targets: Dict[tuple[int, int], tuple[float, float]] = {}
        for r in ranges_cfg:
            base_cv = float(true_cv.get(r["name"], 3.0)) / 100.0
            cv = base_cv * (bad_mult if state == "needs_calibration" else 1.0)
            for col1 in r["columns"]:
                for row in range(8):
                    well_targets[(row, col1 - 1)] = (float(r["target_ul"]), cv)
        sim_backend.seed_dispenses(well_targets)

    lh, tips, source, pr, black = await _build_setup(p, mode, sim_backend)

    # Dispense Rhodamine B at each range's target volume into its columns (real PLR ops).
    rhod_src = source["A1:H1"]
    for r in ranges_cfg:
        target = float(r["target_ul"])
        for col1 in r["columns"]:
            dest = source[f"A{col1}:H{col1}"]
            await lh.pick_up_tips(tips["A1:H1"])
            await lh.aspirate(rhod_src, vols=[target] * 8)
            await lh.dispense(dest, vols=[target] * 8)
            await lh.drop_tips(tips["A1:H1"])

    # Read the black plate on the Synergy H1.
    reads = await pr.read_fluorescence(
        excitation_wavelength=settings.excitation_nm,
        emission_wavelength=settings.emission_nm,
        focal_height=settings.read_height_mm,
    )
    rfu = reads if isinstance(reads[0], list) else reads[0]["data"]

    report = ReadinessReport(mode=mode, handler_state=state, settings=settings)
    for r in ranges_cfg:
        vals = [rfu[row][col1 - 1] for col1 in r["columns"] for row in range(8)]
        report.ranges.append(RangeResult(
            name=r["name"], target_ul=float(r["target_ul"]), n_wells=len(vals),
            mean_rfu=_mean(vals), sd_rfu=_sd(vals), cv_pct=_cv_pct(vals),
            cv_threshold_pct=float(r["cv_threshold_pct"]), represents=r.get("represents", ""),
        ))

    await lh.stop()
    return report
