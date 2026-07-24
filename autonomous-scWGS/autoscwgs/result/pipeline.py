"""Generate a runtime-configured WGS analysis handoff."""

from __future__ import annotations

from pathlib import Path
from typing import Optional

from ..params import Params


def build_input_rows(
    p: Params,
    sample_ids: Optional[list[str]] = None,
    fastq_dir: str = "/path/to/fastq",
) -> list[dict[str, str]]:
    """Build placeholder rows from abstract sample identifiers."""
    if sample_ids is None:
        from ..sorting import plan_plate

        sample_ids = plan_plate(p).sample_ids
    rows = []
    for sample_id in sample_ids:
        safe_id = str(sample_id)
        rows.append(
            {
                "biosampleName": safe_id,
                "read1": f"{fastq_dir}/{safe_id}_R1.fastq.gz",
                "read2": f"{fastq_dir}/{safe_id}_R2.fastq.gz",
            }
        )
    return rows


def generate_input_csv(p: Params, sample_ids: Optional[list[str]] = None) -> str:
    columns = ["biosampleName", "read1", "read2"]
    rows = build_input_rows(p, sample_ids)
    lines = [",".join(columns)]
    lines.extend(",".join(row[column] for column in columns) for row in rows)
    return "\n".join(lines) + "\n"


def generate_pipeline(p: Params) -> str:
    del p
    return r'''#!/usr/bin/env bash
# Runtime-configured WGS analysis handoff. RESEARCH USE ONLY.
# The public repository defines an adapter contract, not a tool-specific stack.
set -euo pipefail

SCRIPT_SOURCE="${BASH_SOURCE[0]}"
case "$SCRIPT_SOURCE" in
  */*) SCRIPT_PARENT="${SCRIPT_SOURCE%/*}" ;;
  *) SCRIPT_PARENT="." ;;
esac
SCRIPT_DIR="$(cd -- "$SCRIPT_PARENT" && pwd)"

WGS_PIPELINE_ADAPTER="${WGS_PIPELINE_ADAPTER:?Set WGS_PIPELINE_ADAPTER}"
INPUT_CSV="${INPUT_CSV:-$SCRIPT_DIR/input.csv}"
ANALYSIS_CONFIG="${ANALYSIS_CONFIG:?Set ANALYSIS_CONFIG}"
REFERENCE_BUNDLE="${REFERENCE_BUNDLE:?Set REFERENCE_BUNDLE}"
PUBLISH_DIR="${PUBLISH_DIR:?Set PUBLISH_DIR}"

if [ ! -s "$INPUT_CSV" ]; then
  echo "[wgs-analysis] Missing or empty input CSV: $INPUT_CSV" >&2
  exit 2
fi
IFS= read -r INPUT_HEADER < "$INPUT_CSV"
if [ "$INPUT_HEADER" != "biosampleName,read1,read2" ]; then
  echo "[wgs-analysis] Invalid input CSV header: $INPUT_HEADER" >&2
  exit 2
fi
for path in "$ANALYSIS_CONFIG" "$REFERENCE_BUNDLE"; do
  if [ ! -e "$path" ]; then
    echo "[wgs-analysis] Missing required runtime input: $path" >&2
    exit 2
  fi
done
if [ ! -x "$WGS_PIPELINE_ADAPTER" ]; then
  echo "[wgs-analysis] Adapter must be a local executable: $WGS_PIPELINE_ADAPTER" >&2
  exit 3
fi

mkdir -p "$PUBLISH_DIR"
export INPUT_CSV ANALYSIS_CONFIG REFERENCE_BUNDLE PUBLISH_DIR
exec "$WGS_PIPELINE_ADAPTER"
'''


def write_pipeline(
    p: Params,
    out_dir: Path | str,
    sample_ids: Optional[list[str]] = None,
) -> dict[str, str]:
    out = Path(out_dir)
    out.mkdir(parents=True, exist_ok=True)
    runner = out / "run_wgs_analysis.sh"
    runner.write_text(generate_pipeline(p), encoding="utf-8")
    runner.chmod(0o755)
    csv = out / "input.csv"
    csv.write_text(generate_input_csv(p, sample_ids), encoding="utf-8")
    return {"pipeline": str(runner), "input_csv": str(csv)}
