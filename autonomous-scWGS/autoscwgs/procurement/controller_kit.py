"""First-time-buyer mode: spec a controller bring-up kit (Raspberry Pi + cabling).

Only invoked when the user has no existing PLR controller. The core kit and
networking come from instruments.yaml `controller_kit`; the per-instrument cables
come from the connectivity resolver so the same registry drives both. These are
engineering recommendations, not protocol values -- confirm current part numbers.
"""

from __future__ import annotations

from ..params import Params
from .connectivity import resolve_connectivity


def build_controller_kit(p: Params) -> dict:
    kit = p.instruments.get("controller_kit", {})
    resolved = resolve_connectivity(p)
    instrument_cables = [
        {"for": lk["make_model"], "cable": lk["cable"], "flagged": lk["flagged"]}
        for lk in resolved["links"]
    ]
    return {
        "recommend_when": kit.get("recommend_when", ""),
        "core": kit.get("core", []),
        "networking": kit.get("networking", []),
        "instrument_cables": instrument_cables,
        "host_link": resolved["host_link"],
    }


def controller_kit_markdown(kit: dict) -> str:
    lines = ["## First-time-buyer: controller bring-up kit\n"]
    lines.append(f"_Recommended when: {kit.get('recommend_when','')}_\n")
    lines.append("**Core (Raspberry Pi controller):**")
    for it in kit.get("core", []):
        note = f" -- {it['note']}" if it.get("note") else ""
        lines.append(f"- {it['name']} x{it.get('qty',1)} ({it.get('role','')}){note}")
    lines.append("\n**Networking:**")
    for it in kit.get("networking", []):
        opt = " (optional)" if it.get("optional") else ""
        note = f" -- {it['note']}" if it.get("note") else ""
        lines.append(f"- {it['name']} x{it.get('qty',1)}{opt}{note}")
    lines.append("\n**Instrument cables (from connectivity resolver):**")
    for c in kit.get("instrument_cables", []):
        flag = "  `# TODO: verify interface`" if c["flagged"] else ""
        lines.append(f"- {c['for']}: {c['cable']}{flag}")
    lines.append(
        "\n> These are hardware recommendations, not protocol values. Confirm current\n"
        "> models/part numbers and compatibility before purchase."
    )
    return "\n".join(lines)
