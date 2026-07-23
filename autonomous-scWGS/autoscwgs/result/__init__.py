"""Result stage: generate WGS analysis inputs and a Nextflow runner."""

from .pipeline import (
    generate_pipeline,
    write_pipeline,
    generate_input_csv,
    build_input_rows,
)

__all__ = [
    "generate_pipeline",
    "write_pipeline",
    "generate_input_csv",
    "build_input_rows",
]
