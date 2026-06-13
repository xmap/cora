"""Unit tests for the `decommission_enclosure` slice's pure decider.

Pin the not-found guard, the strict-not-idempotent already-decommissioned
guard, the Active -> Decommissioned transition, reason VO validation +
trimming, purity, handler-injected `triggered_by` / `now` capture, and
the permit_status orthogonality lock (event payload carries NO
permit_status mutation; the two axes evolve independently).
"""

from datetime import UTC, datetime
from uuid import UUID, uuid4

import pytest

from cora.enclosure.aggregates._value_types import EnclosureId
from cora.enclosure.aggregates.enclosure import (
    Enclosure,
    EnclosureCannotDecommissionError,
    EnclosureLifecycle,
    EnclosureName,
    EnclosureNotFoundError,
    EnclosurePermitStatus,
    InvalidEnclosureReasonError,
)
from cora.enclosure.features import decommission_enclosure
from cora.enclosure.features.decommission_enclosure import DecommissionEnclosure
from cora.shared.identity import ActorId
from cora.shared.text_bounds import REASON_MAX_LENGTH

_NOW = datetime(2026, 7, 1, 9, 30, 0, tzinfo=UTC)
_REGISTERED_AT = datetime(2026, 6, 8, 12, 0, 0, tzinfo=UTC)
_ENCLOSURE_ID = EnclosureId(UUID("01900000-0000-7000-8000-0000000ec102"))
_CONTAINING_ASSET_ID = UUID("01900000-0000-7000-8000-0000000ec150")
_PRINCIPAL_ID = ActorId(UUID("01900000-0000-7000-8000-0000000ec101"))
_REGISTERED_BY = ActorId(UUID("01900000-0000-7000-8000-0000000ec199"))


def _command(**overrides: object) -> DecommissionEnclosure:
    base: dict[str, object] = {
        "enclosure_id": _ENCLOSURE_ID,
        "reason": "end-of-life",
    }
    base.update(overrides)
    return DecommissionEnclosure(**base)  # type: ignore[arg-type]


def _active_enclosure(
    *,
    permit_status: EnclosurePermitStatus = EnclosurePermitStatus.PERMITTED,
) -> Enclosure:
    return Enclosure(
        id=_ENCLOSURE_ID,
        name=EnclosureName("Hutch B"),
        containing_asset_id=_CONTAINING_ASSET_ID,
        permit_status=permit_status,
        lifecycle=EnclosureLifecycle.ACTIVE,
        registered_at=_REGISTERED_AT,
        registered_by=_REGISTERED_BY,
        decommissioned_at=None,
        decommissioned_by=None,
    )


def _decommissioned_enclosure(
    *,
    permit_status: EnclosurePermitStatus = EnclosurePermitStatus.PERMITTED,
) -> Enclosure:
    return Enclosure(
        id=_ENCLOSURE_ID,
        name=EnclosureName("Hutch B"),
        containing_asset_id=_CONTAINING_ASSET_ID,
        permit_status=permit_status,
        lifecycle=EnclosureLifecycle.DECOMMISSIONED,
        registered_at=_REGISTERED_AT,
        registered_by=_REGISTERED_BY,
        decommissioned_at=_NOW,
        decommissioned_by=_PRINCIPAL_ID,
    )


# ---------- not-found guard ----------


@pytest.mark.unit
def test_decommission_enclosure_rejects_none_state_as_not_found() -> None:
    with pytest.raises(EnclosureNotFoundError) as exc:
        decommission_enclosure.decide(
            state=None,
            command=_command(),
            now=_NOW,
            triggered_by=_PRINCIPAL_ID,
        )
    assert exc.value.enclosure_id == _ENCLOSURE_ID


# ---------- already-decommissioned guard ----------


@pytest.mark.unit
def test_decommission_enclosure_rejects_already_decommissioned() -> None:
    with pytest.raises(EnclosureCannotDecommissionError) as exc:
        decommission_enclosure.decide(
            state=_decommissioned_enclosure(),
            command=_command(),
            now=_NOW,
            triggered_by=_PRINCIPAL_ID,
        )
    assert exc.value.enclosure_id == _ENCLOSURE_ID


# ---------- valid transition ----------


@pytest.mark.unit
def test_decommission_enclosure_emits_one_event_for_active_state() -> None:
    events = decommission_enclosure.decide(
        state=_active_enclosure(),
        command=_command(),
        now=_NOW,
        triggered_by=_PRINCIPAL_ID,
    )
    assert len(events) == 1
    event = events[0]
    assert event.enclosure_id == _ENCLOSURE_ID
    assert event.triggered_by == _PRINCIPAL_ID
    assert event.occurred_at == _NOW
    assert event.reason == "end-of-life"


@pytest.mark.unit
def test_decommission_enclosure_trims_reason_via_vo() -> None:
    events = decommission_enclosure.decide(
        state=_active_enclosure(),
        command=_command(reason="  end-of-life  "),
        now=_NOW,
        triggered_by=_PRINCIPAL_ID,
    )
    assert events[0].reason == "end-of-life"


# ---------- reason VO validation ----------


@pytest.mark.unit
def test_decommission_enclosure_rejects_empty_reason() -> None:
    with pytest.raises(InvalidEnclosureReasonError):
        decommission_enclosure.decide(
            state=_active_enclosure(),
            command=_command(reason=""),
            now=_NOW,
            triggered_by=_PRINCIPAL_ID,
        )


@pytest.mark.unit
def test_decommission_enclosure_rejects_whitespace_only_reason() -> None:
    with pytest.raises(InvalidEnclosureReasonError):
        decommission_enclosure.decide(
            state=_active_enclosure(),
            command=_command(reason="   "),
            now=_NOW,
            triggered_by=_PRINCIPAL_ID,
        )


@pytest.mark.unit
def test_decommission_enclosure_rejects_too_long_reason() -> None:
    too_long = "a" * (REASON_MAX_LENGTH + 1)
    with pytest.raises(InvalidEnclosureReasonError):
        decommission_enclosure.decide(
            state=_active_enclosure(),
            command=_command(reason=too_long),
            now=_NOW,
            triggered_by=_PRINCIPAL_ID,
        )


# ---------- permit_status orthogonality lock ----------


@pytest.mark.unit
def test_decommission_enclosure_event_payload_omits_permit_status() -> None:
    """The lifecycle-axis terminal event MUST NOT carry permit_status.

    Per the locked design's orthogonality note, `permit_status` is
    preserved untouched across decommission as audit trail; the
    `EnclosureDecommissioned` event payload carries only the four
    minimal fields (`enclosure_id`, `reason`, `triggered_by`,
    `occurred_at`). Carrying any permit_status discriminator on this
    event would couple the two orthogonal axes and violate the D6.L2
    observation-axis-only anti-lock.
    """
    events = decommission_enclosure.decide(
        state=_active_enclosure(permit_status=EnclosurePermitStatus.NOT_PERMITTED),
        command=_command(),
        now=_NOW,
        triggered_by=_PRINCIPAL_ID,
    )
    event = events[0]
    assert not hasattr(event, "permit_status")
    assert not hasattr(event, "from_permit_status")
    assert not hasattr(event, "to_permit_status")


# ---------- purity + handler-injected capture ----------


@pytest.mark.unit
def test_decommission_enclosure_is_pure_same_inputs_same_outputs() -> None:
    state = _active_enclosure()
    first = decommission_enclosure.decide(
        state=state,
        command=_command(),
        now=_NOW,
        triggered_by=_PRINCIPAL_ID,
    )
    second = decommission_enclosure.decide(
        state=state,
        command=_command(),
        now=_NOW,
        triggered_by=_PRINCIPAL_ID,
    )
    assert first == second


@pytest.mark.unit
def test_decommission_enclosure_uses_handler_injected_actor_verbatim() -> None:
    injected = ActorId(uuid4())
    events = decommission_enclosure.decide(
        state=_active_enclosure(),
        command=_command(),
        now=_NOW,
        triggered_by=injected,
    )
    assert events[0].triggered_by == injected


@pytest.mark.unit
def test_decommission_enclosure_uses_handler_injected_now_verbatim() -> None:
    custom_now = datetime(2030, 12, 31, 23, 59, 59, tzinfo=UTC)
    events = decommission_enclosure.decide(
        state=_active_enclosure(),
        command=_command(),
        now=custom_now,
        triggered_by=_PRINCIPAL_ID,
    )
    assert events[0].occurred_at == custom_now


@pytest.mark.unit
def test_decommission_enclosure_accepts_reason_at_max_length_boundary() -> None:
    """`reason` of exactly REASON_MAX_LENGTH chars is accepted.

    Pins the off-by-one upper boundary (the reject path is at +1).
    """
    boundary = "a" * REASON_MAX_LENGTH
    state = _active_enclosure()
    events = decommission_enclosure.decide(
        state,
        DecommissionEnclosure(enclosure_id=state.id, reason=boundary),
        now=_NOW,
        triggered_by=_PRINCIPAL_ID,
    )
    assert len(events) == 1
    assert events[0].reason == boundary
