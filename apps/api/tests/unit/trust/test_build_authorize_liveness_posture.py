"""`build_authorize` refuses the misconfigurations that would serve nothing.

Both guards here exist because a gate review found the first version
unreachable in the exact case most likely to occur. The posture check
originally ran AFTER the `trust_policy_id is None` early return, so a
deployment setting `liveness_posture=enforce` while still on
`AllowAllAuthorize` booted permitting every command, with no liveness and
no error. Asking for a security control and silently getting none is the
failure the guard was written to prevent, and the guard had it.

Ordering is therefore the property under test, not the messages.
"""

from datetime import UTC, datetime
from uuid import UUID

import pytest

from cora.infrastructure.adapters.in_memory_event_store import InMemoryEventStore
from cora.infrastructure.config import Settings
from cora.infrastructure.ports import (
    Allow,
    AllowAllAuthorize,
    AlwaysLivePrincipalLivenessLookup,
    Deny,
    FakeClock,
    FixedIdGenerator,
)
from cora.trust.authorize import TrustAuthorize
from cora.trust.build_authorize import build_authorize

_POLICY_ID = UUID("01900000-0000-7000-8000-000000000601")


def _settings(**overrides: object) -> Settings:
    return Settings(app_env="test", **overrides)  # pyright: ignore[reportCallIssue, reportArgumentType]


def _build(settings: Settings, lookup: object = None) -> object:
    return build_authorize(
        settings,
        InMemoryEventStore(),
        pool=None,
        clock=FakeClock(datetime(2026, 5, 9, 12, 0, 0, tzinfo=UTC)),
        id_generator=FixedIdGenerator([]),
        liveness_lookup=lookup,  # pyright: ignore[reportArgumentType]
    )


@pytest.mark.unit
def test_enforce_without_a_policy_id_refuses_to_boot() -> None:
    """The regression. AllowAll plus enforce must not be a silent no-op."""
    with pytest.raises(ValueError, match="no effect without trust_policy_id"):
        _build(_settings(liveness_posture="enforce"), AlwaysLivePrincipalLivenessLookup())


@pytest.mark.unit
def test_shadow_without_a_policy_id_refuses_to_boot() -> None:
    """Shadow is a measurement, and a measurement of nothing is worse than none.

    Under AllowAll no conjunct runs, so a shadow deployment here would
    report zero would-be denials and be read as "nobody is affected".
    """
    with pytest.raises(ValueError, match="no effect without trust_policy_id"):
        _build(_settings(liveness_posture="shadow"), AlwaysLivePrincipalLivenessLookup())


@pytest.mark.unit
def test_enforce_without_a_lookup_refuses_to_boot() -> None:
    with pytest.raises(ValueError, match="requires a PrincipalLivenessLookup"):
        _build(_settings(liveness_posture="enforce", trust_policy_id=_POLICY_ID))


@pytest.mark.unit
def test_off_posture_with_no_policy_still_returns_the_permissive_stub() -> None:
    """The default path stays exactly as it was."""
    assert isinstance(_build(_settings()), AllowAllAuthorize)


@pytest.mark.unit
def test_enforce_with_both_wired_builds_the_real_gate() -> None:
    built = _build(
        _settings(liveness_posture="enforce", trust_policy_id=_POLICY_ID),
        AlwaysLivePrincipalLivenessLookup(),
    )

    assert isinstance(built, TrustAuthorize)


# --- policy_posture wiring ---------------------------------------------------


@pytest.mark.unit
def test_shadow_without_a_policy_id_is_refused_at_boot() -> None:
    """The misconfiguration that would look most like success.

    Asking for a shadow rollout with nothing to shadow boots cleanly,
    refuses nothing, records nothing, and leaves an operator waiting for an
    inventory that will never arrive. Same shape as the liveness guard above
    and for the same reason: a control that was asked for and silently not
    supplied is worse than one that was never asked for.
    """
    with pytest.raises(ValueError, match="policy_posture='shadow' has no effect"):
        _build(_settings(trust_policy_id=None, policy_posture="shadow"))


# Both postures are asserted through the verdict the built adapter reaches,
# never through its private flag: the attribute name is not the contract,
# the refusal is. Neither store here holds the configured policy, so the
# Deny comes from the adapter's own fail-closed path, which is a refusal a
# shadow rollout equally must not apply.


@pytest.mark.unit
async def test_enforce_is_the_default_posture() -> None:
    """Absent an explicit posture, a configured policy still refuses."""
    authorize = _build(_settings(trust_policy_id=_POLICY_ID))
    assert isinstance(authorize, TrustAuthorize)

    result = await authorize.authorize(_POLICY_ID, "RegisterActor", UUID(int=0))

    assert isinstance(result, Deny)


@pytest.mark.unit
async def test_shadow_posture_reaches_the_adapter() -> None:
    authorize = _build(_settings(trust_policy_id=_POLICY_ID, policy_posture="shadow"))
    assert isinstance(authorize, TrustAuthorize)

    result = await authorize.authorize(_POLICY_ID, "RegisterActor", UUID(int=0))

    assert isinstance(result, Allow)
