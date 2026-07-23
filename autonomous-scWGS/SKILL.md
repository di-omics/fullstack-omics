---
name: autonomous-scWGS
description: >
  Take a scientist from "run single-cell whole-genome sequencing (WGS) on N cells" through
  purchase planning, simulated FACS sort, automated wet-lab execution, and a generated
  external-analysis handoff on a Hamilton STAR (PyLabRobot) with a Hamilton ODTC on-deck
  thermocycler and a BioTek Synergy H1 plate reader, with a BD FACS Melody sort up front.
  Use this whenever the
  user mentions single-cell whole-genome amplification (WGA), NEBNext Ultra II library prep for
  single-cell WGS, FACS Melody sorting into a WGA plate, PyLabRobot/Hamilton automation
  of a single-cell DNA protocol, Rhodamine B liquid-handling QC on a plate reader, or
  building a BOM / purchase plan / bench manual / WGS analysis pipeline for single-cell
  genome sequencing. Wet-lab stages run in the PyLabRobot simulator with no hardware;
  external analysis is an operator-run step.
  RESEARCH USE ONLY -- not clinically validated.
license: MIT
---

# autonomous-scWGS skill

Automates the **single-cell WGS wet-lab flow** on a Hamilton deck via PyLabRobot: a **BD FACS
Melody** sort -> **single-cell whole-genome amplification (WGA)** ->
**NEBNext Ultra II** library prep (NEB E7645) -> pool -> generated analysis handoff. Second in a series after
`flashseq-skill` (FLASH-seq scRNA-seq). The shared **Rhodamine B readiness QC** and
**humanoid ops** modules are part of the series.

**Methods are proprietary vendor protocols (RESEARCH USE ONLY), not open-licensed.** Every
reagent, volume, temperature, time, and bead ratio comes from the vendor guides - see
`config/*.yaml`, annotated `# src: [A]` (WGA) / `# src: [B]` (NEBNext). Nothing is
invented: values absent from a guide are `# TODO: expert value`; values the user must tune
(NEBNext input, PCR cycles, adaptor dilution, insert size) are `# expert-tunable` with the
guide default kept. Verify all values against the source guides before running.

## Source of truth (edit these, not the code)

- `config/protocol_params.yaml` - volumes, temps, times, cycles, bead ratios, QC gates.
- `config/reagents.yaml` - kit-based BOM (part numbers; TODO where a guide omits one).
- `config/reagents.local.yaml` - ignored private supplier/SKU/channel overrides.
- `config/instruments.yaml` - connectivity registry + PLR backends + controller kit.
- `config/readiness.yaml` - Rhodamine B QC settings (engineering defaults, `# expert-tunable`).
- `references/source_map.md` - stable source IDs and local source/procurement and analysis
  interface contracts.

## Run everything (PLR simulator, no hardware)

```bash
pip install -r requirements.txt
python scripts/run_all.py --n 16 --first-time-buyer [--operator humanoid]
python tests/test_end_to_end.py     # 10/10
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
Kit-based BOM scaled to N (one WGA + one NEBNext kit per 96) -> routed to a channel
(**browser-agent** carts for NEB/Thermo/Agilent/..., **direct** for specialty suppliers/BD, **PO**
fallback) -> ONE "approve to purchase" summary. **Nothing is ordered without a single human
approval**; unresolved supplier/SKU/channel entries route to `verify`, and
`place_orders()` refuses until private/local configuration is complete. It remains a dry
run even with `--approve`. First-time buyers get a
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

### 4. Analysis handoff (`autoscwgs/result/`)
The generated handoff targets a compatible external **WGS Nextflow pipeline** supplied through
`WGS_PIPELINE_DIR`. Pipeline stages include Sentieon BWA MEM -> LocusCollector+Dedup ->
BQSR -> DNAScope or Haplotyper -> SnpEff/ClinVar/dbSNP -> Sentieon metrics -> VCFeval
(GIAB only) -> MultiQC. The stage generates `input.csv` (one row per sorted single-cell
library) and `run_wgs_analysis.sh`, which runs the compatible `main.nf` with
genome/platform/model/resources. `DNASCOPE_MODEL` must be set explicitly. External
dependencies (Java, Nextflow, Docker, AWS CLI, Sentieon license) are required by the
runner but not bundled. The simulator generates and validates the handoff; it does not
execute the external pipeline. Values use `src: [C]`.

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
- `references/source_map.md` - stable source IDs, private-map schema, and interface contract.
