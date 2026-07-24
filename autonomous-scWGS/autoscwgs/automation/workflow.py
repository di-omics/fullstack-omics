"""Abstract single-cell WGS workflow-state simulation.

The public simulator emits no liquid-handler, thermal, or physical instrument
commands. Its numeric values are unitless synthetic signals used only to exercise
orchestration and analysis-handoff logic.
"""

from __future__ import annotations

import importlib
import inspect
import random
from dataclasses import dataclass, field
from typing import Any

from ..params import Params
from ..readiness import ReadinessReport, run_readiness_check
from ..sorting import InputRegistrationResult, run_sort
from . import qc


@dataclass
class WorkflowResult:
    mode: str
    n_samples: int
    steps: list[str] = field(default_factory=list)
    sample_ids: list[str] = field(default_factory=list)
    synthetic_quality_scores: list[float] = field(default_factory=list)
    qc: qc.QCReport = field(default_factory=qc.QCReport)
    readiness: ReadinessReport | None = None
    sort: InputRegistrationResult | None = None
    ops_actions: list[str] = field(default_factory=list)
    flags: list[str] = field(default_factory=list)

    def summary(self) -> str:
        lines = [
            f"single-cell WGS workflow-state simulation -- N={self.n_samples}",
            "Simulation only: no physical parameters or instrument commands.",
        ]
        if self.readiness is not None:
            lines.append(f"Contract readiness: {self.readiness.verdict}")
        lines.extend(f"{index}. {step}" for index, step in enumerate(self.steps, start=1))
        for result in self.qc.results:
            lines.append(f"[{result.status}] {result.gate}: {result.detail}")
        return "\n".join(lines)


async def _run_local_adapter(p: Params, **kwargs: Any) -> WorkflowResult:
    profile = p.require_hardware_profile()
    target = profile["execution_adapter"]
    if ":" not in target:
        raise RuntimeError("execution_adapter must use 'module:function' syntax")
    module_name, function_name = target.split(":", 1)
    function = getattr(importlib.import_module(module_name), function_name)
    result = function(p=p, **kwargs)
    if inspect.isawaitable(result):
        result = await result
    if not isinstance(result, WorkflowResult):
        raise TypeError("The local execution adapter must return WorkflowResult")
    return result


async def run_workflow(
    p: Params,
    mode: str = "sim",
    n_samples: int | None = None,
    readiness: str = "required",
    operator: str = "human",
) -> WorkflowResult:
    if n_samples is not None:
        p = p.with_run(n_samples=n_samples)
    if mode == "hardware":
        return await _run_local_adapter(
            p,
            n_samples=p.n_samples,
            readiness=readiness,
            operator=operator,
        )
    if mode != "sim":
        raise ValueError("mode must be 'sim' or 'hardware'")

    result = WorkflowResult(mode=mode, n_samples=p.n_samples)
    if readiness != "skip":
        result.readiness = await run_readiness_check(p, mode="sim")
        if not result.readiness.ready:
            raise RuntimeError("Synthetic workflow contract needs review")
    else:
        result.flags.append("Synthetic contract readiness was skipped")

    result.sort = await run_sort(p, mode="sim", n_samples=p.n_samples)
    result.sample_ids = result.sort.plan.sample_ids[: result.sort.n_deposited]
    for stage in p.protocol["simulation"]["stages"]:
        result.steps.append(f"{stage['id']} -> {stage['output_state']}")

    quality = p.protocol["simulation"]["synthetic_quality"]
    rng = random.Random(int(p.protocol["simulation"]["seed"]) + p.n_samples)
    center = float(quality["center"])
    spread = float(quality["spread"])
    result.synthetic_quality_scores = [
        round(min(1.0, max(0.0, rng.gauss(center, spread))), 4)
        for _ in result.sample_ids
    ]
    result.qc.add(
        qc.gate_synthetic_quality(
            result.sample_ids,
            result.synthetic_quality_scores,
            float(quality["decision_boundary"]),
        )
    )
    result.ops_actions = [
        f"{operator}: review simulation contract",
        f"{operator}: review WGS analysis handoff",
    ]
    return result
