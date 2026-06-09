"""Unit tests for the `register_enclosure` slice's pure decider.

Pin the genesis-collision guard, name VO validation (empty, whitespace,
too-long), event payload completeness, every-arm acceptance, purity
(same inputs -> same outputs), and handler-injected new_id /
registered_by / now capture per the non-determinism principle (capture,
don't recompute).
"""

from datetime import UTC, datetime
from uuid import UUID, uuid4

import pytest

from cora.enclosure.aggregates.enclosure import (
    Enclosure,
    EnclosureAlreadyExistsError,
    EnclosureId,
    EnclosureLifecycle,
    EnclosureName,
    EnclosurePermitStatus,
    EnclosureRegistered,
    InvalidEnclosureNameError,
)
from cora.enclosure.features import register_enclosure
from cora.enclosure.features.register_enclosure import RegisterEnclosure
from cora.shared.identity import ActorId

_NOW = datetime(2026, 6, 9, 12, 0, 0, tzinfo=UTC)
_PRINCIPAL_ID = ActorId(UUID("01900000-0000-7000-8000-0000000ec101"))
_ENCLOSURE_ID = EnclosureId(UUID("01900000-0000-7000-8000-0000000ec102"))
_CONTAINING_ASSET_ID = UUID("01900000-0000-7000-8000-0000000ec103")
_REGISTERED_BY = ActorId(UUID("01900000-0000-7000-8000-0000000ec199"))


def _command(**overrides: object) -> RegisterEnclosure:
    base: dict[str, object] = {
        "name": "2-BM-A Hutch",
        "containing_asset_id": _CONTAINING_ASSET_ID,
    }
    base.update(overrides)
    return RegisterEnclosure(**base)  # type: ignore[arg-type]


def _existing_state() -> Enclosure:
    return Enclosure(
        id=_ENCLOSURE_ID,
        name=EnclosureName("2-BM-A Hutch"),
        containing_asset_id=_CONTAINING_ASSET_ID,
        permit_status=EnclosurePermitStatus.UNKNOWN,
        lifecycle=EnclosureLifecycle.ACTIVE,
        registered_at=_NOW,
        registered_by=_REGISTERED_BY,
        decommissioned_at=None,
        decommissioned_by=None,
    )


# ---------- genesis-collision guard ----------


@pytest.mark.unit
def test_register_enclosure_rejects_when_state_already_exists() -> None:
    """Genesis-only: a non-None state surfaces EnclosureAlreadyExistsError."""
    with pytest.raises(EnclosureAlreadyExistsError) as exc:
        register_enclosure.decide(
            state=_existing_state(),
            command=_command(),
            now=_NOW,
            new_id=_ENCLOSURE_ID,
            registered_by=_PRINCIPAL_ID,
        )
    assert exc.value.enclosure_id == _ENCLOSURE_ID


# ---------- name VO validation ----------


@pytest.mark.unit
def test_register_enclosure_rejects_empty_name() -> None:
    with pytest.raises(InvalidEnclosureNameError):
        register_enclosure.decide(
            state=None,
            command=_command(name=""),
            now=_NOW,
            new_id=_ENCLOSURE_ID,
            registered_by=_PRINCIPAL_ID,
        )


@pytest.mark.unit
def test_register_enclosure_rejects_whitespace_only_name() -> None:
    with pytest.raises(InvalidEnclosureNameError):
        register_enclosure.decide(
            state=None,
            command=_command(name="   "),
            now=_NOW,
            new_id=_ENCLOSURE_ID,
            registered_by=_PRINCIPAL_ID,
        )


@pytest.mark.unit
def test_register_enclosure_rejects_too_long_name() -> None:
    with pytest.raises(InvalidEnclosureNameError):
        register_enclosure.decide(
            state=None,
            command=_command(name="a" * 201),
            now=_NOW,
            new_id=_ENCLOSURE_ID,
            registered_by=_PRINCIPAL_ID,
        )


@pytest.mark.unit
def test_register_enclosure_trims_name() -> None:
    events = register_enclosure.decide(
        state=None,
        command=_command(name="  2-BM-A Hutch  "),
        now=_NOW,
        new_id=_ENCLOSURE_ID,
        registered_by=_PRINCIPAL_ID,
    )
    assert events[0].name == "2-BM-A Hutch"


# ---------- event payload completeness ----------


@pytest.mark.unit
def test_register_enclosure_emits_enclosure_registered_when_stream_is_empty() -> None:
    events = register_enclosure.decide(
        state=None,
        command=_command(),
        now=_NOW,
        new_id=_ENCLOSURE_ID,
        registered_by=_PRINCIPAL_ID,
    )
    assert events == [
        EnclosureRegistered(
            enclosure_id=_ENCLOSURE_ID,
            name="2-BM-A Hutch",
            containing_asset_id=_CONTAINING_ASSET_ID,
            registered_by=_PRINCIPAL_ID,
            occurred_at=_NOW,
        )
    ]


@pytest.mark.unit
def test_register_enclosure_event_carries_command_fields_verbatim() -> None:
    events = register_enclosure.decide(
        state=None,
        command=_command(name="2-BM-A Hutch"),
        now=_NOW,
        new_id=_ENCLOSURE_ID,
        registered_by=_PRINCIPAL_ID,
    )
    assert len(events) == 1
    event = events[0]
    assert event.enclosure_id == _ENCLOSURE_ID
    assert event.name == "2-BM-A Hutch"
    assert event.containing_asset_id == _CONTAINING_ASSET_ID
    assert event.registered_by == _PRINCIPAL_ID
    assert event.occurred_at == _NOW


# ---------- purity + handler-injected capture ----------


@pytest.mark.unit
def test_register_enclosure_is_pure_same_inputs_same_outputs() -> None:
    first = register_enclosure.decide(
        state=None,
        command=_command(),
        now=_NOW,
        new_id=_ENCLOSURE_ID,
        registered_by=_PRINCIPAL_ID,
    )
    second = register_enclosure.decide(
        state=None,
        command=_command(),
        now=_NOW,
        new_id=_ENCLOSURE_ID,
        registered_by=_PRINCIPAL_ID,
    )
    assert first == second


@pytest.mark.unit
def test_register_enclosure_uses_handler_injected_new_id_verbatim() -> None:
    injected = EnclosureId(uuid4())
    events = register_enclosure.decide(
        state=None,
        command=_command(),
        now=_NOW,
        new_id=injected,
        registered_by=_PRINCIPAL_ID,
    )
    assert events[0].enclosure_id == injected


@pytest.mark.unit
def test_register_enclosure_uses_handler_injected_actor_id_verbatim() -> None:
    injected = ActorId(uuid4())
    events = register_enclosure.decide(
        state=None,
        command=_command(),
        now=_NOW,
        new_id=_ENCLOSURE_ID,
        registered_by=injected,
    )
    assert events[0].registered_by == injected


@pytest.mark.unit
def test_register_enclosure_uses_handler_injected_now_verbatim() -> None:
    custom_now = datetime(2027, 1, 15, 9, 30, 0, tzinfo=UTC)
    events = register_enclosure.decide(
        state=None,
        command=_command(),
        now=custom_now,
        new_id=_ENCLOSURE_ID,
        registered_by=_PRINCIPAL_ID,
    )
    assert events[0].occurred_at == custom_now
