#!/usr/bin/env python3
"""Stage 0 -- Rhodamine B liquid-handling QC (REQUIRED before a run).

  python scripts/run_readiness.py                              # simulate a calibrated handler
  python scripts/run_readiness.py --state needs_calibration    # simulate a bad handler
  python scripts/run_readiness.py --mode hardware              # requires instruments.yaml filled

Dispenses Rhodamine B at low/medium/high protocol volume scales across a 96-well
plate, reads on the Synergy H1, and reports per-range CV -> READY or NEEDS_CALIBRATION.
"""
import argparse
import asyncio
import contextlib
import io

import _bootstrap  # noqa: F401
from _bootstrap import OUTPUT_DIR

from autoscwgs.params import load_params
from autoscwgs.readiness import run_readiness_check


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--mode", default="sim", choices=["sim", "hardware"])
    ap.add_argument("--state", default=None, choices=["calibrated", "needs_calibration"],
                    help="(sim only) simulate a calibrated or mis-calibrated handler")
    ap.add_argument("--verbose", action="store_true")
    args = ap.parse_args()

    p = load_params()
    if args.verbose:
        report = asyncio.run(run_readiness_check(p, mode=args.mode, handler_state=args.state))
    else:
        with contextlib.redirect_stdout(io.StringIO()):
            report = asyncio.run(run_readiness_check(p, mode=args.mode, handler_state=args.state))

    print(report.summary())
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    (OUTPUT_DIR / "instrument_readiness.txt").write_text(report.summary(), encoding="utf-8")
    print(f"\n[readiness] -> {OUTPUT_DIR / 'instrument_readiness.txt'}")
    raise SystemExit(0 if report.ready else 2)


if __name__ == "__main__":
    main()
