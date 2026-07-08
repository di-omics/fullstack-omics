"""Sequencing analysis stage: WGS analysis WGS analysis (the vendor Nextflow pipeline).

This generates the two things you actually need to run the analysis on whole-genome sequencing / whole-genome amplification
data end to end:
  1. `input.csv` -- one row per single-cell library (biosampleName, read1, read2), the
     WGS analysis metadata input.
  2. `run_bj_wgs.sh` -- clones the vendor/bj-wgs and runs the exact `nextflow run main.nf`
     command with the right params (genome, platform, whole-genome amplification-corrected DNAScope model,
     resources), plus a preflight for Java/Nextflow/Docker/AWS CLI + the Sentieon license.

WGS analysis is a Nextflow + Docker + Sentieon pipeline (external, not bundled). All values are
transcribed from the WGS analysis README (src: [C]). RESEARCH USE ONLY. Author: di.
"""

from __future__ import annotations

from pathlib import Path
from typing import List, Optional

from ..params import Params


def _biosample_name(well: str) -> str:
    return f"scwgs_{well}"


def build_input_rows(p: Params, sample_wells: Optional[List[str]] = None,
                     fastq_dir: str = "/path/to/fastq") -> list[dict]:
    """One WGS analysis input row per single-cell library. Fastq paths are placeholders to
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
    """The WGS analysis runner script (bash). src: [C] WGS analysis README."""
    a = p.protocol["analysis"]
    res = a["resources"]["typical"]
    mods = a["optional_modules"]
    tv = a["tool_versions"]
    return f"""#!/usr/bin/env bash
# =============================================================================
# run_bj_wgs.sh -- single-cell WGS sequencing analysis (WGS analysis WGS analysis)
# Pipeline: {a['repo']}  (Nextflow). src: WGS analysis README.
# WGA: whole-genome amplification (the vendor). Library prep: NEBNext Ultra II (NEB E7645).
# Author: di. RESEARCH USE ONLY -- not clinically validated.
#
# WGS analysis maps reads (Sentieon BWA MEM), dedups (LocusCollector + Dedup), BQSR,
# calls variants (DNAScope default / Haplotyper), annotates (SnpEff + ClinVar +
# dbSNP), computes Sentieon metrics, VCFeval (GIAB only), and aggregates in MultiQC.
#
# EXTERNAL (not bundled): Java, Nextflow, Docker, AWS CLI, and a Sentieon license
# (eval/pass-through via a the vendor helpdesk ticket). Tool versions (src: [C]):
#   Seqtk {tv['seqtk']} | Sentieon {tv['sentieon']} | SnpEff {tv['snpeff']} |
#   VCFeval {tv['vcfeval']} | BCFtools {tv['bcftools']}.
# =============================================================================
set -euo pipefail

# ---- 0. Config (EDIT THESE) ------------------------------------------------
INPUT_CSV="${{INPUT_CSV:-$PWD/input.csv}}"          # biosampleName,read1,read2
PUBLISH_DIR="${{PUBLISH_DIR:-results/bj-wgs}}"
GENOME="${{GENOME:-{a['genome_default']}}}"                       # {" | ".join(a['genomes'])}
PLATFORM="${{PLATFORM:-{a['platform_default']}}}"                # {" | ".join(a['platforms'])}
# whole-genome amplification data: use the whole-genome amplification-corrected DNAScope model on Illumina (src: [C]).
DNASCOPE_MODEL="${{DNASCOPE_MODEL:-{a['dnascope_model_pta']}}}"   # or '{a['dnascope_model_selection']}'
MIN_READS="${{MIN_READS:-{a['min_reads']}}}"
MAX_CPUS="${{MAX_CPUS:-{res['max_cpus']}}}"                        # large runs: {a['resources']['large']['max_cpus']}
MAX_MEMORY="${{MAX_MEMORY:-{res['max_memory_gb']}.GB}}"           # large runs: {a['resources']['large']['max_memory_gb']}.GB
SENTIEON_LICENSE="${{SENTIEON_LICENSE:-$PWD/bj-wgs/sentieon_eval.lic}}"

# ---- 1. Preflight (src: [C] Running Locally) --------------------------------
for tool in java nextflow docker aws; do
  command -v "$tool" >/dev/null 2>&1 || \\
    echo "[bj-wgs] MISSING external tool: $tool (see the WGS analysis README 'Running Locally')" >&2
done
if [ ! -f "$SENTIEON_LICENSE" ]; then
  echo "[bj-wgs] Sentieon license not found at $SENTIEON_LICENSE" >&2
  echo "[bj-wgs] Submit a the vendor helpdesk ticket for an eval/pass-through Sentieon license," >&2
  echo "[bj-wgs] save it at bj-wgs/sentieon_eval.lic, then re-run." >&2
fi
export SENTIEON_LICENSE

# ---- 2. Get the pipeline ----------------------------------------------------
[ -d bj-wgs ] || git clone {a['repo']}.git
cd bj-wgs

# ---- 3. Run WGS analysis ----------------------------------------------------------
# Optional modules (defaults from src: [C]): skip_vcfeval={str(mods['skip_vcfeval']).lower()},
#   skip_variant_annotation={str(mods['skip_variant_annotation']).lower()},
#   skip_gene_coverage={str(mods['skip_gene_coverage']).lower()}, skip_ado={str(mods['skip_ado']).lower()},
#   skip_subsampling={str(mods['skip_subsampling']).lower()}, skip_sigprofile={str(mods['skip_sigprofile']).lower()}.
nextflow run main.nf \\
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
echo "[bj-wgs] Done. MultiQC report: $PUBLISH_DIR/{a['outputs']['report']}"

# Sequencing depth targets (src: [A] Appendix C):
#   low-pass QC : {a['depth_targets']['low_pass']}
#   deep        : {a['depth_targets']['deep']}
"""


def write_pipeline(p: Params, out_dir: Path | str, sample_wells: Optional[List[str]] = None) -> dict:
    out = Path(out_dir)
    out.mkdir(parents=True, exist_ok=True)
    runner = out / "run_bj_wgs.sh"
    runner.write_text(generate_pipeline(p), encoding="utf-8")
    runner.chmod(0o755)
    csv = out / "input.csv"
    csv.write_text(generate_input_csv(p, sample_wells), encoding="utf-8")
    return {"pipeline": str(runner), "input_csv": str(csv)}
