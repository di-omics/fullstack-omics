#!/usr/bin/env python3
"""Stage 1 -- Procurement (kit-based BOM -> single approval summary).

  python scripts/run_procurement.py --n 96 [--first-time-buyer] [--approve]

Nothing is ordered without a single human APPROVE, and even --approve is a DRY RUN.
"""
import argparse

import _bootstrap  # noqa: F401
from _bootstrap import OUTPUT_DIR

from autoscwgs.params import load_params
from autoscwgs.procurement import (
    build_bom, route_channels, approval_summary_markdown, place_orders,
    build_controller_kit, controller_kit_markdown, resolve_connectivity, connectivity_markdown,
)


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--n", type=int, default=96)
    ap.add_argument("--first-time-buyer", action="store_true")
    ap.add_argument("--approve", action="store_true", help="DRY-RUN place orders (no live checkout)")
    args = ap.parse_args()

    p = load_params().with_run(n_samples=args.n)
    items = route_channels(build_bom(p))
    ck_md = controller_kit_markdown(build_controller_kit(p)) if args.first_time_buyer else None
    conn_md = connectivity_markdown(resolve_connectivity(p))
    approval = approval_summary_markdown(items, p=p, controller_kit_md=ck_md, connectivity_md=conn_md)

    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    out = OUTPUT_DIR / "purchase_approval.md"
    out.write_text(approval, encoding="utf-8")
    print(approval)
    print(f"\n[procurement] -> {out}")

    if args.approve:
        record = place_orders(items, approved=True)
        print(f"\n[procurement] {record['status']}")
        print(f"[procurement] {record['todo']}")


if __name__ == "__main__":
    main()
