#!/usr/bin/env python3
"""Stage 4 -- Result: generate the analysis pipeline stub (protocol section 12).

  python scripts/generate_analysis.py
"""
import argparse

import _bootstrap  # noqa: F401
from _bootstrap import OUTPUT_DIR

from flashseq.params import load_params
from flashseq.result import write_pipeline


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--n", type=int, default=None)
    args = ap.parse_args()

    p = load_params().with_run(n_cells=args.n)
    result = write_pipeline(p, OUTPUT_DIR)
    print(f"[result] fastq->counts pipeline -> {result['pipeline']}")
    print(f"[result] counts->analysis (scanpy) -> {result['analysis']}")
    print("[result] External tools required: bcl2fastq, umi_tools, STAR, samtools, featureCounts, bbmap, scanpy.")


if __name__ == "__main__":
    main()
