---
name: scrnaseq-simulator
description: >
  Model a method-agnostic scRNA-seq workflow as abstract states and generate a
  runtime-configured analysis-adapter handoff. Simulation only.
license: MIT
---

# scRNA-seq simulator

Use this module for workflow-graph testing, artifact generation, and computational
handoff validation. It does not provide an executable wet-lab method.

## Run

```bash
python scripts/run_all.py --n 16
python tests/test_end_to_end.py
```

## Public interfaces

1. Functional requirements become a non-orderable checklist.
2. Abstract workflow states become a planning brief.
3. Unitless synthetic signals exercise orchestration and status reporting.
4. Analysis adapters and all method-dependent choices are supplied at runtime.

## Physical execution

Hardware mode requires an ignored local validated profile and a laboratory-owned
execution adapter. The public simulator never emits physical commands.
