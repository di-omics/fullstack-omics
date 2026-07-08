# Automation

Drives the single-cell WGS flow through PyLabRobot. Runs in the **simulator** with no
hardware; the same code targets real hardware by swapping backends.

## Deck (`automation/deck.py`)

Hamilton **STARlet** deck (8-channel), 96-well:
- Rail 1: tip carrier - two 50 uL tip racks.
- Rail 8: plate carrier - working plate, reagent-source plate, cleanup plate.
- **Hamilton ODTC** (on-deck thermocycler, heated lid) - the arm moves the working plate in/out.
- **BioTek Synergy H1** + a black plate - dsDNA (Qubit-chemistry) quant.

Reagent-source columns (master mixes, dispensed by the 8-channel head):
`cell_buffer(1) lysis(2) reaction(3) elution(4) end_prep(5) adapter(6) ligation(7) pcr(8)
beads(9) EtOH(10) TE(11) water(12)`.

## Backends (`automation/backends.py`)

- `mode="sim"` - `LiquidHandlerChatterboxBackend`, `ThermocyclerChatterboxBackend`, and a
  `QubitSimBackend` (dsDNA standard-curve signal model). Logs every action; runs anywhere.
- `mode="hardware"` - resolves `STARBackend` / ODTC backend / `SynergyH1Backend` from
  `instruments.yaml`, and **refuses** while any value is a TODO/verify placeholder.

**Verified against pylabrobot 0.2.x:** STARLetDeck, STARBackend, Thermocycler +
ThermocyclerChatterboxBackend, PlateReader + SynergyH1Backend + PlateReaderChatterboxBackend.
**No ODTC backend exists yet** - wire one (Inheco TCP/SiLA) before `mode="hardware"`.

## Flow + thermal programs (`automation/workflow.py`)

Readiness (Stage 0) -> FACS sort (Stage 0b) -> WGA (Lysis/Reaction dispense -> ODTC 30 C 2.5 h)
-> post-WGA dsDNA quant on the H1 (standard curve -> yields) -> NEBNext End Prep / Ligation /
size-select / PCR / cleanup (each thermal step on the ODTC) -> library quant -> pool.

Thermal programs are built from `protocol_params.yaml` via `_program_to_protocol()` into a
PLR `Protocol(stages=[Stage(steps=[Step(...)])])`. Times are **not slept** in sim (the
chatterbox logs the profile); on hardware the backend enforces them.

**Sim tip note:** multi-channel transfers reuse one tip column so any N runs without
exhausting tips. **On hardware, use fresh tips per reagent addition** (no cross-contamination).

## dsDNA quant in sim (`automation/qubit.py`)

The chatterbox reader returns zeros, so `QubitSimBackend` seeds a ground-truth ng/uL per
well (cells + positive controls amplify ~20 ng/uL -> ~800 ng in the 40 uL dilution; NTC +
missed wells ~0), lays a standard series in a column, and returns RFU = blank + slope.conc.
The workflow fits the curve and back-calculates yields - so `gate_wga_yield`, `gate_ntc`,
and `gate_library_yield` are meaningful. On hardware, `SynergyH1Backend` replaces it and the
same math runs on measured RFU.

## Seams to wire (hardware)

- **FACS Melody** (`sorting/facs.py` -> `FacsMelodyHardwareBackend.sort()`): drop in the RE'd
  BD control client. Until then, sorting is simulated.
- **Humanoid ops** (`ops/operator.py` -> `HumanoidOperator.dispatch()`): send the structured
  manipulation commands to a real humanoid SDK. Until then, actions are logged only.
- **ODTC** backend: see above.
