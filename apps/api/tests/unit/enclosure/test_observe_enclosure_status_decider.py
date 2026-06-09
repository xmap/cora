"""Decider tests for `observe_enclosure_status`.

Pins the Monitor truth table per [[project_enclosure_stage1_design]]:

  - Permit-axis transitions are any-to-any across the closed
    `EnclosurePermitStatus` set (`Permitted | NotPermitted | Unknown`).
    There is no source-state allowlist; substrate observability is the
    source of truth and the spine records whatever the adapter saw.
  - Identical-status observations are a no-op: the decider returns
    `[]` rather than emitting a duplicate event (L-EV-2 status-change-
    only). This diverges from the Supply observe precedent, which
    treats identical source-and-target as a guard violation.
  - Decommissioned lifecycle is a tombstone: observation attempts
    raise `EnclosureCannotObserveWhileDecommissionedError`.
  - Trigger is locked to `Monitor` at the decider's command-tier
    guard: a command carrying `trigger="Operator"` raises
    `MonitorTriggerNotPermittedError`, closing the
    operator-assert-Permitted backdoor (D6.L2 observation-axis-only
    anti-lock; no operator path to `Permitted`).
  - Every emitted event carries `trigger="Monitor"`, a typed
    `MonitorSourceId` in `triggered_by`, and the serialized
    `monitor_ref` audit field.
"""

from datetime import UTC, datetime
from uuid import UUID, uuid4

import pytest

from cora.enclosure.aggregates.enclosure import (
    Enclosure,
    EnclosureCannotObserveWhileDecommissionedError,
    EnclosureId,
    EnclosureLifecycle,
    EnclosureName,
    EnclosureNotFoundError,
    EnclosurePermitObserved,
    EnclosurePermitStatus,
    InvalidEnclosureReasonError,
    MonitorRef,
    MonitorTriggerNotPermittedError,
)
from cora.enclosure.features.observe_enclosure_status import (
    ObserveEnclosureStatus,
    decide,
)
from cora.shared.identity import ActorId, MonitorSourceId

_NOW = datetime(2026, 6, 9, 12, 0, 0, tzinfo=UTC)
_MONITOR_REF = MonitorRef(source_kind="EpicsPv", source_id="S35:pss_chain_state")
_MONITOR_SOURCE_ID = MonitorSourceId(uuid4())
_REGISTERED_AT = datetime(2026, 6, 1, 9, 0, 0, tzinfo=UTC)
_REGISTERED_BY = ActorId(UUID("01900000-0000-7000-8000-0000000ec199"))
_CONTAINING_ASSET_ID = UUID("01900000-0000-7000-8000-0000000ec103")


def _state(
    permit_status: EnclosurePermitStatus,
    *,
    lifecycle: EnclosureLifecycle = EnclosureLifecycle.ACTIVE,
) -> Enclosure:
    return Enclosure(
        id=EnclosureId(uuid4()),
        name=EnclosureName("2-BM-A Hutch"),
        containing_asset_id=_CONTAINING_ASSET_ID,
        permit_status=permit_status,
        lifecycle=lifecycle,
        registered_at=_REGISTERED_AT,
        registered_by=_REGISTERED_BY,
        decommissioned_at=None if lifecycle is EnclosureLifecycle.ACTIVE else _NOW,
        decommissioned_by=None if lifecycle is EnclosureLifecycle.ACTIVE else _REGISTERED_BY,
    )


def _cmd(
    enclosure_id: UUID,
    new_status: EnclosurePermitStatus,
    *,
    reason: str = "PSS interlock chain healthy",
    trigger: str = "Monitor",
) -> ObserveEnclosureStatus:
    return ObserveEnclosureStatus(
        enclosure_id=EnclosureId(enclosure_id),
        new_status=new_status,
        monitor_ref=_MONITOR_REF,
        monitor_source_id=_MONITOR_SOURCE_ID,
        reason=reason,
        trigger=trigger,
    )


@pytest.mark.unit
def test_decide_raises_not_found_when_state_is_none() -> None:
    """State-none gate fires FIRST, before any trigger / lifecycle check."""
    enc_id = uuid4()
    with pytest.raises(EnclosureNotFoundError):
        decide(
            None,
            _cmd(enc_id, EnclosurePermitStatus.PERMITTED),
            now=_NOW,
            triggered_by=_MONITOR_SOURCE_ID,
        )


@pytest.mark.unit
def test_decide_rejects_operator_trigger() -> None:
    """No operator path to Permitted: trigger=Operator raises at the
    command-tier guard (D6.L2 observation-axis-only anti-lock)."""
    s = _state(EnclosurePermitStatus.UNKNOWN)
    with pytest.raises(MonitorTriggerNotPermittedError):
        decide(
            s,
            _cmd(s.id, EnclosurePermitStatus.PERMITTED, trigger="Operator"),
            now=_NOW,
            triggered_by=_MONITOR_SOURCE_ID,
        )


@pytest.mark.unit
@pytest.mark.parametrize("trigger", ["Auto", "Scheduler", "", "monitor", "MONITOR"])
def test_decide_rejects_non_monitor_trigger(trigger: str) -> None:
    """Anything other than the exact string 'Monitor' is rejected at
    the command-tier guard; no operator-assert backdoor."""
    s = _state(EnclosurePermitStatus.UNKNOWN)
    with pytest.raises(MonitorTriggerNotPermittedError):
        decide(
            s,
            _cmd(s.id, EnclosurePermitStatus.PERMITTED, trigger=trigger),
            now=_NOW,
            triggered_by=_MONITOR_SOURCE_ID,
        )


@pytest.mark.unit
@pytest.mark.parametrize(
    "target",
    [
        EnclosurePermitStatus.PERMITTED,
        EnclosurePermitStatus.NOT_PERMITTED,
        EnclosurePermitStatus.UNKNOWN,
    ],
)
def test_decide_rejects_observation_on_decommissioned_enclosure(
    target: EnclosurePermitStatus,
) -> None:
    """Decommissioned is a tombstone: every observation target raises."""
    s = _state(EnclosurePermitStatus.PERMITTED, lifecycle=EnclosureLifecycle.DECOMMISSIONED)
    with pytest.raises(EnclosureCannotObserveWhileDecommissionedError) as exc_info:
        decide(s, _cmd(s.id, target), now=_NOW, triggered_by=_MONITOR_SOURCE_ID)
    assert exc_info.value.enclosure_id == s.id
    assert exc_info.value.current_lifecycle is EnclosureLifecycle.DECOMMISSIONED


@pytest.mark.unit
@pytest.mark.parametrize(
    "status",
    [
        EnclosurePermitStatus.UNKNOWN,
        EnclosurePermitStatus.PERMITTED,
        EnclosurePermitStatus.NOT_PERMITTED,
    ],
)
def test_decide_returns_empty_when_target_matches_current_status(
    status: EnclosurePermitStatus,
) -> None:
    """L-EV-2: identical-status observations are a no-op; no event is
    emitted and no error is raised. Diverges from Supply observe (which
    treats identical source-and-target as a guard violation)."""
    s = _state(status)
    events = decide(s, _cmd(s.id, status), now=_NOW, triggered_by=_MONITOR_SOURCE_ID)
    assert events == []


@pytest.mark.unit
@pytest.mark.parametrize(
    ("source", "target"),
    [
        (EnclosurePermitStatus.UNKNOWN, EnclosurePermitStatus.PERMITTED),
        (EnclosurePermitStatus.UNKNOWN, EnclosurePermitStatus.NOT_PERMITTED),
        (EnclosurePermitStatus.PERMITTED, EnclosurePermitStatus.NOT_PERMITTED),
        (EnclosurePermitStatus.NOT_PERMITTED, EnclosurePermitStatus.PERMITTED),
        (EnclosurePermitStatus.PERMITTED, EnclosurePermitStatus.UNKNOWN),
        (EnclosurePermitStatus.NOT_PERMITTED, EnclosurePermitStatus.UNKNOWN),
    ],
)
def test_decide_emits_permit_observed_for_every_legal_edge(
    source: EnclosurePermitStatus,
    target: EnclosurePermitStatus,
) -> None:
    """Every any-to-any transition (where source != target) emits
    exactly one `EnclosurePermitObserved` carrying both endpoints."""
    s = _state(source)
    events = decide(s, _cmd(s.id, target), now=_NOW, triggered_by=_MONITOR_SOURCE_ID)
    assert len(events) == 1
    event = events[0]
    assert isinstance(event, EnclosurePermitObserved)
    assert event.enclosure_id == s.id
    assert event.from_status == source.value
    assert event.to_status == target.value


@pytest.mark.unit
def test_decide_event_carries_monitor_attribution_verbatim() -> None:
    """`trigger`, `triggered_by`, `monitor_ref`, and `reason` are
    carried verbatim onto the emitted event."""
    s = _state(EnclosurePermitStatus.UNKNOWN)
    events = decide(
        s,
        _cmd(s.id, EnclosurePermitStatus.PERMITTED, reason="PSS interlock chain healthy"),
        now=_NOW,
        triggered_by=_MONITOR_SOURCE_ID,
    )
    assert len(events) == 1
    event = events[0]
    assert isinstance(event, EnclosurePermitObserved)
    assert event.trigger == "Monitor"
    assert event.triggered_by == _MONITOR_SOURCE_ID
    assert event.monitor_ref == "EpicsPv:S35:pss_chain_state"
    assert event.reason == "PSS interlock chain healthy"
    assert event.occurred_at == _NOW


@pytest.mark.unit
def test_decide_event_uses_state_id_not_command_id() -> None:
    """The emitted event's `enclosure_id` is taken from `state.id`,
    not from `command.enclosure_id`, mirroring the precedent that the
    aggregate state is the source of truth for identity once loaded."""
    s = _state(EnclosurePermitStatus.UNKNOWN)
    events = decide(
        s,
        _cmd(s.id, EnclosurePermitStatus.PERMITTED),
        now=_NOW,
        triggered_by=_MONITOR_SOURCE_ID,
    )
    assert len(events) == 1
    assert events[0].enclosure_id == s.id


@pytest.mark.unit
def test_decide_rejects_empty_reason() -> None:
    s = _state(EnclosurePermitStatus.UNKNOWN)
    with pytest.raises(InvalidEnclosureReasonError):
        decide(
            s,
            _cmd(s.id, EnclosurePermitStatus.PERMITTED, reason=""),
            now=_NOW,
            triggered_by=_MONITOR_SOURCE_ID,
        )


@pytest.mark.unit
def test_decide_rejects_whitespace_only_reason() -> None:
    s = _state(EnclosurePermitStatus.UNKNOWN)
    with pytest.raises(InvalidEnclosureReasonError):
        decide(
            s,
            _cmd(s.id, EnclosurePermitStatus.PERMITTED, reason="   "),
            now=_NOW,
            triggered_by=_MONITOR_SOURCE_ID,
        )


@pytest.mark.unit
def test_decide_rejects_too_long_reason() -> None:
    s = _state(EnclosurePermitStatus.UNKNOWN)
    with pytest.raises(InvalidEnclosureReasonError):
        decide(
            s,
            _cmd(s.id, EnclosurePermitStatus.PERMITTED, reason="a" * 501),
            now=_NOW,
            triggered_by=_MONITOR_SOURCE_ID,
        )


@pytest.mark.unit
def test_decide_trims_reason_on_emitted_event() -> None:
    """`EnclosureReason` trims surrounding whitespace; the trimmed
    value lands on the event payload."""
    s = _state(EnclosurePermitStatus.UNKNOWN)
    events = decide(
        s,
        _cmd(
            s.id,
            EnclosurePermitStatus.PERMITTED,
            reason="  PSS interlock chain healthy  ",
        ),
        now=_NOW,
        triggered_by=_MONITOR_SOURCE_ID,
    )
    assert len(events) == 1
    assert events[0].reason == "PSS interlock chain healthy"


@pytest.mark.unit
def test_decide_is_pure_same_inputs_same_outputs() -> None:
    s = _state(EnclosurePermitStatus.UNKNOWN)
    first = decide(
        s,
        _cmd(s.id, EnclosurePermitStatus.PERMITTED),
        now=_NOW,
        triggered_by=_MONITOR_SOURCE_ID,
    )
    second = decide(
        s,
        _cmd(s.id, EnclosurePermitStatus.PERMITTED),
        now=_NOW,
        triggered_by=_MONITOR_SOURCE_ID,
    )
    assert first == second


# ---------- ordering invariant ----------


@pytest.mark.unit
def test_decide_operator_trigger_on_decommissioned_raises_trigger_not_permitted() -> None:
    """Trigger guard fires BEFORE lifecycle guard.

    On a decommissioned enclosure with `trigger='Operator'`, the decider
    must raise `MonitorTriggerNotPermittedError` (400) rather than
    `EnclosureCannotObserveWhileDecommissionedError` (409). Pins the
    400-vs-409 HTTP contract against a silent decider-refactor flip.
    """
    s = _state(EnclosurePermitStatus.PERMITTED, lifecycle=EnclosureLifecycle.DECOMMISSIONED)
    with pytest.raises(MonitorTriggerNotPermittedError):
        decide(
            s,
            _cmd(s.id, EnclosurePermitStatus.PERMITTED, trigger="Operator"),
            now=_NOW,
            triggered_by=_MONITOR_SOURCE_ID,
        )
