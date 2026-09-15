"""Autonomy-scope verdict and aggregation primitives."""

from .aggregate import aggregate_runs
from .verdict import assess_boundary, evaluate_scope

__all__ = ["evaluate_scope", "assess_boundary", "aggregate_runs"]
