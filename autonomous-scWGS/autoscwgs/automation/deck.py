"""Build the Hamilton STAR deck (8-channel) plus the Hamilton ODTC (on-deck
thermocycler) and BioTek Synergy H1 plate reader as PLR machines.

Layout (96-well, single plate):
  - tip carrier with two 50 uL tip racks
  - a plate carrier holding: working plate, reagent-source plate, cleanup plate
  - a black plate for the dsDNA (Qubit-on-H1) read, assigned to the plate reader

Reagents live as full columns in a reagent-source plate so the 8-channel head can
aspirate a whole column of one reagent/master-mix at a time.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from pylabrobot.liquid_handling import LiquidHandler
from pylabrobot.resources import (
    PLT_CAR_L5AC_A00,
    TIP_CAR_480_A00,
    Cor_96_wellplate_360ul_Fb,
    Microplate_96_Well,
    hamilton_96_tiprack_50uL,
)
from pylabrobot.resources.coordinate import Coordinate
from pylabrobot.thermocycling import Thermocycler
from pylabrobot.plate_reading import PlateReader

from .backends import BackendBundle

# Reagent / master-mix name -> 1-indexed source column in the reagent-source plate.
REAGENT_COLUMN = {
    "cell_buffer": 1,       # top-up to 3 uL for dry-sorted wells (src: [A] step 10)
    "lysis_mix": 2,         # WGA Lysis Mix
    "reaction_mix": 3,      # WGA Reaction Mix
    "elution_buffer": 4,    # dilute WGA product to 40 uL; general elutions
    "end_prep_mix": 5,      # NEBNext End Prep buffer + enzyme
    "adapter": 6,           # NEBNext UMI adaptor
    "ligation_mix": 7,      # NEBNext Ligation Master Mix + Ligation Enhancer
    "pcr_mix": 8,           # NEBNext Primer Mix + Q5 Master Mix
    "beads": 9,             # SPRI cleanup beads / WGA magnetic beads
    "ethanol": 10,          # 80% EtOH wash
    "te_0_1x": 11,          # 0.1X TE elution
    "water": 12,            # nuclease-free water / general
}


@dataclass
class DeckLayout:
    lh: LiquidHandler
    deck: Any
    tip_racks: list
    working_plate: Any
    reagent_plate: Any
    cleanup_plate: Any
    black_plate: Any
    thermocycler: Thermocycler
    plate_reader: PlateReader

    def reagent_column(self, name: str):
        """Return the 8 source wells (A..H) of the column holding `name`."""
        col = REAGENT_COLUMN[name]
        return self.reagent_plate[f"A{col}:H{col}"]


async def build_deck(bundle: BackendBundle) -> DeckLayout:
    deck = bundle.deck
    lh = LiquidHandler(backend=bundle.lh_backend, deck=deck)
    await lh.setup()

    tip_car = TIP_CAR_480_A00(name="tip_carrier")
    tip_car[0] = tips_a = hamilton_96_tiprack_50uL(name="tips_50ul_A")
    tip_car[1] = tips_b = hamilton_96_tiprack_50uL(name="tips_50ul_B")
    deck.assign_child_resource(tip_car, rails=1)

    plt_car = PLT_CAR_L5AC_A00(name="plate_carrier")
    plt_car[0] = working = Cor_96_wellplate_360ul_Fb(name="working_plate")
    plt_car[1] = reagents = Cor_96_wellplate_360ul_Fb(name="reagent_source_plate")
    plt_car[2] = cleanup = Cor_96_wellplate_360ul_Fb(name="cleanup_plate")
    deck.assign_child_resource(plt_car, rails=8)

    # Hamilton ODTC (on-deck thermocycler; heated lid) -- holds the working plate during
    # thermal steps. Modelled as a standalone machine; the arm moves the plate in/out.
    tc = Thermocycler(
        name="hamilton_odtc",
        size_x=140, size_y=90, size_z=50,
        backend=bundle.tc_backend,
        child_location=Coordinate(0, 0, 0),
    )
    await tc.setup()

    # Synergy H1 plate reader with a black dsDNA-quant plate assigned into it.
    pr = PlateReader(
        name="synergy_h1",
        size_x=140, size_y=90, size_z=60,
        backend=bundle.pr_backend,
    )
    await pr.setup()
    black = Microplate_96_Well(name="dsdna_black_plate")
    pr.assign_child_resource(black)

    return DeckLayout(
        lh=lh, deck=deck, tip_racks=[tips_a, tips_b],
        working_plate=working, reagent_plate=reagents, cleanup_plate=cleanup,
        black_plate=black, thermocycler=tc, plate_reader=pr,
    )
