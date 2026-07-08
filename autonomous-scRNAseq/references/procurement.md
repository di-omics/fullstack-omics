# Stage 1 - Procurement

## Flow

```
build_bom(p)  ->  route_channels(items)  ->  approval_summary_markdown(...)  ->  [HUMAN APPROVE]  ->  place_orders(approved=True)  [DRY RUN in v1]
```

1. **BOM** (`bom.py`) scales `reagents.yaml` to N cells:
   - `by_volume` → total µL consumed = per-well volume (scaled to plate format) ×
     wells × (1 + overage). Shared reagents (RNase inhibitor, Betaine) sum across
     both mixes.
   - `per_plate` → one unit per plate; `per_sample` → one per cell; `per_run` → one
     bulk unit; custom oligos → one synthesis order.
2. **Channels** (`channels.py`) route each item:
   - `idt_api` - custom FLASH-seq oligos (and Quartzy where the lab routes oligos).
   - `browser` - vendor storefronts a browser-agent agent can drive (Thermo,
     Sigma/Millipore, Takara, NEB, Illumina, Invitrogen…).
   - `po` - institutional punch-out (Coupa/Jaggaer) for everything else.
3. **Approval** - one Markdown summary grouped by channel, with an
   OCR/verify callout and a scheduling section. **Nothing is ordered without it.**
4. **Order placement** - `place_orders(approved=True)` is a **dry run** in v1. Wiring
   the live IDT API, the browser cart flow, and the PO submission are external deps.

## First-time-buyer mode (`--first-time-buyer`)

If the user has no controller, `controller_kit.py` specs a Raspberry Pi bring-up kit
(Pi 4/5 + USB-C PSU + microSD w/ PLR image + active cooling + powered USB hub +
networking) and the **connectivity resolver** (`connectivity.py`) adds the exact
cables per instrument by reading `instruments.yaml`.

**Port types are never hardcoded.** The resolver reads verified connectors from the
registry; anything marked `# TODO: verify interface` propagates to a flagged cable
line and into the wiring diagram. PLR backend names (STARBackend, SynergyH1Backend,
ThermocyclerChatterboxBackend) are verified against the installed pylabrobot.

## Scheduling on lead times

Lead times aren't in the protocol. After ordering, fill them from vendor quotes; the
longest (usually custom oligos via IDT) sets the earliest automation-run date
(`max(lead_time) + buffer`).

## Safety

`place_orders(items, approved=False)` raises `PermissionError`. Present the approval
summary and only pass `approved=True` after the user replies `APPROVE`.
