"""Operator abstraction: a human or a humanoid robot as the bench "ops person."

The workflow calls high-level operator methods (prepare_bench, setup_deck,
load_reagents, load_sorter, start_sort, start_run, seal_plate, move_plate,
handle_alert, collect_output). Each returns an `OperatorAction`, and the operator
keeps an ordered log. This keeps "who does the physical steps" swappable -- exactly
like the liquid-handler backend is swappable.

The vision (user's): to help labs onboard, a general-purpose humanoid robot can be
the ops person -- it sets up the deck, loads reagents, and clicks run. Baked in as
`HumanoidOperator` (a structured-command stub; wire a real humanoid SDK to
`dispatch()`). <3
"""

from __future__ import annotations

import json
from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import List


@dataclass
class OperatorAction:
    actor: str          # "human" | "humanoid"
    verb: str           # e.g. "load_reagents", "press_run"
    detail: str
    command: dict | None = None   # structured command (humanoid) or None (human)


class LabOperator(ABC):
    role = "operator"
    actor = "operator"

    def __init__(self) -> None:
        self.log: List[OperatorAction] = []

    @abstractmethod
    def _do(self, verb: str, detail: str) -> OperatorAction:
        ...

    def _record(self, action: OperatorAction) -> OperatorAction:
        self.log.append(action)
        return action

    # -- high-level bench tasks the workflow calls ------------------------
    def prepare_bench(self) -> OperatorAction:
        return self._do("prepare_bench",
                        "clean pre-amplification workspace / PCR hood; keep reactions on ice")

    def load_sorter(self, layout: str) -> OperatorAction:
        return self._do("load_sorter",
                        f"load 96-well plate with 3 uL Cell Buffer/well + controls into FACS Melody: {layout}")

    def start_sort(self, n: int) -> OperatorAction:
        return self._do("start_sort", f"start FACS Melody single-cell sort of {n} wells")

    def setup_deck(self, layout: str) -> OperatorAction:
        return self._do("setup_deck", f"place carriers/tips/plates per layout: {layout}")

    def load_reagents(self, summary: str) -> OperatorAction:
        return self._do("load_reagents", f"load reagents into source positions: {summary}")

    def start_run(self) -> OperatorAction:
        return self._do("press_run", "confirm deck + start the PyLabRobot run")

    def seal_plate(self, plate: str) -> OperatorAction:
        return self._do("seal_plate", f"seal, spin 10 s ~750 xg, thermal-mix per protocol: {plate}")

    def move_plate(self, src: str, dst: str) -> OperatorAction:
        return self._do("move_plate", f"move plate {src} -> {dst}")

    def handle_alert(self, message: str) -> OperatorAction:
        return self._do("handle_alert", f"attend QC alert: {message}")

    def collect_output(self, artifact: str) -> OperatorAction:
        return self._do("collect_output", f"retrieve and store: {artifact}")


class HumanOperator(LabOperator):
    """Default operator: emits clear, imperative bench instructions for a person."""

    actor = "human"

    def _do(self, verb: str, detail: str) -> OperatorAction:
        return self._record(OperatorAction(actor="human", verb=verb, detail=detail))


class HumanoidOperator(LabOperator):
    """EXPERIMENTAL: a general-purpose humanoid robot as the ops person.

    This does NOT drive a real robot. It compiles each bench task into a structured
    manipulation command (primitive + parameters) of the kind you'd send to a
    humanoid's task/manipulation stack -- pick/place, press_button, peel_seal,
    open_drawer, load_sorter, etc. Swap `dispatch()` for a real client when a robot
    is available.

    Yes, the vision is: the robot sets up the deck, loads the sorter, and clicks run
    so a lab can onboard automation without a trained operator. Baked in. <3
    """

    actor = "humanoid"

    # Map high-level verbs to manipulation primitives + target affordances.
    _PRIMITIVES = {
        "prepare_bench": ("wipe_surface", {"tool": "decontaminant_wipe"}),
        "load_sorter": ("pick_and_place", {"targets": "plate->facs_melody_stage", "then": ["close_door"]}),
        "start_sort": ("press_button", {"ui": "sort", "software": "FACSChorus", "confirm": True}),
        "setup_deck": ("pick_and_place", {"targets": "carriers,tip_racks,plates"}),
        "load_reagents": ("pick_and_place", {"targets": "reagent_tubes->source_positions", "keep_on_ice": True}),
        "press_run": ("press_button", {"ui": "run", "confirm": True}),
        "seal_plate": ("apply_seal", {"then": ["spin_down", "thermal_mix"]}),
        "move_plate": ("pick_and_place", {"grip": "plate_edges"}),
        "handle_alert": ("notify_and_pause", {"escalate_to": "human_on_call"}),
        "collect_output": ("pick_and_place", {"targets": "output_plate->cold_storage"}),
    }

    def _do(self, verb: str, detail: str) -> OperatorAction:
        primitive, params = self._PRIMITIVES.get(verb, ("noop", {}))
        command = {
            "primitive": primitive,
            "params": {**params, "context": detail},
            "safety": {"require_confirmation_for": ["press_run", "start_sort", "collect_output"]},
        }
        return self._record(OperatorAction(actor="humanoid", verb=verb, detail=detail, command=command))

    def dispatch(self, action: OperatorAction) -> None:  # pragma: no cover
        """TODO: send `action.command` to a real humanoid manipulation API."""
        raise NotImplementedError(
            "HumanoidOperator.dispatch is a stub. Wire a humanoid robot client here "
            "(pick/place/press primitives). Until then, actions are logged only."
        )

    def command_log_json(self) -> str:
        return json.dumps([a.command for a in self.log if a.command], indent=2)


def make_operator(kind: str = "human") -> LabOperator:
    kind = (kind or "human").lower()
    if kind == "human":
        return HumanOperator()
    if kind in ("humanoid", "robot"):
        return HumanoidOperator()
    raise ValueError(f"Unknown operator kind {kind!r}; expected 'human' or 'humanoid'.")
