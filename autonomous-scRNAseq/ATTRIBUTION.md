# Attribution

## Method (CC-BY)

This skill automates the **FLASH-seq UMI protocol, Version 3**.

> Simone Picelli, Vincent Hahaut (2022). *FLASH-seq UMI protocol.* protocols.io.
> Institute of Molecular and Clinical Ophthalmology Basel (IOB).
> DOI: [10.17504/protocols.io.bp2l619rdvqe/v3](https://dx.doi.org/10.17504/protocols.io.bp2l619rdvqe/v3)

The protocol is distributed under the **Creative Commons Attribution License
(CC-BY)**, which permits unrestricted use, distribution, and reproduction in any
medium, provided the original author and source are credited.

All reagents, volumes, temperatures, times, cycle counts, bead ratios, QC
thresholds, and analysis commands reproduced in `config/*.yaml`,
`flashseq/`, and the generated artifacts are taken from this protocol and are used
under CC-BY with the attribution above. Each value is annotated in the YAML with the
protocol stage it came from (`# src: Stage N`).

## Code (MIT)

The flashseq-skill code (generators, PyLabRobot automation, CLIs, tests) is original
work licensed under the MIT License - see `LICENSE`.

## Data-integrity note

This repository was assembled partly from an OCR pass over the protocol PDF.
Catalog numbers and oligo sequences that OCR left ambiguous are marked `verify: true`
in `config/reagents.yaml`, and any value not present in the protocol is marked
`# TODO: expert value`. **Verify all per-well volumes and catalog numbers against the
DOI before a real run.**

## Third-party tools

- **PyLabRobot** - hardware abstraction + simulator (see its own license).
- Analysis pipeline (Stage 4) invokes external tools not bundled here: bcl2fastq
  (Illumina), umi_tools, STAR, samtools, featureCounts (subread), bbmap.
