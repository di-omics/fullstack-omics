# Architecture

```
autonomous-scWGS/
+-- config/                         # SOURCE OF TRUTH (edit these, not the code)
|   +-- protocol_params.yaml        # WGA [A] + NEBNext [B] volumes/temps/times/ratios
|   +-- reagents.yaml               # kit-based BOM (part numbers; TODO where omitted)
|   +-- reagents.local.yaml         # ignored private ordering overrides
|   +-- instruments.yaml            # connectivity registry + PLR backends + controller kit
|   `-- readiness.yaml              # Rhodamine B QC settings (engineering defaults)
+-- autoscwgs/
|   +-- params.py                   # load + scale configs (mix totals; kit counts)
|   +-- sorting/facs.py             # FACS Melody sort interface + simulator (RE pending)
|   +-- readiness/rhodamine.py      # Stage 0 Rhodamine B liquid-handling QC (fail-closed)
|   +-- ops/operator.py             # human / humanoid ops person (swappable)
|   +-- procurement/                # bom, channels, connectivity, controller_kit
|   +-- automation/
|   |   +-- backends.py             # sim/hardware backend factory
|   |   +-- qubit.py                # dsDNA (Qubit-on-H1) signal model for sim
|   |   +-- deck.py                 # STAR + ODTC + Synergy H1 deck
|   |   +-- qc.py                   # QC gates + tacit guards
|   |   `-- workflow.py             # simulated wet-lab flow
|   +-- result/pipeline.py          # generated input.csv + external-pipeline runner
|   `-- manual/{render,wiring}.py   # printable bench manual + wiring diagram
+-- references/source_map.md        # stable source IDs + private/interface contracts
+-- scripts/                        # CLI entry points (run_all + per-stage)
`-- tests/test_end_to_end.py        # 10 tests: simulator + artifact/runner checks
```

## Data flow

`config/*.yaml` -> `params.Params` -> every stage. There is exactly one source of truth;
tuning a run means editing YAML, not code.

- **Scaling** lives only in `params.py`: `mix_total_ul(per_rxn, overage, n)` reproduces the
  protocol master-mix tables (e.g. WGA Lysis 3 uL x 96 x 1.30 ~ 375 uL); `n_kits(n)` =
  ceil(n / 96).
- **Backends** are swappable (`automation/backends.py`): `sim` uses PLR chatterbox backends
  + a dsDNA signal model; `hardware` resolves the real backends named in `instruments.yaml`
  and **refuses** while any TODO placeholder remains.
- **Sorting** and **ops** are separate seams (not PLR devices): the FACS Melody client and a
  humanoid SDK drop in behind `CellSorterBackend` / `HumanoidOperator.dispatch()`.
- **Analysis** is a generated handoff. The simulator writes and validates `input.csv` and
  the runner; execution of the runtime-supplied external pipeline is separate.

## Series relationship

Sibling of `flashseq-skill` (FLASH-seq scRNA-seq, CC-BY method). The Rhodamine B readiness
QC and the human/humanoid operator are shared designs across the series; here they are
adapted for the WGA + NEBNext volume scales and the FACS-sort front end.
