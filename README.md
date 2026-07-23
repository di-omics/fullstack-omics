# fullstack-omics

> RESEARCH USE ONLY - not clinically validated.

Full-stack, autonomous single-cell omics: from *"run this assay on N cells"* all the
way to a result. Cheap, fast, autonomous, with molecule counting (UMIs), aimed at
expert-level benchmarks on commodity hardware (Hamilton + PyLabRobot + on-deck
thermocycler + BioTek Synergy H1).

Each assay is a self-contained module spanning purchase planning, instrument bring-up,
liquid-handling readiness, and automated execution. The scRNA-seq module also runs its
analysis locally; the scWGS module generates a validated handoff for a separately
licensed external pipeline. Wet-lab stages run in the PyLabRobot simulator with no
hardware attached.

## Modules

| Module | Assay | Status |
|---|---|---|
| [`autonomous-scRNAseq/`](autonomous-scRNAseq) | FLASH-seq UMI v3 (low-input full-length scRNA-seq + UMIs) | v0.1: 4 stages + Rhodamine B readiness QC + human/humanoid operator + fastq-to-analysis (scanpy), all wired end to end in the PyLabRobot simulator |
| [`autonomous-scWGS/`](autonomous-scWGS) | single-cell WGS: whole-genome amplification + NEBNext Ultra II (FACS Melody sort up front) | v0.1: simulated sort + WGA + library prep + Rhodamine readiness + human/humanoid operator, plus generated WGS analysis inputs/runner (10/10 tests) |

`autonomous-scRNAseq/` is the FLASH-seq scRNA-seq pipeline. It delivers, all runnable
with no hardware: procurement (BOM to IDT/browser/PO channels to one human approval),
a printable bench manual, instrument-readiness QC (Rhodamine B pipetting precision on
a Synergy H1), the full FLASH-seq automation in the simulator with QC gates and tacit
guards, a swappable human or humanoid operator, and a fastq-to-analysis pipeline
(bcl2fastq to umi_tools to STAR to featureCounts to umi_tools count to scanpy).

`autonomous-scWGS/` is the single-cell whole-genome sequencing pipeline: a BD FACS Melody
sort into Cell Buffer, single-cell whole-genome amplification, post-WGA
dsDNA QC on the Synergy H1, NEBNext Ultra II library prep (exact SPRI ratios, do-not-
over-dry guards), and pooling. It then generates `input.csv` and a fail-closed runner for
a runtime-supplied external WGS Nextflow pipeline; that external analysis is not executed
by the simulator. It shares the Rhodamine B readiness QC and human/humanoid operator with
the scRNAseq module. The underlying kits are proprietary (RESEARCH USE ONLY), not CC-BY;
values are sourced from authorized guides and never invented. The FACS Melody control
plane is being reverse-engineered (owner's TODO); sorting is simulated until wired.

## The autonomy stack (shared across modules)

1. Procurement - resolve reagents to SKUs, route to IDT API / browser carts / PO, one
   human approval, schedule the run on lead times.
2. Instrument bring-up - controller kit (Raspberry Pi + PyLabRobot) and a connectivity
   registry that emits exact cabling. Includes reverse-engineering the cell sorter.
3. Readiness - Rhodamine B liquid-handling CV check: READY or NEEDS_CALIBRATION.
4. Execution - the assay on a Hamilton deck + on-deck thermocycler + Synergy H1.
5. Ops - a human or an (experimental) humanoid robot sets up the deck, presses run,
   collects output.
6. Analysis - local scRNA-seq analysis or a validated scWGS external-pipeline handoff.

## Known hard subproblem: FACS Melody

The single-cell sort (cells into lysis buffer) depends on a BD FACS Melody, which has
no open automation API, so programmatic control has to be reverse-engineered. Tracked
per module. Nothing about that interface is invented; unknowns stay TODO.

## Principles

- Never invent a value: source from the protocol; unknowns are `# TODO`,
  OCR-ambiguous items are `verify`, tuning knobs are `# expert-tunable`.
- One human approval before any purchase; fail closed on readiness.
- Swappable backends: everything runs in simulation with no hardware.

## License

Code: MIT ([`LICENSE`](LICENSE)). Each module credits its source protocol under that
protocol's own license (FLASH-seq UMI v3 is CC-BY; see the module's ATTRIBUTION).
