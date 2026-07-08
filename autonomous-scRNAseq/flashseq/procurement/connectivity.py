"""Connectivity resolver: instruments.yaml -> exact cables + PLR backends.

For each instrument we read the *verified* physical connector on the instrument and
on the Raspberry Pi, then look up the matching cable in `cable_catalog`. We NEVER
hardcode port types here: anything the registry marks `# TODO: verify interface`
propagates to a flagged cable line so it's obvious what still needs confirming.

The host talks to the Pi over ethernet; the Pi runs PyLabRobot and talks to each
instrument locally.
"""

from __future__ import annotations

from typing import Any

from ..params import Params

_TODO_MARKERS = ("todo", "verify", "expert value")


def _is_unresolved(value: Any) -> bool:
    if value is None:
        return True
    return any(m in str(value).lower() for m in _TODO_MARKERS)


def _lookup_cable(catalog: dict[str, str], pi_conn: str, instr_conn: str) -> str:
    for key in (f"{pi_conn}__{instr_conn}", f"{instr_conn}__{pi_conn}"):
        if key in catalog:
            return catalog[key]
    return f"cable {pi_conn} <-> {instr_conn} (not in cable_catalog)"


def resolve_connectivity(p: Params) -> dict:
    """Return structured links (per instrument) + the host<->Pi ethernet link."""
    instruments = p.instruments.get("instruments", {})
    catalog = p.instruments.get("cable_catalog", {})
    links: list[dict[str, Any]] = []

    for iid, spec in instruments.items():
        conn = spec.get("connectivity", {})
        plr = spec.get("plr", {})
        instr_conn = conn.get("instrument_connector")
        pi_conn = conn.get("pi_connector")
        flagged = _is_unresolved(instr_conn) or _is_unresolved(pi_conn)
        if flagged:
            cable = "# TODO: verify interface -- confirm port(s), then cable resolves automatically"
        else:
            cable = _lookup_cable(catalog, str(pi_conn), str(instr_conn))
        links.append(
            {
                "id": iid,
                "make_model": spec.get("make_model", iid),
                "role": spec.get("role", ""),
                "interface": conn.get("instrument_interface"),
                "instrument_connector": instr_conn,
                "pi_connector": pi_conn,
                "cable": cable,
                "flagged": flagged,
                "backend_hardware": plr.get("backend_hardware"),
                "backend_sim": plr.get("backend_sim"),
                "driver_notes": conn.get("driver_notes", ""),
            }
        )

    host_link = {
        "from": "host / agent",
        "to": "Raspberry Pi",
        "cable": catalog.get("ethernet__ethernet", "Ethernet patch cable"),
        "note": "host <-> Pi over ethernet; Pi runs PyLabRobot",
    }
    return {"links": links, "host_link": host_link}


def connectivity_markdown(resolved: dict) -> str:
    lines = ["## Cabling (resolved from instruments.yaml)\n"]
    lines.append("| Instrument | Interface | Pi port | Instrument port | Cable | PLR backend (HW) |")
    lines.append("|---|---|---|---|---|---|")
    for lk in resolved["links"]:
        lines.append(
            f"| {lk['make_model']} | {lk['interface']} | {lk['pi_connector']} | "
            f"{lk['instrument_connector']} | {lk['cable']} | `{lk['backend_hardware']}` |"
        )
    hl = resolved["host_link"]
    lines.append(f"\n- **{hl['from']} -> {hl['to']}**: {hl['cable']} ({hl['note']}).")
    flagged = [lk for lk in resolved["links"] if lk["flagged"]]
    if flagged:
        lines.append("\n**Unverified interfaces (confirm against instrument manuals):**")
        for lk in flagged:
            lines.append(f"- {lk['make_model']}: {lk['driver_notes'] or 'confirm port type'}")
    return "\n".join(lines)
