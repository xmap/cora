"""Unit tests for `list_all_family_ids`.

Sibling to `list_family_ids` that differs ONLY in whether Deprecated
Families are filtered out. The discovery-side helper
(`list_family_ids`) keeps the `WHERE deprecated_at IS NULL` filter;
the cross-BC existence-check helper (`list_all_family_ids`, used by
`define_model` and `add_model_family`) drops it. Per the Model
aggregate's design memo, Family.deprecation is an authoring signal
NOT a runtime gate, so binding a Model to a Deprecated Family is
permitted; using the discovery filter for the existence check would
surface a misleading `FamilyNotFoundError` for a Family that
genuinely exists.

Database-backed differentiator (Deprecated-INCLUDED behavior) is
pinned in the integration suite via the deprecated-family flows
through `define_model` and `add_model_family`. This file pins the
pool-None short-circuit at unit tier.
"""

import pytest

from cora.equipment.aggregates.family import list_all_family_ids


@pytest.mark.unit
async def test_list_all_family_ids_returns_empty_for_none_pool() -> None:
    """No-database app_env contract: `pool=None` returns `[]` instead
    of raising. Mirrors `list_family_ids`; tests that need a populated
    lookup must wire a real pool."""
    assert await list_all_family_ids(None) == []
