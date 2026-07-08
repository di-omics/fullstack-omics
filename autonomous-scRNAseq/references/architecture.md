# Architecture

## Principle: one source of truth

`config/*.yaml` holds every protocol value. `flashseq/params.py` loads and scales it.
Everything else (BOM, manual, automation, analysis) reads from `Params` - so tuning a
run is a YAML edit, never a code edit.

```
config/protocol_params.yaml ─┐
config/reagents.yaml         ├─► flashseq.params.load_params() ─► Params
config/instruments.yaml      ─┘                                     │
                                                                    ▼
        ┌───────────────┬───────────────┬───────────────┬───────────────┐
        │ procurement   │ manual        │ automation    │ result        │
        │ (Stage 1)     │ (Stage 2)     │ (Stage 3)     │ (Stage 4)     │
        └──────┬────────┴──────┬────────┴──────┬────────┴──────┬────────┘
        purchase_approval.md  flashseq_manual.md  (PLR sim run)  flashseq_pipeline.sh
```

## Module map

| Path | Responsibility |
|---|---|
| `flashseq/params.py` | load YAML; 384→96 volume scaling; overage; run overrides |
| `flashseq/procurement/bom.py` | scale materials to N |
| `flashseq/procurement/channels.py` | route to IDT/browser/PO; approval doc; dry-run orders |
| `flashseq/procurement/connectivity.py` | registry → exact cables (flags TODOs) |
| `flashseq/procurement/controller_kit.py` | first-time-buyer Pi kit |
| `flashseq/manual/render.py` | bench manual (Markdown; optional PDF) |
| `flashseq/manual/wiring.py` | ASCII wiring diagram |
| `flashseq/automation/backends.py` | sim ↔ hardware backend factory |
| `flashseq/automation/deck.py` | STARlet deck + thermocycler + reader |
| `flashseq/automation/picogreen.py` | PicoGreen signal model + standard curve |
| `flashseq/automation/qc.py` | gates + guards |
| `flashseq/automation/workflow.py` | the FLASH-seq flow |
| `flashseq/result/pipeline.py` | §12 analysis script generator |
| `scripts/*.py` | CLI entry points (`run_all.py` chains all four) |
| `tests/test_end_to_end.py` | runs all four stages in the simulator |

## Extending to the next protocol (TIP-seq)

The pattern generalizes: add `config/` YAML for the new protocol, reuse `params.py`,
`procurement/`, `manual/`, the backend factory, and `qc.py`; write a new
`workflow.py` and analysis generator. Keep the "never invent a value" rule.
