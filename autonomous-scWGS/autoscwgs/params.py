"""Load the protocol-sourced YAML configs and ignored local ordering overrides.

Everything downstream (sort, BOM, manual, automation, analysis) reads its numbers
from here so public protocol values have one source of truth in `config/*.yaml`.
Private supplier/SKU/channel data may be supplied by `config/reagents.local.yaml`.

Unlike flashseq-skill, there is NO 384->96 volume multiplier: both protocols are
natively 96-well with explicit per-reaction volumes. The scaling this module owns is
master-mix totals: total = per_reaction * n_samples * (1 + overage), with each mix's
own overage (the WGA mixes use 30%; NEB mixes state their own).
"""

from __future__ import annotations

import copy
import functools
import math
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import yaml

# Repo layout: this file is autoscwgs/params.py; configs live in ../config/.
REPO_ROOT = Path(__file__).resolve().parent.parent
CONFIG_DIR = REPO_ROOT / "config"


def _load_yaml(path: Path) -> dict[str, Any]:
    with path.open("r", encoding="utf-8") as fh:
        value = yaml.safe_load(fh)
    if not isinstance(value, dict):
        raise ValueError(f"Expected a YAML mapping in {path}")
    return value


def _deep_merge(base: dict[str, Any], override: dict[str, Any]) -> dict[str, Any]:
    """Recursively merge a private/local mapping into a public base mapping.

    List values override base values as a unit so a local reagent list cannot accidentally retain
    unresolved public placeholder entries.
    """
    merged = copy.deepcopy(base)
    for key, value in override.items():
        if isinstance(value, dict) and isinstance(merged.get(key), dict):
            merged[key] = _deep_merge(merged[key], value)
        else:
            merged[key] = copy.deepcopy(value)
    return merged


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
    def n_samples(self) -> int:
        return int(self.protocol["run"]["n_samples"])

    @property
    def plate_format(self) -> int:
        return int(self.protocol["run"]["plate_format"])

    @property
    def plate_capacity(self) -> int:
        return int(self.protocol["run"].get("plate_capacity", 96))

    def with_run(self, n_samples: int | None = None) -> "Params":
        """Return a copy with run.n_samples overridden (CLI use)."""
        new = copy.deepcopy(self)
        if n_samples is not None:
            if n_samples < 1:
                raise ValueError("n_samples must be >= 1")
            new.protocol["run"]["n_samples"] = int(n_samples)
        return new

    # -- scaling ------------------------------------------------------------
    def n_plates(self, n: int | None = None) -> int:
        n = self.n_samples if n is None else n
        return max(1, math.ceil(n / self.plate_capacity))

    def n_kits(self, n: int | None = None) -> int:
        """Kits needed: one kit per plate_capacity (96) reactions."""
        return self.n_plates(n)

    def mix_total_ul(self, per_reaction_ul: float, overage_fraction: float,
                     n: int | None = None) -> float:
        """Master-mix volume to prepare for n reactions, with the mix's own overage.

        Matches the protocol tables: e.g. WGA Lysis Mix 3.0 uL/rxn x 96 x 1.30
        = 374.4 ~ 375 uL/96 (Table 2).
        """
        n = self.n_samples if n is None else n
        return round(per_reaction_ul * n * (1.0 + overage_fraction), 3)

    # -- convenience --------------------------------------------------------
    def stage(self, key: str) -> dict[str, Any]:
        return self.protocol[key]


@functools.lru_cache(maxsize=8)
def _load_cached(config_dir: str) -> Params:
    cdir = Path(config_dir)
    readiness_path = cdir / "readiness.yaml"
    readiness = _load_yaml(readiness_path) if readiness_path.exists() else {}
    reagents = _load_yaml(cdir / "reagents.yaml")
    local_reagents_path = cdir / "reagents.local.yaml"
    if local_reagents_path.exists():
        reagents = _deep_merge(reagents, _load_yaml(local_reagents_path))
    return Params(
        protocol=_load_yaml(cdir / "protocol_params.yaml"),
        reagents=reagents,
        instruments=_load_yaml(cdir / "instruments.yaml"),
        config_dir=cdir,
        readiness=readiness,
    )


def load_params(config_dir: Path | str | None = None) -> Params:
    """Load configs from `config_dir` (default: repo config/). Returns a fresh deep
    copy each call so callers can mutate run params safely; the cached base is
    treated as read-only."""
    cdir = Path(config_dir) if config_dir else CONFIG_DIR
    base = _load_cached(str(cdir))
    return base.with_run()
