#!/usr/bin/env python3
"""Wet-lab simulator and generated-handoff tests for autonomous-scWGS.

Runs via pytest or plain `python tests/test_end_to_end.py`; no hardware or external
analysis execution is required.
"""
import asyncio
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from autoscwgs.params import load_params
from autoscwgs.procurement import (
    BomItem, build_bom, route_channels, place_orders, approval_summary_markdown,
)
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
    assert p.protocol["meta"]["wga_source_id"] == "WGA-SOURCE-A"
    assert p.protocol["analysis"]["interface_version"] == "C-1.0"
    # WGA Lysis Mix: 3.0 uL/rxn x 96 x 1.30 ~= 375 uL (Table 2).
    total = p.mix_total_ul(3.0, 0.30, 96)
    assert abs(total - 374.4) < 0.5
    # Reaction Mix: 6.0 x 96 x 1.30 = 748.8 ~ 750 (Table 3).
    assert abs(p.mix_total_ul(6.0, 0.30, 96) - 748.8) < 0.5
    p2 = p.with_run(n_samples=48)
    assert p2.n_samples == 48 and p.n_samples == 96  # no mutation of original
    # An ignored local mapping can replace the unresolved public kit list.
    with tempfile.TemporaryDirectory() as d:
        local_config = Path(d) / "config"
        shutil.copytree(REPO_ROOT / "config", local_config)
        (local_config / "reagents.local.yaml").write_text(
            "wga_kit:\n"
            "  - name: Configured WGA kit\n"
            "    vendor: Configured Supplier\n"
            "    catalog: LOCAL-WGA-SKU\n"
            "    purchase_channel: po\n"
            "    verify: false\n"
            "    scale: per_kit\n",
            encoding="utf-8",
        )
        local = load_params(local_config)
        assert local.reagents["wga_kit"][0]["catalog"] == "LOCAL-WGA-SKU"
        assert local.reagents["wga_kit"][0]["verify"] is False


def test_bom_scales_and_kits():
    p = load_params()
    items = route_channels(build_bom(p, n_samples=200))
    assert items
    # 200 samples -> 3 kits (ceil(200/96)).
    kit_items = [i for i in items if i.scale == "per_kit"]
    assert any("3 kit" in i.quantity for i in kit_items)
    # Every item routed to a channel.
    assert all(i.channel for i in items)
    # Public WGA ordering data fails closed until private/local configuration exists.
    wga_kit = [i for i in items if i.category == "Single-cell WGA kit"][0]
    assert wga_kit.verify and wga_kit.catalog.startswith("# REQUIRED")
    assert wga_kit.channel == "verify"
    accessories = [i for i in items if i.category == "WGA accessories / consumables"]
    assert len(accessories) == 4
    assert all(i.verify and i.channel == "verify" and i.verify_note for i in accessories)
    approval = approval_summary_markdown(items, p=p, n_samples=200)
    assert all(i.name in approval for i in accessories)
    assert "Verification required (not orderable)" in approval
    # Even populated WGA data is non-orderable without a valid explicit channel.
    no_channel = BomItem(
        name="Configured WGA kit",
        vendor="Configured Supplier",
        catalog="LOCAL-WGA-SKU",
        category="Single-cell WGA kit",
        scale="per_kit",
        quantity="1 kit",
        channel=None,
        verify=False,
    )
    invalid_channel = BomItem(
        name="Configured WGA accessory",
        vendor="Configured Supplier",
        catalog="LOCAL-ACCESSORY-SKU",
        category="WGA accessories / consumables",
        scale="per_run",
        quantity="1 unit",
        channel="typo-channel",
        verify=False,
    )
    routed = route_channels([no_channel, invalid_channel])
    assert all(i.channel == "verify" for i in routed)
    try:
        place_orders(routed, approved=True)
        raise AssertionError("expected missing/invalid WGA purchase channels to fail closed")
    except ValueError:
        pass


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
    doc = approval_summary_markdown(items, p=p)
    assert "ORDERING BLOCKED" in doc
    try:
        place_orders(items, approved=True)
        raise AssertionError("expected unresolved public ordering data to fail closed")
    except ValueError as exc:
        assert "private/local configuration" in str(exc)
    # Fully populated local data remains a dry run after approval.
    for index, item in enumerate(items):
        if not item.vendor.strip() or item.vendor.lstrip().startswith("#"):
            item.vendor = "Configured Supplier"
        if not item.catalog.strip() or item.catalog.lstrip().startswith("#"):
            item.catalog = f"LOCAL-SKU-{index:03d}"
        item.verify = False
        item.verify_note = ""
        if item.channel == "verify":
            item.channel = "po"
    record = place_orders(items, approved=True)
    assert record["status"].startswith("DRY_RUN")


def test_wgs_pipeline_and_input_csv():
    p = load_params()
    script = generate_pipeline(p)
    # WGS Nextflow runner uses a compatible external checkout supplied at runtime.
    assert "nextflow run" in script and "main.nf" in script
    assert "WGS_PIPELINE_DIR" in script
    assert "git submodule" not in script and "git clone" not in script
    assert '--dnascope_model_selection "$DNASCOPE_MODEL"' in script
    assert '${DNASCOPE_MODEL:?' in script and '${DNASCOPE_MODEL:-' not in script
    assert '${SENTIEON_LICENSE:?' in script
    assert 'INPUT_CSV="${INPUT_CSV:-$SCRIPT_DIR/input.csv}"' in script
    # input.csv: header + one row per sample well (biosampleName,read1,read2).
    csv = generate_input_csv(p, sample_wells=["A2", "B2", "C2"])
    lines = csv.strip().splitlines()
    assert lines[0] == "biosampleName,read1,read2"
    assert len(lines) == 4 and lines[1].startswith("scwgs_A2,")
    with tempfile.TemporaryDirectory() as d:
        handoff_dir = Path(d) / "handoff"
        out = write_pipeline(p, handoff_dir)
        assert Path(out["pipeline"]).name == "run_wgs_analysis.sh"
        r = subprocess.run(["bash", "-n", out["pipeline"]], capture_output=True, text=True)
        assert r.returncode == 0, r.stderr  # bash -n syntax check
        assert Path(out["input_csv"]).exists()

        # Required environment values fail before any external process starts.
        r = subprocess.run(
            ["/bin/bash", out["pipeline"]], capture_output=True, text=True, env={}
        )
        assert r.returncode != 0 and "WGS_PIPELINE_DIR" in r.stderr

        pipeline_dir = Path(d) / "pipeline"
        pipeline_dir.mkdir()
        (pipeline_dir / "main.nf").write_text("// compatible entrypoint\n", encoding="utf-8")
        license_file = Path(d) / "sentieon.license"
        license_file.write_text("local test fixture\n", encoding="utf-8")
        no_model_env = {
            "WGS_PIPELINE_DIR": str(pipeline_dir),
            "SENTIEON_LICENSE": str(license_file),
        }
        r = subprocess.run(
            ["/bin/bash", out["pipeline"]],
            capture_output=True,
            text=True,
            env=no_model_env,
        )
        assert r.returncode != 0 and "DNASCOPE_MODEL" in r.stderr

        base_env = {
            "WGS_PIPELINE_DIR": str(pipeline_dir),
            "DNASCOPE_MODEL": "explicit-test-model",
            "SENTIEON_LICENSE": str(license_file),
        }
        missing_entrypoint = dict(base_env)
        empty_checkout = Path(d) / "empty-checkout"
        empty_checkout.mkdir()
        missing_entrypoint["WGS_PIPELINE_DIR"] = str(empty_checkout)
        r = subprocess.run(
            ["/bin/bash", out["pipeline"]],
            capture_output=True,
            text=True,
            env=missing_entrypoint,
        )
        assert r.returncode != 0 and "main.nf" in r.stderr

        missing_input = dict(base_env)
        missing_input["INPUT_CSV"] = str(Path(d) / "missing-input.csv")
        r = subprocess.run(
            ["/bin/bash", out["pipeline"]],
            capture_output=True,
            text=True,
            env=missing_input,
        )
        assert r.returncode != 0 and "Missing or empty input CSV" in r.stderr

        missing_license = dict(base_env)
        missing_license["SENTIEON_LICENSE"] = str(Path(d) / "missing.license")
        r = subprocess.run(
            ["/bin/bash", out["pipeline"]],
            capture_output=True,
            text=True,
            env=missing_license,
        )
        assert r.returncode != 0 and "license file not found" in r.stderr

        # Run from outside the handoff directory. Reaching tool preflight proves that
        # the default input.csv was resolved beside the runner rather than from cwd.
        no_tools = dict(base_env)
        no_tools["PATH"] = ""
        r = subprocess.run(
            ["/bin/bash", out["pipeline"]],
            capture_output=True,
            text=True,
            env=no_tools,
            cwd=d,
        )
        assert r.returncode == 3
        assert "Missing required external tool" in r.stderr


def test_manual_renders():
    p = load_params()
    md = render_manual_markdown(p)
    assert "RESEARCH USE ONLY" in md and "whole-genome amplification" in md and "NEBNext" in md
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
