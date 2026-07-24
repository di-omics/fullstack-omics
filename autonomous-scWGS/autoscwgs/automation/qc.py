"""Quality labels for synthetic WGS workflow-state signals."""

from __future__ import annotations

from dataclasses import dataclass, field

PASS = "PASS"
FLAG = "FLAG"


@dataclass
class QCResult:
    gate: str
    status: str
    detail: str
    flagged_samples: list[str] = field(default_factory=list)

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


def gate_synthetic_quality(
    sample_ids: list[str],
    scores: list[float],
    boundary: float,
) -> QCResult:
    """Label unitless simulator outputs; this is not a laboratory acceptance gate."""
    flagged = [
        sample_id
        for sample_id, score in zip(sample_ids, scores)
        if score < boundary
    ]
    return QCResult(
        gate="synthetic WGS preparation quality",
        status=FLAG if flagged else PASS,
        detail=(
            f"{len(sample_ids) - len(flagged)}/{len(sample_ids)} simulated samples "
            "at or above the unitless demonstration boundary"
        ),
        flagged_samples=flagged,
    )
