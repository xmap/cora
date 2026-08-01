"""Integration tests for `PostgresCapabilityLookup` against a real Postgres.

Pins the affordance-containment + status filter under the real Recipe
Capability projection: seeds capabilities via `define_capability`,
drains the projection worker, then queries through the adapter and
verifies the result matches the seeded capabilities.

Mirrors `test_postgres_caution_lookup.py` for shape (per-call seed +
drain + assert), differing only in the filter semantics (text[] subset
containment instead of severity-thresholded target match).
"""

# pyright: reportUnknownMemberType=false, reportUnknownVariableType=false, reportUnknownArgumentType=false

from datetime import UTC, datetime
from uuid import UUID, uuid4

import asyncpg
import pytest

from cora.equipment.aggregates.family import Affordance
from cora.infrastructure.projection import ProjectionRegistry, drain_projections
from cora.recipe._projections import register_recipe_projections
from cora.recipe.adapters import PostgresCapabilityLookup
from cora.recipe.aggregates.capability import ExecutorShape
from cora.recipe.features import define_capability, deprecate_capability
from cora.recipe.features.define_capability import DefineCapability
from cora.recipe.features.deprecate_capability import DeprecateCapability
from cora.shared.deprecation import DeprecationReason
from tests.integration._helpers import build_postgres_deps

_NOW = datetime(2026, 6, 4, 12, 0, 0, tzinfo=UTC)
_LATER = datetime(2026, 6, 4, 14, 0, 0, tzinfo=UTC)
_PRINCIPAL_ID = UUID("01900000-0000-7000-8000-00000000c001")
_CORRELATION_ID = UUID("01900000-0000-7000-8000-00000000c002")


async def _drain(db_pool: asyncpg.Pool) -> None:
    registry = ProjectionRegistry()
    register_recipe_projections(registry)
    await drain_projections(db_pool, registry, deadline_seconds=2.0)


def _define_command(
    *,
    code: str,
    name: str,
    required_affordances: frozenset[Affordance],
    executor_shapes: frozenset[ExecutorShape] | None = None,
) -> DefineCapability:
    return DefineCapability(
        code=code,
        name=name,
        required_affordances=required_affordances,
        executor_shapes=executor_shapes or frozenset({ExecutorShape.METHOD}),
    )


@pytest.mark.integration
async def test_empty_projection_returns_empty_result(db_pool: asyncpg.Pool) -> None:
    """No capabilities seeded -> []."""
    lookup = PostgresCapabilityLookup(db_pool)
    result = await lookup.find_applicable_by_affordances(frozenset({Affordance.POSABLE.value}))
    assert result == []


@pytest.mark.integration
async def test_capability_with_zero_required_affordances_always_matches(
    db_pool: asyncpg.Pool,
) -> None:
    """A Capability requiring no affordances is covered by every Asset
    (empty set is a subset of every set, per the `<@` operator)."""
    cap_id = uuid4()
    deps = build_postgres_deps(db_pool, now=_NOW, ids=[cap_id, uuid4()])
    await define_capability.bind(deps)(
        _define_command(
            code="cora.capability.no_req",
            name="NoRequirements",
            required_affordances=frozenset(),
        ),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )
    await _drain(db_pool)

    lookup = PostgresCapabilityLookup(db_pool)
    # Empty affordance set still matches a zero-requirement capability.
    result_empty = await lookup.find_applicable_by_affordances(frozenset())
    cap_ids_empty = {r.capability_id for r in result_empty}
    assert cap_id in cap_ids_empty
    # Populated affordance set also matches.
    result_populated = await lookup.find_applicable_by_affordances(
        frozenset({Affordance.POSABLE.value})
    )
    cap_ids_populated = {r.capability_id for r in result_populated}
    assert cap_id in cap_ids_populated


@pytest.mark.integration
async def test_capability_filtered_when_required_affordance_missing(
    db_pool: asyncpg.Pool,
) -> None:
    """A Capability whose required_affordances are not a subset of the
    passed affordances is excluded."""
    cap_id = uuid4()
    deps = build_postgres_deps(db_pool, now=_NOW, ids=[cap_id, uuid4()])
    await define_capability.bind(deps)(
        _define_command(
            code="cora.capability.needs_two",
            name="NeedsTwo",
            required_affordances=frozenset({Affordance.POSABLE, Affordance.TRIGGERABLE}),
        ),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )
    await _drain(db_pool)

    lookup = PostgresCapabilityLookup(db_pool)
    # Only one of the two required affordances present -> excluded.
    result_partial = await lookup.find_applicable_by_affordances(
        frozenset({Affordance.POSABLE.value})
    )
    assert cap_id not in {r.capability_id for r in result_partial}
    # Both required affordances present -> included.
    result_full = await lookup.find_applicable_by_affordances(
        frozenset({Affordance.POSABLE.value, Affordance.TRIGGERABLE.value})
    )
    assert cap_id in {r.capability_id for r in result_full}


@pytest.mark.integration
async def test_deprecated_capability_never_returned(db_pool: asyncpg.Pool) -> None:
    """The status filter excludes Deprecated capabilities even when
    affordance containment passes."""
    cap_id = uuid4()
    deps_d = build_postgres_deps(db_pool, now=_NOW, ids=[cap_id, uuid4()])
    await define_capability.bind(deps_d)(
        _define_command(
            code="cora.capability.outdated",
            name="Outdated",
            required_affordances=frozenset({Affordance.POSABLE}),
        ),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )
    deps_dep = build_postgres_deps(db_pool, now=_LATER, ids=[uuid4()])
    await deprecate_capability.bind(deps_dep)(
        DeprecateCapability(reason=DeprecationReason.SUPERSEDED, capability_id=cap_id),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )
    await _drain(db_pool)

    lookup = PostgresCapabilityLookup(db_pool)
    result = await lookup.find_applicable_by_affordances(frozenset({Affordance.POSABLE.value}))
    assert cap_id not in {r.capability_id for r in result}


@pytest.mark.integration
async def test_result_is_sorted_by_code_ascending(db_pool: asyncpg.Pool) -> None:
    """Result ordering is deterministic on `code` ascending for stable
    downstream serialization."""
    cap_charlie = uuid4()
    cap_alpha = uuid4()
    cap_bravo = uuid4()
    deps_c = build_postgres_deps(db_pool, now=_NOW, ids=[cap_charlie, uuid4()])
    await define_capability.bind(deps_c)(
        _define_command(
            code="cora.capability.charlie",
            name="Charlie",
            required_affordances=frozenset({Affordance.POSABLE}),
        ),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )
    deps_a = build_postgres_deps(db_pool, now=_NOW, ids=[cap_alpha, uuid4()])
    await define_capability.bind(deps_a)(
        _define_command(
            code="cora.capability.alpha",
            name="Alpha",
            required_affordances=frozenset({Affordance.POSABLE}),
        ),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )
    deps_b = build_postgres_deps(db_pool, now=_NOW, ids=[cap_bravo, uuid4()])
    await define_capability.bind(deps_b)(
        _define_command(
            code="cora.capability.bravo",
            name="Bravo",
            required_affordances=frozenset({Affordance.POSABLE}),
        ),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )
    await _drain(db_pool)

    lookup = PostgresCapabilityLookup(db_pool)
    result = await lookup.find_applicable_by_affordances(frozenset({Affordance.POSABLE.value}))
    seeded_codes = [
        r.code for r in result if r.capability_id in {cap_alpha, cap_bravo, cap_charlie}
    ]
    assert seeded_codes == [
        "cora.capability.alpha",
        "cora.capability.bravo",
        "cora.capability.charlie",
    ]
