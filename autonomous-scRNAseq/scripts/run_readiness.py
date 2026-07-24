#!/usr/bin/env python3
"""Run synthetic software-contract readiness checks."""

import argparse
import asyncio

import _bootstrap  # noqa: F401
from _bootstrap import OUTPUT_DIR

from scrnaseq.params import load_params
from scrnaseq.readiness import run_readiness_check


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--state", choices=["calibrated", "needs_review"], default="calibrated")
    args = parser.parse_args()
    report = asyncio.run(
        run_readiness_check(load_params(), mode="sim", handler_state=args.state)
    )
    print(report.summary())
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    path = OUTPUT_DIR / "contract_readiness.txt"
    path.write_text(report.summary(), encoding="utf-8")
    raise SystemExit(0 if report.ready else 2)


if __name__ == "__main__":
    main()
