# Procurement

Kit-based, so procurement is mostly "buy the kit." The BOM scales to N samples and routes
each item to a channel; everything lands in ONE approval document.

## Scaling (`procurement/bom.py`)

- `per_kit` -> `ceil(n / 96)` kits (one kit = 96 reactions): single-cell WGA kit, NEBNext
  Ultra II kit, NEBNext UMI adaptor oligos.
- `per_plate` -> one unit per plate: QC tapes, plate seals, plates.
- `per_sample` / `per_run` / `once` -> per cell / bulk / one-time (magnet, etc.).

## Channels (`procurement/channels.py`)

- **browser** - the browser agent fills carts on vendor storefronts (NEB, Thermo Fisher,
  Agilent, Beckman, Eppendorf, Illumina, VWR, Sigma/Millipore).
- **vendor_direct** - specialty suppliers without a public cart and **BD Biosciences**
  (quote). Emit a pre-filled order request.
- **po** - General Lab Supplier + institutional punch-out (Coupa / Jaggaer) fallback.
- **verify** - unresolved supplier, SKU, channel, or verification state. These entries
  are not orderable.

## Approval + ordering (safety)

`approval_summary_markdown()` assembles ONE human-facing document (`output/purchase_approval.md`).
**Nothing is ordered without a single human `APPROVE`.** Approval alone cannot bypass
unresolved data: `place_orders(items, approved=True)` refuses the entire batch when any
entry remains in `verify`, has `verify: true`, or has a blank/placeholder supplier or
SKU. After local configuration is complete it is still a **dry run** - it records what
*would* be ordered per channel; wiring the live
browser-cart / specialty-supplier or BD direct / Coupa-Jaggaer PO flows are external deps
(marked TODO).

## Verify-before-ordering

Items whose supplier, catalog number, or channel is not publicly configured carry
`verify: true` + a neutral note and appear in a dedicated non-orderable section. The WGA
kit and all four WGA accessory lines remain there until the ignored
`config/reagents.local.yaml` supplies complete orderable entries. The merge contract and
example schema are in [source_map.md](source_map.md). Other guide omissions such as the
NEBNext UMI adaptor set, HS D1000 tape, and general consumables also fail closed.

## First-time-buyer controller kit (`procurement/controller_kit.py`)

With `--first-time-buyer`, add a Raspberry Pi controller kit (Pi 5, PSU, microSD w/ PLR
image, cooling, powered USB hub) + networking, and the **exact per-instrument cables** from
the connectivity resolver. Unverified ports propagate as `# TODO: verify interface` - note
the **ODTC is typically ethernet** (a switch is likely needed) and the **FACS Melody is
workstation-driven**, not Pi-driven.

## Scheduling

Lead times are not in the protocols - fill from vendor quotes. The kits usually set the
critical path; schedule the run at `max(lead_time) + buffer` after orders are placed.
