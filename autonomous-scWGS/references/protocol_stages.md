# Protocol stages (exact values)

Sources: **[A]** supplier-provided single-cell WGA protocol (proprietary, RUO).
**[B]** NEBNext Ultra II (NEB E7645). All values live in
`config/protocol_params.yaml` with `# src:` provenance. Verify against authorized source
documentation before running. RESEARCH USE ONLY.

## Stage 0b - FACS Melody sort  (src: [A])
- Single cell / nucleus per well into **3 uL Cell Buffer** (or dry, then add buffer).
- Column 1 = controls: A1/B1 NTC, C1/D1 1 ng, E1/F1 100 pg, G1/H1 10 pg gDNA (Figure 5).
- Control gDNA: 2 uL 50 ng/uL + 8 uL Cell Buffer -> 10 ng/uL; serial -> 1 ng/100 pg/10 pg /uL.

## Stage W1 - Single-cell whole-genome amplification (WGA)  (src: [A] Tables 1-3)
- **Lysis Mix** 3.0 uL/rxn (L1 1.68, L2 0.12, L3 1.20); 30% overage -> 375 uL/96. Add 3 uL/well;
  thermal-mix RT 20 min @ 1400 rpm.
- **Reaction Mix** 6.0 uL/rxn (R1 5.4, R2 0.6); 30% overage -> 750 uL/96. Add 6 uL/well (R1 then R2);
  thermal-mix RT 1 min @ 1000 rpm. **Do not vortex R2.**
- **DNA Amplification** (lid 70 C): 30 C **2.5 h** -> 65 C **3 min** -> 4 C hold.
- Safe stop: -20 C overnight.

## Stage W2 - Post-WGA QC  (src: [A])
- Dilute reaction to **40 uL** (Elution Buffer). Qubit dsDNA (2 uL + 198 uL reagent).
- Tapestation **HS D5000** at 2 ng/uL. Expect ~800 ng yield, avg ~1275 bp (250-3500 bp).

## Stage L - NEBNext Ultra II library prep  (src: [B])
- **Input:** WGA product to **50 uL** in 1x TE (100 ng default; NEB range 500 pg-1 ug - expert-tunable).
- **End Prep** (sec 1): +7 uL buffer +3 uL enzyme -> 60 uL; **20 C 30 min -> 65 C 30 min** (lid >= 75 C).
- **Adaptor Ligation** (sec 2): +2.5 uL UMI adaptor +30 uL Ligation MM +1 uL Enhancer -> 93.5 uL;
  **20 C 15 min** (lid off). Adaptor dilution by input (20/2/0.4 uM) - expert-tunable.
- **Size-select** (sec 3A): **0.4x** (40 uL) keep sup -> **0.2x** (20 uL) keep beads; 2x 80% EtOH;
  air-dry <= 5 min; elute 22 uL 0.1x TE -> transfer 20 uL.
- **PCR enrichment** (sec 4): +5 uL Primer +25 uL Q5 -> 50 uL; 98 C 30 s -> [98 C 10 s / 65 C 75 s]
  x **3** (expert-tunable, 3-15 by input) -> 65 C 5 min (lid >= 103 C).
- **PCR cleanup** (sec 5): **0.8x** (40 uL) beads; 2x 80% EtOH; elute 33 uL 0.1x TE -> transfer 30 uL.

## Library QC + pool  (src: [A] post-lib QC + [B] 5.12)
- Qubit HS dsDNA; Tapestation **HS D1000**. Final pool: **0.75x** SPRI (e.g. 100 uL + 75 uL beads).

## Sequencing  (src: [A] Appendix C)
- Illumina, UDI adapters. Low-pass: **50 bp PE, 2-5 M reads/cell** (CNV). Deep: **25-30x** (SNV).

## Analysis  (src: [C] compatible pipeline interface)
- External WGS Nextflow pipeline: Sentieon BWA MEM ->
  LocusCollector+Dedup -> BQSR -> explicitly configured variant model ->
  SnpEff/ClinVar/dbSNP -> Sentieon metrics -> VCFeval (GIAB only) -> MultiQC.
- Genomes GRCh38 (default) / GRCm39; platforms Illumina (default) / Ultima / Element;
  `--min_reads 1000`; typical 8 CPU / 50 GB, large 64 CPU / 120 GB.
- `result/` generates `input.csv` (biosampleName,read1,read2 per sorted well) +
  `run_wgs_analysis.sh`; `DNASCOPE_MODEL` is required at runtime with no repository default.
- External deps: Java, Nextflow, Docker, AWS CLI, and a valid **Sentieon** license.

## Expert-tunable / TODO (never invented)
- NEBNext **input ng**, **PCR cycles**, **adaptor dilution**, **insert size** - guide defaults kept.
- **Qubit-on-H1 ex/em** (485/530) - guides use a Qubit fluorometer; verify on your H1.
- WGA **whole-kit catalog #**, HS D1000 catalog #, GLS/sorter consumables - `# TODO`.
- Reference build (GRCh38) - confirm.
