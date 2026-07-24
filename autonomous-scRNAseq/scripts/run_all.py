#!/usr/bin/env python3
"""Generate all public scRNA-seq simulation and handoff artifacts."""

import argparse
import asyncio

import _bootstrap  # noqa: F401
from _bootstrap import OUTPUT_DIR

from scrnaseq.automation import run_scrnaseq
from scrnaseq.manual import write_manual
from scrnaseq.params import load_params
from scrnaseq.procurement import approval_summary_markdown, build_bom, route_channels
from scrnaseq.result import write_pipeline


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--n", type=int, default=16)
    args = parser.parse_args()
    params = load_params().with_run(n_cells=args.n)
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    items = route_channels(build_bom(params))
    (OUTPUT_DIR / "functional_checklist.md").write_text(
        approval_summary_markdown(items, p=params),
        encoding="utf-8",
    )
    write_manual(params, OUTPUT_DIR)
    result = asyncio.run(run_scrnaseq(params, mode="sim"))
    (OUTPUT_DIR / "simulation_run.txt").write_text(result.summary(), encoding="utf-8")
    if result.readiness is not None:
        (OUTPUT_DIR / "contract_readiness.txt").write_text(
            result.readiness.summary(),
            encoding="utf-8",
        )
    write_pipeline(params, OUTPUT_DIR)
    print(result.summary())
    print(f"[done] artifacts -> {OUTPUT_DIR}")


if __name__ == "__main__":
    main()
