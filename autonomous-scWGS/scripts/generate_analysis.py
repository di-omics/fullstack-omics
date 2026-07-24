#!/usr/bin/env python3
"""Generate the runtime-configured WGS analysis handoff."""

import _bootstrap  # noqa: F401
from _bootstrap import OUTPUT_DIR

from autoscwgs.params import load_params
from autoscwgs.result import write_pipeline


def main() -> None:
    result = write_pipeline(load_params(), OUTPUT_DIR)
    print(f"[analysis] runner -> {result['pipeline']}")
    print(f"[analysis] manifest -> {result['input_csv']}")


if __name__ == "__main__":
    main()
