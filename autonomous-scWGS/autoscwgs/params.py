"""Load the public WGS simulation contract and an optional local profile."""

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
    def n_samples(self) -> int:
        return int(self.protocol["run"]["n_samples"])

    @property
    def plate_capacity(self) -> int:
        return int(self.protocol["run"]["batch_capacity"])

    @property
    def plate_format(self) -> int:
        return self.plate_capacity

    @property
    def has_validated_profile(self) -> bool:
        return (
            self.local_profile.get("validated") is True
            and isinstance(self.local_profile.get("execution_adapter"), str)
            and bool(self.local_profile["execution_adapter"].strip())
        )

    def with_run(self, n_samples: int | None = None) -> "Params":
        new = copy.deepcopy(self)
        if n_samples is not None:
            if int(n_samples) < 1:
                raise ValueError("n_samples must be positive")
            new.protocol["run"]["n_samples"] = int(n_samples)
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
