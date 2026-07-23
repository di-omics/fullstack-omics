"""Single-cell WGS wet-lab flow, wired for the PLR simulator.

Flow (src: WGA protocol [A] + NEBNext Ultra II [B]; all volumes/temps/times from
protocol_params.yaml):

  FACS Melody sort (3 uL Cell Buffer/well, controls in col 1)
    -> Lysis Mix 3 uL + thermal-mix -> Reaction Mix 6 uL + thermal-mix
    -> ODTC WGA: 30 C 2.5 h -> 65 C 3 min -> 4 C
    -> dilute to 40 uL -> dsDNA quant on Synergy H1 -> WGA QC gates
    -> NEBNext End Prep (20 C 30 min / 65 C 30 min)
    -> Adaptor Ligation (20 C 15 min) -> SPRI size-select 0.4X/0.2X
    -> PCR enrichment (98 C; [98/65] x3) -> SPRI 0.8X cleanup
    -> library dsDNA quant on H1 -> pool (0.75X) -> sequence.

QC gates + guards (qc.py) fire at the protocols' checkpoints. Times are NOT slept in
sim (the ODTC chatterbox logs the profile); on hardware the backend enforces them.

Sim note: to keep the demo runnable for any N without exhausting tips, multi-channel
transfers reuse one tip column. On hardware each reagent addition uses FRESH tips
(no cross-contamination) -- provision tip racks accordingly.
"""

from __future__ import annotations

import math
import random
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple

from ..params import Params
from ..readiness import run_readiness_check, ReadinessReport
from ..ops import make_operator
from ..sorting import run_sort, SortResult
from .backends import make_backends
from .deck import build_deck, DeckLayout
from .qubit import DEFAULT_STANDARDS_NG_PER_UL, StandardCurve
from . import qc

_ROWS = "ABCDEFGH"


class InstrumentNotReady(RuntimeError):
    """Raised when the required Rhodamine B liquid-handling QC fails (fail closed)."""


def _rc(well: str) -> Tuple[int, int]:
    """'A1' -> (row0, col0)."""
    return _ROWS.index(well[0]), int(well[1:]) - 1


@dataclass
class WorkflowResult:
    mode: str
    n_samples: int
    steps: List[str] = field(default_factory=list)
    qc: qc.QCReport = field(default_factory=qc.QCReport)
    wga_yields_ng: Dict[str, float] = field(default_factory=dict)
    library_yields_ng: Dict[str, float] = field(default_factory=dict)
    safe_stops: List[str] = field(default_factory=list)
    flags: List[str] = field(default_factory=list)
    readiness: "ReadinessReport | None" = None
    sort: "SortResult | None" = None
    ops_actions: List[str] = field(default_factory=list)

    def summary(self) -> str:
        lines = [
            f"Single-cell WGS automation ({self.mode}) -- N={self.n_samples} (WGA + NEBNext Ultra II)",
            "=" * 72,
        ]
        if self.readiness is not None:
            lines.append(f"Stage 0a  Instrument readiness (Rhodamine B QC): {self.readiness.verdict}")
            for r in self.readiness.ranges:
                mark = "PASS" if r.passed else "FAIL"
                lines.append(f"    [{mark}] {r.name:6} {r.target_ul:>5.1f} uL  CV={r.cv_pct:.2f}% "
                             f"(<= {r.cv_threshold_pct:.1f}%)")
        if self.sort is not None:
            lines.append(f"Stage 0b  FACS Melody sort: {self.sort.n_deposited}/"
                         f"{self.sort.plan.n_sample_wells} cells (eff {self.sort.sort_efficiency_pct:.1f}%)")
        lines.append("")
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


def _n_columns(n: int) -> int:
    return min(12, max(1, math.ceil(n / 8)))


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
    await lh.drop_tips(tips)


async def _dispense_reagent(layout: DeckLayout, reagent: str, vol_ul: float, n_cols: int) -> None:
    src = layout.reagent_column(reagent)
    for c in range(1, n_cols + 1):
        dest = layout.working_plate[f"A{c}:H{c}"]
        await _transfer(layout, src, dest, vol_ul)


# ---------------------------------------------------------------------------
# dsDNA quant helpers (seed truth from the sort, read on the Synergy H1).
# ---------------------------------------------------------------------------
def _seed_wga_truth(pr_backend, sort: SortResult, seed: int) -> None:
    """Seed the reader's ground-truth ng/uL for the post-WGA dsDNA read.

    Cells + positive controls amplify (~20 ng/uL in the 40 uL dilution -> ~800 ng);
    NTC + missed wells stay near zero. Concentrations are a sim model, NOT protocol
    values (the protocol reports >800 ng typical, which this reproduces)."""
    rng = random.Random(seed)
    values: Dict[Tuple[int, int], float] = {}
    cells = set(sort.wells_with_cell)
    for well, ctype in sort.plan.controls.items():
        r, c = _rc(well)
        if ctype == "NTC":
            values[(r, c)] = max(0.0, rng.gauss(0.05, 0.03))          # ~0 ng/uL
        else:
            values[(r, c)] = max(2.0, rng.gauss(22.0, 4.0))           # positive controls amplify
    for well in sort.plan.sample_wells:
        r, c = _rc(well)
        if well in cells:
            values[(r, c)] = max(2.0, 22.0 * math.exp(rng.gauss(0.0, 0.35)))  # good WGA
        else:
            values[(r, c)] = max(0.0, rng.gauss(0.2, 0.1))            # no cell -> ~0
    pr_backend.seed_wells(values)
    pr_backend.seed_standards(DEFAULT_STANDARDS_NG_PER_UL, col=11)


async def _read_dsdna(layout: DeckLayout, p: Params, block: str) -> Dict[Tuple[int, int], float]:
    """Read the black plate on the Synergy H1 and back-calculate ng/uL per well."""
    fl = p.protocol[block]["quant"]["synergy_h1_fluorescence"] if block == "wga_qc" else \
        p.protocol["wga_qc"]["quant"]["synergy_h1_fluorescence"]
    reads = await layout.plate_reader.read_fluorescence(
        excitation_wavelength=int(fl["excitation_nm"]),
        emission_wavelength=int(fl["emission_nm"]),
        focal_height=7.0,
    )
    rfu = reads if isinstance(reads[0], list) else reads[0]["data"]
    std_rfu = [rfu[row][11] for row in range(len(DEFAULT_STANDARDS_NG_PER_UL))]
    curve = StandardCurve.fit(DEFAULT_STANDARDS_NG_PER_UL, std_rfu)
    out: Dict[Tuple[int, int], float] = {}
    for r in range(8):
        for c in range(11):  # col 11 (index 11) holds standards
            out[(r, c)] = curve.concentration_ng_per_ul(rfu[r][c])
    return out


async def run_workflow(
    p: Params,
    mode: str = "sim",
    n_samples: int | None = None,
    readiness: str = "required",
    operator: str = "human",
    sort_efficiency: float = 0.9,
) -> WorkflowResult:
    if n_samples is not None:
        p = p.with_run(n_samples=n_samples)
    n = p.n_samples
    n_cols = _n_columns(n)
    res = WorkflowResult(mode=mode, n_samples=n)

    # -- Stage 0a (REQUIRED): instrument readiness -- Rhodamine B liquid-handling QC.
    if readiness != "skip":
        report = await run_readiness_check(p, mode=mode)
        res.readiness = report
        if not report.ready:
            raise InstrumentNotReady(
                f"Rhodamine B QC = {report.verdict}. Calibrate the Hamilton STAR before "
                "running the protocol. Pass readiness='skip' only to knowingly override."
            )
    else:
        res.flags.append("Instrument readiness QC SKIPPED (override) -- required before real runs.")

    # -- Operator (human default; humanoid = experimental robot ops person).
    op = make_operator(operator)
    op.prepare_bench()

    # -- Stage 0b: FACS Melody single-cell sort (up front). -----------------
    op.load_sorter("controls in col 1 (NTC/1ng/100pg/10pg); cells cols 2-12")
    op.start_sort(n)
    sort = await run_sort(p, mode=mode, n_samples=n, sort_efficiency=sort_efficiency)
    res.sort = sort
    res.qc.note_guard(qc.guard_on_ice("keep the sorted plate on ice / process promptly"))
    res.qc.note_guard(qc.guard_pipet_on_wall("all single-cell reagent additions"))

    # -- Deck bring-up. -----------------------------------------------------
    op.setup_deck("STAR: tips rail 1, plates rail 8, Hamilton ODTC + Synergy H1")
    op.load_reagents("cell_buffer/lysis/reaction/elution/end_prep/adapter/ligation/pcr/beads/EtOH/TE/water")
    op.start_run()
    bundle = make_backends(p, mode=mode)
    layout = await build_deck(bundle)
    res.flags += bundle.notes
    res.flags.append("Sim tip reuse enabled; on hardware use fresh tips per reagent addition.")

    # ======================================================================
    # STAGE W1 -- Single-cell WGA. src: [A].
    # ======================================================================
    wga = p.protocol["wga"]
    lysis = wga["lysis_mix"]
    rxn = wga["reaction_mix"]
    res.qc.note_guard(qc.guard_no_vortex_r2("thaw/mix Reaction Mix reagents"))
    res.qc.note_guard(qc.guard_thermal_mix_not_vortex("WGA mixing steps with cells"))

    # Top up dry-sorted wells to 3 uL Cell Buffer (src: [A] step 10), then Lysis Mix.
    await _dispense_reagent(layout, "lysis_mix", float(lysis["add_to_well_ul"]), n_cols)
    res.steps.append(
        f"WGA Lysis Mix: {lysis['add_to_well_ul']} uL/well (L1/L2/L3); {lysis['mix']} "
        f"[master mix total {p.mix_total_ul(lysis['volume_per_reaction_ul'], lysis['overage_fraction'])} uL "
        f"for {n} rxn @ {int(lysis['overage_fraction']*100)}% overage] (src: [A] Table 2)"
    )
    await _dispense_reagent(layout, "reaction_mix", float(rxn["add_to_well_ul"]), n_cols)
    res.steps.append(
        f"WGA Reaction Mix: {rxn['add_to_well_ul']} uL/well (R1 then R2); {rxn['mix_after_add']} "
        f"[master mix total {p.mix_total_ul(rxn['volume_per_reaction_ul'], rxn['overage_fraction'])} uL] (src: [A] Table 3)"
    )
    await layout.thermocycler.run_protocol(
        _program_to_protocol({"steps": wga["amplification_program"]["steps"]}),
        block_max_volume=float(lysis["add_to_well_ul"]) + float(rxn["add_to_well_ul"]),
    )
    res.steps.append("ODTC WGA: 30 C 2.5 h -> 65 C 3 min -> 4 C hold (src: [A] Table 1)")
    res.safe_stops.append(wga["safe_stop"])

    # ======================================================================
    # STAGE W2 -- Post-WGA QC.  src: [A].
    # ======================================================================
    wqc = p.protocol["wga_qc"]
    await _dispense_reagent(layout, "elution_buffer", 0.0 if n == 0 else 1.0, n_cols)  # representative dilution add
    _seed_wga_truth(layout.plate_reader.backend, sort, seed=n * 7 + 3)
    concs = await _read_dsdna(layout, p, "wga_qc")
    dilute_to = float(wqc["dilute_to_ul"])
    # yields ng = concentration (ng/uL) * dilution volume (uL)
    sample_yields = {w: round(concs[_rc(w)] * dilute_to, 1) for w in sort.plan.sample_wells}
    ntc_yields = {w: round(concs[_rc(w)] * dilute_to, 1)
                  for w, t in sort.plan.controls.items() if t == "NTC"}
    res.wga_yields_ng = sample_yields
    res.steps.append(
        f"Post-WGA: dilute to {dilute_to} uL (Elution Buffer); Qubit dsDNA on Synergy H1 "
        f"(standard curve); {len(sample_yields)} sample wells quantified (src: [A])"
    )
    res.qc.add(qc.gate_wga_yield(sample_yields, p))
    res.qc.add(qc.gate_ntc(ntc_yields, p))
    # Simulated Tapestation fragment sizes (avg ~1275 bp).
    rng = random.Random(n * 11 + 5)
    sizes = {w: round(max(150.0, rng.gauss(1275.0, 220.0)), 0) for w in sort.plan.sample_wells}
    res.qc.add(qc.gate_wga_fragment_size(sizes, p))

    # ======================================================================
    # STAGE L -- NEBNext Ultra II library prep.  src: [B].
    # ======================================================================
    lp = p.protocol["libprep"]
    res.qc.note_guard(qc.guard_on_ice("thaw/hold NEBNext reagents on ice"))

    # -- End Prep. ---------------------------------------------------------
    ep = lp["end_prep"]
    end_prep_add = float(ep["components"][1]["volume_ul"]) + float(ep["components"][2]["volume_ul"])  # 7 + 3
    await _dispense_reagent(layout, "end_prep_mix", end_prep_add, n_cols)
    await layout.thermocycler.run_protocol(
        _program_to_protocol({"steps": ep["program"]["steps"]}),
        block_max_volume=float(ep["total_volume_ul"]),
    )
    res.steps.append(
        f"NEBNext End Prep: input {lp['input']['dna_input_ng']} ng WGA -> {lp['input']['bring_to_volume_ul']} uL "
        f"(expert-tunable); +{end_prep_add} uL End Prep mix; 20 C 30 min / 65 C 30 min (src: [B] 1)"
    )
    res.safe_stops.append(ep["safe_stop"])

    # -- Adaptor Ligation. -------------------------------------------------
    al = lp["adaptor_ligation"]
    adapter_v = float(al["components"][1]["volume_ul"])                      # 2.5
    ligation_v = float(al["components"][2]["volume_ul"]) + float(al["components"][3]["volume_ul"])  # 30 + 1
    await _dispense_reagent(layout, "adapter", adapter_v, n_cols)
    await _dispense_reagent(layout, "ligation_mix", ligation_v, n_cols)
    res.steps.append(
        f"Adaptor Ligation: +{adapter_v} uL UMI adaptor ({al['selected_working_conc_uM']} uM, expert-tunable) "
        f"+{ligation_v} uL Ligation MM+Enhancer; 20 C 15 min (src: [B] 2)"
    )
    res.safe_stops.append(al["safe_stop"])

    # -- SPRI size-selection (0.4X keep sup, 0.2X keep beads).  src: [B] 3A. -
    cl = lp["cleanup_ligation"]["size_selection"]
    qc.guard_bead_ratio("Ligation size-select 1st", 0.4, float(cl["bead_add_1_ratio_x"]))
    qc.guard_bead_ratio("Ligation size-select 2nd", 0.2, float(cl["bead_add_2_ratio_x"]))
    res.qc.note_guard(qc.guard_no_overdry("Ligation size-select", float(cl["air_dry_max_min"])))
    await _dispense_reagent(layout, "beads", float(cl["bead_add_1_ul"]), n_cols)
    await _dispense_reagent(layout, "beads", float(cl["bead_add_2_ul"]), n_cols)
    await _dispense_reagent(layout, "ethanol", float(cl["ethanol_volume_ul"]) / 10.0, n_cols)  # scaled demo vol
    await _dispense_reagent(layout, "te_0_1x", float(cl["elute_te_ul"]), n_cols)
    res.steps.append(
        f"SPRI size-select: {cl['bead_add_1_ul']} uL (0.4X) keep sup -> {cl['bead_add_2_ul']} uL (0.2X) keep beads; "
        f"2x 80% EtOH; air-dry <= {cl['air_dry_max_min']} min (do NOT over-dry); "
        f"elute {cl['elute_te_ul']} uL 0.1X TE, transfer {cl['transfer_ul']} uL (src: [B] 3A)"
    )

    # -- PCR enrichment. ---------------------------------------------------
    pe = lp["pcr_enrichment"]
    pcr_add = float(pe["components"][1]["volume_ul"]) + float(pe["components"][2]["volume_ul"])  # 5 + 25
    await _dispense_reagent(layout, "pcr_mix", pcr_add, n_cols)
    await layout.thermocycler.run_protocol(
        _program_to_protocol({"steps": pe["program"]["steps"]}),
        block_max_volume=float(pe["total_volume_ul"]),
    )
    res.steps.append(
        f"PCR enrichment: +{pcr_add} uL Primer+Q5; 98 C 30 s -> [98 C 10 s / 65 C 75 s] x {pe['cycles']} "
        f"(expert-tunable, range {pe['cycles_range']}) -> 65 C 5 min (src: [B] 4)"
    )

    # -- SPRI 0.8X PCR cleanup.  src: [B] 5. -------------------------------
    cp = lp["cleanup_pcr"]
    qc.guard_bead_ratio("PCR cleanup", 0.8, float(cp["bead_ratio_x"]))
    res.qc.note_guard(qc.guard_no_overdry("PCR cleanup", float(cp["air_dry_max_min"])))
    await _dispense_reagent(layout, "beads", float(cp["bead_volume_ul"]), n_cols)
    await _dispense_reagent(layout, "ethanol", float(cp["ethanol_volume_ul"]) / 10.0, n_cols)
    await _dispense_reagent(layout, "te_0_1x", float(cp["elute_te_ul"]), n_cols)
    res.steps.append(
        f"SPRI 0.8X PCR cleanup: {cp['bead_volume_ul']} uL beads; 2x 80% EtOH; "
        f"elute {cp['elute_te_ul']} uL 0.1X TE, transfer {cp['transfer_ul']} uL; Bioanalyzer HS (src: [B] 5)"
    )

    # ======================================================================
    # Library QC + pool.  src: [A] post-lib QC + [B] 5.12.
    # ======================================================================
    lib_conc: Dict[Tuple[int, int], float] = {}
    lrng = random.Random(n * 13 + 9)
    lib_truth: Dict[Tuple[int, int], float] = {}
    for w, y in sample_yields.items():
        r, c = _rc(w)
        lib_truth[(r, c)] = max(0.0, (12.0 if y >= p.protocol["wga_qc"]["gates"]["min_yield_ng"]
                                       else 0.2) * math.exp(lrng.gauss(0.0, 0.3)))
    layout.plate_reader.backend.seed_wells(lib_truth)
    layout.plate_reader.backend.seed_standards(DEFAULT_STANDARDS_NG_PER_UL, col=11)
    lib_conc = await _read_dsdna(layout, p, "library_qc")
    lq = p.protocol["library_qc"]
    library_yields = {w: round(lib_conc[_rc(w)] * 40.0, 1) for w in sample_yields}  # elution ~40 uL
    res.library_yields_ng = library_yields
    res.steps.append(
        f"Library QC: Qubit HS dsDNA on Synergy H1 + Tapestation HS D1000 sizing (src: [A] post-lib QC)"
    )
    res.qc.add(qc.gate_library_yield(library_yields, p))

    # Final pool + 0.75X cleanup.
    fp = lq["final_pool_cleanup"]
    qc.guard_bead_ratio("Final pool cleanup", 0.75, float(fp["bead_ratio_x"]))
    seq = p.protocol["sequencing"]
    res.steps.append(
        f"Pool libraries -> final 0.75X SPRI ({fp['example']}) -> sequence Illumina: low-pass "
        f"{seq['low_pass']['read_length_bp']}bp PE {seq['low_pass']['reads_per_cell_millions']} M reads/cell "
        f"(CNV); deep {seq['deep']['coverage_x']}X (SNV) (src: [A] Appendix C)"
    )

    op.collect_output("final pooled WGS library -> -20 C")
    res.ops_actions = [f"{a.actor}: {a.verb} -- {a.detail}" for a in op.log]

    await layout.lh.stop()
    return res
