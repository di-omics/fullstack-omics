"""Result stage: generate WGS inputs and a method-agnostic adapter runner."""

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
