"""Unit tests for the Federation actor-stamping update-handler factory.

Covers: (a) the envelope `principal_id` flows under the supplied
`actor_kwarg` into the decider; (b) decider-raised exceptions
propagate without wrapping; (c) the Authorize-port `Deny` branch
raises `UnauthorizedError` and writes nothing; (d) the Seal
`resolve_stream_id` override targets the deterministic stream UUID
without changing the log field name; (e) the three per-aggregate
wrappers compose cleanly over each aggregate's codec quartet.
"""

from datetime import UTC, datetime
from typing import Any
from uuid import UUID

import pytest

from cora.federation._actor_update_handler import (
    make_credential_update_handler,
    make_permit_update_handler,
    make_seal_update_handler,
)
from cora.federation.aggregates.credential import (
    CredentialRotationStarted,
)
from cora.federation.aggregates.permit import (
    PermitSuspended,
)
from cora.federation.aggregates.seal import (
    SealRepublishingStarted,
)
from cora.federation.aggregates.seal._stream_id import seal_stream_id
from cora.federation.errors import UnauthorizedError
from cora.infrastructure.adapters.in_memory_event_store import InMemoryEventStore
from cora.shared.identity import ActorId
from tests.unit._helpers import build_deps as _build_deps_shared
from tests.unit.federation._helpers import (
    seed_active_credential,
    seed_active_permit,
    seed_live_seal,
)

_T0 = datetime(2026, 5, 30, 10, 0, 0, tzinfo=UTC)
_T1 = datetime(2026, 5, 30, 11, 0, 0, tzinfo=UTC)
_T2 = datetime(2026, 5, 30, 12, 0, 0, tzinfo=UTC)
_EXPIRES_AT = datetime(2027, 5, 30, 12, 0, 0, tzinfo=UTC)
_PERMIT_ID = UUID("01900000-0000-7000-8000-0000000aa001")
_CRED_ID = UUID("01900000-0000-7000-8000-0000000aa002")
_GENESIS_ID = UUID("01900000-0000-7000-8000-0000000aa003")
_ACTIVATE_ID = UUID("01900000-0000-7000-8000-0000000aa004")
_NEXT_EVENT_ID = UUID("01900000-0000-7000-8000-0000000aa005")
_PRINCIPAL_ID = UUID("01900000-0000-7000-8000-00000000aa99")
_CORRELATION_ID = UUID("01900000-0000-7000-8000-00000000aaaa")
_FACILITY_ID = "aps-2bm"


class _BoomError(Exception):
    """Sentinel error class used to verify exception passthrough."""


@pytest.mark.unit
async def test_factory_passes_principal_id_under_actor_kwarg() -> None:
    """The factory injects `principal_id` into the decider under the
    supplied `actor_kwarg` name, on top of state/command/now."""
    captured: dict[str, Any] = {}

    def fake_decide(
        *,
        state: Any,
        command: Any,
        now: datetime,
        suspended_by: UUID,
    ) -> list[PermitSuspended]:
        captured["state"] = state
        captured["command"] = command
        captured["now"] = now
        captured["suspended_by"] = suspended_by
        return [
            PermitSuspended(
                permit_id=command.permit_id,
                suspended_by=suspended_by,
                occurred_at=now,
            )
        ]

    store = InMemoryEventStore()
    await seed_active_permit(
        store,
        permit_id=_PERMIT_ID,
        genesis_event_id=_GENESIS_ID,
        activate_event_id=_ACTIVATE_ID,
        correlation_id=_CORRELATION_ID,
        principal_id=_PRINCIPAL_ID,
        defined_at=_T0,
        activated_at=_T1,
        expires_at=_EXPIRES_AT,
    )
    deps = _build_deps_shared(ids=[_NEXT_EVENT_ID], now=_T2, event_store=store)
    handler = make_permit_update_handler(
        deps,
        command_name="SuspendPermit",
        log_prefix="suspend_permit",
        decide_fn=fake_decide,
        actor_kwarg="suspended_by",
    )

    class _Cmd:
        permit_id = _PERMIT_ID

    await handler(
        _Cmd(),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )

    assert captured["suspended_by"] == _PRINCIPAL_ID
    assert captured["now"] == _T2
    events, version = await store.load("Permit", _PERMIT_ID)
    assert version == 3
    assert events[-1].payload["suspended_by"] == str(_PRINCIPAL_ID)


@pytest.mark.unit
async def test_factory_propagates_decider_exception_without_wrapping() -> None:
    """A decider-raised exception bubbles out as the same class
    (the factory does not wrap or translate domain errors)."""

    def boom_decide(
        *,
        state: Any,
        command: Any,
        now: datetime,
        suspended_by: UUID,
    ) -> list[PermitSuspended]:
        _ = (state, command, now, suspended_by)
        raise _BoomError("decider rejected")

    store = InMemoryEventStore()
    await seed_active_permit(
        store,
        permit_id=_PERMIT_ID,
        genesis_event_id=_GENESIS_ID,
        activate_event_id=_ACTIVATE_ID,
        correlation_id=_CORRELATION_ID,
        principal_id=_PRINCIPAL_ID,
        defined_at=_T0,
        activated_at=_T1,
        expires_at=_EXPIRES_AT,
    )
    deps = _build_deps_shared(ids=[_NEXT_EVENT_ID], now=_T2, event_store=store)
    handler = make_permit_update_handler(
        deps,
        command_name="SuspendPermit",
        log_prefix="suspend_permit",
        decide_fn=boom_decide,
        actor_kwarg="suspended_by",
    )

    class _Cmd:
        permit_id = _PERMIT_ID

    with pytest.raises(_BoomError):
        await handler(
            _Cmd(),
            principal_id=_PRINCIPAL_ID,
            correlation_id=_CORRELATION_ID,
        )
    _, version = await store.load("Permit", _PERMIT_ID)
    assert version == 2  # untouched after decider rejection


@pytest.mark.unit
async def test_factory_raises_unauthorized_and_skips_decide_on_deny() -> None:
    """Authz `Deny` raises `UnauthorizedError` and never calls the decider."""
    called = False

    def fake_decide(
        *,
        state: Any,
        command: Any,
        now: datetime,
        suspended_by: UUID,
    ) -> list[PermitSuspended]:
        nonlocal called
        called = True
        _ = (state, command, now, suspended_by)
        return []

    store = InMemoryEventStore()
    await seed_active_permit(
        store,
        permit_id=_PERMIT_ID,
        genesis_event_id=_GENESIS_ID,
        activate_event_id=_ACTIVATE_ID,
        correlation_id=_CORRELATION_ID,
        principal_id=_PRINCIPAL_ID,
        defined_at=_T0,
        activated_at=_T1,
        expires_at=_EXPIRES_AT,
    )
    deps = _build_deps_shared(ids=[_NEXT_EVENT_ID], now=_T2, event_store=store, deny=True)
    handler = make_permit_update_handler(
        deps,
        command_name="SuspendPermit",
        log_prefix="suspend_permit",
        decide_fn=fake_decide,
        actor_kwarg="suspended_by",
    )

    class _Cmd:
        permit_id = _PERMIT_ID

    with pytest.raises(UnauthorizedError):
        await handler(
            _Cmd(),
            principal_id=_PRINCIPAL_ID,
            correlation_id=_CORRELATION_ID,
        )
    assert called is False
    _, version = await store.load("Permit", _PERMIT_ID)
    assert version == 2


@pytest.mark.unit
async def test_credential_wrapper_stamps_actor_under_supplied_kwarg() -> None:
    """The Credential per-aggregate wrapper threads `principal_id` as
    `rotation_started_by` (or whatever `actor_kwarg` names)."""

    def fake_decide(
        *,
        state: Any,
        command: Any,
        now: datetime,
        rotation_started_by: UUID,
    ) -> list[CredentialRotationStarted]:
        _ = (state, command)
        return [
            CredentialRotationStarted(
                credential_id=command.credential_id,
                pending_secret_ref="vault://pending/v2",
                pending_public_material_ref="vault://pending/pub/v2",
                rotation_started_by=rotation_started_by,
                occurred_at=now,
            )
        ]

    store = InMemoryEventStore()
    await seed_active_credential(
        store,
        credential_id=_CRED_ID,
        genesis_event_id=_GENESIS_ID,
        correlation_id=_CORRELATION_ID,
        principal_id=_PRINCIPAL_ID,
        registered_at=_T0,
        expires_at=_EXPIRES_AT,
    )
    deps = _build_deps_shared(ids=[_NEXT_EVENT_ID], now=_T2, event_store=store)
    handler = make_credential_update_handler(
        deps,
        command_name="StartCredentialRotation",
        log_prefix="start_credential_rotation",
        decide_fn=fake_decide,
        actor_kwarg="rotation_started_by",
    )

    class _Cmd:
        credential_id = _CRED_ID

    await handler(
        _Cmd(),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )
    events, version = await store.load("Credential", _CRED_ID)
    assert version == 2
    assert events[-1].event_type == "CredentialRotationStarted"
    assert events[-1].payload["rotation_started_by"] == str(_PRINCIPAL_ID)


@pytest.mark.unit
async def test_seal_wrapper_resolves_stream_via_seal_stream_id() -> None:
    """Seal wrapper routes load/append through `seal_stream_id(facility_id)`
    so the per-facility singleton stream stays addressable from a str id."""
    expected_stream = seal_stream_id(_FACILITY_ID)

    def fake_decide(
        *,
        state: Any,
        command: Any,
        now: datetime,
        started_by: ActorId,
    ) -> list[SealRepublishingStarted]:
        _ = state
        return [
            SealRepublishingStarted(
                facility_id=command.facility_id,
                started_by=started_by,
                occurred_at=now,
            )
        ]

    store = InMemoryEventStore()
    await seed_live_seal(
        store,
        stream_id=expected_stream,
        genesis_event_id=_GENESIS_ID,
        correlation_id=_CORRELATION_ID,
        principal_id=_PRINCIPAL_ID,
        initialized_at=_T0,
        facility_id=_FACILITY_ID,
    )
    deps = _build_deps_shared(ids=[_NEXT_EVENT_ID], now=_T2, event_store=store)
    handler = make_seal_update_handler(
        deps,
        command_name="StartSealRepublishing",
        log_prefix="start_seal_republishing",
        decide_fn=fake_decide,
        actor_kwarg="started_by",
    )

    class _Cmd:
        facility_id = _FACILITY_ID

    await handler(
        _Cmd(),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )
    events, version = await store.load("Seal", expected_stream)
    assert version == 2
    assert events[-1].event_type == "SealRepublishingStarted"
    assert events[-1].payload["started_by"] == str(_PRINCIPAL_ID)
    assert events[-1].payload["facility_id"] == _FACILITY_ID


@pytest.mark.unit
async def test_factory_appends_after_decide_so_decider_errors_leave_stream_intact() -> None:
    """Append happens AFTER decide returns; a decider raise leaves the
    underlying stream byte-identical (no half-write)."""

    def boom_decide(
        *,
        state: Any,
        command: Any,
        now: datetime,
        suspended_by: UUID,
    ) -> list[PermitSuspended]:
        _ = (state, command, now, suspended_by)
        raise ValueError("decider rejected")

    store = InMemoryEventStore()
    await seed_active_permit(
        store,
        permit_id=_PERMIT_ID,
        genesis_event_id=_GENESIS_ID,
        activate_event_id=_ACTIVATE_ID,
        correlation_id=_CORRELATION_ID,
        principal_id=_PRINCIPAL_ID,
        defined_at=_T0,
        activated_at=_T1,
        expires_at=_EXPIRES_AT,
    )
    before_events, before_version = await store.load("Permit", _PERMIT_ID)
    deps = _build_deps_shared(ids=[_NEXT_EVENT_ID], now=_T2, event_store=store)
    handler = make_permit_update_handler(
        deps,
        command_name="SuspendPermit",
        log_prefix="suspend_permit",
        decide_fn=boom_decide,
        actor_kwarg="suspended_by",
    )

    class _Cmd:
        permit_id = _PERMIT_ID

    with pytest.raises(ValueError):
        await handler(
            _Cmd(),
            principal_id=_PRINCIPAL_ID,
            correlation_id=_CORRELATION_ID,
        )
    after_events, after_version = await store.load("Permit", _PERMIT_ID)
    assert after_version == before_version
    assert len(after_events) == len(before_events)
