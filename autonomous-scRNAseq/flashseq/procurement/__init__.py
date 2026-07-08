"""Stage 1 -- Procurement: BOM -> channel routing -> single approval -> (dry-run) order.

No live ordering happens in v1. This package builds the scaled BOM, resolves each
item to a purchase channel, specs a controller kit + cabling for first-time buyers,
and emits ONE "approve to purchase" summary. Placing real orders is gated behind an
explicit human approval and is stubbed (marked external dependency).
"""

from .bom import BomItem, build_bom
from .channels import route_channels, approval_summary_markdown
from .controller_kit import build_controller_kit
from .connectivity import resolve_connectivity

__all__ = [
    "BomItem",
    "build_bom",
    "route_channels",
    "approval_summary_markdown",
    "build_controller_kit",
    "resolve_connectivity",
]
