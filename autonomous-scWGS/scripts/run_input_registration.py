#!/usr/bin/env python3
"""Run abstract single-cell input registration."""

import argparse
import asyncio

import _bootstrap  # noqa: F401

from autoscwgs.params import load_params
from autoscwgs.sorting import run_sort


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--n", type=int, default=16)
    args = parser.parse_args()
    result = asyncio.run(run_sort(load_params(), mode="sim", n_samples=args.n))
    print(f"Registered {result.n_deposited}/{result.n_requested} synthetic inputs.")


if __name__ == "__main__":
    main()
