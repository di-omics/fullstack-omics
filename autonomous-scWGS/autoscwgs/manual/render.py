"""Render the printable bench manual (Markdown; optional PDF) from protocol_params.yaml."""

from __future__ import annotations

import shutil
import subprocess
from pathlib import Path

from ..params import Params
from .wiring import wiring_diagram_ascii

DISCLAIMER = (
    "> **RESEARCH USE ONLY -- not clinically validated.** Volumes/temps/times are "
    "transcribed from an authorized proprietary WGA protocol and the NEBNext Ultra II "
    "(NEB E7645) user guide. **Verify every value against authorized source "
    "documentation before a real run.** See ATTRIBUTION.md."
)


def _mix_table(p: Params, title: str, components: list[dict], per_rxn: float,
               overage: float, src: str) -> str:
    lines = [f"### {title}  ({src})", ""]
    lines.append("| Component | Per-reaction | Total for run (+overage) |")
    lines.append("|---|---|---|")
    for c in components:
        v = float(c["volume_ul"])
        total = p.mix_total_ul(v, overage)
        cap = f" ({c['cap_color']})" if c.get("cap_color") and c["cap_color"] != "-" else ""
        lines.append(f"| {c['name']}{cap} | {v} uL | {total} uL |")
    lines.append(f"| **Total** | **{per_rxn} uL** | "
                 f"**{p.mix_total_ul(per_rxn, overage)} uL** ({int(overage*100)}% overage) |")
    lines.append("")
    return "\n".join(lines)


def _thermal_table(program: dict, title: str, src: str) -> str:
    lines = [f"### {title}  ({src})", "", "| Step | Temp | Time | Cycles |", "|---|---|---|---|"]
    lid = program.get("heated_lid_c")
    if lid:
        lines[0] += ""  # keep title
    for step in program["steps"]:
        if "substeps" in step:
            cyc = step["cycles"]
            for s in step["substeps"]:
                lines.append(f"| {s['name']} | {s['temperature_c']} C | {s['time_s']} s | x{cyc} |")
        else:
            t = step["time_s"]
            time_str = "hold" if t == 0 else (f"{t} s" if t < 600 else f"{t//60} min")
            lines.append(f"| {step['name']} | {step['temperature_c']} C | {time_str} | x{step.get('cycles',1)} |")
    if lid:
        lines.append(f"\n_Heated lid: {lid} C._")
    lines.append("")
    return "\n".join(lines)


def _readiness_section(p: Params) -> str:
    cfg = p.readiness
    if not cfg:
        return ""
    s = cfg["synergy_h1"]
    rh = cfg["rhodamine"]
    lines = ["## Stage 0 -- Instrument readiness (REQUIRED before any run)\n"]
    lines.append("Before spending irreplaceable single cells, prove the Hamilton STAR pipettes "
                 "precisely with a **Rhodamine B fluorescence check** on the Synergy H1. Low CV -> "
                 "**READY**; high CV -> **NEEDS_CALIBRATION** (calibrate before running).\n")
    lines.append(f"- Rhodamine B working solution: ~{rh['working_conc_uM']} uM "
                 f"(~{rh['working_conc_ug_per_ml']} ug/mL) in {rh['diluent']}; "
                 f"top wells to {rh['final_volume_ul']} uL final. _(expert-tunable)_")
    lines.append(f"- Synergy H1: ex {s['excitation_nm']} / em {s['emission_nm']} nm, "
                 f"gain={s['gain']}, {s['optics']} optics, height {s['read_height_mm']} mm. "
                 "_(Rhodamine B peaks ~553/627 nm; match your filter set.)_")
    lines.append("\n| Range | Target volume | Wells (columns) | CV pass threshold | Represents |")
    lines.append("|---|---|---|---|---|")
    for r in cfg["volume_ranges"]:
        cols = ",".join(str(c) for c in r["columns"])
        lines.append(f"| {r['name']} | {r['target_ul']} uL | cols {cols} | "
                     f"<= {r['cv_threshold_pct']}% | {r.get('represents','')} |")
    lines.append("\n_Run it: `python scripts/run_readiness.py`. Ops person: a human, or the "
                 "experimental humanoid robot operator (`--operator humanoid`)._\n")
    return "\n".join(lines)


def render_manual_markdown(p: Params) -> str:
    L: list[str] = []
    L.append(f"# Single-cell WGS -- Bench Manual  (N = {p.n_samples} samples, 96-well)\n")
    L.append(DISCLAIMER + "\n")
    L.append("**Workflow:** FACS Melody sort -> single-cell WGA -> post-WGA QC -> "
             "NEBNext Ultra II library prep -> library QC -> pool -> sequence.\n")

    L.append("## 1. Run configuration\n")
    L.append(f"- Samples / wells: **{p.n_samples}** (kits needed: {p.n_kits()})")
    L.append("- Plate format: **96-well** (both protocols are 96-well native)\n")

    L.append(_readiness_section(p))

    sc = p.protocol["sorting"]
    L.append("## 2. Stage 0b -- FACS Melody sort (up front)\n")
    L.append(f"- Sort single cells/nuclei into **{sc['cell_buffer_volume_ul']} uL Cell Buffer/well** "
             "(or dry, then add buffer). src: [A].")
    L.append("- **Column 1 = controls** (per protocol Figure 5):")
    for c in sc.get("controls", []):
        L.append(f"    - {c['well']}: {c['type']} ({c['formulation']})")
    L.append("- Columns 2-12: one sorted single cell per well.")
    L.append(f"- Control gDNA series: {sc['control_gdna']['make_10ng_stock']}; then dilute to "
             f"{sc['control_gdna']['serial_dilutions_ng_per_ul']} ng/uL.")
    L.append("- _BD FACS Melody control plane is being reverse-engineered (user's TODO); "
             "sorting is simulated until wired._\n")

    L.append("## 3. Deck layout (Hamilton STAR, 8-channel)\n")
    L.append("- Rail 1: tip carrier -- two 50 uL tip racks (fresh tips per reagent addition).")
    L.append("- Rail 8: plate carrier -- working plate, reagent-source plate, cleanup plate.")
    L.append("- Hamilton ODTC (on-deck thermocycler, heated lid) -- arm moves the plate in/out.")
    L.append("- BioTek Synergy H1 + black plate -- dsDNA (Qubit-chemistry) quant.")
    L.append("- Reagent-source columns: cell_buffer(1) lysis(2) reaction(3) elution(4) end_prep(5) "
             "adapter(6) ligation(7) pcr(8) beads(9) EtOH(10) TE(11) water(12).\n")

    wga = p.protocol["wga"]
    L.append("## 4. Stage W1 -- Single-cell whole-genome amplification (WGA)\n")
    L.append(_mix_table(p, "Lysis Mix", wga["lysis_mix"]["components"],
                        wga["lysis_mix"]["volume_per_reaction_ul"],
                        wga["lysis_mix"]["overage_fraction"], "src: [A] Table 2"))
    L.append(f"- Add **{wga['lysis_mix']['add_to_well_ul']} uL/well**; {wga['lysis_mix']['mix']}. "
             "**Use a thermal plate mixer, NOT a vortex** (cells).")
    L.append(_mix_table(p, "Reaction Mix", wga["reaction_mix"]["components"],
                        wga["reaction_mix"]["volume_per_reaction_ul"],
                        wga["reaction_mix"]["overage_fraction"], "src: [A] Table 3"))
    L.append(f"- Add **{wga['reaction_mix']['add_to_well_ul']} uL/well** (R1 then R2); "
             f"{wga['reaction_mix']['mix_after_add']}. **Do NOT vortex R2.**")
    L.append(_thermal_table(wga["amplification_program"], "DNA Amplification (ODTC)", "src: [A] Table 1"))
    L.append(f"- **SAFE STOP:** {wga['safe_stop']}.\n")

    wqc = p.protocol["wga_qc"]
    L.append("## 5. Stage W2 -- Post-WGA QC\n")
    L.append(f"- Dilute each reaction to **{wqc['dilute_to_ul']} uL** with Elution Buffer.")
    L.append(f"- Quant: {wqc['quant']['method']} ({wqc['quant']['qubit_sample_ul']} uL sample + "
             f"{wqc['quant']['qubit_reagent_ul']} uL Qubit reagent).")
    L.append(f"- Sizing: {wqc['sizing']['method']} at {wqc['sizing']['dilution_ng_per_ul']} ng/uL "
             f"(expected avg ~{wqc['sizing']['expected_fragment_bp']} bp, yield ~"
             f"{wqc['sizing']['expected_yield_ng']} ng).")
    L.append(f"- Gates: yield >= {wqc['gates']['min_yield_ng']} ng (expert-tunable); "
             f"NTC <= {wqc['gates']['ntc_max_ng']} ng (contamination FAILS the run).\n")

    lp = p.protocol["libprep"]
    ep = lp["end_prep"]
    L.append("## 6. Stage L -- NEBNext Ultra II library prep\n")
    L.append(f"**Input:** {lp['input']['dna_input_ng']} ng WGA product (expert-tunable; NEB supports "
             f"500 pg-1 ug) brought to {lp['input']['bring_to_volume_ul']} uL in {lp['input']['diluent']}.\n")
    L.append("### 6a. End Prep  (src: [B] Section 1)")
    L.append(f"- {ep['components'][1]['volume_ul']} uL End Prep Reaction Buffer + "
             f"{ep['components'][2]['volume_ul']} uL End Prep Enzyme Mix -> {ep['total_volume_ul']} uL; "
             f"{ep['mix']}.")
    L.append(_thermal_table(ep["program"], "End Prep program (ODTC)", "src: [B] 1.3"))

    al = lp["adaptor_ligation"]
    L.append("### 6b. Adaptor Ligation  (src: [B] Section 2)")
    L.append(f"- Adaptor dilution (choose by input): 20 uM (1 ug-101 ng) / 2 uM (100-5 ng) / "
             f"0.4 uM (<5 ng). **Selected: {al['selected_working_conc_uM']} uM** _(expert-tunable)_.")
    L.append(f"- {al['components'][1]['volume_ul']} uL adaptor + {al['components'][2]['volume_ul']} uL "
             f"Ligation MM + {al['components'][3]['volume_ul']} uL Enhancer -> {al['total_volume_ul']} uL; "
             f"{al['incubate']['temperature_c']} C {al['incubate']['time_s']//60} min (lid off).\n")

    cl = lp["cleanup_ligation"]["size_selection"]
    L.append("### 6c. SPRI size-selection  (src: [B] Section 3A)")
    L.append(f"- {cl['bead_add_1_ul']} uL beads (**0.4X, exact**) -> keep **supernatant**; "
             f"{cl['bead_add_2_ul']} uL beads (**0.2X, exact**) -> keep **beads**.")
    L.append(f"- 2x 80% EtOH ({cl['ethanol_volume_ul']} uL); air-dry <= {cl['air_dry_max_min']} min "
             "**(do NOT over-dry -- elute while dark brown + glossy)**.")
    L.append(f"- Elute {cl['elute_te_ul']} uL 0.1X TE; transfer {cl['transfer_ul']} uL.\n")

    pe = lp["pcr_enrichment"]
    L.append("### 6d. PCR enrichment  (src: [B] Section 4)")
    L.append(f"- {pe['components'][1]['volume_ul']} uL Primer Mix + {pe['components'][2]['volume_ul']} uL "
             f"Q5 MM -> {pe['total_volume_ul']} uL.")
    L.append(f"- **{pe['cycles']} cycles** _(expert-tunable; range {pe['cycles_range']} by input, "
             "src: [B] Table 4.1)_.")
    L.append(_thermal_table(pe["program"], "PCR enrichment (ODTC)", "src: [B] 4.1.3"))

    cp = lp["cleanup_pcr"]
    L.append("### 6e. SPRI 0.8X PCR cleanup  (src: [B] Section 5)")
    L.append(f"- {cp['bead_volume_ul']} uL beads (**0.8X, exact**); 2x 80% EtOH; air-dry "
             f"<= {cp['air_dry_max_min']} min (do NOT over-dry).")
    L.append(f"- Elute {cp['elute_te_ul']} uL 0.1X TE; transfer {cp['transfer_ul']} uL; Bioanalyzer HS.\n")

    lq = p.protocol["library_qc"]
    seq = p.protocol["sequencing"]
    L.append("## 7. Library QC + pool + sequence\n")
    L.append(f"- Quant: {lq['quant']['method']}. Sizing: {lq['sizing']['method']}.")
    L.append(f"- Final pool: **{lq['final_pool_cleanup']['bead_ratio_x']}X** SPRI "
             f"({lq['final_pool_cleanup']['example']}).")
    L.append(f"- Sequence (Illumina, UDI): low-pass {seq['low_pass']['read_length_bp']} bp PE, "
             f"{seq['low_pass']['reads_per_cell_millions'][0]}-{seq['low_pass']['reads_per_cell_millions'][1]} "
             f"M reads/cell (CNV); deep {seq['deep']['coverage_x'][0]}-{seq['deep']['coverage_x'][1]}X (SNV).\n")

    L.append("## 8. QC gates & tacit guards (baked in)\n")
    L.append("- **Bead ratios exact**: 0.4X + 0.2X (size-select), 0.8X (PCR cleanup), 0.75X (final pool).")
    L.append("- **Do not over-dry beads**: air-dry <= 5 min; elute while dark brown + glossy.")
    L.append("- **On ice** throughout; **do not vortex R2**; **thermal-mix (not vortex)** plates with cells.")
    L.append("- **Pipette on the well wall** (avoid the cell suspension) -- single-cell material loss.")
    L.append("- **WGA yield** floor + **NTC contamination** ceiling (NTC hot -> run FAILS).")
    L.append("- **Safe stops** at -20 C: after WGA, after End Prep, after Ligation, after PCR.\n")

    L.append("## 9. Wiring diagram\n")
    L.append(wiring_diagram_ascii(p))
    L.append("")
    L.append("---")
    L.append("_WGA: proprietary supplier protocol. Library prep: NEBNext Ultra II (NEB E7645). "
             "Sort: BD FACS Melody. Skill code: MIT. RESEARCH USE ONLY._")
    return "\n".join(L)


def write_manual(p: Params, out_dir: Path | str) -> dict:
    out = Path(out_dir)
    out.mkdir(parents=True, exist_ok=True)
    md = render_manual_markdown(p)
    md_path = out / "scwgs_manual.md"
    md_path.write_text(md, encoding="utf-8")
    result = {"markdown": str(md_path), "pdf": None}

    pdf_path = out / "scwgs_manual.pdf"
    if shutil.which("pandoc"):
        try:
            subprocess.run(
                ["pandoc", str(md_path), "-o", str(pdf_path)],
                check=True, capture_output=True, timeout=120,
            )
            result["pdf"] = str(pdf_path)
        except Exception as exc:  # pragma: no cover
            result["pdf_error"] = f"pandoc failed: {exc}"
    else:
        result["pdf_error"] = "pandoc not found; Markdown only (PDF is an external dep)."
    return result
