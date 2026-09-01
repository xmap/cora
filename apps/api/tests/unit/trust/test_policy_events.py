"""Unit tests for the Policy aggregate's event (de)serialization helpers."""

from datetime import UTC, datetime
from uuid import UUID, uuid4

import pytest

from cora.infrastructure.ports import Allow
from cora.infrastructure.ports.event_store import StoredEvent
from cora.infrastructure.routing import SYSTEM_HTTP_SURFACE_ID
from cora.trust.aggregates.policy import evaluate
from cora.trust.aggregates.policy.events import (
    PolicyDefined,
    PolicyGrantRevoked,
    event_type_name,
    from_stored,
    to_payload,
)
from cora.trust.aggregates.policy.evolver import evolve

_NOW = datetime(2026, 5, 10, 12, 0, 0, tzinfo=UTC)


def _stored(
    event_type: str,
    payload: dict[str, object],
    *,
    stream_id: object | None = None,
) -> StoredEvent:
    return StoredEvent(
        position=1,
        event_id=uuid4(),
        stream_type="Policy",
        stream_id=stream_id or uuid4(),  # type: ignore[arg-type]
        version=1,
        event_type=event_type,
        schema_version=1,
        payload=payload,
        correlation_id=uuid4(),
        causation_id=None,
        occurred_at=_NOW,
        recorded_at=_NOW,
    )


@pytest.mark.unit
def test_event_type_name_returns_class_name() -> None:
    event = PolicyDefined(
        policy_id=uuid4(),
        name="X",
        conduit_id=uuid4(),
        grants=(),
        occurred_at=_NOW,
    )
    assert event_type_name(event) == "PolicyDefined"


@pytest.mark.unit
def test_to_payload_serializes_policy_defined_to_primitives() -> None:
    policy_id = uuid4()
    conduit = uuid4()
    p1 = UUID("01900000-0000-7000-8000-000000000111")
    event = PolicyDefined(
        policy_id=policy_id,
        name="Beam-team",
        conduit_id=conduit,
        grants=((p1, "RegisterActor"),),
        occurred_at=_NOW,
    )
    assert to_payload(event) == {
        "policy_id": str(policy_id),
        "name": "Beam-team",
        "conduit_id": str(conduit),
        # for V1-shape callers. V1 events on disk lack the field and fold
        # via `from_stored`'s `.get(..., nil)` default.
        "surface_id": "00000000-0000-0000-0000-000000000000",
        "grants": [[str(p1), "RegisterActor"]],
        "occurred_at": _NOW.isoformat(),
    }


@pytest.mark.unit
def test_to_payload_sorts_permission_lists_deterministically() -> None:
    """Same logical permission set should produce same payload bytes
    regardless of input ordering (matters for idempotency-key hashing
    and content-addressed lookups). Permission sets serialize sorted
    by string form."""
    p1 = UUID("01900000-0000-7000-8000-000000000111")
    p2 = UUID("01900000-0000-7000-8000-000000000222")
    p3 = UUID("01900000-0000-7000-8000-000000000333")

    event_in_one_order = PolicyDefined(
        policy_id=uuid4(),
        name="X",
        conduit_id=uuid4(),
        grants=((p3, "Z"), (p1, "A"), (p2, "M")),
        occurred_at=_NOW,
    )
    payload = to_payload(event_in_one_order)

    assert payload["grants"] == [
        [str(p1), "A"],
        [str(p2), "M"],
        [str(p3), "Z"],
    ]


@pytest.mark.unit
def test_from_stored_rebuilds_policy_defined() -> None:
    policy_id = uuid4()
    conduit = uuid4()
    p1 = uuid4()
    stored = _stored(
        "PolicyDefined",
        {
            "policy_id": str(policy_id),
            "name": "Beam-team",
            "conduit_id": str(conduit),
            "grants": [[str(p1), "RegisterActor"]],
            "occurred_at": _NOW.isoformat(),
        },
    )
    rebuilt = from_stored(stored)
    assert rebuilt == PolicyDefined(
        policy_id=policy_id,
        name="Beam-team",
        conduit_id=conduit,
        grants=((p1, "RegisterActor"),),
        occurred_at=_NOW,
    )


@pytest.mark.unit
def test_to_payload_then_from_stored_round_trips() -> None:
    """Round-trip safety net for the (de)serialization pair."""
    original = PolicyDefined(
        policy_id=uuid4(),
        name="Beam-team",
        conduit_id=uuid4(),
        grants=((uuid4(), "X"), (uuid4(), "Y")),
        occurred_at=_NOW,
    )
    stored = _stored("PolicyDefined", to_payload(original))
    rebuilt = from_stored(stored)
    # Lists may differ in order after sort+rebuild; compare as sets.
    assert isinstance(rebuilt, PolicyDefined)
    assert rebuilt.policy_id == original.policy_id
    assert rebuilt.name == original.name
    assert rebuilt.conduit_id == original.conduit_id
    assert set(rebuilt.grants) == set(original.grants)
    assert rebuilt.occurred_at == original.occurred_at


@pytest.mark.unit
def test_event_type_name_returns_grant_revoked_class_name() -> None:
    event = PolicyGrantRevoked(
        policy_id=uuid4(),
        principal_id=uuid4(),
        revoked_by=uuid4(),
        reason="access review",
        occurred_at=_NOW,
    )
    assert event_type_name(event) == "PolicyGrantRevoked"


@pytest.mark.unit
def test_to_payload_serializes_grant_revoked_to_primitives() -> None:
    policy_id = uuid4()
    principal_id = uuid4()
    revoked_by = uuid4()
    event = PolicyGrantRevoked(
        policy_id=policy_id,
        principal_id=principal_id,
        revoked_by=revoked_by,
        reason="access review",
        occurred_at=_NOW,
    )
    assert to_payload(event) == {
        "policy_id": str(policy_id),
        "principal_id": str(principal_id),
        "revoked_by": str(revoked_by),
        "reason": "access review",
        "occurred_at": _NOW.isoformat(),
    }


@pytest.mark.unit
def test_grant_revoked_to_payload_then_from_stored_round_trips() -> None:
    original = PolicyGrantRevoked(
        policy_id=uuid4(),
        principal_id=uuid4(),
        revoked_by=uuid4(),
        reason="access review",
        occurred_at=_NOW,
    )
    stored = _stored("PolicyGrantRevoked", to_payload(original))
    assert from_stored(stored) == original


@pytest.mark.unit
def test_from_stored_raises_on_unknown_event_type() -> None:
    """Foreign event_types in a stream must fail loud."""
    stored = _stored("ZoneDefined", {})
    with pytest.raises(ValueError, match="Unknown PolicyEvent event_type"):
        from_stored(stored)


# `to_new_event` envelope construction lives at
# `cora.infrastructure.event_envelope` and is covered by
# `tests/unit/test_event_envelope.py`.


@pytest.mark.unit
@pytest.mark.parametrize(
    "event_type",
    [
        "PolicyDefined",
        "PolicyGrantRevoked",
    ],
)
def test_from_stored_raises_on_malformed_payload(event_type: str) -> None:
    """Per the convention adopted post-corpus-survey (Marten /
    pyeventsourcing / Pydantic / msgspec all wrap), each event-type case
    wraps `KeyError`/`TypeError`/`AttributeError` into a tagged
    `ValueError` so a corrupted event row fails loud with the event-type
    name in the message rather than bubbling a raw KeyError from deep
    in the load path."""
    with pytest.raises(ValueError, match=f"Malformed {event_type} payload"):
        from_stored(_stored(event_type, {}))


# ---------- reading a pre-pairs event ----------
#
# `grants` replaced two independent lists that `evaluate` multiplied at
# decision time. Every PolicyDefined already on disk carries the old
# shape, so `from_stored` reconstructs it as the cross-product: the same
# permissions those policies have always granted, reached by multiplying
# in the fold instead of in the check.
#
# These are the load-bearing tests of that change. If the cross-product
# is wrong, live deployments silently gain or lose authority on their
# next restart, and nothing else in the suite would notice.


def _legacy_payload(
    *,
    conduit_id: UUID,
    principal_ids: list[UUID],
    command_names: list[str],
) -> dict[str, object]:
    """A PolicyDefined payload in the shape written before pairs existed."""
    return {
        "policy_id": str(uuid4()),
        "name": "Legacy",
        "conduit_id": str(conduit_id),
        "surface_id": str(SYSTEM_HTTP_SURFACE_ID),
        "permitted_principal_ids": [str(p) for p in principal_ids],
        "permitted_commands": command_names,
        "occurred_at": _NOW.isoformat(),
    }


@pytest.mark.unit
def test_a_pre_pairs_event_folds_to_the_full_cross_product() -> None:
    """Two principals by three commands is six grants."""
    p1 = UUID("01900000-0000-7000-8000-000000000111")
    p2 = UUID("01900000-0000-7000-8000-000000000222")

    rebuilt = from_stored(
        _stored(
            "PolicyDefined",
            _legacy_payload(
                conduit_id=uuid4(),
                principal_ids=[p1, p2],
                command_names=["StartRun", "HoldRun", "AbortRun"],
            ),
        )
    )

    assert isinstance(rebuilt, PolicyDefined)
    assert set(rebuilt.grants) == {
        (p1, "StartRun"),
        (p1, "HoldRun"),
        (p1, "AbortRun"),
        (p2, "StartRun"),
        (p2, "HoldRun"),
        (p2, "AbortRun"),
    }


@pytest.mark.unit
def test_a_pre_pairs_policy_still_permits_everything_it_used_to() -> None:
    """The property, stated as the OLD evaluate would have answered it.

    Asserted by exhaustive evaluation rather than by rebuilding the same
    cross-product the implementation builds. Comparing the fold against a
    second copy of its own construction rule would agree by construction
    and prove nothing; driving real verdicts checks the outcome a
    deployment actually depends on, and stays honest if the fold is ever
    rewritten.
    """
    principals = [UUID(int=1), UUID(int=2)]
    commands = ["StartRun", "HoldRun"]
    conduit_id = uuid4()

    rebuilt = from_stored(
        _stored(
            "PolicyDefined",
            _legacy_payload(
                conduit_id=conduit_id,
                principal_ids=principals,
                command_names=commands,
            ),
        )
    )
    assert isinstance(rebuilt, PolicyDefined)
    policy = evolve(None, rebuilt)

    for principal_id in principals:
        for command_name in commands:
            verdict = evaluate(
                policy,
                principal_id=principal_id,
                command_name=command_name,
                conduit_id=conduit_id,
                surface_id=SYSTEM_HTTP_SURFACE_ID,
            )
            assert isinstance(verdict, Allow), (
                f"{principal_id} could {command_name} before pairs and must still"
            )


@pytest.mark.unit
def test_a_pre_pairs_event_with_repeated_entries_yields_each_pair_once() -> None:
    """A repeated entry in either legacy list must not repeat the pair.

    The old state folded both lists to frozensets, so nothing upstream
    had a reason to prevent duplicates on disk. Folding to `Policy` would
    collapse them regardless; this pins the EVENT, which anything reading
    grants before the fold (an audit trail, a grant count) sees first.
    """
    p1 = UUID("01900000-0000-7000-8000-000000000111")
    p2 = UUID("01900000-0000-7000-8000-000000000222")

    rebuilt = from_stored(
        _stored(
            "PolicyDefined",
            _legacy_payload(
                conduit_id=uuid4(),
                principal_ids=[p1, p1, p2],
                command_names=["StartRun", "StartRun"],
            ),
        )
    )

    assert isinstance(rebuilt, PolicyDefined)
    assert rebuilt.grants == ((p1, "StartRun"), (p2, "StartRun"))


@pytest.mark.unit
def test_a_grants_bearing_payload_with_a_repeated_pair_yields_it_once() -> None:
    """Same guarantee for the new shape, which is hand-writable too."""
    p1 = UUID("01900000-0000-7000-8000-000000000111")

    rebuilt = from_stored(
        _stored(
            "PolicyDefined",
            {
                "policy_id": str(uuid4()),
                "name": "Repeated",
                "conduit_id": str(uuid4()),
                "surface_id": str(SYSTEM_HTTP_SURFACE_ID),
                "grants": [[str(p1), "StartRun"], [str(p1), "StartRun"]],
                "occurred_at": _NOW.isoformat(),
            },
        )
    )

    assert isinstance(rebuilt, PolicyDefined)
    assert rebuilt.grants == ((p1, "StartRun"),)


@pytest.mark.unit
def test_a_pre_pairs_event_with_an_empty_list_stays_deny_all() -> None:
    """Empty on either side cross-products to nothing, as it always did."""
    for principal_ids, command_names in (
        ([], ["StartRun"]),
        ([UUID(int=1)], []),
        ([], []),
    ):
        rebuilt = from_stored(
            _stored(
                "PolicyDefined",
                _legacy_payload(
                    conduit_id=uuid4(),
                    principal_ids=principal_ids,
                    command_names=command_names,
                ),
            )
        )
        assert isinstance(rebuilt, PolicyDefined)
        assert rebuilt.grants == ()


@pytest.mark.unit
def test_a_grants_bearing_payload_is_read_as_written_never_cross_producted() -> None:
    """The new shape is authoritative, and is NOT multiplied.

    The distinguishing case: two principals with DIFFERENT command sets.
    Cross-producting the same material would yield four grants; reading
    it exactly yields two. That difference is the entire point of the
    change, so it is pinned rather than left implied.
    """
    p1 = UUID("01900000-0000-7000-8000-000000000111")
    p2 = UUID("01900000-0000-7000-8000-000000000222")

    rebuilt = from_stored(
        _stored(
            "PolicyDefined",
            {
                "policy_id": str(uuid4()),
                "name": "Precise",
                "conduit_id": str(uuid4()),
                "surface_id": str(SYSTEM_HTTP_SURFACE_ID),
                "grants": [[str(p1), "StartRun"], [str(p2), "AbortRun"]],
                "occurred_at": _NOW.isoformat(),
            },
        )
    )

    assert isinstance(rebuilt, PolicyDefined)
    assert set(rebuilt.grants) == {(p1, "StartRun"), (p2, "AbortRun")}
    assert (p1, "AbortRun") not in rebuilt.grants
    assert (p2, "StartRun") not in rebuilt.grants
