"""Automation ops -- who physically tends the deck.

A `LabOperator` is whoever loads tips/reagents/plates, presses run, peels seals, and
collects output. Two implementations:
  - `HumanOperator`  : prints clear bench instructions for a person (the default).
  - `HumanoidOperator`: EXPERIMENTAL stub that emits structured manipulation commands
    for a general-purpose humanoid robot to be the "automation ops person."

Both produce an ordered action log so the workflow records exactly what a human (or
robot) was asked to do. The humanoid path is a forward-looking scaffold -- it does
not drive a real robot; it defines the command protocol one would send to one.
"""

from .operator import (
    LabOperator,
    HumanOperator,
    HumanoidOperator,
    OperatorAction,
    make_operator,
)

__all__ = [
    "LabOperator",
    "HumanOperator",
    "HumanoidOperator",
    "OperatorAction",
    "make_operator",
]
