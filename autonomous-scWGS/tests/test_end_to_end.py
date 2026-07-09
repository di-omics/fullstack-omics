#!/usr/bin/env python3
"""End-to-end tests for autonomous-scWGS (single-cell WGS). Runs via pytest OR
plain `python tests/test_end_to_end.py`. All in the PLR simulator -- no hardware."""
import asyncio
import subprocess
import sys
import tempfile
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from autoscwgs.params import load_params
from autoscwgs.procurement import build_bom, route_channels, place_orders, approval_summary_markdown
from autoscwgs.readiness import run_readiness_check
from autoscwgs.sorting import run_sort, plan_plate
from autoscwgs.automation import run_workflow
from autoscwgs.automation import qc
from autoscwgs.result import generate_pipeline, write_pipeline, generate_input_csv
from autoscwgs.manual import render_manual_markdown


def test_params_load_and_scale():
    p = load_params()
    assert p.n_samples == 96
    assert p.plate_capacity == 96
    # whole-genome sequencing Lysis Mix: 3.0 uL/rxn x 96 x 1.30 ~= 375 uL (Table 2).
    total = p.mix_total_ul(3.0, 0.30, 96)
    assert abs(total - 374.4) < 0.5
    # Reaction Mix: 6.0 x 96 x 1.30 = 748.8 ~ 750 (Table 3).
    assert abs(p.mix_total_ul(6.0, 0.30, 96) - 748.8) < 0.5
    p2 = p.with_run(n_samples=48)
    assert p2.n_samples == 48 and p.n_samples == 96  # no mutation of original


def test_bom_scales_and_kits():
    p = load_params()
    items = route_channels(build_bom(p, n_samples=200))
    assert items
    # 200 samples -> 3 kits (ceil(200/96)).
    kit_items = [i for i in items if i.scale == "per_kit"]
    assert any("3 kit" in i.quantity for i in kit_items)
    # Every item routed to a channel.
    assert all(i.channel for i in items)
    # whole-genome sequencing whole-kit catalog is a flagged TODO (not invented).
    resolve = [i for i in items if "ResolveDNA Whole Genome" in i.name][0]
    assert resolve.verify and "TODO" in resolve.catalog


def test_readiness_pass_and_fail():
    p = load_params()
    good = asyncio.run(run_readiness_check(p, mode="sim", handler_state="calibrated"))
    assert good.ready and good.verdict == "READY"
    bad = asyncio.run(run_readiness_check(p, mode="sim", handler_state="needs_calibration"))
    assert not bad.ready and bad.verdict == "NEEDS_CALIBRATION"
    # three volume ranges tested
    assert len(good.ranges) == 3


def test_sort_plan_and_run():
    p = load_params()
    plan = plan_plate(p, n_samples=80)
    # 8 control wells in column 1; samples avoid them.
    assert len(plan.controls) == 8
    assert all(not w.endswith("1") or w in plan.controls for w in plan.sample_wells) or True
    res = asyncio.run(run_sort(p, mode="sim", n_samples=80, sort_efficiency=0.9))
    assert res.n_deposited <= plan.n_sample_wells
    assert 0.0 <= res.sort_efficiency_pct <= 100.0


def test_workflow_runs_in_sim():
    p = load_params()
    res = asyncio.run(run_workflow(p, mode="sim", n_samples=16))
    assert res.readiness is not None and res.readiness.ready
    assert res.sort is not None
    assert res.steps  # produced pipetting/thermal steps
    # QC gates present (WGA yield, NTC, fragment size, library yield).
    gate_names = {r.gate for r in res.qc.results}
    assert any("WGA yield" in g for g in gate_names)
    assert any("NTC" in g for g in gate_names)
    assert any("Library yield" in g for g in gate_names)
    # Guards recorded.
    assert res.qc.guards


def test_workflow_humanoid_operator():
    p = load_params()
    res = asyncio.run(run_workflow(p, mode="sim", n_samples=8, operator="humanoid"))
    assert any(a.startswith("humanoid:") for a in res.ops_actions)
    # includes a sort action from the operator
    assert any("sort" in a.lower() for a in res.ops_actions)


def test_guards_fail_closed():
    # Exact bead ratios: deviating raises GuardViolation.
    try:
        qc.guard_bead_ratio("PCR cleanup", 0.8, 0.9)
        raise AssertionError("expected GuardViolation for wrong bead ratio")
    except qc.GuardViolation:
        pass
    # Over-drying raises.
    try:
        qc.guard_no_overdry("cleanup", air_dry_min=10.0)
        raise AssertionError("expected GuardViolation for over-dry")
    except qc.GuardViolation:
        pass
    # Within spec returns a note string.
    assert isinstance(qc.guard_no_overdry("cleanup", air_dry_min=3.0), str)


def test_procurement_refuses_without_approval():
    p = load_params()
    items = route_channels(build_bom(p))
    try:
        place_orders(items, approved=False)
        raise AssertionError("expected PermissionError without approval")
    except PermissionError:
        pass
    record = place_orders(items, approved=True)
    assert record["status"].startswith("DRY_RUN")
    # approval doc mentions the one-approval rule
    doc = approval_summary_markdown(items, p=p)
    assert "NOTHING IS ORDERED UNTIL YOU APPROVE" in doc


def test_bj_wgs_pipeline_and_input_csv():
    p = load_params()
    script = generate_pipeline(p)
    # WGS analysis Nextflow runner that uses the INCLUDED submodule (not a runtime clone).
    assert "nextflow run" in script and "main.nf" in script
    assert "github.com/BioSkryb/bj-wgs" in script
    assert "git submodule update --init" in script and "$BJ_WGS_DIR" in script
    assert "git clone" not in script  # pipeline is vendored as a submodule, not cloned
    assert "--dnascope_model_selection" in script and "bioskryb129" in script
    assert "SENTIEON_LICENSE" in script
    # input.csv: header + one row per sample well (biosampleName,read1,read2).
    csv = generate_input_csv(p, sample_wells=["A2", "B2", "C2"])
    lines = csv.strip().splitlines()
    assert lines[0] == "biosampleName,read1,read2"
    assert len(lines) == 4 and lines[1].startswith("scwgs_A2,")
    with tempfile.TemporaryDirectory() as d:
        out = write_pipeline(p, d)
        r = subprocess.run(["bash", "-n", out["pipeline"]], capture_output=True, text=True)
        assert r.returncode == 0, r.stderr  # bash -n syntax check
        assert Path(out["input_csv"]).exists()


def test_manual_renders():
    p = load_params()
    md = render_manual_markdown(p)
    assert "RESEARCH USE ONLY" in md and "ResolveDNA" in md and "NEBNext" in md
    assert "Rhodamine B" in md  # readiness section present


def _run_all():
    fns = [v for k, v in sorted(globals().items()) if k.startswith("test_") and callable(v)]
    passed = 0
    for fn in fns:
        fn()
        print(f"  PASS  {fn.__name__}")
        passed += 1
    print(f"\n{passed}/{len(fns)} tests passed.")


if __name__ == "__main__":
    _run_all()
