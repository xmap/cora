"""End-to-end integration test: register_procedure_from_recipe against real Postgres.

Pinned: the slice's 2-event genesis block
(`ProcedureRegistered` + `RecipeExpansionRecorded`) lands in the
Procedure stream as a single atomic append; `RecipeExpansionRecorded`'s
canonical-JSON `bindings` payload reproduces `bindings_hash` via
`sha256(payload['bindings'])` even when the operator-supplied dict's
key order differs from sorted order; the `recipe_id` denorm round-trips
through jsonb on `ProcedureRegistered`; and the
`proj_operation_procedure_summary` projection populates the
`recipe_id` column so the partial index added by migration
`20260602124600_procedure_summary_add_recipe_id` can serve
audit-by-Recipe queries.
"""

# pyright: reportUnknownMemberType=false, reportUnknownVariableType=false, reportUnknownArgumentType=false

import hashlib
import json
from datetime import UTC, datetime
from uuid import UUID

import asyncpg
import pytest

from cora.infrastructure.event_envelope import to_new_event
from cora.infrastructure.projection import ProjectionRegistry, drain_projections
from cora.operation._projections import register_operation_projections
from cora.operation.adapters.in_memory_recipe_expander import (
    InMemoryRecipeExpander,
)
from cora.operation.features import register_procedure_from_recipe
from cora.operation.features.register_procedure_from_recipe import (
    RegisterProcedureFromRecipe,
)
from cora.recipe.aggregates.recipe import (
    RecipeDefined,
    RecipeSetpointStep,
    event_type_name,
    to_payload,
)
from tests.integration._helpers import build_postgres_deps, seed_capability_postgres

_NOW = datetime(2026, 6, 2, 12, 0, 0, tzinfo=UTC)
_PRINCIPAL_ID = UUID("01900000-0000-7000-8000-000000000099")
_CORRELATION_ID = UUID("01900000-0000-7000-8000-0000000000aa")


@pytest.mark.integration
async def test_register_procedure_from_recipe_persists_two_event_genesis_block(
    db_pool: asyncpg.Pool,
) -> None:
    procedure_id = UUID("01900000-0000-7000-8000-000005700001")
    event_a = UUID("01900000-0000-7000-8000-000005700002")
    event_b = UUID("01900000-0000-7000-8000-000005700003")
    recipe_id = UUID("01900000-0000-7000-8000-000005700004")
    capability_id = UUID("01900000-0000-7000-8000-000005700005")
    seed_event_id = UUID("01900000-0000-7000-8000-000005700006")

    deps = build_postgres_deps(db_pool, now=_NOW, ids=[procedure_id, event_a, event_b])
    await seed_capability_postgres(deps.event_store, capability_id)

    # Seed the Recipe.
    recipe_event = RecipeDefined(
        recipe_id=recipe_id,
        name="R",
        capability_id=capability_id,
        steps=(RecipeSetpointStep(address="dev:x", value=1.0),),
        occurred_at=_NOW,
    )
    await deps.event_store.append(
        stream_type="Recipe",
        stream_id=recipe_id,
        expected_version=0,
        events=[
            to_new_event(
                event_type=event_type_name(recipe_event),
                payload=to_payload(recipe_event),
                occurred_at=_NOW,
                event_id=seed_event_id,
                command_name="seed",
                correlation_id=_CORRELATION_ID,
                causation_id=None,
                principal_id=_PRINCIPAL_ID,
            )
        ],
    )

    # Multi-key bindings in deliberately non-sorted order so sort_keys
    # canonicalization is structurally exercised (a single-key dict
    # would pass either way).
    bindings = {"beta": 2.0, "alpha": 1.0}
    returned_id = await register_procedure_from_recipe.bind(
        deps, expansion_port=InMemoryRecipeExpander()
    )(
        RegisterProcedureFromRecipe(
            name="P",
            kind="bakeout",
            target_asset_ids=(),
            parent_run_id=None,
            recipe_id=recipe_id,
            bindings=bindings,
        ),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )
    assert returned_id == procedure_id

    events, version = await deps.event_store.load("Procedure", procedure_id)
    assert version == 2
    assert len(events) == 2

    registered, recorded = events
    assert registered.event_type == "ProcedureRegistered"
    assert registered.payload["procedure_id"] == str(procedure_id)
    assert registered.payload["recipe_id"] == str(recipe_id)
    assert registered.payload["capability_id"] == str(capability_id)

    assert recorded.event_type == "RecipeExpansionRecorded"
    assert recorded.payload["procedure_id"] == str(procedure_id)
    assert recorded.payload["recipe_id"] == str(recipe_id)
    assert recorded.payload["capability_id"] == str(capability_id)
    assert recorded.payload["bindings"] == bindings
    assert recorded.payload["step_count"] == 1
    # Canonical-JSON sort_keys + same hash function the decider uses.
    expected_hash = hashlib.sha256(
        json.dumps(bindings, sort_keys=True, separators=(",", ":")).encode("utf-8")
    ).hexdigest()
    assert recorded.payload["bindings_hash"] == expected_hash

    registry = ProjectionRegistry()
    register_operation_projections(registry)
    await drain_projections(db_pool, registry, deadline_seconds=2.0)
    async with db_pool.acquire() as conn:
        row = await conn.fetchrow(
            "SELECT recipe_id FROM proj_operation_procedure_summary WHERE procedure_id = $1",
            procedure_id,
        )
    assert row is not None
    assert row["recipe_id"] == recipe_id
