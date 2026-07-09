# autonomous-scWGS

Autonomous **single-cell genomics** on a Hamilton / PyLabRobot deck - from *instrument
purchase* -> *FACS sort* -> *automated execution* -> *result*, running entirely in the
PyLabRobot **simulator** with no hardware.

> **Part of [`fullstack-omics`](..).** This is the single-cell **WGS (DNA)** module:
> **whole-genome amplification** whole-genome amplification (the vendor) + **NEBNext Ultra II** library
> prep (NEB), with a **BD FACS Melody** sort up front. Its sibling module
> [`autonomous-scRNAseq`](../autonomous-scRNAseq) is the FLASH-seq scRNA-seq pipeline.

> **RESEARCH USE ONLY - not clinically validated.** The methods are **proprietary vendor
> protocols** (whole-genome sequencing the kit user guide; NEBNext E7645) reproduced for automation
> interoperability, **not open-licensed**. Verify every value against the source guides
> before a real run. See [ATTRIBUTION.md](ATTRIBUTION.md).

## The flow

```
FACS Melody sort (3 uL Cell Buffer/well, controls col 1)
  -> Lysis Mix 3 uL + thermal-mix -> Reaction Mix 6 uL + thermal-mix
  -> ODTC WGA (PTA): 30 C 2.5 h -> 65 C 3 min -> 4 C
  -> dilute to 40 uL -> dsDNA quant on Synergy H1 -> WGA QC gates
  -> NEBNext End Prep -> Adaptor Ligation -> SPRI size-select (0.4x/0.2x)
  -> PCR enrichment -> SPRI 0.8x cleanup -> library QC -> pool (0.75x) -> sequence
  -> analysis: BaseJumper BJ-WGS (Nextflow): Sentieon BWA MEM -> Dedup -> BQSR
     -> DNAScope (PTA model) -> SnpEff/ClinVar/dbSNP -> MultiQC
```

Target deck: **Hamilton STAR** (liquid handler) + **Hamilton ODTC** (on-deck
thermocycler) + **BioTek Synergy H1** (dsDNA fluorometric quant) + **BD FACS Melody**
(sort). Backends are swappable (`sim` <-> `hardware`); the sim needs no hardware.

## Quickstart

```bash
pip install -r requirements.txt
git submodule update --init --recursive     # fetch the included BJ-WGS pipeline (pinned 2.1.0)
python scripts/run_all.py --n 16 --first-time-buyer        # all stages -> output/
python tests/test_end_to_end.py                            # 10/10, no hardware
```

> The WGS analysis analysis pipeline is **included as a git submodule** (`bj-wgs/`, pinned to
> release 2.1.0). It's the vendor's proprietary pipeline, referenced (not redistributed);
> the submodule fetches it from the vendor's repo. Running it needs Nextflow + Docker + a
> Sentieon license. The sim (stages 0-3) needs none of that.

Per-stage:

| Stage | Script | Output |
|---|---|---|
| 0. Readiness (Rhodamine B QC) | `python scripts/run_readiness.py [--state needs_calibration]` | `output/instrument_readiness.txt` |
| 0b. FACS sort (sim) | `python scripts/run_sorting.py --n 88` | `output/sort_report.txt` |
| 1. Procurement | `python scripts/run_procurement.py --n 96 [--first-time-buyer] [--approve]` | `output/purchase_approval.md` |
| 2. Manual | `python scripts/render_manual.py --n 96` | `output/scwgs_manual.md` |
| 3. Automation | `python scripts/run_automation.py --n 16 [--operator humanoid]` | `output/automation_run.txt` |
| 4. Result (WGS analysis) | `python scripts/generate_analysis.py` | `output/run_bj_wgs.sh` + `output/input.csv` |

## What's baked in

- **Stage 0 instrument readiness (REQUIRED):** a **Rhodamine B** liquid-handling QC on
  the Synergy H1. Dispenses at low/medium/high protocol volume scales across the 96-well
  plate, computes per-range **CV**, and gates **READY vs NEEDS_CALIBRATION**. The
  automation refuses to run cells until the STAR passes (fail-closed).
- **Humanoid ops person (experimental):** `--operator humanoid` compiles each bench task
  (load the sorter, set up the deck, click run, move plates) into structured manipulation
  commands - the seam to drop a real humanoid SDK into. Baked in to help labs onboard.
- **Kit-based procurement:** BOM scaled to N -> one whole-genome sequencing kit + one NEBNext kit per 96
  -> routed to a purchase channel (browser-agent carts / the vendor.BD direct / PO) -> **one
  human approval**. `place_orders()` refuses without it and is a dry-run even when approved.
- **QC gates + tacit guards:** exact SPRI ratios (0.4x/0.2x/0.8x/0.75x) raise on drift;
  **do-not-over-dry beads**; **on ice**; **do-not-vortex R2**; **thermal-mix (not vortex)**
  for plates with cells; **pipette on the well wall**; WGA-yield floor; **NTC contamination
  fails the run**; fragment-size checks; -20 C safe stops.

## Source of truth (edit these, not the code)

- `config/protocol_params.yaml` - volumes, temps, times, cycles, bead ratios, QC gates
  (every value annotated `# src: [A] ...` / `# src: [B] ...`).
- `config/reagents.yaml` - kit-based BOM (part numbers; `# TODO` where a guide omits one).
- `config/instruments.yaml` - connectivity registry + PLR backends + controller kit.
- `config/readiness.yaml` - Rhodamine B QC settings (engineering defaults; `# expert-tunable`).

## Integration roadmap (hardware wiring)

Everything above runs in the PyLabRobot simulator today. To take it to hardware:

- **FACS Melody control plane:** BD FACSChorus is a closed GUI with no open API, so the
  sort is reverse-engineered by **computer vision + UI automation** of FACSChorus - see the
  di-omics CV stack, [`lab-cv`](https://github.com/di-omics/lab-cv) and
  [`awesome-wetlab-cv`](https://github.com/di-omics/awesome-wetlab-cv). Drop that client into
  `autoscwgs/sorting/facs.py` (`FacsMelodyHardwareBackend`); the simulator seam is unchanged.
- **Hamilton ODTC backend:** PyLabRobot 0.2.x has no ODTC backend. Wire a real **Inheco ODTC
  backend (TCP/IP, SiLA2)** into the di-omics [`pylabrobot`](https://github.com/di-omics/pylabrobot)
  fork, then set `instruments.yaml -> hamilton_odtc.plr.backend_hardware`.
- **NEBNext input / cycles / adaptor dilution / insert size:** `# expert-tunable` with the
  guide default kept - tune on real data (not a blocker).
- **Qubit-on-H1 ex/em:** the guides use a Qubit fluorometer; reading that chemistry on the
  H1 needs a standard curve (ex/em ~485/530, `# TODO: verify` on your filter set).

See `references/` for architecture, procurement, automation, and the protocol-stage tables.
Sibling module: [`autonomous-scRNAseq`](../autonomous-scRNAseq) (FLASH-seq scRNA-seq, CC-BY method).
