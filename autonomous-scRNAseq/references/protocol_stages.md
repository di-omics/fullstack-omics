# FLASH-seq UMI v3 - the 12 stages (with protocol values)

Source: DOI 10.17504/protocols.io.bp2l619rdvqe/v3 (CC-BY). All numbers live in
`config/protocol_params.yaml`; this is a human-readable index. Volumes shown are the
native **384-well** per-well volumes; the 96-well default multiplies them by **5**.

| # | Stage | Key values (384-well) | Notes |
|---|---|---|---|
| 1 | Lysis mix | 1.000 µL/well total | Triton 0.2%, dNTP 6 mM, STRT-P1-T31 1.8 µM, RNaseI 1.2 U/µL, DTT 1.2 mM, dCTP 9 mM, Betaine 1 M |
| 2 | Sort | 1 cell / well | seal foil, −80 °C, ≤6 months |
| 3 | Lysis | 72 °C 3 min → 4 °C | heated lid; keep cold after |
| 4 | RT-PCR | +4.000 µL mix | RT 50 °C 60 min → 98 °C 3 min → [98/65/72, 20s/20s/6min] × **20-24** → 15 °C. Kapa HiFi 1×, SSIV 2 U/µL, TSO-UMI 1.84 µM. Safe stop −20 °C |
| 5 | cDNA cleanup | SPRI **0.6x** | +10 µL water to 5 µL cDNA → +9 µL beads; 5+5 min; resuspend 15 µL; transfer 14 µL. **No over-dry.** Safe stop −20 °C |
| 6 | cDNA QC | 1.8-2.2 kb | Bioanalyzer HS; flag <400 bp; residual primer ~100 bp. Optional/external |
| 7 | cDNA quant | PicoGreen / Synergy H1 | black plate (or Qubit) |
| 8 | Normalize | **100 pg/µL**, 1 µL | wells below target can't be normalized up |
| 9 | Tagmentation + index PCR | ATM **0.1-0.2 µL** + TD 1 µL → 1.2 µL mix + 1 µL cDNA; 55 °C 8 min → 4 °C; +0.5 µL 0.2% SDS 5 min RT; +1 µL index (5 µM); +1.5 µL NPM; 72 °C 3 min → 95 °C 30s → [95/55/72] × **14** → 15 °C. Safe stop −20 °C |
| 10 | Library cleanup | SPRI **0.8x** | 80% EtOH wash (1 mL, 30 s); dry ~2 min until cracks; elute 50 µL, remove 49 µL. ~800 bp; Qubit |
| 11 | Pool + sequence | NextSeq550 100-8-8-50 | PE recommended, R1 ≥75 bp (pref ≥100). Alt 90-8-8-60 / 80-8-8-70 |
| 12 | Analysis | see `flashseq_pipeline.sh` | bcl2fastq → umi_tools extract (8 bp UMI, spacer CTAAC, regex) → STAR → samtools -F 260 → featureCounts (-t exon -g gene_name -s 1 --fracOverlap 0.25) → umi_tools count → Seurat/scanpy |

## Expert-tunable knobs (protocol default kept)

- **RT-PCR cycles** (Stage 4): 20-24. 20-21 for HEK293T, 23-24 for hPBMC. Rule of
  thumb: start at your SMART-seq2 cycle count. Default in YAML = 22.
- **ATM amount** (Stage 9): 0.1-0.2 µL for 100 pg/µL cDNA; optimize so libraries land
  700-1000 bp. Default in YAML = 0.15.

## Values NOT in the protocol (`# TODO: expert value`)

- PicoGreen excitation/emission wavelengths (kit-standard 480/520 assumed; verify).
- Full TSO-UMI sequence and the 48 i7 + 32 i5 extra-index sequences (OCR unreliable -
  copy from the DOI before ordering custom oligos).
- Library-cleanup aliquot volume (protocol says "an aliquot"; BOM assumes full rxn).
- Per-item vendor lead times (fill from quotes; they gate run scheduling).
