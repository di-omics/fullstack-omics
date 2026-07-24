"""Human-review abstraction for simulation artifacts."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass
class OperatorAction:
    actor: str
    verb: str
    detail: str
    command: dict | None = None


class ReviewOperator:
    def __init__(self, actor: str = "human") -> None:
        self.actor = actor
        self.log: list[OperatorAction] = []

    def review_contract(self) -> OperatorAction:
        action = OperatorAction(self.actor, "review_contract", "review public simulation contract")
        self.log.append(action)
        return action

    def review_handoff(self) -> OperatorAction:
        action = OperatorAction(self.actor, "review_handoff", "review computational handoff")
        self.log.append(action)
        return action


HumanOperator = ReviewOperator
HumanoidOperator = ReviewOperator
LabOperator = ReviewOperator


def make_operator(kind: str = "human") -> ReviewOperator:
    if kind not in {"human", "humanoid", "robot"}:
        raise ValueError("kind must be human, humanoid, or robot")
    return ReviewOperator(actor=kind)
