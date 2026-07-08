# Procurement

Kit-based, so procurement is mostly "buy the kit." The BOM scales to N samples and routes
each item to a channel; everything lands in ONE approval document.

## Scaling (`procurement/bom.py`)

- `per_kit` -> `ceil(n / 96)` kits (one kit = 96 reactions): whole-genome sequencing core kit, NEBNext
  Ultra II kit, NEBNext UMI adaptor oligos.
- `per_plate` -> one unit per plate: QC tapes, plate seals, plates.
- `per_sample` / `per_run` / `once` -> per cell / bulk / one-time (magnet, etc.).

## Channels (`procurement/channels.py`)

- **browser** - the browser agent fills carts on vendor storefronts (NEB, Thermo Fisher,
  Agilent, Beckman, Eppendorf, Illumina, VWR, Sigma/Millipore).
- **vendor_direct** - vendors without a public cart: **the vendor** (sales@/orders@bioskryb.com)
  and **BD Biosciences** (quote). Emit a pre-filled order request.
- **po** - General Lab Supplier + institutional punch-out (Coupa / Jaggaer) fallback.

## Approval + ordering (safety)

`approval_summary_markdown()` assembles ONE human-facing document (`output/purchase_approval.md`).
**Nothing is ordered without a single human `APPROVE`.** `place_orders(items, approved=True)`
is a **dry run** - it records what *would* be ordered per channel; wiring the live
browser-cart / the vendor-BD direct / Coupa-Jaggaer PO flows are external deps (marked TODO).

## Verify-before-ordering

Items whose catalog # a vendor guide does not state carry `verify: true` + a note and appear
in a dedicated section - e.g. the **whole-genome sequencing whole-kit catalog #** (the guide lists
component part numbers but not a single orderable SKU), the **NEBNext UMI adaptor** oligo set
(depends on plex), the **HS D1000** tape, and GLS / FACS Melody consumables. These are
`# TODO: expert value` - never invented.

## First-time-buyer controller kit (`procurement/controller_kit.py`)

With `--first-time-buyer`, add a Raspberry Pi controller kit (Pi 5, PSU, microSD w/ PLR
image, cooling, powered USB hub) + networking, and the **exact per-instrument cables** from
the connectivity resolver. Unverified ports propagate as `# TODO: verify interface` - note
the **ODTC is typically ethernet** (a switch is likely needed) and the **FACS Melody is
workstation-driven**, not Pi-driven.

## Scheduling

Lead times are not in the protocols - fill from vendor quotes. The kits usually set the
critical path; schedule the run at `max(lead_time) + buffer` after orders are placed.
