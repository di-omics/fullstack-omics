"""Stage 3 -- Automation: the FLASH-seq flow on a Hamilton STAR + on-deck
thermocycler + BioTek Synergy H1, driven through PyLabRobot.

Default target is the 96-well, 5x-volume version (Hamilton-friendly). The
384-well nL version requires a nanodispenser and is flagged as such.

Backends are swappable: `mode="sim"` runs entirely in the PLR simulator with no
hardware; `mode="hardware"` reads the real backends from instruments.yaml.
"""

from .backends import BackendBundle, make_backends
from .workflow import run_flashseq, WorkflowResult

__all__ = ["BackendBundle", "make_backends", "run_flashseq", "WorkflowResult"]
