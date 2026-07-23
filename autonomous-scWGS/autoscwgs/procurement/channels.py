"""Route each BOM item to its best purchase channel and build ONE approval summary.

Channels for this (kit-based) workflow:
  browser        -- browser-automation agent (browser-automation agent) fills carts on vendor
                    storefronts (NEB, Thermo, Sigma/Millipore, Agilent, Beckman,
                    Eppendorf, Illumina, VWR).
  vendor_direct  -- specialty suppliers and BD Biosciences (quote-based). Emit a
                    pre-filled order request.
  po             -- PO / requisition fallback for General Lab Supplier + institutional
                    punch-out (Coupa / Jaggaer).
  verify         -- unresolved supplier, SKU, or channel data; never orderable.

SAFETY: this module only PLANS and ROUTES. No cart is checked out and no order is
placed until a human replies to the single approval summary. `place_orders()` is a
dry-run stub gated behind `approved=True`; live integrations are external deps (TODO).
"""

from __future__ import annotations

from typing import Iterable, Optional

from ..params import Params
from .bom import BomItem

BROWSER = "browser"
VENDOR_DIRECT = "vendor_direct"
PO = "po"
VERIFY = "verify"
_ORDERABLE_CHANNELS = {BROWSER, VENDOR_DIRECT, PO}
_WGA_CATEGORIES_REQUIRING_CHANNEL = {
    "Single-cell WGA kit",
    "WGA accessories / consumables",
}

_BROWSER_VENDORS = (
    "neb", "new england biolabs", "thermo", "sigma", "millipore", "agilent",
    "beckman", "eppendorf", "illumina", "invitrogen", "vwr", "merck",
)
_DIRECT_VENDORS = ("bd biosciences", "bd ")


def _requires_verification(item: BomItem) -> bool:
    vendor = (item.vendor or "").strip()
    catalog = (item.catalog or "").strip()
    channel = (item.channel or "").strip()
    return bool(
        item.verify
        or channel == VERIFY
        or (channel and channel not in _ORDERABLE_CHANNELS)
        or (item.category in _WGA_CATEGORIES_REQUIRING_CHANNEL and not channel)
        or not vendor
        or not catalog
        or vendor.startswith("#")
        or catalog.startswith("#")
    )


def _route_one(item: BomItem) -> tuple[str, str]:
    if _requires_verification(item):
        return VERIFY, item.channel_reason or (
            "Supplier, SKU, or purchase-channel data requires verification."
        )
    if item.channel in _ORDERABLE_CHANNELS:
        return item.channel, item.channel_reason or "Explicit purchase channel from configuration."
    v = (item.vendor or "").lower()
    if any(k in v for k in _DIRECT_VENDORS):
        return VENDOR_DIRECT, f"{item.vendor} has no public cart -> direct order request (sales/quote)."
    if any(k in v for k in _BROWSER_VENDORS):
        return BROWSER, f"{item.vendor} has a web storefront -> browser-automation agent fills the cart."
    return PO, f"No easy storefront for {item.vendor} -> PO / requisition punch-out (Coupa/Jaggaer)."


def route_channels(items: Iterable[BomItem]) -> list[BomItem]:
    """Annotate each item with .channel / .channel_reason. Returns the same list."""
    out = list(items)
    for it in out:
        it.channel, it.channel_reason = _route_one(it)
    return out


def _lead_time_section() -> str:
    return (
        "## Scheduling\n"
        "Lead times are not in the protocols; fill them from each vendor quote at order time.\n"
        "The WGA and NEBNext Ultra II kits usually set the critical path. After\n"
        "orders are placed, track status and set the automation run date to "
        "`max(lead_time) + buffer`.  `# TODO: expert value -- per-item lead times`\n"
    )


def approval_summary_markdown(
    items: list[BomItem],
    *,
    p: Params,
    controller_kit_md: Optional[str] = None,
    connectivity_md: Optional[str] = None,
    n_samples: Optional[int] = None,
) -> str:
    """Assemble the single human-facing 'approve to purchase' document."""
    n = p.n_samples if n_samples is None else n_samples
    by_channel: dict[str, list[BomItem]] = {
        VERIFY: [], BROWSER: [], VENDOR_DIRECT: [], PO: []
    }
    for it in items:
        by_channel.setdefault(it.channel or PO, []).append(it)

    verify_items = [it for it in items if _requires_verification(it)]
    ordering_blocked = bool(verify_items or by_channel[VERIFY])

    lines: list[str] = []
    lines.append(f"# Single-cell WGS -- Purchase Approval  (N = {n} samples, {p.n_kits(n)} kit(s))\n")
    if ordering_blocked:
        lines.append(
            "> **ORDERING BLOCKED.** Resolve every `VERIFY` item with private/local supplier\n"
            "> configuration before approval can authorize any order.\n"
            "> **RESEARCH USE ONLY -- not clinically validated.**\n"
        )
    else:
        lines.append(
            "> **NOTHING IS ORDERED UNTIL YOU APPROVE.** Reply `APPROVE` to authorize the\n"
            "> single batch below. No individual checkout happens without this one approval.\n"
            "> **RESEARCH USE ONLY -- not clinically validated.**\n"
        )
    lines.append(
        "\n_Library prep here is a KIT, so procurement is mostly \"buy the kit\": one\n"
        "single-cell WGA kit + one NEBNext Ultra II kit per 96 samples, plus QC + consumables._\n"
    )

    channel_titles = {
        VERIFY: "Verification required (not orderable)",
        BROWSER: "Browser-automation agent (browser agent fills carts)",
        VENDOR_DIRECT: "Configured direct supplier / BD order",
        PO: "PO / requisition (institutional punch-out: Coupa / Jaggaer)",
    }
    for ch in (VERIFY, VENDOR_DIRECT, BROWSER, PO):
        group = by_channel.get(ch, [])
        if not group:
            continue
        lines.append(f"\n## {channel_titles[ch]}  ({len(group)} item(s))\n")
        lines.append("| Item | Vendor | Catalog # | Quantity | Flags |")
        lines.append("|---|---|---|---|---|")
        for it in group:
            flags = []
            if _requires_verification(it):
                flags.append("VERIFY")
            if it.optional:
                flags.append("optional")
            flag_str = ", ".join(flags) if flags else ""
            lines.append(f"| {it.name} | {it.vendor} | `{it.catalog}` | {it.quantity} | {flag_str} |")

    if verify_items:
        lines.append("\n## Verify before ordering (missing / ambiguous catalog #s)\n")
        for it in verify_items:
            note = it.verify_note or (
                "Set supplier, SKU, purchase channel, and verification state in "
                "private/local configuration."
            )
            lines.append(f"- **{it.name}** (`{it.catalog}`): {note}")

    if controller_kit_md:
        lines.append("\n" + controller_kit_md)
    if connectivity_md:
        lines.append("\n" + connectivity_md)

    lines.append("\n" + _lead_time_section())
    lines.append(
        "\n---\n_Prices/pack sizes are not in the protocols; fill from vendor quotes._\n"
        "_WGA: proprietary supplier protocol. Library prep: NEBNext Ultra II (NEB E7645). "
        "Sort: BD FACS Melody. RESEARCH USE ONLY._\n"
    )
    return "\n".join(lines)


def place_orders(items: list[BomItem], *, approved: bool) -> dict:
    """DRY-RUN order placement. Refuses unless the human approved. Never checks out live."""
    if not approved:
        raise PermissionError(
            "Refusing to place orders: no human approval. Present the approval summary "
            "and pass approved=True only after the user replies APPROVE."
        )
    unresolved = [it for it in items if _requires_verification(it)]
    if unresolved:
        names = ", ".join(it.name for it in unresolved)
        raise ValueError(
            "Refusing to place orders: unresolved procurement items require private/local "
            f"configuration and verification: {names}"
        )
    record: dict[str, list[str]] = {BROWSER: [], VENDOR_DIRECT: [], PO: []}
    for it in items:
        record.setdefault(it.channel or PO, []).append(f"{it.name} [{it.catalog}] x {it.quantity}")
    return {
        "status": "DRY_RUN (no live orders placed)",
        "todo": "Wire live channels: the browser agent carts (NEB/Thermo/Agilent/...), "
                "specialty-supplier/BD direct order, Coupa/Jaggaer PO.",
        "orders_by_channel": record,
    }
