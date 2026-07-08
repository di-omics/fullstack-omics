#!/usr/bin/env python3
"""Stage 2 -- render the printable bench manual.

  python scripts/render_manual.py --n 96
"""
import argparse

import _bootstrap  # noqa: F401
from _bootstrap import OUTPUT_DIR

from autoscwgs.params import load_params
from autoscwgs.manual import write_manual


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--n", type=int, default=96)
    args = ap.parse_args()

    p = load_params().with_run(n_samples=args.n)
    res = write_manual(p, OUTPUT_DIR)
    print(f"[manual] Markdown -> {res['markdown']}")
    print(f"[manual] PDF: {res.get('pdf') or res.get('pdf_error')}")


if __name__ == "__main__":
    main()
