#!/usr/bin/env python3
"""Stage 1 -- Procurement: build BOM, route channels, emit the single approval doc.

  python scripts/run_procurement.py --n 96 [--first-time-buyer] [--approve]

Nothing is ordered without --approve, and even then order placement is a DRY RUN
(live IDT API / browser carts / Coupa-Jaggaer PO are external deps).
"""
import argparse

import _bootstrap  # noqa: F401  (sets sys.path + OUTPUT_DIR)
from _bootstrap import OUTPUT_DIR

from flashseq.params import load_params
from flashseq.procurement import (
    build_bom, route_channels, approval_summary_markdown,
    build_controller_kit,
)
from flashseq.procurement.controller_kit import controller_kit_markdown
from flashseq.procurement.connectivity import resolve_connectivity, connectivity_markdown
from flashseq.procurement.channels import place_orders


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--n", type=int, default=None, help="number of cells")
    ap.add_argument("--plate", type=int, default=None, choices=[96, 384])
    ap.add_argument("--first-time-buyer", action="store_true",
                    help="also spec a Raspberry Pi controller kit + cabling")
    ap.add_argument("--approve", action="store_true",
                    help="human approval to place orders (DRY RUN only in v1)")
    args = ap.parse_args()

    p = load_params().with_run(n_cells=args.n, plate_format=args.plate)
    items = route_channels(build_bom(p))

    ck_md = None
    conn_md = None
    if args.first_time_buyer:
        ck_md = controller_kit_markdown(build_controller_kit(p))
    conn_md = connectivity_markdown(resolve_connectivity(p))

    summary = approval_summary_markdown(items, p=p, controller_kit_md=ck_md, connectivity_md=conn_md)
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    out = OUTPUT_DIR / "purchase_approval.md"
    out.write_text(summary, encoding="utf-8")

    print(f"[procurement] {len(items)} BOM line items for N={p.n_cells} ({p.plate_format}-well)")
    print(f"[procurement] Approval summary written -> {out}")
    verify = [i for i in items if i.verify]
    if verify:
        print(f"[procurement] {len(verify)} item(s) need verification before ordering:")
        for it in verify:
            print(f"   - {it.name} ({it.catalog})")

    if args.approve:
        record = place_orders(items, approved=True)
        print(f"[procurement] {record['status']}")
        print(f"[procurement] {record['todo']}")
    else:
        print("[procurement] Not ordered. Review the approval doc; re-run with --approve to authorize.")


if __name__ == "__main__":
    main()
