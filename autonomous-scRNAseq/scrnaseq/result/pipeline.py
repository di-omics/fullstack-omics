"""Generate a method-agnostic scRNA-seq analysis handoff."""

from __future__ import annotations

from pathlib import Path

from ..params import Params


def generate_pipeline(p: Params) -> str:
    del p
    return r'''#!/usr/bin/env bash
# scRNA-seq computational handoff. RESEARCH USE ONLY.
# The public repository defines only an adapter contract. A local, validated
# adapter owns read structure, alignment, counting, and method-specific choices.
set -euo pipefail

SCRNASEQ_PIPELINE_ADAPTER="${SCRNASEQ_PIPELINE_ADAPTER:?Set SCRNASEQ_PIPELINE_ADAPTER}"
INPUT_MANIFEST="${INPUT_MANIFEST:?Set INPUT_MANIFEST}"
REFERENCE_BUNDLE="${REFERENCE_BUNDLE:?Set REFERENCE_BUNDLE}"
ANALYSIS_CONFIG="${ANALYSIS_CONFIG:?Set ANALYSIS_CONFIG}"
OUTPUT_DIR="${OUTPUT_DIR:?Set OUTPUT_DIR}"

for path in "$INPUT_MANIFEST" "$REFERENCE_BUNDLE" "$ANALYSIS_CONFIG"; do
  if [ ! -e "$path" ]; then
    echo "[scrnaseq] Missing required runtime input: $path" >&2
    exit 2
  fi
done
if [ ! -x "$SCRNASEQ_PIPELINE_ADAPTER" ]; then
  echo "[scrnaseq] Adapter must be a local executable: $SCRNASEQ_PIPELINE_ADAPTER" >&2
  exit 3
fi

mkdir -p "$OUTPUT_DIR"
export INPUT_MANIFEST REFERENCE_BUNDLE ANALYSIS_CONFIG OUTPUT_DIR
exec "$SCRNASEQ_PIPELINE_ADAPTER"
'''


def write_pipeline(p: Params, out_dir: Path | str) -> dict[str, str]:
    from .analysis import write_analysis

    out = Path(out_dir)
    out.mkdir(parents=True, exist_ok=True)
    script = out / "scrnaseq_pipeline.sh"
    script.write_text(generate_pipeline(p), encoding="utf-8")
    script.chmod(0o755)
    result = {"pipeline": str(script)}
    result.update(write_analysis(p, out))
    return result
