"""ASCII wiring diagram for the printable manual, built from the connectivity resolver.

Host talks to the Raspberry Pi over ethernet; the Pi runs PyLabRobot and connects to
each instrument locally. Unverified interfaces render with a `[verify]` tag so the
diagram itself flags what still needs confirming (never a hardcoded guess). The FACS
Melody is workstation-driven and will show as [verify] until its RE is complete.
"""

from __future__ import annotations

from ..params import Params
from ..procurement.connectivity import resolve_connectivity


def wiring_diagram_ascii(p: Params) -> str:
    resolved = resolve_connectivity(p)
    lines: list[str] = []
    lines.append("```")
    lines.append("        +------------------------+")
    lines.append("        |     Host / Agent       |")
    lines.append("        +-----------+------------+")
    lines.append("                    | ethernet")
    lines.append("        +-----------+------------+")
    lines.append("        | Raspberry Pi           |")
    lines.append("        | (PyLabRobot backend)   |")
    lines.append("        +-----------+------------+")
    lines.append("                    |")
    for lk in resolved["links"]:
        tag = " [verify]" if lk["flagged"] else ""
        port = lk["pi_connector"]
        lines.append(f"    port {port}{tag}")
        lines.append(f"      +---> {lk['make_model']}  ({lk['role']})")
        lines.append(f"            cable: {lk['cable']}")
        lines.append(f"            PLR backend (hardware): {lk['backend_hardware']}")
        lines.append("")
    lines.append("```")
    return "\n".join(lines)
