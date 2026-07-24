"""Render a non-executable scRNA-seq planning brief."""

from __future__ import annotations

from pathlib import Path

from ..params import Params


def render_manual_markdown(p: Params) -> str:
    stage_lines = "\n".join(
        f"- `{stage['id']}` -> `{stage['output_state']}`"
        for stage in p.protocol["simulation"]["stages"]
    )
    return f"""# scRNA-seq workflow planning brief

> RESEARCH USE ONLY. Simulation only. This document is not a bench protocol.

Requested synthetic samples: **{p.n_cells}**

## Abstract workflow states

{stage_lines}

## Local validation boundary

Physical execution requires ignored `config/validated.local.yaml` with
`validated: true` and a laboratory-owned `execution_adapter`. The public project
does not include reagent identities, quantities, physical settings, control maps,
acceptance criteria, or instrument commands.

## Analysis handoff

Input manifests, reference data, analysis configuration, and executable adapters
are provided at runtime.
"""


def write_manual(p: Params, out_dir: Path | str) -> dict[str, str | None]:
    out = Path(out_dir)
    out.mkdir(parents=True, exist_ok=True)
    path = out / "scrnaseq_planning_brief.md"
    path.write_text(render_manual_markdown(p), encoding="utf-8")
    return {"markdown": str(path), "pdf": None}
