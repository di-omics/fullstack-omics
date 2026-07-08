#!/usr/bin/env python3
"""Stage 4 -- generate the WGS analysis WGS analysis analysis (input.csv + nextflow runner).

  python scripts/generate_analysis.py
"""
import _bootstrap  # noqa: F401
from _bootstrap import OUTPUT_DIR

from autoscwgs.params import load_params
from autoscwgs.result import write_pipeline


def main() -> None:
    p = load_params()
    res = write_pipeline(p, OUTPUT_DIR)
    print(f"[result] BJ-WGS runner -> {res['pipeline']}")
    print(f"[result] BJ-WGS input   -> {res['input_csv']}")
    print("[result] Pipeline: BioSkryb BJ-WGS (Nextflow): Sentieon BWA MEM -> Dedup -> BQSR")
    print("[result]   -> DNAScope (PTA model bioskryb129) -> SnpEff/ClinVar/dbSNP -> MultiQC.")
    print("[result] External deps: Java, Nextflow, Docker, AWS CLI, Sentieon license.")


if __name__ == "__main__":
    main()
