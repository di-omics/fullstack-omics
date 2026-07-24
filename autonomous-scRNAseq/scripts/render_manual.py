#!/usr/bin/env python3
"""Render the non-executable scRNA-seq workflow planning brief."""

import argparse

import _bootstrap  # noqa: F401
from _bootstrap import OUTPUT_DIR

from scrnaseq.manual import write_manual
from scrnaseq.params import load_params


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--n", type=int, default=16)
    args = parser.parse_args()
    result = write_manual(load_params().with_run(n_cells=args.n), OUTPUT_DIR)
    print(f"[planning] -> {result['markdown']}")


if __name__ == "__main__":
    main()
