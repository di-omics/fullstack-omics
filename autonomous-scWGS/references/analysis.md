# Sequencing analysis

Fastq-to-variants analysis uses a compatible external WGS Nextflow pipeline. The pipeline
checkout is supplied through `WGS_PIPELINE_DIR`; it is not bundled or fetched by this
repository and remains governed by its own license. The supported interface is source [C].
The simulator generates this handoff but does not execute the external pipeline. See
[source_map.md](source_map.md) for the `WGS-ANALYSIS-INTERFACE-C` versioned contract.
RESEARCH USE ONLY.

## What `autoscwgs/result/` generates

- `input.csv` -- one row per sorted single-cell library using
  `biosampleName,read1,read2` for Illumina data. Sample wells come from the sort plan, so
  analysis inputs correspond to the libraries that were prepared.
- `run_wgs_analysis.sh` -- resolves `input.csv` beside its own script by default, requires
  `WGS_PIPELINE_DIR`, `DNASCOPE_MODEL`, and `SENTIEON_LICENSE`, validates the checkout,
  input header, and license file, then preflights Java, Nextflow, Docker, and AWS CLI
  before running:

  ```bash
  nextflow run "$WGS_PIPELINE_DIR/main.nf" \
    --input_csv "$INPUT_CSV" --publish_dir "$PUBLISH_DIR" \
    --genome GRCh38 --platform Illumina --dnascope_model_selection "$DNASCOPE_MODEL" \
    --min_reads 1000 --max_cpus 8 --max_memory 50.GB
  ```

Use the external pipeline's own test suite to validate that checkout.

## Pipeline steps

1. Map reads -- Sentieon BWA MEM.
2. Remove duplicates -- Sentieon LocusCollector and Dedup.
3. Perform base-quality score recalibration -- Sentieon BQSR.
4. Call variants using the explicitly configured model selection.
5. Annotate variants -- SnpEff, ClinVar, and dbSNP.
6. Compute alignment, GC-bias, insert-size, and coverage metrics.
7. Optionally evaluate GIAB samples with VCFeval.
8. Aggregate results in MultiQC.

## Parameters

- `--genome`: GRCh38 by default; GRCm39 is also supported by the compatible interface.
- `--platform`: Illumina by default; Ultima and Element are supported. Ultima uses
  `biosampleName,reads,cram,crai`.
- `--dnascope_model_selection`: required explicitly through `DNASCOPE_MODEL`; there is no
  repository default or hidden mapping.
- `--min_reads`: 1000.
- Resources: typical 8 CPU / 50 GB; large 64 CPU / 120 GB.
- Optional modules: `skip_vcfeval=true`, `skip_variant_annotation=false`,
  `skip_gene_coverage=false`, `skip_ado=true`, `skip_subsampling=true`,
  `skip_sigprofile=false`.

## Depth targets (src: [A] Appendix C)

- Low-pass QC: 50 bp paired-end, 2-5 million reads per cell for CNV analysis.
- Deep sequencing: 25-30x coverage for SNV and structural-variant analysis.

## External dependencies

Java (JDK), Nextflow, Docker, AWS CLI, and a valid Sentieon license are required by the
compatible pipeline. Seqtk, Sentieon, SnpEff, VCFeval, BCFtools, and MultiQC remain
external and separately licensed. Missing required environment values, files, checkout
entrypoint, or host tools stop the runner with a nonzero exit before pipeline execution.
