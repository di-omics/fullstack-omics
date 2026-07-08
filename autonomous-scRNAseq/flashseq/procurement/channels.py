"""Route each BOM item to its best purchase channel and build ONE approval summary.

Channels (from the build spec):
  idt_api  -- direct vendor API for custom FLASH-seq oligos (and Quartzy where used).
  browser  -- browser-automation agent (Claude in Chrome) fills carts on vendor sites
              that have web storefronts (Thermo, Sigma/Millipore, Takara, NEB, Illumina).
  po       -- PO / requisition fallback for institutional punch-out (Coupa/Jaggaer).

SAFETY: This module only PLANS and ROUTES. No cart is checked out and no order is
placed until a human replies to the single approval summary. `place_orders()` is a
dry-run stub gated behind `approved=True`; live API/browser/PO integration is an
external dependency to be wired per-site (marked TODO there).
"""

from __future__ import annotations

from typing import Iterable, Optional

from ..params import Params
from .bom import BomItem

IDT_API = "idt_api"
BROWSER = "browser"
PO = "po"

# Vendors with web storefronts a browser agent can drive. Others fall back to PO.
_BROWSER_VENDORS = (
    "thermo", "sigma", "millipore", "takara", "neb", "new england biolabs",
    "illumina", "invitrogen", "ambion", "life technologies",
)


def _route_one(item: BomItem) -> tuple[str, str]:
    v = (item.vendor or "").lower()
    cat = (item.category or "").lower()
    if "oligo" in cat or item.catalog == "custom" or "idt" in v:
        return IDT_API, "Custom oligo -> IDT oligo API (or Quartzy where the lab routes oligos)."
    if any(k in v for k in _BROWSER_VENDORS):
        return BROWSER, f"{item.vendor} has a web storefront -> browser-automation agent fills the cart."
    return PO, f"No easy storefront for {item.vendor} -> PO / requisition punch-out (Coupa/Jaggaer)."


def route_channels(items: Iterable[BomItem]) -> list[BomItem]:
    """Annotate each item with .channel / .channel_reason. Returns the same list."""
    out = list(items)
    for it in out:
        it.channel, it.channel_reason = _route_one(it)
    return out


def _lead_time_section(p: Params) -> str:
    """Scheduling hook: reagents' lead times gate when the automation run can start.
    Actual lead times are vendor-quote data (not in the protocol) -> TODO per item."""
    return (
        "## Scheduling\n"
        "Lead times are not in the protocol; fill them from each vendor quote at order time.\n"
        "The longest lead time (usually **custom oligos via IDT**) sets the earliest date the\n"
        "automation run can be scheduled. After orders are placed, track status and set the\n"
        "run date to `max(lead_time) + buffer`.  `# TODO: expert value -- per-item lead times`\n"
    )


def approval_summary_markdown(
    items: list[BomItem],
    *,
    p: Params,
    controller_kit_md: Optional[str] = None,
    connectivity_md: Optional[str] = None,
    n_cells: Optional[int] = None,
) -> str:
    """Assemble the single human-facing 'approve to purchase' document."""
    n = p.n_cells if n_cells is None else n_cells
    by_channel: dict[str, list[BomItem]] = {IDT_API: [], BROWSER: [], PO: []}
    for it in items:
        by_channel.setdefault(it.channel or PO, []).append(it)

    verify_items = [it for it in items if it.verify]

    lines: list[str] = []
    lines.append(f"# FLASH-seq UMI -- Purchase Approval  (N = {n} cells, {p.plate_format}-well)\n")
    lines.append(
        "> **NOTHING IS ORDERED UNTIL YOU APPROVE.** Reply `APPROVE` to authorize the\n"
        "> single batch below. No individual checkout happens without this one approval.\n"
        "> **RESEARCH USE ONLY -- not clinically validated.**\n"
    )

    channel_titles = {
        IDT_API: "Direct vendor API (IDT oligos / Quartzy)",
        BROWSER: "Browser-automation agent (Claude in Chrome fills carts)",
        PO: "PO / requisition (institutional punch-out: Coupa / Jaggaer)",
    }
    for ch in (IDT_API, BROWSER, PO):
        group = by_channel.get(ch, [])
        if not group:
            continue
        lines.append(f"\n## {channel_titles[ch]}  ({len(group)} item(s))\n")
        lines.append("| Item | Vendor | Catalog # | Quantity for this run | Flags |")
        lines.append("|---|---|---|---|---|")
        for it in group:
            flags = []
            if it.verify:
                flags.append("VERIFY")
            if it.optional:
                flags.append("optional")
            flag_str = ", ".join(flags) if flags else ""
            lines.append(
                f"| {it.name} | {it.vendor} | `{it.catalog}` | {it.quantity} | {flag_str} |"
            )

    if verify_items:
        lines.append("\n## Verify before ordering (OCR-ambiguous or expert values)\n")
        for it in verify_items:
            lines.append(f"- **{it.name}** (`{it.catalog}`): {it.verify_note}")

    if controller_kit_md:
        lines.append("\n" + controller_kit_md)
    if connectivity_md:
        lines.append("\n" + connectivity_md)

    lines.append("\n" + _lead_time_section(p))
    lines.append(
        "\n---\n_Prices/pack sizes are not in the protocol; fill from vendor quotes._\n"
        "_Method: FLASH-seq UMI v3, Picelli & Hahaut, DOI 10.17504/protocols.io.bp2l619rdvqe/v3 (CC-BY)._\n"
    )
    return "\n".join(lines)


def place_orders(items: list[BomItem], *, approved: bool) -> dict:
    """DRY-RUN order placement. Refuses unless the human approved. Never checks out live.

    Returns a record of what WOULD be ordered per channel. Wiring the live IDT API,
    the Claude-in-Chrome cart flow, and the Coupa/Jaggaer PO submission are external
    dependencies -- intentionally not implemented in v1.
    """
    if not approved:
        raise PermissionError(
            "Refusing to place orders: no human approval. Present the approval summary "
            "and pass approved=True only after the user replies APPROVE."
        )
    record: dict[str, list[str]] = {IDT_API: [], BROWSER: [], PO: []}
    for it in items:
        record.setdefault(it.channel or PO, []).append(f"{it.name} [{it.catalog}] x {it.quantity}")
    return {
        "status": "DRY_RUN (no live orders placed)",
        "todo": "Wire live channels: IDT oligo API, Claude-in-Chrome carts, Coupa/Jaggaer PO.",
        "orders_by_channel": record,
    }
