#!/usr/bin/env python3
"""End-to-end demo: all 4 FLASH-seq stages wired together in the PLR simulator.

  python scripts/run_all.py --n 16 [--first-time-buyer]

Runs Procurement -> Manual -> Automation(sim) -> Result and writes every artifact
to output/. No hardware and no live ordering. RESEARCH USE ONLY.
"""
import argparse
import asyncio
import contextlib
import io

import _bootstrap  # noqa: F401
from _bootstrap import OUTPUT_DIR

from flashseq.params import load_params
from flashseq.procurement import (
    build_bom, route_channels, approval_summary_markdown, build_controller_kit,
)
from flashseq.procurement.controller_kit import controller_kit_markdown
from flashseq.procurement.connectivity import resolve_connectivity, connectivity_markdown
from flashseq.manual import write_manual
from flashseq.automation import run_flashseq
from flashseq.result import write_pipeline


def _hr(title: str) -> None:
    print("\n" + "=" * 70)
    print(f"  {title}")
    print("=" * 70)


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--n", type=int, default=16)
    ap.add_argument("--plate", type=int, default=None, choices=[96, 384])
    ap.add_argument("--first-time-buyer", action="store_true")
    ap.add_argument("--operator", default="human", choices=["human", "humanoid"],
                    help="who tends the deck: a person, or the experimental humanoid ops robot")
    args = ap.parse_args()

    p = load_params().with_run(n_cells=args.n, plate_format=args.plate)
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    print(f"FLASH-seq skill -- end-to-end (sim). N={p.n_cells}, {p.plate_format}-well.")
    print("RESEARCH USE ONLY -- not clinically validated.")

    # -- Stage 1: Procurement -------------------------------------------------
    _hr("Stage 1/4  PROCUREMENT")
    items = route_channels(build_bom(p))
    ck_md = controller_kit_markdown(build_controller_kit(p)) if args.first_time_buyer else None
    conn_md = connectivity_markdown(resolve_connectivity(p))
    approval = approval_summary_markdown(items, p=p, controller_kit_md=ck_md, connectivity_md=conn_md)
    (OUTPUT_DIR / "purchase_approval.md").write_text(approval, encoding="utf-8")
    verify_n = sum(1 for i in items if i.verify)
    print(f"BOM: {len(items)} line items; {verify_n} need verification before ordering.")
    print(f"-> output/purchase_approval.md  (NOTHING ordered without human APPROVE)")

    # -- Stage 2: Manual ------------------------------------------------------
    _hr("Stage 2/4  MANUAL")
    man = write_manual(p, OUTPUT_DIR)
    print(f"-> {man['markdown']}")
    print(f"   PDF: {man.get('pdf') or man.get('pdf_error')}")

    # -- Stage 3: Automation (PLR simulator) ----------------------------------
    # Instrument readiness (Rhodamine B QC) runs as REQUIRED Step 1 inside run_flashseq.
    _hr("Stage 3/4  AUTOMATION (PyLabRobot simulator)")
    print(f"Operator: {args.operator}")
    buf = io.StringIO()
    with contextlib.redirect_stdout(buf):  # hide verbose chatterbox actions
        res = asyncio.run(run_flashseq(p, mode="sim", operator=args.operator))
    print(res.summary())
    (OUTPUT_DIR / "automation_run.txt").write_text(res.summary(), encoding="utf-8")
    if res.readiness is not None:
        (OUTPUT_DIR / "instrument_readiness.txt").write_text(res.readiness.summary(), encoding="utf-8")

    # -- Stage 4: Result ------------------------------------------------------
    _hr("Stage 4/4  RESULT (analysis pipeline stub)")
    pipe = write_pipeline(p, OUTPUT_DIR)
    print(f"-> {pipe['pipeline']}")
    print("   External tools: bcl2fastq, umi_tools, STAR, samtools, featureCounts, bbmap.")

    _hr("DONE")
    print(f"All artifacts in: {OUTPUT_DIR}")
    for f in sorted(OUTPUT_DIR.glob("*")):
        print(f"  - {f.name}")


if __name__ == "__main__":
    main()
