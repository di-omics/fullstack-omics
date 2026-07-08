"""Load and scale the protocol-sourced YAML configs.

Everything downstream (BOM, manual, automation, analysis) reads its numbers from
here so there is exactly one source of truth: `config/*.yaml`, itself transcribed
from FLASH-seq UMI v3 (DOI 10.17504/protocols.io.bp2l619rdvqe/v3).

The one transformation this module owns is the 384-well -> 96-well volume scaling.
The protocol says: "When using 96-well plates, we recommend using 5 times larger
volume." So effective_volume = base_384_volume * volume_multiplier[plate_format].
"""

from __future__ import annotations

import functools
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import yaml

# Repo layout: this file is flashseq/params.py; configs live in ../config/.
REPO_ROOT = Path(__file__).resolve().parent.parent
CONFIG_DIR = REPO_ROOT / "config"


def _load_yaml(path: Path) -> dict[str, Any]:
    with path.open("r", encoding="utf-8") as fh:
        return yaml.safe_load(fh)


@dataclass
class Params:
    """Parsed configs plus the small amount of derived logic they need."""

    protocol: dict[str, Any]
    reagents: dict[str, Any]
    instruments: dict[str, Any]
    config_dir: Path
    readiness: dict[str, Any] = field(default_factory=dict)

    # -- run config ---------------------------------------------------------
    @property
    def n_cells(self) -> int:
        return int(self.protocol["run"]["n_cells"])

    @property
    def plate_format(self) -> int:
        return int(self.protocol["run"]["plate_format"])

    @property
    def volume_multiplier(self) -> float:
        """5.0 for 96-well (protocol's 5x rule), 1.0 for native 384-well."""
        table = self.protocol["run"]["volume_multiplier_by_format"]
        return float(table[str(self.plate_format)])

    @property
    def overage(self) -> float:
        return float(self.protocol["run"]["pipetting_overage_fraction"])

    def with_run(self, n_cells: int | None = None, plate_format: int | None = None) -> "Params":
        """Return a copy with run.n_cells / run.plate_format overridden (CLI use)."""
        import copy

        new = copy.deepcopy(self)
        if n_cells is not None:
            new.protocol["run"]["n_cells"] = int(n_cells)
        if plate_format is not None:
            if str(plate_format) not in new.protocol["run"]["volume_multiplier_by_format"]:
                raise ValueError(f"Unsupported plate_format {plate_format}; expected 96 or 384.")
            new.protocol["run"]["plate_format"] = int(plate_format)
        return new

    # -- volume scaling -----------------------------------------------------
    def scale_volume(self, base_ul_384: float) -> float:
        """384-well base volume -> effective per-well volume for this run's format."""
        return round(base_ul_384 * self.volume_multiplier, 4)

    def wells_with_overage(self, n: int | None = None) -> float:
        """Effective well-equivalents to prepare, including master-mix overage."""
        n = self.n_cells if n is None else n
        return n * (1.0 + self.overage)

    def component_total_ul(self, base_ul_384: float, n: int | None = None) -> float:
        """Total volume of one mix component to prepare for a run (with overage)."""
        return round(self.scale_volume(base_ul_384) * self.wells_with_overage(n), 3)

    # -- convenience accessors ---------------------------------------------
    def stage(self, key: str) -> dict[str, Any]:
        return self.protocol[key]


@functools.lru_cache(maxsize=8)
def _load_cached(config_dir: str) -> Params:
    cdir = Path(config_dir)
    readiness_path = cdir / "readiness.yaml"
    readiness = _load_yaml(readiness_path) if readiness_path.exists() else {}
    return Params(
        protocol=_load_yaml(cdir / "protocol_params.yaml"),
        reagents=_load_yaml(cdir / "reagents.yaml"),
        instruments=_load_yaml(cdir / "instruments.yaml"),
        config_dir=cdir,
        readiness=readiness,
    )


def load_params(config_dir: Path | str | None = None) -> Params:
    """Load configs from `config_dir` (default: repo config/). Fresh copy each call
    once you go through with_run(); the cached base is treated as read-only."""
    cdir = Path(config_dir) if config_dir else CONFIG_DIR
    base = _load_cached(str(cdir))
    # Hand back a deep copy so callers can mutate run params safely.
    return base.with_run()
