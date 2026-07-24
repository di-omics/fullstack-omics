# fullstack-omics

> RESEARCH USE ONLY - not clinically validated.

Two method-agnostic, simulation-only workflow models:

| Module | Public scope |
|---|---|
| [`autonomous-scRNAseq/`](autonomous-scRNAseq) | scRNA-seq orchestration states and a runtime-configured analysis-adapter handoff |
| [`autonomous-scWGS/`](autonomous-scWGS) | single-cell WGS preparation states and a runtime-configured WGS analysis handoff |

The tracked configuration intentionally contains no executable wet-lab recipe,
supplier selection, control-plate map, acceptance threshold, or hardware program.
Simulation parameters are unitless and synthetic. A laboratory can connect its own
validated, ignored local profile and execution adapter without publishing those
controlled details here.

Each module includes a deterministic simulator, functional procurement checklist,
planning brief, command-line entry points, and tests. Hardware requests fail closed
unless a local validated profile explicitly names a laboratory-owned adapter.

See the module READMEs for usage. Code is licensed under the MIT License.
