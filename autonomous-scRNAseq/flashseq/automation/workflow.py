"""The FLASH-seq UMI flow, wired end-to-end and runnable in the PLR simulator.

Flow (src: FLASH-seq UMI v3, all volumes/temps/times from protocol_params.yaml):
  lysis-mix dispense -> 72C 3min -> RT-PCR-mix dispense -> RT 50C 60min + PCR
  (98C, 20-24 cyc) -> SPRI 0.6x cleanup -> PicoGreen quant (Synergy H1) ->
  normalize to 100 pg/uL -> tagmentation mix -> 55C 8min -> SDS + index adaptors +
  NPM -> enrichment PCR (14 cyc) -> SPRI 0.8x cleanup -> quant -> pool.

QC gates + guards (qc.py) are evaluated at the protocol's checkpoints. Times are
NOT slept in sim (thermocycler backend logs the profile); on hardware the backend
enforces them.

Sim note: to keep the demo runnable for any N without exhausting tips, multi-channel
transfers reuse one tip column and return it. On hardware each reagent addition uses
FRESH tips (no cross-contamination) -- provision tip racks accordingly.
"""

from __future__ import annotations

import math
import random
from dataclasses import dataclass, field
from typing import List

from ..params import Params
from ..readiness import run_readiness_check, ReadinessReport
from ..ops import make_operator
from .backends import make_backends
from .deck import build_deck, DeckLayout
from .picogreen import DEFAULT_STANDARDS_PG_PER_UL, StandardCurve
from . import qc


class InstrumentNotReady(RuntimeError):
    """Raised when the required Rhodamine B liquid-handling QC fails (fail closed)."""


@dataclass
class WorkflowResult:
    mode: str
    n_cells: int
    plate_format: int
    steps: List[str] = field(default_factory=list)
    qc: qc.QCReport = field(default_factory=qc.QCReport)
    concentrations_pg_per_ul: List[float] = field(default_factory=list)
    normalization_water_ul: List[float] = field(default_factory=list)
    safe_stops: List[str] = field(default_factory=list)
    flags: List[str] = field(default_factory=list)
    readiness: "ReadinessReport | None" = None
    ops_actions: List[str] = field(default_factory=list)

    def summary(self) -> str:
        lines = [
            f"FLASH-seq automation ({self.mode}) -- N={self.n_cells}, {self.plate_format}-well",
            "-" * 64,
        ]
        if self.readiness is not None:
            lines.append(f"Instrument readiness (Step 1, Rhodamine B QC): {self.readiness.verdict}")
            for r in self.readiness.ranges:
                mark = "PASS" if r.passed else "FAIL"
                lines.append(f"    [{mark}] {r.name:6} {r.target_ul:>5.1f} uL  CV={r.cv_pct:.2f}% "
                             f"(<= {r.cv_threshold_pct:.1f}%)")
        lines += [f"  {i+1:2d}. {s}" for i, s in enumerate(self.steps)]
        lines.append("\nQC gates:")
        for r in self.qc.results:
            marker = {"PASS": "[PASS]", "FLAG": "[FLAG]", "FAIL": "[FAIL]"}[r.status]
            lines.append(f"  {marker} {r.gate}: {r.detail}")
        lines.append("\nTacit guards enforced:")
        for g in self.qc.guards:
            lines.append(f"  - {g}")
        lines.append("\nSafe-stop points:")
        for s in self.safe_stops:
            lines.append(f"  - {s}")
        if self.ops_actions:
            lines.append("\nOperator actions (" + (self.ops_actions[0].split(":", 1)[0]) + "):")
            for a in self.ops_actions:
                lines.append(f"  > {a}")
        if self.flags:
            lines.append("\nFlags:")
            for f in self.flags:
                lines.append(f"  ! {f}")
        return "\n".join(lines)


def _n_columns(n_cells: int) -> int:
    return min(12, max(1, math.ceil(n_cells / 8)))


def _program_to_protocol(program: dict):
    """Convert a protocol_params thermal program into a PLR Protocol."""
    from pylabrobot.thermocycling.standard import Protocol, Stage, Step

    stages = []
    for step in program["steps"]:
        if "substeps" in step:  # cycled block
            sub = [Step(temperature=[float(s["temperature_c"])], hold_seconds=float(s["time_s"]))
                   for s in step["substeps"]]
            stages.append(Stage(steps=sub, repeats=int(step["cycles"])))
        else:
            stages.append(Stage(
                steps=[Step(temperature=[float(step["temperature_c"])],
                            hold_seconds=float(step["time_s"]))],
                repeats=int(step.get("cycles", 1)),
            ))
    return Protocol(stages=stages)


async def _transfer(layout: DeckLayout, source, dest, vol_ul: float) -> None:
    """One 8-channel aspirate/dispense with tip reuse (sim). See module docstring."""
    tips = layout.tip_racks[0]["A1:H1"]
    lh = layout.lh
    await lh.pick_up_tips(tips)
    await lh.aspirate(source, vols=[vol_ul] * 8)
    await lh.dispense(dest, vols=[vol_ul] * 8)
    await lh.drop_tips(tips)  # returned to source spots for reuse in sim


async def _dispense_reagent(layout: DeckLayout, reagent: str, vol_ul: float, n_cols: int) -> None:
    src = layout.reagent_column(reagent)
    for c in range(1, n_cols + 1):
        dest = layout.working_plate[f"A{c}:H{c}"]
        await _transfer(layout, src, dest, vol_ul)


async def run_flashseq(
    p: Params,
    mode: str = "sim",
    n_cells: int | None = None,
    readiness: str = "required",
    operator: str = "human",
) -> WorkflowResult:
    if n_cells is not None:
        p = p.with_run(n_cells=n_cells)
    n = p.n_cells
    n_cols = _n_columns(n)

    res = WorkflowResult(mode=mode, n_cells=n, plate_format=p.plate_format)

    # -- Step 1 (REQUIRED): instrument readiness -- Rhodamine B liquid-handling QC.
    if readiness != "skip":
        report = await run_readiness_check(p, mode=mode)
        res.readiness = report
        if not report.ready:
            raise InstrumentNotReady(
                f"Rhodamine B QC = {report.verdict}. Calibrate the liquid handler before "
                "running the protocol. Pass readiness='skip' only to knowingly override."
            )
    else:
        res.flags.append("Instrument readiness QC SKIPPED (override) -- required before real runs.")

    # -- Operator (human default; humanoid = experimental robot ops person).
    op = make_operator(operator)
    op.prepare_bench()
    op.setup_deck(f"96-well STARlet: tips rail 1, plates rail 8, thermocycler + Synergy H1")
    op.load_reagents("lysis/RT-PCR/beads/tagmentation/index/NPM/ethanol/PicoGreen source columns")
    op.start_run()

    bundle = make_backends(p, mode=mode)
    layout = await build_deck(bundle)
    res.flags += bundle.notes
    if p.plate_format == 384:
        res.flags.append("384-well selected: requires a nanodispenser (I.DOT). Hamilton default is 96-well.")
    res.flags.append("Sim tip reuse enabled; on hardware use fresh tips per reagent addition.")

    sv = p.scale_volume  # 384-base -> effective volume shorthand

    # -- Stage 1+3: lysis mix already in wells; cells sorted; lyse ----------
    res.qc.note_guard(qc.guard_on_ice("keep lysis plate on ice / cool rack before lysis (Stage 3)"))
    lysis_v = sv(p.protocol["lysis_mix"]["dispense_volume_ul_384"])
    await _dispense_reagent(layout, "lysis_mix", lysis_v, n_cols)
    res.steps.append(f"Dispense lysis mix {lysis_v} uL/well x {n_cols} col(s) (Stage 1)")
    await layout.thermocycler.run_protocol(
        _program_to_protocol({"steps": p.protocol["lysis_thermocycler"]["steps"]}),
        block_max_volume=lysis_v,
    )
    res.steps.append("Thermocycler lysis: 72C 3 min -> 4C hold (Stage 3)")

    # -- Stage 4: RT-PCR ----------------------------------------------------
    rt_v = sv(p.protocol["rt_pcr"]["dispense_volume_ul_384"])
    await _dispense_reagent(layout, "rt_pcr_mix", rt_v, n_cols)
    res.steps.append(f"Dispense RT-PCR mix {rt_v} uL/well (Stage 4)")
    rt_cycles = next(s for s in p.protocol["rt_pcr"]["program"]["steps"] if s["name"] == "pcr_cycles")["cycles"]
    await layout.thermocycler.run_protocol(
        _program_to_protocol(p.protocol["rt_pcr"]["program"]),
        block_max_volume=sv(5.0),
    )
    res.steps.append(f"RT 50C 60 min + PCR 98/65/72 x {rt_cycles} cyc (Stage 4; cycles expert-tunable)")
    res.safe_stops.append(p.protocol["rt_pcr"]["safe_stop"])

    # -- Stage 5: SPRI 0.6x cDNA cleanup -----------------------------------
    cc = p.protocol["cdna_cleanup"]
    qc.guard_bead_ratio("cDNA cleanup", 0.6, float(cc["bead_ratio"]))
    res.qc.note_guard(qc.guard_no_overdry("cDNA cleanup", bool(cc["ethanol_wash"]), None))
    await _dispense_reagent(layout, "water", sv(cc["add_water_ul_384"]), n_cols)
    await _dispense_reagent(layout, "beads", sv(cc["beads_volume_ul_384"]), n_cols)
    res.steps.append(
        f"SPRI 0.6x: +{sv(cc['add_water_ul_384'])} uL water, +{sv(cc['beads_volume_ul_384'])} uL beads; "
        f"{cc['incubate_off_magnet_min']} min off / {cc['incubate_on_magnet_min']} min on magnet; "
        f"resuspend {sv(cc['resuspend_water_ul_384'])} uL; transfer {sv(cc['transfer_volume_ul_384'])} uL (Stage 5)"
    )
    res.safe_stops.append(cc["safe_stop"])

    # -- Stage 7: PicoGreen quant on Synergy H1 ----------------------------
    pr_backend = layout.plate_reader.backend
    pr_backend.seed_samples(n)
    pr_backend.seed_standards(DEFAULT_STANDARDS_PG_PER_UL, col=11)
    reads = await layout.plate_reader.read_fluorescence(
        excitation_wavelength=p.protocol["cdna_quant"]["fluorescence"]["excitation_nm"],
        emission_wavelength=p.protocol["cdna_quant"]["fluorescence"]["emission_nm"],
        focal_height=7.0,
    )
    rfu = reads if isinstance(reads[0], list) else reads[0]["data"]
    std_rfu = [rfu[row][11] for row in range(len(DEFAULT_STANDARDS_PG_PER_UL))]
    curve = StandardCurve.fit(DEFAULT_STANDARDS_PG_PER_UL, std_rfu)
    concs = []
    for idx in range(n):
        row, col = idx % 8, idx // 8
        concs.append(round(curve.concentration_pg_per_ul(rfu[row][col]), 1))
    res.concentrations_pg_per_ul = concs
    res.steps.append(
        f"PicoGreen quant on Synergy H1: fit standard curve "
        f"(slope={curve.slope:.3f}, intercept={curve.intercept:.1f}); {n} wells quantified (Stage 7)"
    )
    res.qc.add(qc.gate_picogreen(concs, p))

    # cDNA size gate (simulated Bioanalyzer; Stage 6, external tool).
    rng = random.Random(n * 7 + 1)
    sizes_kb = []
    for c in concs:
        if c < p.protocol["normalization"]["target_concentration_pg_per_ul"]:
            sizes_kb.append(round(max(0.1, rng.gauss(0.30, 0.08)), 2))  # low input -> degraded/short
        else:
            sizes_kb.append(round(min(3.0, max(0.5, rng.gauss(2.0, 0.22))), 2))
    res.qc.add(qc.gate_cdna_size(sizes_kb, p))

    # -- Stage 8: normalize to 100 pg/uL -----------------------------------
    target = float(p.protocol["normalization"]["target_concentration_pg_per_ul"])
    v_cdna = sv(p.protocol["normalization"]["target_volume_ul_384"])
    water = []
    for c in concs:
        water.append(round(v_cdna * (c / target - 1.0), 3) if c >= target else 0.0)
    res.normalization_water_ul = water
    n_norm = sum(1 for c in concs if c >= target)
    await _dispense_reagent(layout, "water", v_cdna, n_cols)  # representative normalization dispense
    res.steps.append(f"Normalize to {target} pg/uL: {n_norm}/{n} wells normalizable (Stage 8)")

    # -- Stage 9: tagmentation + indexing PCR ------------------------------
    tg = p.protocol["tagmentation"]
    tag_mix_v = sv(tg["tagmentation_mix_total_ul_384"])
    await _dispense_reagent(layout, "tagmentation_mix", tag_mix_v, n_cols)
    await _dispense_reagent(layout, "water", v_cdna, n_cols)  # stand-in for adding normalized cDNA
    await layout.thermocycler.run_protocol(
        _program_to_protocol({"steps": tg["tagmentation_program"]["steps"]}),
        block_max_volume=sv(2.2),
    )
    res.steps.append(
        f"Tagmentation: {tag_mix_v} uL mix (ATM {tg['atm_volume_ul_384']} uL expert-tunable + TD) "
        f"+ 1 uL cDNA; 55C 8 min -> 4C (Stage 9)"
    )
    await _dispense_reagent(layout, "sds", sv(tg["neutralization"]["sds_volume_ul_384"]), n_cols)
    res.qc.note_guard(qc.guard_no_rechill("after 0.2% SDS, incubate 5 min RT (Stage 9)"))
    await _dispense_reagent(layout, "index_adaptors", sv(tg["indexing"]["index_adaptor_volume_ul_384"]), n_cols)
    await _dispense_reagent(layout, "npm", sv(tg["indexing"]["npm_volume_ul_384"]), n_cols)
    res.steps.append("Add 0.2% SDS (5 min RT, no re-chill) -> N7xx+S5xx index adaptors (5 uM) -> NPM (Stage 9)")
    enr_cycles = next(s for s in tg["enrichment_pcr"]["steps"] if s.get("name") == "enrichment_cycles")["cycles"]
    await layout.thermocycler.run_protocol(
        _program_to_protocol(tg["enrichment_pcr"]),
        block_max_volume=sv(5.2),
    )
    res.steps.append(f"Enrichment PCR: 72C 3min -> 95C 30s -> [95/55/72] x {enr_cycles} (Stage 9)")
    res.safe_stops.append(tg["safe_stop"])

    # -- Stage 10: SPRI 0.8x library cleanup -------------------------------
    lc = p.protocol["library_cleanup"]
    qc.guard_bead_ratio("Library cleanup", 0.8, float(lc["bead_ratio"]))
    res.qc.note_guard(qc.guard_no_overdry("Library cleanup", bool(lc["ethanol_wash"]), float(lc["dry_min"])))
    await _dispense_reagent(layout, "beads", sv(5.2 * lc["bead_ratio"]), n_cols)
    await _dispense_reagent(layout, "ethanol", 40.0, n_cols)  # 80% EtOH wash (scaled-down demo volume)
    await _dispense_reagent(layout, "water", lc["elute_water_ul"], n_cols)
    res.steps.append(
        f"SPRI 0.8x library cleanup + 80% EtOH wash; dry {lc['dry_min']} min (until small cracks); "
        f"elute {lc['elute_water_ul']} uL, transfer {lc['transfer_volume_ul']} uL (Stage 10)"
    )

    # Library size gate (simulated Bioanalyzer; Stage 10).
    lib_sizes = []
    for i in range(n):
        base = rng.gauss(lc["qc"]["library_size_bp_target"], 90)
        if i % 17 == 0:  # a few over-tagmented libraries
            base = rng.gauss(1200, 80)
        lib_sizes.append(round(max(200.0, base), 0))
    res.qc.add(qc.gate_library_size(lib_sizes, p))

    # -- Stage 11: pool ----------------------------------------------------
    res.steps.append(
        f"Pool normalizable libraries -> sequence ({p.protocol['sequencing']['platform']}, "
        f"{p.protocol['sequencing']['read_mode']}, PE R1>={p.protocol['sequencing']['read1_min_bp']}bp) (Stage 11)"
    )

    op.collect_output("final pooled library plate -> -20 C")
    res.ops_actions = [f"{a.actor}: {a.verb} -- {a.detail}" for a in op.log]

    await layout.lh.stop()
    return res
