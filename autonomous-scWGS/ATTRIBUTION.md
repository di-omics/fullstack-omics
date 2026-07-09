# Attribution

This skill automates two third-party laboratory kits and a cell sorter. Unlike the
sibling `flashseq-skill` (whose method is CC-BY), **these methods are proprietary
vendor protocols released for RESEARCH USE ONLY. They are not open-licensed.**

## Methods (proprietary -- RESEARCH USE ONLY)

### [A] Whole Genome Amplification -- ResolveDNA (PTA)
> BioSkryb Genomics. *ResolveDNA Whole Genome Single-Cell Core Kit, 96-Well Format --
> Protocol to Prepare WGS-Ready Libraries.* User Guide **TAS-068.5** (05/2025).

ResolveDNA(R) and BaseJumper(R) are registered trademarks of BioSkryb, Inc. PTA (Primary
Template-directed Amplification) is BioSkryb's proprietary chemistry (PNAS 2021, 118(24)
e2024176118).

### [B] Library preparation -- NEBNext Ultra II
> New England Biolabs. *NEBNext Ultra II DNA Library Prep Kit for Illumina*
> (NEB **#E7645/#E7103**). Instruction Manual **v2.0 (5/23)**.

NEBNext(R) is a registered trademark of New England Biolabs, Inc.

### [C] Sequencing analysis -- BaseJumper BJ-WGS
> BioSkryb Genomics. *BJ-WGS* Nextflow pipeline. `https://github.com/BioSkryb/bj-wgs`
> (release 2.1.0). **BioSkryb proprietary LICENSE** (Terms & Conditions), NOT open source.

BJ-WGS is **included as a git submodule** at `autonomous-scWGS/bj-wgs`, pinned to release
2.1.0 (see `.gitmodules`). A submodule stores only a **pointer** to BioSkryb's public repo
at that commit -- this repository does **not** copy or redistribute BioSkryb's code, and no
BJ-WGS files are committed here. Fetching it (`git submodule update --init --recursive`)
downloads it from BioSkryb directly, subject to **BioSkryb's own license/terms**. Running it
additionally requires a **Sentieon** license (commercial; eval/pass-through via a BioSkryb
helpdesk ticket). The `result/` stage generates the `input.csv` + `run_bj_wgs.sh` that drive
this included pipeline.

### Sort -- BD FACS Melody
> BD Biosciences. BD FACS Melody cell sorter (driven by BD FACSChorus).

BD FACSChorus has no open API, so the Melody control plane is reverse-engineered with
**computer vision + UI automation** of FACSChorus (di-omics CV stack: `lab-cv`,
`awesome-wetlab-cv`). Until that client is wired into `FacsMelodyHardwareBackend`, sorting
is **simulated** in this skill. See the README "Integration roadmap".

## What this repo does and does NOT do

- **Records** reagent names, volumes, temperatures, times, cycle counts, and bead ratios
  in `config/*.yaml`, each annotated with its source (`# src: [A] Table N` / `# src: [B]
  Section N`), so an automated workflow can reproduce the protocol. Values not present in
  a guide are marked `# TODO: expert value` -- **never invented**.
- **Does NOT** redistribute the vendor user guides, and grants no rights to them. Obtain
  the guides from BioSkryb / NEB directly. **Verify every value against the source guide
  before a real run.**

## Code (MIT)

The autonomous-scWGS code (generators, PyLabRobot automation, sort/ops/readiness
modules, CLIs, tests) is original work licensed under the MIT License -- see `LICENSE`.

## Third-party tools

- **PyLabRobot** -- hardware abstraction + simulator (see its own license).
- **Sequencing analysis** uses **BaseJumper BJ-WGS** (BioSkryb, `github.com/BioSkryb/bj-wgs`;
  see that repo's own LICENSE) [C]. It is a Nextflow pipeline requiring external, unbundled
  tools: Java, Nextflow, Docker, AWS CLI, and **Sentieon** (commercial; eval/pass-through
  license via a BioSkryb helpdesk ticket), plus SnpEff, VCFeval, BCFtools, Seqtk. This skill
  only generates the `input.csv` and the `nextflow run` command; it does not redistribute or
  modify BJ-WGS.

## Disclaimer

**RESEARCH USE ONLY -- not clinically validated.** This skill is not affiliated with or
endorsed by BioSkryb Genomics, New England Biolabs, BD Biosciences, or Hamilton.
