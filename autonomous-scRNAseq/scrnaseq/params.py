"""Load the public scRNA-seq simulation contract and an optional local profile."""

from __future__ import annotations

import copy
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import yaml

REPO_ROOT = Path(__file__).resolve().parent.parent
CONFIG_DIR = REPO_ROOT / "config"
LOCAL_PROFILE_NAME = "validated.local.yaml"


class HardwareProfileRequired(RuntimeError):
    """Raised when physical execution is requested without controlled local data."""


def _load_yaml(path: Path) -> dict[str, Any]:
    with path.open("r", encoding="utf-8") as handle:
        value = yaml.safe_load(handle) or {}
    if not isinstance(value, dict):
        raise ValueError(f"{path} must contain a YAML mapping")
    return value


@dataclass
class Params:
    protocol: dict[str, Any]
    reagents: dict[str, Any]
    instruments: dict[str, Any]
    readiness: dict[str, Any]
    config_dir: Path
    local_profile: dict[str, Any] = field(default_factory=dict)

    @property
    def n_cells(self) -> int:
        return int(self.protocol["run"]["n_samples"])

    @property
    def n_samples(self) -> int:
        return self.n_cells

    @property
    def plate_format(self) -> int:
        """Compatibility name for the abstract simulation batch capacity."""
        return int(self.protocol["run"]["batch_capacity"])

    @property
    def has_validated_profile(self) -> bool:
        return (
            self.local_profile.get("validated") is True
            and isinstance(self.local_profile.get("execution_adapter"), str)
            and bool(self.local_profile["execution_adapter"].strip())
        )

    def with_run(
        self,
        n_cells: int | None = None,
        n_samples: int | None = None,
        plate_format: int | None = None,
    ) -> "Params":
        new = copy.deepcopy(self)
        requested = n_cells if n_cells is not None else n_samples
        if requested is not None:
            if int(requested) < 1:
                raise ValueError("n_samples must be positive")
            new.protocol["run"]["n_samples"] = int(requested)
        if plate_format is not None:
            if int(plate_format) < 1:
                raise ValueError("batch capacity must be positive")
            new.protocol["run"]["batch_capacity"] = int(plate_format)
        return new

    def require_hardware_profile(self) -> dict[str, Any]:
        if not self.has_validated_profile:
            raise HardwareProfileRequired(
                "Physical execution is disabled. Supply ignored config/"
                f"{LOCAL_PROFILE_NAME} with validated: true and a laboratory-owned "
                "execution_adapter."
            )
        return copy.deepcopy(self.local_profile)


def load_params(config_dir: Path | str | None = None) -> Params:
    directory = Path(config_dir) if config_dir else CONFIG_DIR
    local_path = directory / LOCAL_PROFILE_NAME
    return Params(
        protocol=_load_yaml(directory / "protocol_params.yaml"),
        reagents=_load_yaml(directory / "reagents.yaml"),
        instruments=_load_yaml(directory / "instruments.yaml"),
        readiness=_load_yaml(directory / "readiness.yaml"),
        config_dir=directory,
        local_profile=_load_yaml(local_path) if local_path.exists() else {},
    )
