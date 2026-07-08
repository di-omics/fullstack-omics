"""Render the printable bench manual (Markdown; optional PDF) from protocol_params.yaml."""

from __future__ import annotations

import shutil
import subprocess
from pathlib import Path
from typing import Optional

from ..params import Params
from .wiring import wiring_diagram_ascii

DISCLAIMER = (
    "> **RESEARCH USE ONLY -- not clinically validated.** Volumes/temps/times are "
    "transcribed from FLASH-seq UMI v3 (DOI 10.17504/protocols.io.bp2l619rdvqe/v3, "
    "CC-BY). This document was assembled partly from OCR -- **verify every per-well "
    "volume against the DOI before a real run.**"
)


def _mix_table(p: Params, title: str, components: list[dict], src: str) -> str:
    lines = [f"### {title}  ({src})", ""]
    lines.append("| Reagent | Reaction conc. | Per-well (scaled) | Total for run (+overage) |")
    lines.append("|---|---|---|---|")
    for c in components:
        base = float(c["volume_ul_384"])
        per_well = p.scale_volume(base)
        total = p.component_total_ul(base)
        lines.append(f"| {c['name']} | {c.get('reaction_conc','-')} | {per_well} uL | {total} uL |")
    lines.append("")
    return "\n".join(lines)


def _thermal_table(program: dict, title: str, src: str) -> str:
    lines = [f"### {title}  ({src})", "", "| Step | Temp | Time | Cycles |", "|---|---|---|---|"]
    for step in program["steps"]:
        if "substeps" in step:
            cyc = step["cycles"]
            for s in step["substeps"]:
                lines.append(f"| {s['name']} | {s['temperature_c']} C | {s['time_s']} s | x{cyc} |")
        else:
            t = step["time_s"]
            time_str = "hold" if t == 0 else f"{t} s"
            lines.append(f"| {step['name']} | {step['temperature_c']} C | {time_str} | x{step.get('cycles',1)} |")
    lines.append("")
    return "\n".join(lines)


def _readiness_section(p: Params) -> str:
    cfg = p.readiness
    if not cfg:
        return ""
    s = cfg["synergy_h1"]
    rh = cfg["rhodamine"]
    lines = ["## Instrument readiness - Step 1 (REQUIRED before any run)\n"]
    lines.append("Before spending cells, prove the liquid handler pipettes precisely with a "
                 "**Rhodamine B fluorescence check** on the Synergy H1. Low CV → **READY**; "
                 "high CV → **NEEDS_CALIBRATION** (calibrate before running).\n")
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
    fmt = p.plate_format
    mult = p.volume_multiplier
    L: list[str] = []
    L.append(f"# FLASH-seq UMI -- Bench Manual  (N = {p.n_cells} cells, {fmt}-well)\n")
    L.append(DISCLAIMER + "\n")

    L.append("## 1. Run configuration\n")
    L.append(f"- Cells / wells: **{p.n_cells}**")
    L.append(f"- Plate format: **{fmt}-well** (volume multiplier x{mult})")
    if fmt == 384:
        L.append("- **384-well requires a nanodispenser (I.DOT).** For Hamilton, use 96-well (5x volumes).")
    else:
        L.append("- 96-well uses **5x** the protocol's native 384-well volumes (protocol-recommended).")
    L.append(f"- Master-mix overage: {int(p.overage*100)}%\n")

    L.append(_readiness_section(p))

    L.append("## 2. Deck layout (Hamilton STARlet, 8-channel)\n")
    L.append("- Rail 1: tip carrier -- two 50 uL tip racks (fresh tips per reagent addition).")
    L.append("- Rail 8: plate carrier -- working plate, reagent-source plate, cleanup plate.")
    L.append("- On-deck thermocycler (heated lid) -- arm moves the working plate in/out.")
    L.append("- BioTek Synergy H1 + black plate -- PicoGreen dsDNA read.")
    L.append("- Reagent-source plate columns: lysis(1) RT-PCR(2) water(3) beads(4) tagmentation(5) "
             "SDS(6) index(7) NPM(8) ethanol(9) PicoGreen(10).\n")

    L.append("## 3. Reagent preparation\n")
    L.append(_mix_table(p, "Lysis mix", p.protocol["lysis_mix"]["components"], "Stage 1"))
    L.append(_mix_table(p, "RT-PCR mix", p.protocol["rt_pcr"]["mix_components"], "Stage 4"))

    L.append("## 4. Step-by-step\n")
    L.append("**Stage 1-2 -- Lysis mix + sort.** Dispense "
             f"{p.scale_volume(p.protocol['lysis_mix']['dispense_volume_ul_384'])} uL lysis/well. "
             "Sort single cells into wells. Seal (foil). **Keep ON ICE / store -80 C.**\n")
    L.append("**Stage 3 -- Lysis.** Thermocycler, heated lid:")
    L.append(_thermal_table({"steps": p.protocol["lysis_thermocycler"]["steps"]}, "Lysis program", "Stage 3"))
    L.append("_After: spin condensation, keep on cool rack, proceed quickly._\n")

    L.append("**Stage 4 -- RT-PCR.** Add "
             f"{p.scale_volume(p.protocol['rt_pcr']['dispense_volume_ul_384'])} uL RT-PCR mix/well.")
    L.append(_thermal_table(p.protocol["rt_pcr"]["program"], "RT-PCR program", "Stage 4"))
    L.append("- PCR cycles are **expert-tunable** (protocol 20-24; 20-21 HEK293T, 23-24 hPBMC).")
    L.append(f"- **SAFE STOP:** {p.protocol['rt_pcr']['safe_stop']}.\n")

    cc = p.protocol["cdna_cleanup"]
    L.append("**Stage 5 -- cDNA cleanup (SPRI 0.6x).**")
    L.append(f"- Add {p.scale_volume(cc['add_water_ul_384'])} uL water to cDNA, then "
             f"{p.scale_volume(cc['beads_volume_ul_384'])} uL beads (**0.6x, exact**).")
    L.append(f"- {cc['incubate_off_magnet_min']} min off-magnet (RT) -> {cc['incubate_on_magnet_min']} min "
             "on-magnet -> remove sup.")
    L.append(f"- Resuspend {p.scale_volume(cc['resuspend_water_ul_384'])} uL water; "
             f"transfer {p.scale_volume(cc['transfer_volume_ul_384'])} uL.")
    L.append("- **GUARD: do NOT over-dry beads** (no ethanol wash; resuspend before pellet dries).")
    L.append(f"- **SAFE STOP:** {cc['safe_stop']}.\n")

    g = p.protocol["cdna_qc"]["gates"]
    L.append("**Stage 6-7 -- QC + quant.** Bioanalyzer HS (optional): avg "
             f"{g['cdna_size_kb_min']}-{g['cdna_size_kb_max']} kb, flag <{g['flag_below_bp']} bp. "
             "PicoGreen dsDNA on **Synergy H1** (black plate).\n")

    L.append(f"**Stage 8 -- Normalize** to {p.protocol['normalization']['target_concentration_pg_per_ul']} "
             "pg/uL. Wells below target cannot be normalized up.\n")

    tg = p.protocol["tagmentation"]
    L.append("**Stage 9 -- Tagmentation + indexing PCR.**")
    L.append(f"- Tagmentation mix: ATM {tg['atm_volume_ul_384']} uL (**expert-tunable**, 0.1-0.2) + "
             f"TD {p.scale_volume(tg['td_volume_ul_384'])} uL. Dispense "
             f"{p.scale_volume(tg['tagmentation_mix_total_ul_384'])} uL + 1 uL normalized cDNA.")
    L.append(_thermal_table({"steps": tg["tagmentation_program"]["steps"]}, "Tagmentation", "Stage 9"))
    L.append(f"- Add {p.scale_volume(tg['neutralization']['sds_volume_ul_384'])} uL 0.2% SDS, "
             f"{tg['neutralization']['incubate_rt_min']} min RT. **GUARD: do NOT put back on ice.**")
    L.append(f"- Add {p.scale_volume(tg['indexing']['index_adaptor_volume_ul_384'])} uL index adaptors "
             f"({tg['indexing']['index_adaptor_concentration_uM']} uM) + "
             f"{p.scale_volume(tg['indexing']['npm_volume_ul_384'])} uL NPM.")
    L.append(_thermal_table(tg["enrichment_pcr"], "Enrichment PCR", "Stage 9"))
    L.append(f"- **SAFE STOP:** {tg['safe_stop']}.\n")

    lc = p.protocol["library_cleanup"]
    L.append("**Stage 10 -- Library cleanup (SPRI 0.8x).**")
    L.append(f"- Beads **0.8x (exact)**; {lc['ethanol_percent']}% EtOH wash "
             f"({lc['ethanol_volume_ul']} uL, {lc['ethanol_incubate_s']} s).")
    L.append(f"- Dry {lc['dry_min']} min **until small cracks appear (do NOT over-dry)**; "
             f"elute {lc['elute_water_ul']} uL, transfer {lc['transfer_volume_ul']} uL.")
    L.append(f"- QC: Bioanalyzer ~{lc['qc']['library_size_bp_target']} bp; flag >{lc['qc']['flag_above_bp']} bp.\n")

    seq = p.protocol["sequencing"]
    L.append(f"**Stage 11 -- Pool + sequence.** {seq['platform']}, read mode {seq['read_mode']} "
             f"(alt {', '.join(seq['read_mode_alternatives'])}); PE recommended, R1 >= {seq['read1_min_bp']} bp "
             f"(pref {seq['read1_preferred_bp']}).\n")

    L.append("## 5. QC gates & tacit guards\n")
    L.append("- Bead ratios are **exact**: 0.6x (cDNA), 0.8x (library).")
    L.append("- **Do not over-dry beads** (both cleanups).")
    L.append("- **On ice** through lysis/RT setup; **do not re-chill** after SDS.")
    L.append("- cDNA 1.8-2.2 kb (flag <400 bp); library ~700-1000 bp (flag >1000 bp).")
    L.append("- PicoGreen: wells < 100 pg/uL cannot be normalized up.")
    L.append("- Safe stops at -20 C: after RT-PCR, after cDNA cleanup, after enrichment PCR.\n")

    L.append("## 6. Wiring diagram\n")
    L.append(wiring_diagram_ascii(p))
    L.append("")
    L.append("---")
    L.append("_Method: FLASH-seq UMI v3, Picelli & Hahaut, protocols.io 2022, "
             "DOI 10.17504/protocols.io.bp2l619rdvqe/v3 (CC-BY). Skill code: MIT._")
    return "\n".join(L)


def write_manual(p: Params, out_dir: Path | str) -> dict:
    out = Path(out_dir)
    out.mkdir(parents=True, exist_ok=True)
    md = render_manual_markdown(p)
    md_path = out / "flashseq_manual.md"
    md_path.write_text(md, encoding="utf-8")
    result = {"markdown": str(md_path), "pdf": None}

    # Optional PDF via pandoc (external dependency; skipped if unavailable).
    pdf_path = out / "flashseq_manual.pdf"
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
