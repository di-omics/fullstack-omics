"""Stage 2 -- Manual: render a printable bench manual from protocol_params.yaml.

Produces Markdown (always) and, if pandoc or weasyprint is available, a PDF.
Includes deck layout, per-step volumes/timings, on-ice vs RT handling, safe-stop
points, and a wiring diagram built from instruments.yaml.
"""

from .render import render_manual_markdown, write_manual
from .wiring import wiring_diagram_ascii

__all__ = ["render_manual_markdown", "write_manual", "wiring_diagram_ascii"]
