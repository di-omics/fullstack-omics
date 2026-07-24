"""Generate a method-agnostic scRNA-seq downstream-analysis handoff."""

from __future__ import annotations

from pathlib import Path

from ..params import Params


def generate_analysis_handoff(p: Params) -> str:
    del p
    return r'''#!/usr/bin/env bash
# scRNA-seq downstream-analysis adapter contract. RESEARCH USE ONLY.
set -euo pipefail

SCRNASEQ_ANALYSIS_ADAPTER="${SCRNASEQ_ANALYSIS_ADAPTER:?Set SCRNASEQ_ANALYSIS_ADAPTER}"
COUNT_MATRIX="${COUNT_MATRIX:?Set COUNT_MATRIX}"
ANALYSIS_CONFIG="${ANALYSIS_CONFIG:?Set ANALYSIS_CONFIG}"
ANALYSIS_OUTPUT="${ANALYSIS_OUTPUT:?Set ANALYSIS_OUTPUT}"

for path in "$COUNT_MATRIX" "$ANALYSIS_CONFIG"; do
  if [ ! -e "$path" ]; then
    echo "[scrnaseq] Missing required analysis input: $path" >&2
    exit 2
  fi
done
if [ ! -x "$SCRNASEQ_ANALYSIS_ADAPTER" ]; then
  echo "[scrnaseq] Analysis adapter must be a local executable" >&2
  exit 3
fi

export COUNT_MATRIX ANALYSIS_CONFIG ANALYSIS_OUTPUT
exec "$SCRNASEQ_ANALYSIS_ADAPTER"
'''


def write_analysis(p: Params, out_dir: Path | str) -> dict[str, str]:
    out = Path(out_dir)
    out.mkdir(parents=True, exist_ok=True)
    script = out / "run_scrnaseq_analysis.sh"
    script.write_text(generate_analysis_handoff(p), encoding="utf-8")
    script.chmod(0o755)
    return {"analysis": str(script)}
