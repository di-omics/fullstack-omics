#!/usr/bin/env python3
"""Stage 3 -- Automation (FACS sort + WGA + library prep) in the PLR simulator.

  python scripts/run_automation.py --n 16 --mode sim [--operator humanoid] [--verbose]

Instrument readiness (Rhodamine B QC) runs first as REQUIRED Stage 0.
"""
import argparse
import asyncio
import contextlib
import io

import _bootstrap  # noqa: F401
from _bootstrap import OUTPUT_DIR

from autoscwgs.params import load_params
from autoscwgs.automation import run_workflow


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--n", type=int, default=16)
    ap.add_argument("--mode", default="sim", choices=["sim", "hardware"])
    ap.add_argument("--operator", default="human", choices=["human", "humanoid"])
    ap.add_argument("--readiness", default="required", choices=["required", "skip"])
    ap.add_argument("--verbose", action="store_true")
    args = ap.parse_args()

    p = load_params().with_run(n_samples=args.n)

    async def _go():
        return await run_workflow(p, mode=args.mode, operator=args.operator, readiness=args.readiness)

    if args.verbose:
        res = asyncio.run(_go())
    else:
        with contextlib.redirect_stdout(io.StringIO()):
            res = asyncio.run(_go())

    print(res.summary())
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    (OUTPUT_DIR / "automation_run.txt").write_text(res.summary(), encoding="utf-8")
    print(f"\n[automation] -> {OUTPUT_DIR / 'automation_run.txt'}")


if __name__ == "__main__":
    main()
