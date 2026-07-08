"""Build the Hamilton STARlet deck (8-channel) plus the on-deck thermocycler and
Synergy H1 plate reader as PLR machines.

Layout is deliberately simple and 96-well (the Hamilton-friendly 5x-volume default):
  - tip carrier with two 50 uL tip racks
  - a plate carrier holding: working plate, reagent-source plate, cleanup plate
  - a black plate for the PicoGreen read, assigned to the plate reader

Reagents live as full columns in a reagent-source plate so the 8-channel head can
aspirate a whole column of one reagent at a time.
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

# Reagent name -> 1-indexed source column in the reagent-source plate.
REAGENT_COLUMN = {
    "lysis_mix": 1,
    "rt_pcr_mix": 2,
    "water": 3,
    "beads": 4,
    "tagmentation_mix": 5,
    "sds": 6,
    "index_adaptors": 7,
    "npm": 8,
    "ethanol": 9,
    "picogreen_reagent": 10,
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

    # On-deck thermocycler (holds the working plate during thermal steps -- modelled
    # here as a standalone machine; the arm moves the plate in/out).
    tc = Thermocycler(
        name="on_deck_thermocycler",
        size_x=140, size_y=90, size_z=50,
        backend=bundle.tc_backend,
        child_location=Coordinate(0, 0, 0),
    )
    await tc.setup()

    # Synergy H1 plate reader with a black PicoGreen plate assigned into it.
    pr = PlateReader(
        name="synergy_h1",
        size_x=140, size_y=90, size_z=60,
        backend=bundle.pr_backend,
    )
    await pr.setup()
    black = Microplate_96_Well(name="picogreen_black_plate")
    pr.assign_child_resource(black)

    return DeckLayout(
        lh=lh, deck=deck, tip_racks=[tips_a, tips_b],
        working_plate=working, reagent_plate=reagents, cleanup_plate=cleanup,
        black_plate=black, thermocycler=tc, plate_reader=pr,
    )
