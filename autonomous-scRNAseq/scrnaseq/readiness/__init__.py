"""Synthetic contract readiness for the public scRNA-seq simulator."""

from .simulation import CheckResult, ReadinessReport, run_readiness_check

__all__ = ["CheckResult", "ReadinessReport", "run_readiness_check"]
