"""Abstract single-cell input registration for the WGS simulator."""

from __future__ import annotations

from dataclasses import dataclass

from ..params import Params


@dataclass
class InputPlan:
    sample_ids: list[str]

    @property
    def n_sample_wells(self) -> int:
        """Compatibility count; no physical well map is represented."""
        return len(self.sample_ids)


@dataclass
class InputRegistrationResult:
    plan: InputPlan
    n_requested: int
    n_deposited: int
    sort_efficiency_pct: float


def plan_plate(p: Params, n_samples: int | None = None) -> InputPlan:
    """Create stable sample identifiers without assigning physical locations."""
    count = p.n_samples if n_samples is None else int(n_samples)
    if count < 1:
        raise ValueError("n_samples must be positive")
    return InputPlan(sample_ids=[f"sample_{index:04d}" for index in range(1, count + 1)])


async def run_sort(
    p: Params,
    mode: str = "sim",
    n_samples: int | None = None,
    sort_efficiency: float = 1.0,
) -> InputRegistrationResult:
    """Simulate input registration; no sorter command or physical map is emitted."""
    if mode != "sim":
        p.require_hardware_profile()
        raise RuntimeError(
            "Physical isolation must be implemented by the laboratory-owned "
            "execution adapter."
        )
    plan = plan_plate(p, n_samples)
    bounded = min(1.0, max(0.0, float(sort_efficiency)))
    registered = round(len(plan.sample_ids) * bounded)
    return InputRegistrationResult(
        plan=plan,
        n_requested=len(plan.sample_ids),
        n_deposited=registered,
        sort_efficiency_pct=bounded * 100.0,
    )
