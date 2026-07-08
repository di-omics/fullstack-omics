---
name: flashseq-skill
description: >
  Take a scientist from "run FLASH-seq on N cells" all the way to a result --
  procurement, wire-up, automated execution, and analysis -- on a Hamilton STAR/
  STARlet (PyLabRobot) with an on-deck thermocycler and a BioTek Synergy H1 plate
  reader. Use this whenever the user mentions FLASH-seq, FLASH-seq UMI, low-input or
  full-length single-cell RNA-seq library prep, single-cell cDNA amplification +
  Nextera XT tagmentation on a liquid handler, PyLabRobot/Hamilton automation of an
  scRNA-seq protocol, PicoGreen normalization to 100 pg/uL, a Rhodamine B
  liquid-handling / pipetting-precision (CV) check on a Synergy H1, instrument-
  readiness QC, a humanoid/robot lab operator, or building a BOM / purchase plan /
  bench manual / analysis pipeline for FLASH-seq. Runs entirely in the PyLabRobot
  simulator with no hardware. RESEARCH USE ONLY -- not clinically validated.
license: MIT
---

# FLASH-seq skill

Automates the **FLASH-seq UMI protocol v3** (Picelli & Hahaut, protocols.io 2022,
DOI [10.17504/protocols.io.bp2l619rdvqe/v3](https://dx.doi.org/10.17504/protocols.io.bp2l619rdvqe/v3),
CC-BY) end-to-end on a Hamilton deck via PyLabRobot. First of a series (TIP-seq next).

**Every reagent, volume, temperature, time, and catalog number comes from the
protocol** - see `config/*.yaml`. Nothing is invented: values absent from the
protocol are marked `# TODO: expert value`, and OCR-ambiguous values carry a
`verify` flag. Values the author flags for tuning (PCR cycle count by cell type,
Tn5/ATM amount) are marked `# expert-tunable` with the protocol default kept.

## Source of truth (edit these, not the code)

- `config/protocol_params.yaml` - volumes, temps, times, cycles, bead ratios, QC gates.
- `config/reagents.yaml` - vendor, catalog #, scaling rule per material.
- `config/instruments.yaml` - connectivity registry + PLR backends + controller kit.

The generators read from these, so tuning a run means editing YAML. The default
run is **96-well at 5x volumes** - the Hamilton-friendly version the protocol
explicitly supports. 384-well (native nL volumes) is available but flagged
**"requires a nanodispenser."**

## The four stages

Run everything at once (all four wired in the PLR simulator):

```bash
pip install -r requirements.txt
python scripts/run_all.py --n 96 --first-time-buyer
```

Or run a stage at a time:

| Stage | Script | Output |
|---|---|---|
| 1. Procurement | `python scripts/run_procurement.py --n 96 [--first-time-buyer] [--approve]` | `output/purchase_approval.md` |
| 2. Manual | `python scripts/render_manual.py --n 96` | `output/flashseq_manual.md` |
| 0. Readiness (Step 1) | `python scripts/run_readiness.py [--state needs_calibration]` | `output/instrument_readiness.txt` |
| 3. Automation | `python scripts/run_automation.py --n 16 --mode sim [--verbose]` | `output/automation_run.txt` |
| 4. Result | `python scripts/generate_analysis.py` | `output/flashseq_pipeline.sh` + `flashseq_analysis.py` |

## Instrument readiness - required Step 1 (`flashseq/readiness/`)

Before spending irreplaceable cells, prove the liquid handler pipettes precisely: a
**Rhodamine B fluorescence check** dispenses dye at **low / medium / high** protocol
volume scales across a 96-well plate, reads on the **Synergy H1** (settings in
`config/readiness.yaml`), and computes the **per-well CV** per range → **READY** or
**NEEDS_CALIBRATION**. Automation (`run_flashseq`) runs this first and **fails closed**
if the handler isn't ready (`readiness="required"` by default). See `references/readiness.md`.

## Operator - who tends the deck (`flashseq/ops/`)

The physical "ops person" is swappable like a backend: `HumanOperator` (default -
prints bench instructions) or `HumanoidOperator` (**experimental** - compiles each
bench task into structured manipulation commands for a humanoid robot to set up the
deck and press run). `python scripts/run_all.py --operator humanoid`.

### 1. Procurement (`flashseq/procurement/`)
Builds the BOM scaled to N, routes each item to a channel - **IDT oligo API** for
custom oligos, **browser-automation agent** (Claude in Chrome) for vendor
storefronts, **PO/requisition** (Coupa/Jaggaer) fallback - and emits ONE "approve
to purchase" summary. **Nothing is ordered without a single human approval**, and
even with `--approve`, order placement is a DRY RUN in v1 (live channels are
external deps). First-time buyers get a Raspberry Pi controller kit + exact cabling
from the connectivity resolver (`--first-time-buyer`). See `references/procurement.md`.

### 2. Manual (`flashseq/manual/`)
Renders a printable bench manual from `protocol_params.yaml`: deck layout, scaled
reagent tables, per-step volumes/timings, on-ice vs RT handling, safe-stop points,
QC gates, and an ASCII wiring diagram. Markdown always; PDF if `pandoc` is present.

### 3. Automation (`flashseq/automation/`)
Drives the FLASH-seq flow through PyLabRobot with **swappable backends**
(`mode="sim"` = chatterbox, no hardware; `mode="hardware"` = real backends from
`instruments.yaml`). Flow: lysis-mix dispense → 72 °C 3 min → RT-PCR-mix → RT 50 °C
60 min + PCR (20-24 cyc) → SPRI 0.6x → PicoGreen on Synergy H1 → normalize to
100 pg/µL → tagmentation → 55 °C 8 min → SDS + index + NPM → enrichment PCR (14 cyc)
→ SPRI 0.8x → quant → pool. **QC gates + tacit guards** are enforced at the
protocol's checkpoints (see below). Details: `references/automation.md`.

### 4. Result (`flashseq/result/`)
Generates the full **fastq to analysis** pipeline for protocol §12. Two artifacts:
`flashseq_pipeline.sh` (`bcl2fastq → umi_tools extract`, UMI in R1/R2, CTAAC spacer,
8 bp UMI, regex `→ STAR → samtools -F 260 → featureCounts → umi_tools count`) and
`flashseq_analysis.py` (scanpy: assemble count matrices `→ QC → normalize → HVG →
PCA → Leiden → UMAP → marker genes`). External tools are preflighted and marked
(not bundled): bcl2fastq, umi_tools, STAR, samtools, featureCounts, bbmap, scanpy.

## QC gates + tacit guards (baked in)

- **Bead ratios are exact**: 0.6x (cDNA cleanup), 0.8x (library cleanup). The code
  raises `GuardViolation` if a ratio drifts.
- **Do not over-dry beads**: cDNA cleanup does no ethanol wash and resuspends before
  the pellet dries; library cleanup dries only ~2 min "until small cracks."
- **On ice** through lysis/RT setup; **do not re-chill** after SDS neutralization.
- **cDNA size** 1.8-2.2 kb (flag < 400 bp); **library** ~700-1000 bp (flag > 1000 bp).
- **PicoGreen**: wells < 100 pg/µL cannot be normalized up and are flagged.
- **Safe stops** (−20 °C) after RT-PCR, cDNA cleanup, and enrichment PCR.

## Hard safety rule

Source every value from the protocol; never invent one. If it's not in the
protocol, it's `# TODO: expert value`. Any per-well volume here was assembled partly
from OCR - **verify against the DOI before a real run.** RESEARCH USE ONLY.

## Reference files (read as needed)

- `references/protocol_stages.md` - the 12 stages with the exact protocol values.
- `references/procurement.md` - channels, approval flow, first-time-buyer kit.
- `references/readiness.md` - Rhodamine B liquid-handling QC + Synergy H1 settings.
- `references/automation.md` - deck layout, backend swap, sim vs hardware, operator.
- `references/architecture.md` - repo map and how the pieces fit.
