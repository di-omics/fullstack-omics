"""Swappable PLR backend factory.

`mode="sim"`      -> hardware-free simulation (chatterbox backends + a PicoGreen
                     signal model for the plate reader). Runs anywhere.
`mode="hardware"` -> resolves the real backends named in instruments.yaml
                     (STARBackend / SynergyH1Backend / your thermocycler backend).
                     Refuses to run if the registry still has TODO placeholders.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from ..params import Params
from .picogreen import PicoGreenSimBackend


@dataclass
class BackendBundle:
    mode: str
    lh_backend: Any
    deck: Any
    tc_backend: Any
    pr_backend: Any
    notes: list[str]


def _sim_bundle(p: Params) -> BackendBundle:
    from pylabrobot.liquid_handling.backends import LiquidHandlerChatterboxBackend
    from pylabrobot.resources.hamilton import STARLetDeck
    from pylabrobot.thermocycling import ThermocyclerChatterboxBackend

    return BackendBundle(
        mode="sim",
        lh_backend=LiquidHandlerChatterboxBackend(num_channels=8),
        deck=STARLetDeck(),
        tc_backend=ThermocyclerChatterboxBackend(),
        pr_backend=PicoGreenSimBackend(seed=p.n_cells),  # deterministic per run size
        notes=["Simulation mode: no hardware. Chatterbox backends log every action."],
    )


def _resolve_hardware(p: Params) -> BackendBundle:  # pragma: no cover - needs hardware
    """Build hardware backends from instruments.yaml. Raises if anything is a TODO."""
    inst = p.instruments["instruments"]

    def _check(val: Any, where: str) -> str:
        s = str(val)
        if val is None or any(m in s.lower() for m in ("todo", "verify", "expert value")):
            raise RuntimeError(
                f"instruments.yaml is not ready for hardware at {where}: {val!r}. "
                "Fill in the verified backend/interface before running mode='hardware'."
            )
        return s

    lh_name = _check(inst["hamilton_star"]["plr"].get("backend_hardware"), "hamilton_star.backend_hardware")
    tc_name = _check(inst["on_deck_thermocycler"]["plr"].get("backend_hardware"), "on_deck_thermocycler.backend_hardware")
    pr_name = _check(inst["synergy_h1"]["plr"].get("backend_hardware"), "synergy_h1.backend_hardware")

    import importlib

    def _load(module: str, name: str):
        return getattr(importlib.import_module(module), name)

    lh_backend = _load("pylabrobot.liquid_handling.backends", lh_name)()
    from pylabrobot.resources.hamilton import STARLetDeck  # or STARDeck for a full STAR

    tc_backend = _load("pylabrobot.thermocycling", tc_name)()
    pr_backend = _load("pylabrobot.plate_reading", pr_name)()

    return BackendBundle(
        mode="hardware",
        lh_backend=lh_backend,
        deck=STARLetDeck(),
        tc_backend=tc_backend,
        pr_backend=pr_backend,
        notes=[f"Hardware backends: {lh_name}, {tc_name}, {pr_name}."],
    )


def make_backends(p: Params, mode: str = "sim") -> BackendBundle:
    if mode == "sim":
        return _sim_bundle(p)
    if mode == "hardware":
        return _resolve_hardware(p)
    raise ValueError(f"Unknown backend mode {mode!r}; expected 'sim' or 'hardware'.")
