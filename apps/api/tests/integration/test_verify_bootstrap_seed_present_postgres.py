"""Integration tests for `verify_bootstrap_seed_present`.

Covers the two branches:
  1. trust_policy_id == SYSTEM_BOOTSTRAP_POLICY_ID -> load the bootstrap
     policy + all 3 Surfaces; assert the policy binds to the HTTP
     Surface (GR3 BC-7 binding check).
  2. Otherwise -> no-op.

Also pins the failure paths: missing bootstrap-policy stream / missing
seeded Surface / policy mis-bound to a non-HTTP surface.

The retired nil-surface bootstrap policy (...0001) is no longer a
branch here: its evaluate-time wildcard fold was removed, so the
verifier has a single canonical (surface-bound) behavior.
"""

from dataclasses import replace
from datetime import UTC, datetime
from unittest.mock import patch

import asyncpg
import pytest

from cora.infrastructure.config import Settings
from cora.infrastructure.kernel import Kernel
from cora.trust._bootstrap import (
    SYSTEM_BOOTSTRAP_POLICY_ID,
    verify_bootstrap_seed_present,
)
from tests.integration._helpers import build_postgres_deps

_NOW = datetime(2026, 5, 19, 12, 0, 0, tzinfo=UTC)


def _deps_with_trust_policy_id(db_pool: asyncpg.Pool, policy_id: object) -> Kernel:
    """Build a Kernel with a custom `trust_policy_id` setting.

    Uses `dataclasses.replace` on the Settings dataclass — avoids
    directly constructing a fresh Kernel, which would trip the
    architecture-fitness single-construction-site invariant.
    """
    base = build_postgres_deps(db_pool, now=_NOW)
    new_settings = Settings.model_validate(
        {**base.settings.model_dump(), "trust_policy_id": policy_id},
    )
    return replace(base, settings=new_settings)


@pytest.mark.integration
async def test_verify_passes_when_bootstrap_policy_and_surfaces_all_seeded(
    db_pool: asyncpg.Pool,
) -> None:
    """Happy path: bootstrap policy + 3 Surfaces present (the test DB
    template has them via the bootstrap seed migration)."""
    deps = _deps_with_trust_policy_id(db_pool, SYSTEM_BOOTSTRAP_POLICY_ID)
    await verify_bootstrap_seed_present(deps)  # no exception


@pytest.mark.integration
async def test_verify_noop_when_custom_policy_id_configured(
    db_pool: asyncpg.Pool,
) -> None:
    """A custom (non-seeded) policy id falls into the no-op branch.
    Operators using their own admin Policy aren't blocked at boot."""
    from uuid import UUID

    custom = UUID("01900000-0000-7000-8000-0000000ccccc")
    deps = _deps_with_trust_policy_id(db_pool, custom)
    await verify_bootstrap_seed_present(deps)  # no exception


@pytest.mark.integration
async def test_verify_noop_when_no_policy_id_configured(
    db_pool: asyncpg.Pool,
) -> None:
    """trust_policy_id=None means AllowAllAuthorize is wired; verifier
    has nothing to check."""
    deps = _deps_with_trust_policy_id(db_pool, None)
    await verify_bootstrap_seed_present(deps)  # no exception


@pytest.mark.integration
async def test_verify_raises_when_bootstrap_policy_stream_missing(
    db_pool: asyncpg.Pool,
) -> None:
    """Bootstrap policy configured but the policy stream isn't seeded —
    fail-fast with a runbook pointer."""
    deps = _deps_with_trust_policy_id(db_pool, SYSTEM_BOOTSTRAP_POLICY_ID)
    with (
        patch("cora.trust._bootstrap.load_policy", return_value=None),
        pytest.raises(RuntimeError, match="bootstrap policy"),
    ):
        await verify_bootstrap_seed_present(deps)


@pytest.mark.integration
async def test_verify_raises_when_seeded_surface_missing(
    db_pool: asyncpg.Pool,
) -> None:
    """Bootstrap policy configured + stream present but one of the 3
    Surfaces is missing: partial-fail mitigation."""
    deps = _deps_with_trust_policy_id(db_pool, SYSTEM_BOOTSTRAP_POLICY_ID)
    with (
        patch("cora.trust._bootstrap.load_surface", return_value=None),
        pytest.raises(RuntimeError, match=r"seeded Surface .* is missing"),
    ):
        await verify_bootstrap_seed_present(deps)


@pytest.mark.integration
async def test_verify_raises_when_bootstrap_policy_misbound_to_non_http_surface(
    db_pool: asyncpg.Pool,
) -> None:
    """GR3 BC-7: bootstrap policy loaded but folded `surface_id !=
    SYSTEM_HTTP_SURFACE_ID` (for example, post-seed mutation, or an
    unauthorized PolicyDefined appended to the stream). The verifier
    catches it instead of silently denying every request, since
    evaluate strict-matches the surface."""
    from uuid import UUID

    from cora.trust.aggregates.policy import PolicyName
    from cora.trust.aggregates.policy.state import Policy

    deps = _deps_with_trust_policy_id(db_pool, SYSTEM_BOOTSTRAP_POLICY_ID)
    # Stub the policy to fold with a non-HTTP surface_id (corrupted).
    bogus_policy = Policy(
        id=SYSTEM_BOOTSTRAP_POLICY_ID,
        name=PolicyName("Tampered"),
        conduit_id=UUID(int=0),
        permitted_principal_ids=frozenset(),
        permitted_commands=frozenset(),
        surface_id=UUID(int=99),  # NOT SYSTEM_HTTP_SURFACE_ID
    )
    with (
        patch("cora.trust._bootstrap.load_policy", return_value=bogus_policy),
        pytest.raises(RuntimeError, match="folded with surface_id="),
    ):
        await verify_bootstrap_seed_present(deps)
