#!/usr/bin/env python3
"""Stage 4 -- generate WGS analysis inputs and a Nextflow runner.

  python scripts/generate_analysis.py
"""
import _bootstrap  # noqa: F401
from _bootstrap import OUTPUT_DIR

from autoscwgs.params import load_params
from autoscwgs.result import write_pipeline


def main() -> None:
    p = load_params()
    res = write_pipeline(p, OUTPUT_DIR)
    print(f"[result] WGS runner -> {res['pipeline']}")
    print(f"[result] WGS input  -> {res['input_csv']}")
    print("[result] Pipeline: external WGS Nextflow workflow: Sentieon BWA MEM -> Dedup -> BQSR")
    print("[result]   -> DNAScope -> SnpEff/ClinVar/dbSNP -> MultiQC.")
    print("[result] Generated handoff only; external analysis has not run.")
    print("[result] Required runtime config: WGS_PIPELINE_DIR, DNASCOPE_MODEL, SENTIEON_LICENSE.")
    print("[result] Required host tools: Java, Nextflow, Docker, AWS CLI.")


if __name__ == "__main__":
    main()
