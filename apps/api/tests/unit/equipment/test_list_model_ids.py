"""Unit tests for `list_model_ids`.

Discovery-side helper that reads every non-Deprecated Model id from
the `proj_equipment_model_summary` projection. Mirrors
`list_family_ids`: returns `[]` when `pool is None` so the
no-database app_env (and unit tests that do not wire a pool) do not
need a defensive None-check at every call site.

The Deprecated-excluded behavior and the canonical
`model_id::text`-ascending sort order are pinned in the integration
suite at `tests/integration/test_postgres_list_model_ids.py`.
"""

import pytest

from cora.equipment.aggregates.model import list_model_ids


@pytest.mark.unit
async def test_list_model_ids_returns_empty_list_when_pool_is_none() -> None:
    """No-database app_env contract: `pool=None` returns `[]` instead
    of raising. Mirrors `list_family_ids`; tests that need a populated
    lookup must wire a real pool."""
    assert await list_model_ids(None) == []
