#!/usr/bin/env python3
"""Stage 3 -- Automation: run the FLASH-seq flow in the PLR simulator (or hardware).

  python scripts/run_automation.py --n 16 --mode sim
  python scripts/run_automation.py --n 96 --mode hardware   # requires instruments.yaml filled

By default this prints only the high-level summary. Pass --verbose to also see every
PyLabRobot action the chatterbox backends log.
"""
import argparse
import asyncio
import contextlib
import io

import _bootstrap  # noqa: F401
from _bootstrap import OUTPUT_DIR

from flashseq.params import load_params
from flashseq.automation import run_flashseq


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--n", type=int, default=16)
    ap.add_argument("--plate", type=int, default=None, choices=[96, 384])
    ap.add_argument("--mode", default="sim", choices=["sim", "hardware"])
    ap.add_argument("--verbose", action="store_true", help="show all PLR chatterbox actions")
    args = ap.parse_args()

    p = load_params().with_run(n_cells=args.n, plate_format=args.plate)

    if args.verbose:
        res = asyncio.run(run_flashseq(p, mode=args.mode))
    else:
        buf = io.StringIO()
        with contextlib.redirect_stdout(buf):
            res = asyncio.run(run_flashseq(p, mode=args.mode))

    print(res.summary())

    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    out = OUTPUT_DIR / "automation_run.txt"
    out.write_text(res.summary(), encoding="utf-8")
    print(f"\n[automation] Summary written -> {out}")


if __name__ == "__main__":
    main()
