"""Procurement: kit-based BOM, channel routing, approval summary, connectivity."""

from .bom import BomItem, build_bom
from .channels import VERIFY, route_channels, approval_summary_markdown, place_orders
from .connectivity import resolve_connectivity, connectivity_markdown
from .controller_kit import build_controller_kit, controller_kit_markdown

__all__ = [
    "BomItem",
    "build_bom",
    "VERIFY",
    "route_channels",
    "approval_summary_markdown",
    "place_orders",
    "resolve_connectivity",
    "connectivity_markdown",
    "build_controller_kit",
    "controller_kit_markdown",
]
