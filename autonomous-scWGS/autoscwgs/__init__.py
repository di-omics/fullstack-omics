"""autonomous-scWGS -- autonomous single-cell genomics on a Hamilton/PyLabRobot deck.

First implemented protocol: single-cell whole-genome sequencing (WGS) via whole-genome
amplification (WGA) + NEBNext Ultra II library prep (NEB), with a BD FACS
Melody sort up front. Wet-lab stages run in the PyLabRobot simulator with no hardware;
the result stage generates a handoff for an external analysis pipeline.

(Repo name reflects the umbrella series "autonomous single-cell genomics"; this first
protocol is DNA/WGS, not RNA -- see README.)
"""

__version__ = "0.1.0"
