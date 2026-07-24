#!/usr/bin/env python3
"""End-to-end tests for the public single-cell WGS workflow-state simulator."""

import asyncio
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT))

from autoscwgs.automation import run_workflow
from autoscwgs.manual import render_manual_markdown
from autoscwgs.params import HardwareProfileRequired, load_params
from autoscwgs.procurement import (
    approval_summary_markdown,
    build_bom,
    place_orders,
    route_channels,
)
from autoscwgs.readiness import run_readiness_check
from autoscwgs.result import generate_input_csv, generate_pipeline
from autoscwgs.sorting import plan_plate, run_sort


def test_public_profile_is_abstract():
    params = load_params()
    assert params.protocol["meta"]["public_profile"] == "simulation_only"
    assert params.protocol["meta"]["actionable_wet_lab_parameters_included"] is False
    text = str(params.protocol).lower()
    for key in ("volume_", "temperature_", "incubate_", "bead_", "control_well"):
        assert key not in text


def test_run_override_is_immutable():
    base = load_params()
    changed = base.with_run(n_samples=7)
    assert base.n_samples == 96
    assert changed.n_samples == 7


def test_readiness_is_synthetic():
    params = load_params()
    ready = asyncio.run(run_readiness_check(params, handler_state="calibrated"))
    review = asyncio.run(run_readiness_check(params, handler_state="needs_review"))
    assert ready.ready and ready.verdict == "READY"
    assert not review.ready and review.verdict == "NEEDS_REVIEW"


def test_input_plan_has_no_physical_map():
    plan = plan_plate(load_params(), n_samples=5)
    assert plan.sample_ids == [
        "sample_0001",
        "sample_0002",
        "sample_0003",
        "sample_0004",
        "sample_0005",
    ]
    result = asyncio.run(run_sort(load_params(), n_samples=5))
    assert result.n_deposited == 5


def test_simulation_is_deterministic():
    params = load_params().with_run(n_samples=12)
    first = asyncio.run(run_workflow(params))
    second = asyncio.run(run_workflow(params))
    assert first.synthetic_quality_scores == second.synthetic_quality_scores
    assert first.steps[-1].endswith("analysis_ready")
    assert len(first.sample_ids) == 12


def test_hardware_fails_without_local_profile():
    try:
        asyncio.run(run_workflow(load_params(), mode="hardware"))
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


def test_analysis_handoff_is_runtime_configured():
    params = load_params().with_run(n_samples=3)
    csv_text = generate_input_csv(params)
    assert csv_text.splitlines()[0] == "biosampleName,read1,read2"
    assert len(csv_text.splitlines()) == 4
    script = generate_pipeline(params)
    for token in (
        "WGS_PIPELINE_ADAPTER",
        "ANALYSIS_CONFIG",
        "REFERENCE_BUNDLE",
        "PUBLISH_DIR",
    ):
        assert f"${{{token}:?" in script
    completed = subprocess.run(["bash", "-n"], input=script, text=True, capture_output=True)
    assert completed.returncode == 0, completed.stderr


def _run_all():
    tests = [value for name, value in sorted(globals().items()) if name.startswith("test_")]
    for test in tests:
        test()
        print(f"PASS {test.__name__}")
    print(f"{len(tests)}/{len(tests)} passed")


if __name__ == "__main__":
    _run_all()
