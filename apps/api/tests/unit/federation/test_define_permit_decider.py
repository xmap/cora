"""Unit tests for the `define_permit` slice's pure decider.

Pin the genesis-collision guard + every field-shape rejection branch
the decider raises on + the direction-matches-terms invariant +
OutboundTerms scope-collapse matrix + handler-injected `new_id`
reproducibility. Slice-level integration (handler -> event-store ->
projection) is covered by the integration suite.
"""

from datetime import UTC, datetime
from uuid import UUID, uuid4

import pytest

from cora.federation.aggregates.permit import (
    AbiTier,
    Direction,
    InboundTerms,
    InvalidPermitScopeError,
    OnwardActionScope,
    OutboundTerms,
    Permit,
    PermitAlreadyExistsError,
    PermitScopeCollapseError,
    PermitStatus,
    ReadScope,
    ScopeRef,
)
from cora.federation.features import define_permit
from cora.federation.features.define_permit import DefinePermit
from cora.shared.identity import ActorId

_NOW = datetime(2026, 5, 30, 12, 0, 0, tzinfo=UTC)
_EXPIRES_AT = datetime(2027, 1, 1, 0, 0, 0, tzinfo=UTC)
_PRINCIPAL_ID = ActorId(UUID("01900000-0000-7000-8000-000000fed001"))
_PERMIT_ID = UUID("01900000-0000-7000-8000-000000fed002")
_NEW_ID = UUID("01900000-0000-7000-8000-000000fed003")
_CREDENTIAL_ID = UUID("01900000-0000-7000-8000-000000fed004")


def _outbound_terms(
    *,
    scopes: frozenset[ScopeRef] | None = None,
    read_scope: ReadScope = ReadScope.READ_ALL_ARTIFACTS,
    onward_action_scope: OnwardActionScope = OnwardActionScope.READ_ONLY,
) -> OutboundTerms:
    return OutboundTerms(
        scopes=scopes
        if scopes is not None
        else frozenset({ScopeRef(kind="dataset", name="public", qualifier=None)}),
        read_scope=read_scope,
        onward_action_scope=onward_action_scope,
    )


def _inbound_terms() -> InboundTerms:
    return InboundTerms(
        inbound_allowed_artifact_kinds=frozenset({"dataset"}),
    )


def _command(**overrides: object) -> DefinePermit:
    base: dict[str, object] = {
        "peer_facility_id": "aps-2bm",
        "direction": Direction.OUTBOUND,
        "allowed_credential_ids": frozenset({_CREDENTIAL_ID}),
        "allowed_payload_types": frozenset({"application/json"}),
        "allowed_artifact_kinds": frozenset({"dataset"}),
        "abi_tier_floor": AbiTier.STABLE,
        "expires_at": _EXPIRES_AT,
        "terms": _outbound_terms(),
    }
    base.update(overrides)
    return DefinePermit(**base)  # type: ignore[arg-type]


def _existing_state() -> Permit:
    return Permit(
        id=_PERMIT_ID,
        peer_facility_id="aps-2bm",
        direction=Direction.OUTBOUND,
        allowed_credential_ids=frozenset({_CREDENTIAL_ID}),
        allowed_payload_types=frozenset({"application/json"}),
        allowed_artifact_kinds=frozenset({"dataset"}),
        abi_tier_floor=AbiTier.STABLE,
        expires_at=_EXPIRES_AT,
        defined_by=_PRINCIPAL_ID,
        defined_at=_NOW,
        status=PermitStatus.DEFINED,
        terms=_outbound_terms(),
    )


@pytest.mark.unit
def test_define_permit_emits_event_for_valid_outbound_command() -> None:
    events = define_permit.decide(
        state=None,
        command=_command(),
        now=_NOW,
        new_id=_NEW_ID,
        defined_by=_PRINCIPAL_ID,
    )
    assert len(events) == 1
    event = events[0]
    assert event.permit_id == _NEW_ID
    assert event.peer_facility_id == "aps-2bm"
    assert event.direction is Direction.OUTBOUND
    assert event.allowed_credential_ids == frozenset({_CREDENTIAL_ID})
    assert event.allowed_payload_types == frozenset({"application/json"})
    assert event.allowed_artifact_kinds == frozenset({"dataset"})
    assert event.abi_tier_floor is AbiTier.STABLE
    assert event.expires_at == _EXPIRES_AT
    assert event.defined_by == _PRINCIPAL_ID
    assert isinstance(event.terms, OutboundTerms)
    assert event.occurred_at == _NOW


@pytest.mark.unit
def test_define_permit_emits_event_for_valid_inbound_command() -> None:
    events = define_permit.decide(
        state=None,
        command=_command(direction=Direction.INBOUND, terms=_inbound_terms()),
        now=_NOW,
        new_id=_NEW_ID,
        defined_by=_PRINCIPAL_ID,
    )
    assert len(events) == 1
    event = events[0]
    assert event.direction is Direction.INBOUND
    assert isinstance(event.terms, InboundTerms)


@pytest.mark.unit
def test_define_permit_trims_peer_facility_id() -> None:
    events = define_permit.decide(
        state=None,
        command=_command(peer_facility_id="  aps-2bm  "),
        now=_NOW,
        new_id=_NEW_ID,
        defined_by=_PRINCIPAL_ID,
    )
    assert events[0].peer_facility_id == "aps-2bm"


@pytest.mark.unit
def test_define_permit_rejects_when_state_already_exists() -> None:
    with pytest.raises(PermitAlreadyExistsError):
        define_permit.decide(
            state=_existing_state(),
            command=_command(),
            now=_NOW,
            new_id=_NEW_ID,
            defined_by=_PRINCIPAL_ID,
        )


@pytest.mark.unit
def test_define_permit_rejects_empty_peer_facility_id() -> None:
    with pytest.raises(InvalidPermitScopeError):
        define_permit.decide(
            state=None,
            command=_command(peer_facility_id=""),
            now=_NOW,
            new_id=_NEW_ID,
            defined_by=_PRINCIPAL_ID,
        )


@pytest.mark.unit
def test_define_permit_rejects_whitespace_only_peer_facility_id() -> None:
    with pytest.raises(InvalidPermitScopeError):
        define_permit.decide(
            state=None,
            command=_command(peer_facility_id="   "),
            now=_NOW,
            new_id=_NEW_ID,
            defined_by=_PRINCIPAL_ID,
        )


@pytest.mark.unit
def test_define_permit_rejects_expires_at_in_the_past() -> None:
    with pytest.raises(InvalidPermitScopeError):
        define_permit.decide(
            state=None,
            command=_command(expires_at=datetime(2025, 1, 1, 0, 0, 0, tzinfo=UTC)),
            now=_NOW,
            new_id=_NEW_ID,
            defined_by=_PRINCIPAL_ID,
        )


@pytest.mark.unit
def test_define_permit_rejects_expires_at_equal_to_now() -> None:
    """Strict inequality: expires_at must be > now."""
    with pytest.raises(InvalidPermitScopeError):
        define_permit.decide(
            state=None,
            command=_command(expires_at=_NOW),
            now=_NOW,
            new_id=_NEW_ID,
            defined_by=_PRINCIPAL_ID,
        )


@pytest.mark.unit
def test_define_permit_rejects_empty_allowed_credential_ids() -> None:
    with pytest.raises(InvalidPermitScopeError):
        define_permit.decide(
            state=None,
            command=_command(allowed_credential_ids=frozenset[str]()),
            now=_NOW,
            new_id=_NEW_ID,
            defined_by=_PRINCIPAL_ID,
        )


@pytest.mark.unit
def test_define_permit_rejects_empty_allowed_payload_types() -> None:
    with pytest.raises(InvalidPermitScopeError):
        define_permit.decide(
            state=None,
            command=_command(allowed_payload_types=frozenset[str]()),
            now=_NOW,
            new_id=_NEW_ID,
            defined_by=_PRINCIPAL_ID,
        )


@pytest.mark.unit
def test_define_permit_rejects_whitespace_only_allowed_payload_type_entry() -> None:
    with pytest.raises(InvalidPermitScopeError):
        define_permit.decide(
            state=None,
            command=_command(allowed_payload_types=frozenset({"application/json", "   "})),
            now=_NOW,
            new_id=_NEW_ID,
            defined_by=_PRINCIPAL_ID,
        )


@pytest.mark.unit
def test_define_permit_rejects_empty_allowed_artifact_kinds() -> None:
    with pytest.raises(InvalidPermitScopeError):
        define_permit.decide(
            state=None,
            command=_command(allowed_artifact_kinds=frozenset[str]()),
            now=_NOW,
            new_id=_NEW_ID,
            defined_by=_PRINCIPAL_ID,
        )


@pytest.mark.unit
def test_define_permit_rejects_whitespace_only_allowed_artifact_kind_entry() -> None:
    with pytest.raises(InvalidPermitScopeError):
        define_permit.decide(
            state=None,
            command=_command(allowed_artifact_kinds=frozenset({"dataset", "   "})),
            now=_NOW,
            new_id=_NEW_ID,
            defined_by=_PRINCIPAL_ID,
        )


@pytest.mark.unit
def test_define_permit_rejects_outbound_direction_with_inbound_terms() -> None:
    with pytest.raises(InvalidPermitScopeError):
        define_permit.decide(
            state=None,
            command=_command(direction=Direction.OUTBOUND, terms=_inbound_terms()),
            now=_NOW,
            new_id=_NEW_ID,
            defined_by=_PRINCIPAL_ID,
        )


@pytest.mark.unit
def test_define_permit_rejects_inbound_direction_with_outbound_terms() -> None:
    with pytest.raises(InvalidPermitScopeError):
        define_permit.decide(
            state=None,
            command=_command(direction=Direction.INBOUND, terms=_outbound_terms()),
            now=_NOW,
            new_id=_NEW_ID,
            defined_by=_PRINCIPAL_ID,
        )


@pytest.mark.unit
def test_define_permit_rejects_outbound_terms_with_empty_scopes() -> None:
    with pytest.raises(InvalidPermitScopeError):
        define_permit.decide(
            state=None,
            command=_command(terms=_outbound_terms(scopes=frozenset())),
            now=_NOW,
            new_id=_NEW_ID,
            defined_by=_PRINCIPAL_ID,
        )


@pytest.mark.unit
def test_define_permit_rejects_outbound_terms_collapse_matrix() -> None:
    """ListMetadataOnly + MayExportOffPlatform: no carrier to export."""
    with pytest.raises(PermitScopeCollapseError):
        define_permit.decide(
            state=None,
            command=_command(
                terms=_outbound_terms(
                    read_scope=ReadScope.LIST_METADATA_ONLY,
                    onward_action_scope=OnwardActionScope.MAY_EXPORT_OFF_PLATFORM,
                )
            ),
            now=_NOW,
            new_id=_NEW_ID,
            defined_by=_PRINCIPAL_ID,
        )


@pytest.mark.unit
def test_define_permit_is_pure_same_inputs_same_outputs() -> None:
    first = define_permit.decide(
        state=None,
        command=_command(),
        now=_NOW,
        new_id=_NEW_ID,
        defined_by=_PRINCIPAL_ID,
    )
    second = define_permit.decide(
        state=None,
        command=_command(),
        now=_NOW,
        new_id=_NEW_ID,
        defined_by=_PRINCIPAL_ID,
    )
    assert first == second


@pytest.mark.unit
def test_define_permit_is_immune_to_uuid4_stub() -> None:
    """Sanity: handler-injected new_id is used verbatim; decider doesn't call uuid4()."""
    new_id = uuid4()
    events = define_permit.decide(
        state=None,
        command=_command(),
        now=_NOW,
        new_id=new_id,
        defined_by=_PRINCIPAL_ID,
    )
    assert events[0].permit_id == new_id
