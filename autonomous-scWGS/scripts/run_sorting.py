#!/usr/bin/env python3
"""Stage 0b -- FACS Melody single-cell sort (simulated; control-plane RE pending).

  python scripts/run_sorting.py --n 88 [--efficiency 0.9]
"""
import argparse
import asyncio

import _bootstrap  # noqa: F401
from _bootstrap import OUTPUT_DIR

from autoscwgs.params import load_params
from autoscwgs.sorting import run_sort


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--n", type=int, default=88)
    ap.add_argument("--efficiency", type=float, default=0.9, help="(sim) sort efficiency 0-1")
    args = ap.parse_args()

    p = load_params().with_run(n_samples=args.n)
    res = asyncio.run(run_sort(p, mode="sim", n_samples=args.n, sort_efficiency=args.efficiency))
    print(res.summary())
    for e in res.events:
        print(f"  {e}")
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    (OUTPUT_DIR / "sort_report.txt").write_text(res.summary(), encoding="utf-8")
    print(f"\n[sort] -> {OUTPUT_DIR / 'sort_report.txt'}")


if __name__ == "__main__":
    main()
