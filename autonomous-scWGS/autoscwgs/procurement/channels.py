"""Render a fail-closed planning checklist; public data is never orderable."""

from __future__ import annotations

from collections.abc import Iterable

from ..params import Params
from .bom import BomItem

VERIFY = "verify"


def route_channels(items: Iterable[BomItem]) -> list[BomItem]:
    routed = list(items)
    for item in routed:
        item.channel = VERIFY
        item.channel_reason = "Resolve in the ignored local validated profile."
    return routed


def approval_summary_markdown(
    items: list[BomItem],
    *,
    p: Params,
    n_samples: int | None = None,
    **_: object,
) -> str:
    count = p.n_samples if n_samples is None else int(n_samples)
    lines = [
        f"# WGS functional planning checklist (N = {count})",
        "",
        "> Planning only. The public profile contains no orderable item or quantity.",
        "",
        "| Requirement | Status |",
        "|---|---|",
    ]
    lines.extend(
        f"| {item.name} | define in ignored local validated profile |"
        for item in items
    )
    return "\n".join(lines) + "\n"


def place_orders(items: list[BomItem], *, approved: bool) -> dict:
    if not approved:
        raise PermissionError("Explicit approval is required.")
    if any(item.verify or item.channel == VERIFY for item in items):
        raise ValueError("Public functional requirements are not orderable.")
    return {"status": "DRY_RUN", "items": [item.name for item in items]}
