#!/usr/bin/env python3
"""Generate the non-orderable scRNA-seq functional checklist."""

import argparse

import _bootstrap  # noqa: F401
from _bootstrap import OUTPUT_DIR

from scrnaseq.params import load_params
from scrnaseq.procurement import approval_summary_markdown, build_bom, route_channels


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--n", type=int, default=16)
    args = parser.parse_args()
    params = load_params().with_run(n_cells=args.n)
    items = route_channels(build_bom(params))
    summary = approval_summary_markdown(items, p=params)
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    path = OUTPUT_DIR / "functional_checklist.md"
    path.write_text(summary, encoding="utf-8")
    print(f"[planning] -> {path}")


if __name__ == "__main__":
    main()
