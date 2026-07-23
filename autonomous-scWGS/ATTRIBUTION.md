# Attribution and third-party methods

This module automates third-party laboratory methods and integrates an external analysis
pipeline. The laboratory methods are proprietary, research-use-only supplier protocols;
they are not open-licensed.

## Methods

### [A] Single-cell whole-genome amplification

The WGA stages, reagent handling, quality-control checkpoints, and sequencing-depth
guidance are based on authorized supplier documentation for a proprietary 96-well
single-cell WGA workflow. Obtain the current protocol from the authorized supplier and
verify every value before a real run.

### [B] Library preparation -- NEBNext Ultra II

> New England Biolabs. *NEBNext Ultra II DNA Library Prep Kit for Illumina*
> (NEB **#E7645/#E7103**). Instruction Manual **v2.0 (5/23)**.

NEBNext(R) is a registered trademark of New England Biolabs, Inc.

### [C] Sequencing analysis

The result stage emits `input.csv` and `run_wgs_analysis.sh` for a compatible external WGS
Nextflow pipeline supplied through `WGS_PIPELINE_DIR`. The pipeline is not bundled or
fetched by this repository and remains subject to its own license and terms. Running the
generated workflow also requires separately installed tools and a valid Sentieon license.
Public code identifies this contract as `WGS-ANALYSIS-INTERFACE-C` version `C-1.0`; the
private source-record interface is documented in [references/source_map.md](references/source_map.md).

### Sort -- BD FACS Melody

> BD Biosciences. BD FACS Melody cell sorter (driven by BD FACSChorus).

BD FACSChorus has no open API, so the Melody control plane is reverse-engineered with
computer vision and UI automation. Until that client is wired into
`FacsMelodyHardwareBackend`, sorting is simulated in this module.

## What this repository does

- Records reagent roles, volumes, temperatures, times, cycle counts, and bead ratios in
  `config/*.yaml`, annotated with `# src: [A]` or `# src: [B]`.
- Marks values absent from authorized documentation as `# TODO: expert value`.
- Does not redistribute supplier manuals or grant rights to third-party methods, software,
  trademarks, or documentation.
- Requires users to verify all protocol values against authorized source documentation
  before a real run.
- Uses neutral source IDs and an ignored local source map for private supplier, document,
  and license records; see [references/source_map.md](references/source_map.md).

## Code license

The autonomous-scWGS generators, PyLabRobot automation, sorting, operations, readiness
modules, command-line scripts, and tests are original code licensed under the MIT License.
That license does not apply to third-party laboratory methods, pipeline software, manuals,
or other supplier materials.

## Third-party tools

- **PyLabRobot** -- hardware abstraction and simulator; see its own license.
- **WGS analysis pipeline** -- compatible external Nextflow software supplied by the user
  and governed by its own license.
- **Analysis dependencies** -- Java, Nextflow, Docker, AWS CLI, Sentieon, SnpEff, VCFeval,
  BCFtools, Seqtk, and MultiQC; each remains separately licensed.

## Disclaimer

**RESEARCH USE ONLY -- not clinically validated.** This module is not affiliated with or
endorsed by New England Biolabs, BD Biosciences, Hamilton, or any WGA protocol supplier.
