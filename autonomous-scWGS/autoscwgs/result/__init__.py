"""Result stage: generate the WGS analysis WGS analysis analysis (input.csv + nextflow runner)."""

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
