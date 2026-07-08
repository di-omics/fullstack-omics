"""Printable bench manual (Markdown; optional PDF via pandoc)."""

from .render import render_manual_markdown, write_manual

__all__ = ["render_manual_markdown", "write_manual"]
