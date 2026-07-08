"""Stage 4 -- Result: generate the analysis pipeline stub (protocol section 12).

bcl2fastq -> umi_tools extract (UMI in R1 & R2, CTAAC spacer, 8 bp UMI, regex) ->
separate internal/UMI reads -> STAR -> samtools -F 260 -> featureCounts ->
umi_tools count -> Seurat/scanpy handoff. All external-tool dependencies are marked.
"""

from .pipeline import generate_pipeline, write_pipeline
from .analysis import generate_scanpy_analysis, write_analysis

__all__ = [
    "generate_pipeline",
    "write_pipeline",
    "generate_scanpy_analysis",
    "write_analysis",
]
