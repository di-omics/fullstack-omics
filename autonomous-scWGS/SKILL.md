---
name: autonomous-scWGS
description: >
  Take a scientist from "run single-cell whole-genome sequencing (WGS) on N cells" all
  the way to a result -- purchase, FACS sort, automated execution, and analysis -- on a
  Hamilton STAR (PyLabRobot) with a Hamilton ODTC on-deck thermocycler and a BioTek
  Synergy H1 plate reader, with a BD FACS Melody sort up front. Use this whenever the
  user mentions whole-genome sequencing, the vendor, whole-genome amplification / Primary Template-directed Amplification,
  single-cell whole-genome amplification (WGA), NEBNext Ultra II library prep for
  single-cell WGS, FACS Melody sorting into a WGA plate, PyLabRobot/Hamilton automation
  of a single-cell DNA protocol, Rhodamine B liquid-handling QC on a plate reader, or
  building a BOM / purchase plan / bench manual / WGS analysis pipeline for single-cell
  genome sequencing. Runs entirely in the PyLabRobot simulator with no hardware.
  RESEARCH USE ONLY -- not clinically validated.
license: MIT
---

# autonomous-scWGS skill

Automates **single-cell WGS** end-to-end on a Hamilton deck via PyLabRobot: a **BD FACS
Melody** sort -> **whole-genome amplification** whole-genome amplification (the kit user guide) ->
**NEBNext Ultra II** library prep (NEB E7645) -> pool -> analysis. Second in a series after
`flashseq-skill` (FLASH-seq scRNA-seq). The shared **Rhodamine B readiness QC** and
**humanoid ops** modules are part of the series.

**Methods are proprietary vendor protocols (RESEARCH USE ONLY), not open-licensed.** Every
reagent, volume, temperature, time, and bead ratio comes from the vendor guides - see
`config/*.yaml`, annotated `# src: [A]` (whole-genome sequencing) / `# src: [B]` (NEBNext). Nothing is
invented: values absent from a guide are `# TODO: expert value`; values the user must tune
(NEBNext input, PCR cycles, adaptor dilution, insert size) are `# expert-tunable` with the
guide default kept. Verify all values against the source guides before running.

## Source of truth (edit these, not the code)

- `config/protocol_params.yaml` - volumes, temps, times, cycles, bead ratios, QC gates.
- `config/reagents.yaml` - kit-based BOM (part numbers; TODO where a guide omits one).
- `config/instruments.yaml` - connectivity registry + PLR backends + controller kit.
- `config/readiness.yaml` - Rhodamine B QC settings (engineering defaults, `# expert-tunable`).

## Run everything (PLR simulator, no hardware)

```bash
pip install -r requirements.txt
python scripts/run_all.py --n 16 --first-time-buyer [--operator humanoid]
python tests/test_end_to_end.py     # 9/9
```

## Stages

### 0. Instrument readiness (`autoscwgs/readiness/`) - REQUIRED
Rhodamine B liquid-handling QC on the Synergy H1: dispense at low/medium/high protocol
volume scales across the 96-well plate, compute per-range **CV**, gate **READY vs
NEEDS_CALIBRATION**. The automation fails closed (`InstrumentNotReady`) until the STAR
passes. `python scripts/run_readiness.py [--state needs_calibration]`.

### 0b. FACS Melody sort (`autoscwgs/sorting/`)
Plans the plate (controls in column 1 per protocol Figure 5; cells in cols 2-12) and
sorts single cells into 3 uL Cell Buffer/well. The Melody control plane is the user's
reverse-engineering TODO, so sorting is **simulated** (`FacsMelodyHardwareBackend` is the
seam for the real client). `python scripts/run_sorting.py --n 88`.

### 1. Procurement (`autoscwgs/procurement/`)
Kit-based BOM scaled to N (one whole-genome sequencing + one NEBNext kit per 96) -> routed to a channel
(**browser-agent** carts for NEB/Thermo/Agilent/..., **direct** for the vendor/BD, **PO**
fallback) -> ONE "approve to purchase" summary. **Nothing is ordered without a single human
approval**; `place_orders()` is a dry run even with `--approve`. First-time buyers get a
Raspberry Pi controller kit + exact cabling from the connectivity resolver.

### 2. Manual (`autoscwgs/manual/`)
Printable bench manual from the configs: sort layout, deck layout, scaled reagent tables,
thermal programs, on-ice/RT handling, safe stops, QC gates, ASCII wiring diagram. Markdown
always; PDF if `pandoc` is present.

### 3. Automation (`autoscwgs/automation/`)
Drives the flow through PyLabRobot with swappable backends (`sim` = chatterbox + a dsDNA
signal model; `hardware` = real backends from `instruments.yaml`, refusing while TODOs
remain). Readiness + sort run first. QC gates + tacit guards fire at the protocols'
checkpoints (see below). `--operator humanoid` routes bench tasks through the experimental
humanoid ops layer.

### 4. Result (`autoscwgs/result/`)
Sequencing analysis via **WGS analysis WGS analysis** (the vendor Nextflow pipeline for whole-genome sequencing /
whole-genome amplification data, `github.com/the vendor/bj-wgs`): Sentieon BWA MEM -> LocusCollector+Dedup -> BQSR ->
DNAScope (whole-genome amplification-corrected `bioskryb129` model) or Haplotyper -> SnpEff/ClinVar/dbSNP -> Sentieon
metrics -> VCFeval (GIAB only) -> MultiQC. The stage generates the WGS analysis `input.csv` (one row
per sorted single-cell library) and `run_bj_wgs.sh` (the exact `nextflow run main.nf` command
with genome/platform/model/resources). External deps (Java, Nextflow, Docker, AWS CLI,
Sentieon license) are preflighted and marked (not bundled). Values from `src: [C]` WGS analysis README.

## QC gates + tacit guards (baked in)

- **Bead ratios are exact**: 0.4x/0.2x (NEBNext size-select), 0.8x (PCR cleanup), 0.75x
  (final pool). The code raises `GuardViolation` on drift.
- **Do not over-dry beads**: air-dry <= 5 min; elute while dark brown + glossy.
- **On ice** throughout; **do not vortex R2**; **thermal-mix (not vortex)** plates with
  cells; **pipette on the well wall** (single-cell material loss).
- **WGA yield** floor; **NTC contamination** ceiling -> run **FAILS** if NTC is hot;
  **fragment size** ~250-3500 bp (avg ~1275 bp).
- **Safe stops** (-20 C) after WGA, End Prep, Ligation, PCR.

## Hard safety rule

Source every value from the vendor guides; never invent one. If it's not in a guide, it's
`# TODO: expert value`. Methods are proprietary and RESEARCH USE ONLY - verify against the
source guides before a real run, and do not redistribute the vendor manuals.

## Reference files (read as needed)

- `references/protocol_stages.md` - the stages with exact protocol values.
- `references/procurement.md` - channels, approval flow, first-time-buyer kit.
- `references/automation.md` - deck layout, backend swap, sim vs hardware, FACS/ops seams.
- `references/architecture.md` - repo map and how the pieces fit.
