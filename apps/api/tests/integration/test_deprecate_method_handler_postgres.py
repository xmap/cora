"""End-to-end integration test: deprecate_method against real Postgres.

Round-trip: define + version + deprecate + load_method returns the
deprecated state with version preserved.
"""

from datetime import UTC, datetime
from uuid import UUID

import asyncpg
import pytest

from cora.recipe.aggregates.method import ExecutionPattern, MethodStatus, load_method
from cora.recipe.features import define_method, deprecate_method, version_method
from cora.recipe.features.define_method import DefineMethod
from cora.recipe.features.deprecate_method import DeprecateMethod
from cora.recipe.features.version_method import VersionMethod
from tests.integration._helpers import build_postgres_deps, seed_capability_postgres

_NOW = datetime(2026, 5, 10, 12, 0, 0, tzinfo=UTC)
_PRINCIPAL_ID = UUID("01900000-0000-7000-8000-000000000099")
_CORRELATION_ID = UUID("01900000-0000-7000-8000-0000000000aa")
_CAPABILITY_ID = UUID("01900000-0000-7000-8000-00000058fb0c")


@pytest.mark.integration
async def test_deprecate_method_persists_and_preserves_version_through_fold(
    db_pool: asyncpg.Pool,
) -> None:
    method_id = UUID("01900000-0000-7000-8000-00000058fb01")
    defined_event_id = UUID("01900000-0000-7000-8000-00000058fb0e")
    versioned_event_id = UUID("01900000-0000-7000-8000-00000058fb0f")
    deprecated_event_id = UUID("01900000-0000-7000-8000-00000058fb10")

    deps = build_postgres_deps(
        db_pool,
        now=_NOW,
        ids=[method_id, defined_event_id, versioned_event_id, deprecated_event_id],
    )
    await seed_capability_postgres(deps.event_store, _CAPABILITY_ID)

    await define_method.bind(deps)(
        DefineMethod(
            execution_pattern=ExecutionPattern.BATCH,
            name="XRF Fly Mapping",
            capability_id=_CAPABILITY_ID,
        ),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )
    await version_method.bind(deps)(
        VersionMethod(method_id=method_id, version_tag="2026-Q2"),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )
    await deprecate_method.bind(deps)(
        DeprecateMethod(method_id=method_id),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )

    events, version = await deps.event_store.load("Method", method_id)
    assert version == 3
    assert [e.event_type for e in events] == [
        "MethodDefined",
        "MethodVersioned",
        "MethodDeprecated",
    ]
    deprecated = events[2]
    assert deprecated.event_id == deprecated_event_id

    state = await load_method(deps.event_store, method_id)
    assert state is not None
    assert state.status is MethodStatus.DEPRECATED
    # Audit signal: latest version_tag preserved through deprecation.
    assert state.version == "2026-Q2"
