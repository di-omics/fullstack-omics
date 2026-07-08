"""Instrument readiness -- Step 1: Rhodamine B liquid-handling QC.

REQUIRED before a real run. Dispense Rhodamine B at low/medium/high protocol volume
scales across a 96-well plate, read on the Synergy H1, and compute the per-well CV.
Low CV -> READY; high CV -> NEEDS_CALIBRATION (physical calibration required).
"""

from .rhodamine import (
    run_readiness_check,
    ReadinessReport,
    RangeResult,
    SynergyH1ReadSettings,
    RhodamineSimBackend,
)

__all__ = [
    "run_readiness_check",
    "ReadinessReport",
    "RangeResult",
    "SynergyH1ReadSettings",
    "RhodamineSimBackend",
]
