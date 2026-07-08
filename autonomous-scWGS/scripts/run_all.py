#!/usr/bin/env python3
"""End-to-end demo: all stages wired together in the PLR simulator.

  python scripts/run_all.py --n 16 [--first-time-buyer] [--operator humanoid]

Runs Procurement -> Manual -> Sort+Automation(sim) -> Result and writes every
artifact to output/. No hardware, no live ordering. RESEARCH USE ONLY.
"""
import argparse
import asyncio
import contextlib
import io

import _bootstrap  # noqa: F401
from _bootstrap import OUTPUT_DIR

from autoscwgs.params import load_params
from autoscwgs.procurement import (
    build_bom, route_channels, approval_summary_markdown, build_controller_kit,
    controller_kit_markdown, resolve_connectivity, connectivity_markdown,
)
from autoscwgs.manual import write_manual
from autoscwgs.automation import run_workflow
from autoscwgs.result import write_pipeline


def _hr(title: str) -> None:
    print("\n" + "=" * 72)
    print(f"  {title}")
    print("=" * 72)


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--n", type=int, default=16)
    ap.add_argument("--first-time-buyer", action="store_true")
    ap.add_argument("--operator", default="human", choices=["human", "humanoid"],
                    help="who tends the deck: a person, or the experimental humanoid ops robot")
    args = ap.parse_args()

    p = load_params().with_run(n_samples=args.n)
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    print(f"autonomous-scWGS -- single-cell WGS end-to-end (sim). N={p.n_samples}.")
    print("WGA: ResolveDNA PTA | Library: NEBNext Ultra II | Sort: FACS Melody")
    print("RESEARCH USE ONLY -- not clinically validated.")

    # -- Procurement ----------------------------------------------------------
    _hr("Stage 1/4  PROCUREMENT (kit-based)")
    items = route_channels(build_bom(p))
    ck_md = controller_kit_markdown(build_controller_kit(p)) if args.first_time_buyer else None
    conn_md = connectivity_markdown(resolve_connectivity(p))
    approval = approval_summary_markdown(items, p=p, controller_kit_md=ck_md, connectivity_md=conn_md)
    (OUTPUT_DIR / "purchase_approval.md").write_text(approval, encoding="utf-8")
    verify_n = sum(1 for i in items if i.verify)
    print(f"BOM: {len(items)} line items; {verify_n} need verification before ordering.")
    print("-> output/purchase_approval.md  (NOTHING ordered without human APPROVE)")

    # -- Manual ---------------------------------------------------------------
    _hr("Stage 2/4  MANUAL")
    man = write_manual(p, OUTPUT_DIR)
    print(f"-> {man['markdown']}")
    print(f"   PDF: {man.get('pdf') or man.get('pdf_error')}")

    # -- Automation (PLR simulator; readiness + sort baked in) ----------------
    _hr("Stage 3/4  AUTOMATION (PyLabRobot simulator)")
    print(f"Operator: {args.operator}")
    buf = io.StringIO()
    with contextlib.redirect_stdout(buf):  # hide verbose chatterbox actions
        res = asyncio.run(run_workflow(p, mode="sim", operator=args.operator))
    print(res.summary())
    (OUTPUT_DIR / "automation_run.txt").write_text(res.summary(), encoding="utf-8")
    if res.readiness is not None:
        (OUTPUT_DIR / "instrument_readiness.txt").write_text(res.readiness.summary(), encoding="utf-8")
    if res.sort is not None:
        (OUTPUT_DIR / "sort_report.txt").write_text(res.sort.summary(), encoding="utf-8")

    # -- Result ---------------------------------------------------------------
    _hr("Stage 4/4  RESULT (BJ-WGS sequencing analysis)")
    # Feed the actual sorted sample wells into the WGS analysis input.csv.
    sample_wells = res.sort.plan.sample_wells if res.sort is not None else None
    pipe = write_pipeline(p, OUTPUT_DIR, sample_wells=sample_wells)
    print(f"-> {pipe['pipeline']}")
    print(f"-> {pipe['input_csv']}")
    print("   BJ-WGS (Nextflow): Sentieon BWA MEM -> Dedup -> BQSR -> DNAScope")
    print("   -> SnpEff/ClinVar/dbSNP -> MultiQC. Deps: Nextflow, Docker, Sentieon license.")

    _hr("DONE")
    print(f"All artifacts in: {OUTPUT_DIR}")
    for f in sorted(OUTPUT_DIR.glob("*")):
        print(f"  - {f.name}")


if __name__ == "__main__":
    main()
