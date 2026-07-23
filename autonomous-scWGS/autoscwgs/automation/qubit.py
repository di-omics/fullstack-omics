"""A dsDNA (Qubit / Quant-iT HS) signal model so quant/QC are meaningful in sim.

The WGA workflow quantifies both the amplification product and the final libraries with a
Qubit fluorometric dsDNA HS assay. The user's deck reads that chemistry on the BioTek
Synergy H1 instead of a Qubit fluorometer -- which requires a standard curve. This
module models exactly that:
  1. seed a deterministic ground-truth concentration (ng/uL) per well,
  2. lay down a dsDNA standard series in known wells,
  3. return RFU = blank + slope * conc (+ small noise) for every well,
  4. let the workflow fit the standard curve and back-calculate concentration.

On real hardware you drop in `SynergyH1Backend` and the same standard-curve math runs
on measured RFU.  (ex/em for Qubit dsDNA HS ~ 485/530 -- see protocol_params.yaml,
flagged TODO because the vendor protocol uses a Qubit fluorometer, not a plate reader.)
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, List, Optional, Tuple
import random

from pylabrobot.plate_reading import PlateReaderChatterboxBackend

# dsDNA HS standard series (ng/uL) used to build the curve. Brackets the WGA product
# (~20 ng/uL after the protocol's 40 uL dilution) and diluted libraries.
DEFAULT_STANDARDS_NG_PER_UL = [0.0, 5.0, 10.0, 20.0, 50.0, 100.0]

_BLANK_RFU = 50.0          # blank/background fluorescence (sim)
_SLOPE_RFU = 10.0          # RFU per ng/uL (sim assay sensitivity)


@dataclass
class StandardCurve:
    slope: float
    intercept: float

    def concentration_ng_per_ul(self, rfu: float) -> float:
        if self.slope == 0:
            return 0.0
        return max(0.0, (rfu - self.intercept) / self.slope)

    @staticmethod
    def fit(standards_ng_per_ul: List[float], rfus: List[float]) -> "StandardCurve":
        """Ordinary least squares linear fit rfu = slope*conc + intercept."""
        n = len(standards_ng_per_ul)
        sx = sum(standards_ng_per_ul)
        sy = sum(rfus)
        sxx = sum(x * x for x in standards_ng_per_ul)
        sxy = sum(x * y for x, y in zip(standards_ng_per_ul, rfus))
        denom = n * sxx - sx * sx
        if denom == 0:
            return StandardCurve(slope=_SLOPE_RFU, intercept=_BLANK_RFU)
        slope = (n * sxy - sx * sy) / denom
        intercept = (sy - slope * sx) / n
        return StandardCurve(slope=slope, intercept=intercept)


class QubitSimBackend(PlateReaderChatterboxBackend):
    """Chatterbox plate reader that emits dsDNA-like RFU from seeded truth (ng/uL)."""

    def __init__(
        self,
        seed: int = 0,
        blank_rfu: float = _BLANK_RFU,
        slope_rfu: float = _SLOPE_RFU,
        noise_frac: float = 0.03,
    ) -> None:
        super().__init__()
        self._rng = random.Random(seed)
        self._blank = blank_rfu
        self._slope = slope_rfu
        self._noise = noise_frac
        # 8x12 ground-truth concentration matrix (ng/uL); None = empty well.
        self._truth: List[List[Optional[float]]] = [[None] * 12 for _ in range(8)]

    # -- seeding helpers ----------------------------------------------------
    def seed_wells(self, values: Dict[Tuple[int, int], float]) -> None:
        """Set ground-truth ng/uL for specific (row0, col0) wells."""
        for (row, col), conc in values.items():
            self._truth[row][col] = conc

    def seed_standards(self, standards_ng_per_ul: List[float], col: int = 11) -> None:
        """Place a dsDNA standard series down `col` (default last column)."""
        for row, conc in enumerate(standards_ng_per_ul[:8]):
            self._truth[row][col] = conc

    def truth_ng_per_ul(self, row: int, col: int) -> Optional[float]:
        return self._truth[row][col]

    # -- reader override ----------------------------------------------------
    def _rfu(self, conc: Optional[float]) -> float:
        if conc is None:
            return self._blank + self._rng.uniform(-2, 2)
        noise = 1.0 + self._rng.uniform(-self._noise, self._noise)
        return (self._blank + self._slope * conc) * noise

    async def read_fluorescence(  # type: ignore[override]
        self,
        plate: Any,
        wells: Any,
        excitation_wavelength: int,
        emission_wavelength: int,
        focal_height: float,
    ) -> List[dict]:
        data = [[self._rfu(self._truth[r][c]) for c in range(12)] for r in range(8)]
        return [
            {
                "time": 0.0,
                "temperature": float("nan"),
                "data": data,
                "ex_wavelength": excitation_wavelength,
                "em_wavelength": emission_wavelength,
            }
        ]
