"""A PicoGreen signal model so quant/normalize/QC are meaningful in simulation.

The chatterbox plate reader returns zeros. For a faithful demo we instead:
  1. seed a deterministic ground-truth cDNA concentration (pg/uL) per sample well,
  2. lay down a PicoGreen standard series in known wells,
  3. return RFU = blank + slope * conc (+ small noise) for every well,
  4. let the workflow fit a standard curve and back-calculate sample concentration.

On real hardware you drop in `SynergyH1Backend` instead (see instruments.yaml) and
the same standard-curve + normalization math applies to the measured RFU.
"""

from __future__ import annotations

import math
import random
from dataclasses import dataclass
from typing import Any, List, Optional

from pylabrobot.plate_reading import PlateReaderChatterboxBackend

# PicoGreen standard series (pg/uL) used to build the curve. Chosen around the
# 100 pg/uL normalization target from the protocol (Stage 8).
DEFAULT_STANDARDS_PG_PER_UL = [0.0, 50.0, 100.0, 250.0, 500.0, 1000.0]

_BLANK_RFU = 50.0          # blank/background fluorescence (sim)
_SLOPE_RFU = 2.0           # RFU per pg/uL (sim assay sensitivity)


@dataclass
class StandardCurve:
    slope: float
    intercept: float

    def concentration_pg_per_ul(self, rfu: float) -> float:
        if self.slope == 0:
            return 0.0
        return max(0.0, (rfu - self.intercept) / self.slope)

    @staticmethod
    def fit(standards_pg_per_ul: List[float], rfus: List[float]) -> "StandardCurve":
        """Ordinary least squares linear fit rfu = slope*conc + intercept."""
        n = len(standards_pg_per_ul)
        sx = sum(standards_pg_per_ul)
        sy = sum(rfus)
        sxx = sum(x * x for x in standards_pg_per_ul)
        sxy = sum(x * y for x, y in zip(standards_pg_per_ul, rfus))
        denom = n * sxx - sx * sx
        if denom == 0:
            return StandardCurve(slope=_SLOPE_RFU, intercept=_BLANK_RFU)
        slope = (n * sxy - sx * sy) / denom
        intercept = (sy - slope * sx) / n
        return StandardCurve(slope=slope, intercept=intercept)


class PicoGreenSimBackend(PlateReaderChatterboxBackend):
    """Chatterbox plate reader that emits PicoGreen-like RFU from seeded truth."""

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
        # 8x12 ground-truth concentration matrix (pg/uL); None = empty well.
        self._truth: List[List[Optional[float]]] = [[None] * 12 for _ in range(8)]

    # -- seeding helpers ----------------------------------------------------
    def seed_samples(self, n_samples: int, median_pg_per_ul: float = 600.0, sigma: float = 0.7) -> None:
        """Fill the first n_samples wells (column-major) with lognormal truth."""
        for idx in range(min(n_samples, 96)):
            row, col = idx % 8, idx // 8
            val = median_pg_per_ul * math.exp(self._rng.gauss(0.0, sigma))
            self._truth[row][col] = max(10.0, min(5000.0, val))

    def seed_standards(self, standards_pg_per_ul: List[float], col: int = 11) -> None:
        """Place a PicoGreen standard series down `col` (default last column)."""
        for row, conc in enumerate(standards_pg_per_ul[:8]):
            self._truth[row][col] = conc

    def truth_pg_per_ul(self, idx: int) -> Optional[float]:
        return self._truth[idx % 8][idx // 8]

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
