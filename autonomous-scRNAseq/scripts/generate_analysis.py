#!/usr/bin/env python3
"""Generate the runtime-configured scRNA-seq analysis handoff."""

import _bootstrap  # noqa: F401
from _bootstrap import OUTPUT_DIR

from scrnaseq.params import load_params
from scrnaseq.result import write_pipeline


def main() -> None:
    result = write_pipeline(load_params(), OUTPUT_DIR)
    print(f"[analysis] runner -> {result['pipeline']}")
    print(f"[analysis] downstream skeleton -> {result['analysis']}")


if __name__ == "__main__":
    main()
