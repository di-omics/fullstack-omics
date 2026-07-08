"""End-to-end tests. Run with `pytest` or `python tests/test_end_to_end.py`.

These assert the two things that matter most for this skill:
  1. Every number traces to the protocol (no invented values; scaling is correct).
  2. All four stages run wired together in the PLR simulator with QC/guards firing.
"""

import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from flashseq.params import load_params
from flashseq.procurement import build_bom, route_channels
from flashseq.procurement.channels import place_orders
from flashseq.manual import render_manual_markdown
from flashseq.automation import run_flashseq
from flashseq.automation import qc
from flashseq.readiness import run_readiness_check
from flashseq.ops import make_operator, HumanoidOperator
from flashseq.result import generate_pipeline


# ---- 1. Params + scaling (protocol source of truth) -------------------------

def test_protocol_totals_match_source():
    p = load_params()
    lysis = sum(c["volume_ul_384"] for c in p.protocol["lysis_mix"]["components"])
    rt = sum(c["volume_ul_384"] for c in p.protocol["rt_pcr"]["mix_components"])
    assert abs(lysis - 1.000) < 1e-6, "lysis mix must total 1.000 uL/well (Stage 1)"
    assert abs(rt - 4.000) < 1e-6, "RT-PCR mix must total 4.000 uL/well (Stage 4)"


def test_96well_is_5x():
    p96 = load_params().with_run(plate_format=96)
    p384 = load_params().with_run(plate_format=384)
    assert p96.volume_multiplier == 5.0
    assert p384.volume_multiplier == 1.0
    assert p96.scale_volume(1.0) == 5.0  # protocol's 5x rule


def test_bead_ratios_are_exact():
    p = load_params()
    assert p.protocol["cdna_cleanup"]["bead_ratio"] == 0.6
    assert p.protocol["library_cleanup"]["bead_ratio"] == 0.8


# ---- 2. Procurement ---------------------------------------------------------

def test_bom_scales_and_routes():
    p = load_params().with_run(n_cells=96)
    items = route_channels(build_bom(p))
    assert len(items) > 20
    # custom oligos route to IDT
    oligo = next(i for i in items if i.name == "TSO-UMI")
    assert oligo.channel == "idt_api"
    # OCR-ambiguous items are flagged for verification
    assert any(i.verify for i in items)


def test_no_autocheckout_without_approval():
    p = load_params().with_run(n_cells=8)
    items = route_channels(build_bom(p))
    raised = False
    try:
        place_orders(items, approved=False)
    except PermissionError:
        raised = True
    assert raised, "place_orders must refuse without human approval"


# ---- 3. Manual --------------------------------------------------------------

def test_manual_has_key_sections():
    p = load_params().with_run(n_cells=96)
    md = render_manual_markdown(p)
    for token in ["RESEARCH USE ONLY", "Lysis mix", "RT-PCR", "0.6x", "0.8x",
                  "Wiring diagram", "SAFE STOP", "expert-tunable",
                  "Instrument readiness", "Rhodamine B"]:
        assert token in md, f"manual missing: {token}"


# ---- 3b. Instrument readiness (Rhodamine B QC) ------------------------------

def test_readiness_calibrated_is_ready():
    p = load_params()
    rep = asyncio.run(run_readiness_check(p, mode="sim", handler_state="calibrated"))
    assert rep.ready and rep.verdict == "READY"
    assert len(rep.ranges) == 3                      # low / medium / high
    # signal scales with volume (high target reads brightest)
    means = [r.mean_rfu for r in rep.ranges]
    assert means == sorted(means)


def test_readiness_needs_calibration_fails():
    p = load_params()
    rep = asyncio.run(run_readiness_check(p, mode="sim", handler_state="needs_calibration"))
    assert not rep.ready and rep.verdict == "NEEDS_CALIBRATION"


def test_workflow_runs_readiness_and_ops():
    p = load_params()
    res = asyncio.run(run_flashseq(p, mode="sim", n_cells=16, operator="humanoid"))
    assert res.readiness is not None and res.readiness.ready
    assert res.ops_actions and any("press_run" in a for a in res.ops_actions)


def test_humanoid_operator_emits_commands():
    op = make_operator("humanoid")
    assert isinstance(op, HumanoidOperator)
    op.start_run()
    assert op.log[-1].command is not None
    assert op.log[-1].command["primitive"] == "press_button"


# ---- 4. Automation (PLR simulator) ------------------------------------------

def test_automation_runs_in_sim():
    p = load_params()
    res = asyncio.run(run_flashseq(p, mode="sim", n_cells=16))
    assert res.mode == "sim"
    assert len(res.steps) >= 12
    assert len(res.concentrations_pg_per_ul) == 16
    assert len(res.qc.results) == 3          # picogreen, cDNA size, library size
    assert len(res.qc.guards) >= 4           # on-ice, no-overdry x2, no-rechill
    assert res.safe_stops                    # -20C safe stops recorded


def test_guard_rejects_wrong_bead_ratio():
    raised = False
    try:
        qc.guard_bead_ratio("test", 0.6, 0.8)
    except qc.GuardViolation:
        raised = True
    assert raised


# ---- 5. Result --------------------------------------------------------------

def test_pipeline_has_protocol_commands():
    p = load_params()
    sh = generate_pipeline(p)
    for token in ["bcl2fastq", "umi_tools extract", "CTAACGG", "-F 260",
                  "featureCounts", "-t exon", "-g gene_name", "umi_tools count",
                  ".{8}"]:
        assert token in sh, f"pipeline missing: {token}"


if __name__ == "__main__":
    fns = [v for k, v in sorted(globals().items()) if k.startswith("test_") and callable(v)]
    failed = 0
    for fn in fns:
        try:
            fn()
            print(f"PASS  {fn.__name__}")
        except Exception as exc:  # noqa: BLE001
            failed += 1
            print(f"FAIL  {fn.__name__}: {exc}")
    print(f"\n{len(fns) - failed}/{len(fns)} passed")
    sys.exit(1 if failed else 0)
