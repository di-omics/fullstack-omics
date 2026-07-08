#!/usr/bin/env python3
"""Stage 2 -- Manual: render the printable bench manual (Markdown; optional PDF).

  python scripts/render_manual.py --n 96 [--plate 96|384]
"""
import argparse

import _bootstrap  # noqa: F401
from _bootstrap import OUTPUT_DIR

from flashseq.params import load_params
from flashseq.manual import write_manual


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--n", type=int, default=None)
    ap.add_argument("--plate", type=int, default=None, choices=[96, 384])
    args = ap.parse_args()

    p = load_params().with_run(n_cells=args.n, plate_format=args.plate)
    result = write_manual(p, OUTPUT_DIR)
    print(f"[manual] Markdown -> {result['markdown']}")
    if result.get("pdf"):
        print(f"[manual] PDF -> {result['pdf']}")
    else:
        print(f"[manual] PDF skipped: {result.get('pdf_error')}")


if __name__ == "__main__":
    main()
