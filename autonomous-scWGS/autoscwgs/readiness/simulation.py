"""Deterministic, non-physical readiness checks for the public WGS simulator."""

from __future__ import annotations

from dataclasses import dataclass

from ..params import Params


@dataclass
class CheckResult:
    name: str
    score: float
    decision_boundary: float

    @property
    def passed(self) -> bool:
        return self.score >= self.decision_boundary


@dataclass
class ReadinessReport:
    mode: str
    scenario: str
    checks: list[CheckResult]

    @property
    def ready(self) -> bool:
        return bool(self.checks) and all(check.passed for check in self.checks)

    @property
    def verdict(self) -> str:
        return "READY" if self.ready else "NEEDS_REVIEW"

    def summary(self) -> str:
        lines = [
            f"Synthetic contract readiness ({self.mode})",
            "No physical measurement or laboratory acceptance decision is represented.",
        ]
        for check in self.checks:
            label = "PASS" if check.passed else "FLAG"
            lines.append(f"[{label}] {check.name}: unitless score {check.score:.2f}")
        lines.append(f"VERDICT: {self.verdict}")
        return "\n".join(lines)


async def run_readiness_check(
    p: Params,
    mode: str = "sim",
    handler_state: str | None = None,
) -> ReadinessReport:
    if mode != "sim":
        p.require_hardware_profile()
        raise RuntimeError(
            "Readiness for physical execution must be implemented by the "
            "laboratory-owned execution adapter."
        )
    cfg = p.readiness["simulation"]
    scenario = handler_state or "calibrated"
    score = (
        float(cfg["needs_review_score"])
        if scenario in {"needs_calibration", "needs_review"}
        else float(cfg["calibrated_score"])
    )
    boundary = float(cfg["decision_boundary"])
    checks = [
        CheckResult(name=name, score=score, decision_boundary=boundary)
        for name in p.readiness["checks"]
    ]
    return ReadinessReport(mode=mode, scenario=scenario, checks=checks)
