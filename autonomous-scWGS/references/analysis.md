# Sequencing analysis (WGS analysis WGS analysis)

The fastq-to-variants analysis is **WGS analysis WGS analysis**, the vendor Nextflow pipeline for
whole-genome sequencing / whole-genome amplification data (`github.com/the vendor/bj-wgs`, release 2.1.0). All values below are
from the WGS analysis README (src: [C]). RESEARCH USE ONLY. Author: di.

## What `autoscwgs/result/` generates

- `input.csv` - one row per sorted single-cell library: `biosampleName,read1,read2`
  (Illumina). The sample wells come straight from the FACS sort plan, so the analysis input
  lines up with what was actually sorted/prepped.
- `run_bj_wgs.sh` - preflights Java / Nextflow / Docker / AWS CLI + the Sentieon license,
  clones `bj-wgs`, and runs the exact command:
  ```
  nextflow run main.nf --input_csv input.csv --publish_dir results/bj-wgs \
    --genome GRCh38 --platform Illumina --dnascope_model_selection bioskryb129 \
    --min_reads 1000 --max_cpus 8 --max_memory 50.GB
  ```

## Pipeline steps (tools)

1. Map reads - **Sentieon BWA MEM**
2. Remove duplicates - **Sentieon LocusCollector + Dedup**
3. Base quality score recalibration - **Sentieon BQSR**
4. Variant calling - **DNAScope** (default) or **Haplotyper**. For whole-genome amplification data on Illumina,
   use the whole-genome amplification-corrected DNAScope model `bioskryb129` (`--dnascope_model_selection`).
5. Variant annotation - **SnpEff + ClinVar + dbSNP**
6. Metrics - **Sentieon** (alignment, GC bias, insert size, coverage)
7. Analytical performance - **VCFeval** (GIAB HG001-HG007 only; `--skip_vcfeval` default true)
8. Aggregate - **MultiQC**

## Parameters (defaults)

- `--genome`: GRCh38 (default) or GRCm39.
- `--platform`: Illumina (default), Ultima, Element. Ultima uses a 4-column input
  (`biosampleName,reads,cram,crai`).
- `--min_reads`: 1000 (samples below are flagged).
- Resources: typical 8 CPU / 50 GB; large 64 CPU / 120 GB.
- Optional modules: `skip_vcfeval=true`, `skip_variant_annotation=false`,
  `skip_gene_coverage=false`, `skip_ado=true`, `skip_subsampling=true`, `skip_sigprofile=false`.

## Depth targets (src: [A] Appendix C)

- Low-pass QC: 50 bp PE, 2-5 M reads/cell (CNV; BJ-DNA-QC-style triage).
- Deep: 25-30x coverage (SNV / structural variants).

## External dependencies (not bundled)

Java (JDK), Nextflow, Docker, AWS CLI, and a **Sentieon** license (commercial; eval or
pass-through via a the vendor helpdesk ticket, saved at `bj-wgs/sentieon_eval.lic`). Tool
versions pinned by WGS analysis: Seqtk 1.3-r106, Sentieon 202308.01, SnpEff 5.1d, VCFeval 3.12.1,
BCFtools 1.14.
