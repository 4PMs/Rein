"""Verdict and aggregation primitives for Rein."""

from .aggregate import aggregate_recommended_scope, aggregate_runs
from .verdict import assess_boundary, evaluate_scope

__all__ = [
    "evaluate_scope",
    "assess_boundary",
    "aggregate_runs",
    "aggregate_recommended_scope",
]
