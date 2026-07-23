"""Sequencing analysis stage: configurable external WGS Nextflow pipeline.

This generates the two artifacts for a separately operated external WGS analysis:
  1. `input.csv` -- one row per single-cell library (biosampleName, read1, read2), the
     compatible pipeline metadata input.
  2. `run_wgs_analysis.sh` -- runs `nextflow run main.nf` from a compatible checkout
     supplied through WGS_PIPELINE_DIR, with genome, platform, model, and resource
     parameters plus a preflight for Java/Nextflow/Docker/AWS CLI and Sentieon.

The simulator does not execute the external analysis pipeline. The pipeline is not
bundled, and the versioned interface is documented as source [C]. RESEARCH USE ONLY.
Author: di.
"""

from __future__ import annotations

from pathlib import Path
from typing import List, Optional

from ..params import Params


def _biosample_name(well: str) -> str:
    return f"scwgs_{well}"


def build_input_rows(p: Params, sample_wells: Optional[List[str]] = None,
                     fastq_dir: str = "/path/to/fastq") -> list[dict]:
    """One WGS input row per single-cell library. Fastq paths are placeholders to
    edit after demultiplexing (bcl2fastq / BaseSpace). src: [C] Input Options."""
    if sample_wells is None:
        from ..sorting import plan_plate
        sample_wells = plan_plate(p).sample_wells
    rows = []
    for w in sample_wells:
        name = _biosample_name(w)
        rows.append({
            "biosampleName": name,
            "read1": f"{fastq_dir}/{name}_R1_001.fastq.gz",
            "read2": f"{fastq_dir}/{name}_R2_001.fastq.gz",
        })
    return rows


def generate_input_csv(p: Params, sample_wells: Optional[List[str]] = None) -> str:
    a = p.protocol["analysis"]
    cols = a["input_csv_columns_illumina"]   # src: [C] biosampleName,read1,read2
    rows = build_input_rows(p, sample_wells)
    lines = [",".join(cols)]
    for r in rows:
        lines.append(",".join(str(r[c]) for c in cols))
    return "\n".join(lines) + "\n"


def generate_pipeline(p: Params) -> str:
    """Generate the external WGS pipeline runner script (bash). src: [C]."""
    a = p.protocol["analysis"]
    res = a["resources"]["typical"]
    mods = a["optional_modules"]
    tv = a["tool_versions"]
    return f"""#!/usr/bin/env bash
# =============================================================================
# run_wgs_analysis.sh -- single-cell WGS sequencing analysis
# Pipeline interface: {a['interface_id']} {a['interface_version']}.
# Compatible external Nextflow checkout supplied at runtime. src: [C].
# WGA: single-cell whole-genome amplification. Library prep: NEBNext Ultra II.
# Author: di. RESEARCH USE ONLY -- not clinically validated.
#
# The configured pipeline maps reads (Sentieon BWA MEM), dedups (LocusCollector +
# Dedup), performs BQSR, calls variants (DNAScope or Haplotyper), annotates with
# SnpEff/ClinVar/dbSNP, computes metrics, optionally evaluates GIAB samples, and
# aggregates reports in MultiQC.
#
# The pipeline checkout and its license are external. This repository neither bundles
# nor fetches it. External tools: Java, Nextflow, Docker, AWS CLI, and a Sentieon
# license. Tool versions expected by the compatible interface (src: [C]):
#   Seqtk {tv['seqtk']} | Sentieon {tv['sentieon']} | SnpEff {tv['snpeff']} |
#   VCFeval {tv['vcfeval']} | BCFtools {tv['bcftools']}.
# =============================================================================
set -euo pipefail

# ---- 0. Config --------------------------------------------------------------
SCRIPT_SOURCE="${{BASH_SOURCE[0]}}"
case "$SCRIPT_SOURCE" in
  */*) SCRIPT_PARENT="${{SCRIPT_SOURCE%/*}}" ;;
  *) SCRIPT_PARENT="." ;;
esac
SCRIPT_DIR="$(cd -- "$SCRIPT_PARENT" && pwd)"
WGS_PIPELINE_DIR="${{WGS_PIPELINE_DIR:?Set WGS_PIPELINE_DIR to a compatible pipeline checkout}}"
DNASCOPE_MODEL="${{DNASCOPE_MODEL:?Set DNASCOPE_MODEL explicitly for this dataset}}"
SENTIEON_LICENSE="${{SENTIEON_LICENSE:?Set SENTIEON_LICENSE to a valid license file}}"
INPUT_CSV="${{INPUT_CSV:-$SCRIPT_DIR/input.csv}}"   # biosampleName,read1,read2
PUBLISH_DIR="${{PUBLISH_DIR:-$SCRIPT_DIR/results/wgs}}"
GENOME="${{GENOME:-{a['genome_default']}}}"         # {" | ".join(a['genomes'])}
PLATFORM="${{PLATFORM:-{a['platform_default']}}}"   # {" | ".join(a['platforms'])}
MIN_READS="${{MIN_READS:-{a['min_reads']}}}"
MAX_CPUS="${{MAX_CPUS:-{res['max_cpus']}}}"         # large runs: {a['resources']['large']['max_cpus']}
MAX_MEMORY="${{MAX_MEMORY:-{res['max_memory_gb']}.GB}}"  # large runs: {a['resources']['large']['max_memory_gb']}.GB

# ---- 1. Validate runtime inputs ----------------------------------------------
if [ ! -f "$WGS_PIPELINE_DIR/{a['entrypoint']}" ]; then
  echo "[wgs-analysis] Missing $WGS_PIPELINE_DIR/{a['entrypoint']}" >&2
  exit 2
fi
if [ ! -s "$INPUT_CSV" ]; then
  echo "[wgs-analysis] Missing or empty input CSV: $INPUT_CSV" >&2
  exit 2
fi
IFS= read -r INPUT_HEADER < "$INPUT_CSV"
if [ "$INPUT_HEADER" != "biosampleName,read1,read2" ]; then
  echo "[wgs-analysis] Invalid input CSV header: $INPUT_HEADER" >&2
  exit 2
fi
if [ ! -f "$SENTIEON_LICENSE" ]; then
  echo "[wgs-analysis] Sentieon license file not found: $SENTIEON_LICENSE" >&2
  exit 2
fi

# ---- 2. Preflight (src: [C] Running Locally) --------------------------------
for tool in java nextflow docker aws; do
  if ! command -v "$tool" >/dev/null 2>&1; then
    echo "[wgs-analysis] Missing required external tool: $tool" >&2
    exit 3
  fi
done
export SENTIEON_LICENSE

# ---- 3. Run the WGS analysis pipeline ---------------------------------------
# Optional modules (defaults from src: [C]): skip_vcfeval={str(mods['skip_vcfeval']).lower()},
#   skip_variant_annotation={str(mods['skip_variant_annotation']).lower()},
#   skip_gene_coverage={str(mods['skip_gene_coverage']).lower()}, skip_ado={str(mods['skip_ado']).lower()},
#   skip_subsampling={str(mods['skip_subsampling']).lower()}, skip_sigprofile={str(mods['skip_sigprofile']).lower()}.
nextflow run "$WGS_PIPELINE_DIR/{a['entrypoint']}" \\
  --input_csv "$INPUT_CSV" \\
  --publish_dir "$PUBLISH_DIR" \\
  --genome "$GENOME" \\
  --platform "$PLATFORM" \\
  --dnascope_model_selection "$DNASCOPE_MODEL" \\
  --min_reads "$MIN_READS" \\
  --max_cpus "$MAX_CPUS" --max_memory "$MAX_MEMORY"

# ---- 4. Outputs (src: [C] Outputs) -----------------------------------------
#   alignment  : $PUBLISH_DIR/{a['outputs']['alignment']}
#   metrics    : $PUBLISH_DIR/{a['outputs']['metrics']}
#   variants   : $PUBLISH_DIR/{a['outputs']['variants']}
#   annotation : $PUBLISH_DIR/{a['outputs']['annotation']}
#   report     : $PUBLISH_DIR/{a['outputs']['report']}
echo "[wgs-analysis] Done. MultiQC report: $PUBLISH_DIR/{a['outputs']['report']}"

# Sequencing depth targets (src: [A] Appendix C):
#   low-pass QC : {a['depth_targets']['low_pass']}
#   deep        : {a['depth_targets']['deep']}
"""


def write_pipeline(p: Params, out_dir: Path | str, sample_wells: Optional[List[str]] = None) -> dict:
    out = Path(out_dir)
    out.mkdir(parents=True, exist_ok=True)
    runner = out / "run_wgs_analysis.sh"
    runner.write_text(generate_pipeline(p), encoding="utf-8")
    runner.chmod(0o755)
    csv = out / "input.csv"
    csv.write_text(generate_input_csv(p, sample_wells), encoding="utf-8")
    return {"pipeline": str(runner), "input_csv": str(csv)}
