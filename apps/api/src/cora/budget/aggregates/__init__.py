"""Aggregate kernels owned by the budget BC.

Budget is a single-aggregate BC today (Allocation). The `aggregates`
sub-package exists so other BCs can target the aggregate kernel
specifically via `cora.budget.aggregates` in `tach.toml`, while
`cora.budget.features` stays implicitly off-limits to sibling BCs
per the cross-BC dependency contract.

This module is intentionally empty of re-exports: each aggregate
exposes its own surface via `cora.budget.aggregates.<aggregate>`.
"""
