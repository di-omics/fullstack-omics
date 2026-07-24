"""Quality labels for synthetic workflow-state signals."""

from __future__ import annotations

from dataclasses import dataclass, field

PASS = "PASS"
FLAG = "FLAG"


@dataclass
class QCResult:
    gate: str
    status: str
    detail: str
    flagged_samples: list[int] = field(default_factory=list)

    @property
    def ok(self) -> bool:
        return self.status == PASS


@dataclass
class QCReport:
    results: list[QCResult] = field(default_factory=list)

    def add(self, result: QCResult) -> QCResult:
        self.results.append(result)
        return result

    @property
    def any_fail(self) -> bool:
        return False


def gate_synthetic_quality(scores: list[float], boundary: float) -> QCResult:
    """Label unitless simulator outputs; this is not a laboratory acceptance gate."""
    flagged = [index for index, score in enumerate(scores) if score < boundary]
    return QCResult(
        gate="synthetic workflow quality",
        status=FLAG if flagged else PASS,
        detail=(
            f"{len(scores) - len(flagged)}/{len(scores)} simulated samples at or "
            "above the unitless demonstration boundary"
        ),
        flagged_samples=flagged,
    )
