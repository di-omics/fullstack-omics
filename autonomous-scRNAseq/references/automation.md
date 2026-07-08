# Stage 3 - Automation (PyLabRobot)

## Devices & backends (swappable)

| Device | Sim backend (default) | Hardware backend (from `instruments.yaml`) |
|---|---|---|
| Hamilton STAR/STARlet | `LiquidHandlerChatterboxBackend` | `STARBackend` (deck `STARLetDeck`) |
| On-deck thermocycler | `ThermocyclerChatterboxBackend` | `ProflexBackend` / `OpentronsThermocyclerBackend` / `ATCBackend` (`# TODO: pick`) |
| BioTek Synergy H1 | `PicoGreenSimBackend` (wraps chatterbox) | `SynergyH1Backend` |

`make_backends(p, mode="sim"|"hardware")` builds the bundle. In `hardware` mode it
refuses to run while any backend/interface in `instruments.yaml` is a `# TODO`.

## Deck layout (96-well default)

- Rail 1: tip carrier, two 50 µL tip racks.
- Rail 8: plate carrier - working plate, reagent-source plate, cleanup plate.
- On-deck thermocycler (machine); Synergy H1 (machine) with a black PicoGreen plate.
- Reagent-source columns: lysis(1) RT-PCR(2) water(3) beads(4) tagmentation(5)
  SDS(6) index(7) NPM(8) ethanol(9) PicoGreen(10). The 8-channel head aspirates a
  full column of one reagent at a time.

## Flow (`workflow.py`)

lysis-mix → 72 °C 3 min → RT-PCR-mix → RT 50 °C 60 min + PCR (20-24 cyc) → SPRI 0.6x
→ PicoGreen on Synergy H1 → normalize to 100 pg/µL → tagmentation → 55 °C 8 min →
SDS + index + NPM → enrichment PCR (14 cyc) → SPRI 0.8x → quant → pool.

Thermal programs are built from `protocol_params.yaml` into PLR `Protocol/Stage/Step`
objects. Times are not slept in sim (the chatterbox logs the profile); on hardware
the backend enforces them.

## PicoGreen quant in sim (`picogreen.py`)

The chatterbox reader returns zeros, so `PicoGreenSimBackend` seeds a deterministic
ground-truth concentration per well, lays a standard series in the last column, and
returns RFU = blank + slope·conc + noise. The workflow fits the standard curve
(`StandardCurve.fit`) and back-calculates each well - exercising the real
quant → normalization → gate math. On hardware, drop in `SynergyH1Backend`; the same
math runs on measured RFU.

## QC gates + guards (`qc.py`)

- `guard_bead_ratio` - raises `GuardViolation` if 0.6x/0.8x drift.
- `guard_no_overdry` - enforces no-EtOH-wash + immediate resuspend (cDNA) and
  ≤~2 min dry (library).
- `guard_on_ice` / `guard_no_rechill` - record the temperature-handling rules.
- `gate_picogreen` / `gate_cdna_size` / `gate_library_size` - PASS / FLAG / FAIL
  against protocol thresholds.

## Sim simplification (documented in the run flags)

To keep any N runnable without exhausting tips, multi-channel transfers reuse one tip
column in sim. On hardware, use **fresh tips per reagent addition** (no
cross-contamination) and provision tip racks accordingly.
