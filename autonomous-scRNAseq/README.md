# flashseq-skill

> **RESEARCH USE ONLY - not clinically validated.**

An open-source [skill](SKILL.md) that takes a scientist from *"run FLASH-seq
on N cells"* all the way to a result - **procurement → wire-up → automated execution
→ analysis** - on a Hamilton STAR/STARlet deck via [PyLabRobot](https://pylabrobot.org),
with an on-deck thermocycler and a BioTek Synergy H1 plate reader. It runs **entirely
in the PyLabRobot simulator** with no hardware attached, so it's testable and
demoable today. First of a series (TIP-seq next).

The laboratory method is the **FLASH-seq UMI protocol v3** (Picelli & Hahaut,
protocols.io 2022, DOI
[10.17504/protocols.io.bp2l619rdvqe/v3](https://dx.doi.org/10.17504/protocols.io.bp2l619rdvqe/v3),
CC-BY). See [`ATTRIBUTION.md`](ATTRIBUTION.md).

## Quickstart

```bash
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt

# All four stages, wired end-to-end in the simulator:
python scripts/run_all.py --n 96 --first-time-buyer

# Tests:
python tests/test_end_to_end.py       # or: pytest -q
```

Artifacts land in `output/`:
`purchase_approval.md`, `flashseq_manual.md`, `instrument_readiness.txt`,
`automation_run.txt`, `flashseq_pipeline.sh`, `flashseq_analysis.py`.

## The four stages

1. **Procurement** - BOM scaled to N → routed to IDT API / browser-agent carts /
   PO fallback → **one human approval** (nothing ordered otherwise) → optional
   Raspberry Pi controller kit + exact cabling.
2. **Manual** - printable bench manual (deck layout, scaled volumes, timings,
   on-ice/RT, safe stops, wiring diagram) from `config/protocol_params.yaml`.
3. **Automation** - the FLASH-seq flow through PyLabRobot with **swappable
   backends** (sim ↔ Hamilton/Synergy H1/thermocycler), with QC gates + tacit
   guards baked in.
4. **Result** - runnable **fastq to analysis** pipeline for protocol §12: a shell
   pipeline (bcl2fastq → umi_tools → STAR → featureCounts → umi_tools count) plus a
   scanpy analysis script (counts → QC → cluster → UMAP → markers).

## Configure by editing YAML, not code

| File | What |
|---|---|
| [`config/protocol_params.yaml`](config/protocol_params.yaml) | volumes, temps, times, cycles, ratios, QC gates |
| [`config/reagents.yaml`](config/reagents.yaml) | vendor, catalog #, scaling rule per material |
| [`config/instruments.yaml`](config/instruments.yaml) | connectivity registry, PLR backends, controller kit |

The default run is **96-well at 5× volumes** (Hamilton-friendly, protocol-supported).
384-well (native nL volumes) is available but flagged *"requires a nanodispenser."*

## Design rules

- **Never invent a value.** Every reagent/volume/temp/time/catalog # traces to the
  protocol, annotated `# src: Stage N`. Missing → `# TODO: expert value`.
  OCR-ambiguous → `verify: true`. Author-flagged tuning knobs → `# expert-tunable`.
- **Never checkout without one human approval.** Procurement stops at the approval
  summary; live ordering is a dry-run stub in v1.
- **Swappable backends.** `mode="sim"` needs no hardware; `mode="hardware"` reads
  real backends from `instruments.yaml` and refuses to run while TODOs remain.

## Repo layout

```
config/            protocol-sourced YAML (source of truth)
flashseq/
  params.py        loads + scales the YAML
  procurement/     Stage 1: BOM, channels, controller kit, connectivity
  manual/          Stage 2: bench manual + wiring diagram
  automation/      Stage 3: PLR workflow, backends, PicoGreen sim, QC gates/guards
  result/          Stage 4: analysis pipeline generator
scripts/           CLI entry points (run_all.py + one per stage)
references/         deeper docs (progressive disclosure from SKILL.md)
tests/             end-to-end tests (run in the simulator)
```

## Requirements

Python 3.10+, `pylabrobot`, `pyyaml` (see `requirements.txt`). PDF export needs
`pandoc` (optional). The Stage 4 pipeline needs bcl2fastq / umi_tools / STAR /
samtools / featureCounts / bbmap installed separately (external deps).

## License

Code: **MIT** ([`LICENSE`](LICENSE)). Method: **CC-BY** ([`ATTRIBUTION.md`](ATTRIBUTION.md)).
