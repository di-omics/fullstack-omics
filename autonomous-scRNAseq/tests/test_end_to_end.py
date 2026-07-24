#!/usr/bin/env python3
"""End-to-end tests for the public scRNA-seq workflow-state simulator."""

import asyncio
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT))

from scrnaseq.automation import run_scrnaseq
from scrnaseq.manual import render_manual_markdown
from scrnaseq.ops import make_operator
from scrnaseq.params import HardwareProfileRequired, load_params
from scrnaseq.procurement import (
    approval_summary_markdown,
    build_bom,
    place_orders,
    route_channels,
)
from scrnaseq.readiness import run_readiness_check
from scrnaseq.result import generate_analysis_handoff, generate_pipeline


def test_public_profile_is_abstract():
    params = load_params()
    assert params.protocol["meta"]["public_profile"] == "simulation_only"
    assert params.protocol["meta"]["actionable_wet_lab_parameters_included"] is False
    text = str(params.protocol).lower()
    for key in ("volume_", "temperature_", "incubate_", "bead_", "control_well"):
        assert key not in text


def test_run_override_is_immutable():
    base = load_params()
    changed = base.with_run(n_cells=7)
    assert base.n_cells == 96
    assert changed.n_cells == 7


def test_readiness_is_synthetic():
    params = load_params()
    ready = asyncio.run(run_readiness_check(params, handler_state="calibrated"))
    review = asyncio.run(run_readiness_check(params, handler_state="needs_review"))
    assert ready.ready and ready.verdict == "READY"
    assert not review.ready and review.verdict == "NEEDS_REVIEW"
    assert all(0.0 <= check.score <= 1.0 for check in ready.checks)


def test_simulation_is_deterministic():
    params = load_params().with_run(n_cells=12)
    first = asyncio.run(run_scrnaseq(params))
    second = asyncio.run(run_scrnaseq(params))
    assert first.synthetic_quality_scores == second.synthetic_quality_scores
    assert first.steps[-1].endswith("analysis_ready")
    assert len(first.synthetic_quality_scores) == 12


def test_hardware_fails_without_local_profile():
    try:
        asyncio.run(run_scrnaseq(load_params(), mode="hardware"))
        raise AssertionError("hardware request should fail closed")
    except HardwareProfileRequired:
        pass


def test_local_profile_is_ignored_boundary():
    with tempfile.TemporaryDirectory() as directory:
        config = Path(directory) / "config"
        shutil.copytree(REPO_ROOT / "config", config)
        (config / "validated.local.yaml").write_text(
            "validated: true\nexecution_adapter: local_adapter:run\n",
            encoding="utf-8",
        )
        params = load_params(config)
        assert params.has_validated_profile
        assert params.require_hardware_profile()["execution_adapter"] == "local_adapter:run"


def test_functional_checklist_is_non_orderable():
    params = load_params()
    items = route_channels(build_bom(params))
    assert items and all(item.verify for item in items)
    summary = approval_summary_markdown(items, p=params)
    assert "no orderable item or quantity" in summary
    try:
        place_orders(items, approved=True)
        raise AssertionError("public checklist should not be orderable")
    except ValueError:
        pass


def test_planning_brief_is_not_a_bench_protocol():
    document = render_manual_markdown(load_params())
    assert "not a bench protocol" in document
    assert "analysis_ready" in document
    assert "physical settings" in document


def test_analysis_runner_requires_method_choices():
    script = generate_pipeline(load_params())
    for token in (
        "SCRNASEQ_PIPELINE_ADAPTER",
        "INPUT_MANIFEST",
        "REFERENCE_BUNDLE",
        "ANALYSIS_CONFIG",
        "OUTPUT_DIR",
    ):
        assert f"${{{token}:?" in script
    completed = subprocess.run(["bash", "-n"], input=script, text=True, capture_output=True)
    assert completed.returncode == 0, completed.stderr


def test_downstream_analysis_is_adapter_driven():
    script = generate_analysis_handoff(load_params())
    for token in (
        "SCRNASEQ_ANALYSIS_ADAPTER",
        "COUNT_MATRIX",
        "ANALYSIS_CONFIG",
        "ANALYSIS_OUTPUT",
    ):
        assert f"${{{token}:?" in script
    completed = subprocess.run(["bash", "-n"], input=script, text=True, capture_output=True)
    assert completed.returncode == 0, completed.stderr


def test_review_operator_emits_no_physical_command():
    operator = make_operator("human")
    action = operator.review_contract()
    assert action.command is None
    assert action.verb == "review_contract"


def _run_all():
    tests = [value for name, value in sorted(globals().items()) if name.startswith("test_")]
    for test in tests:
        test()
        print(f"PASS {test.__name__}")
    print(f"{len(tests)}/{len(tests)} passed")


if __name__ == "__main__":
    _run_all()
