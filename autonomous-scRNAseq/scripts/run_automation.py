#!/usr/bin/env python3
"""Run the scRNA-seq workflow-state simulator or a controlled local adapter."""

import argparse
import asyncio

import _bootstrap  # noqa: F401
from _bootstrap import OUTPUT_DIR

from scrnaseq.automation import run_scrnaseq
from scrnaseq.params import load_params


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--n", type=int, default=16)
    parser.add_argument("--mode", choices=["sim", "hardware"], default="sim")
    args = parser.parse_args()
    result = asyncio.run(
        run_scrnaseq(load_params(), mode=args.mode, n_cells=args.n)
    )
    print(result.summary())
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    path = OUTPUT_DIR / "simulation_run.txt"
    path.write_text(result.summary(), encoding="utf-8")


if __name__ == "__main__":
    main()
