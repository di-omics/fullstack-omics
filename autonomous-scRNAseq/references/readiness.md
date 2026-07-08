# Instrument readiness - Step 1 (Rhodamine B liquid-handling QC)

**Required before any real run.** Proves the liquid handler pipettes precisely at the
volumes the protocol actually uses, before you spend irreplaceable cells.

## Method

Dispense a Rhodamine B working solution at **low / medium / high** target volumes into
replicate wells across a 96-well black plate, top up to a constant final volume, read
fluorescence on the **Synergy H1**, and compute the **per-well CV** for each range.

- Low CV → **READY**.
- CV above the range's threshold → **NEEDS_CALIBRATION** (calibrate before running:
  check tips, teach points, aspirate/dispense speeds, channel health).

Precision (CV) is the gate; mean/SD are reported alongside. `run_flashseq` runs this
first and **fails closed** (`InstrumentNotReady`) unless `readiness="skip"`.

## Config (`config/readiness.yaml`, all `# expert-tunable`)

- **Rhodamine B**: ~10 µM (~4.8 µg/mL); tune conc + H1 gain so the highest-volume
  wells read high-but-not-saturated. Rhodamine B is NOT in the protocol - added by
  this skill; the reagent is in the BOM with a `verify` flag.
- **Synergy H1 read**: ex 540 / em 625 nm (Rhodamine B peaks ~553/627; match your
  filter set), gain `extended`/auto, top optics, read height 7 mm.
- **Volume ranges** (bracket the 96-well 5× protocol volumes):
  | Range | Target | Columns | CV threshold | Represents |
  |---|---|---|---|---|
  | low | 1.0 µL | 1-4 | ≤ 10% | small reagent adds (index, SDS, oligos) |
  | medium | 5.0 µL | 5-8 | ≤ 5% | lysis-mix dispense (Stage 1) |
  | high | 20.0 µL | 9-12 | ≤ 3% | RT-PCR-mix dispense (Stage 4) |

  CV thresholds are acceptance criteria - set them to your lab's validated spec.

## Sim vs hardware

- **sim**: `RhodamineSimBackend` injects a modelled true pipetting CV per range
  (`simulation.true_cv_pct`); `handler_state: needs_calibration` multiplies it to
  demo the fail path. Liquid-handling ops are real PLR chatterbox actions.
- **hardware**: swap in `SynergyH1Backend`; the same CV math runs on measured RFU.

## Run it

```bash
python scripts/run_readiness.py                      # calibrated handler -> READY
python scripts/run_readiness.py --state needs_calibration   # -> NEEDS_CALIBRATION (exit 2)
```

## Onboarding: humanoid ops (experimental)

`flashseq/ops/` lets a **humanoid robot** be the ops person that sets up the deck and
presses run - `HumanoidOperator` compiles each bench task into structured
manipulation commands (pick/place, press_button, apply_seal…). It's a scaffold: it
logs the command protocol; `dispatch()` is where a real robot client would plug in.
Default is `HumanOperator` (prints bench instructions for a person).
