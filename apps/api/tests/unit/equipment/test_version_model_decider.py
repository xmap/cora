"""Pure-decider tests for the `version_model` slice.

Multi-source-state guard: `Defined | Versioned -> Versioned`. Both
source states are valid; only Deprecated is rejected. Bounded-text VOs
(name, part_number, version_tag) and `declared_families` cardinality
are validated defensively in the decider so direct callers get the same
protection as API-boundary callers.
"""

from datetime import UTC, datetime
from uuid import uuid4

import pytest

from cora.equipment.aggregates.model import (
    InvalidDeclaredFamiliesError,
    InvalidModelNameError,
    InvalidModelVersionTagError,
    InvalidPartNumberError,
    Manufacturer,
    ManufacturerName,
    Model,
    ModelCannotVersionError,
    ModelName,
    ModelNotFoundError,
    ModelStatus,
    ModelVersioned,
    PartNumber,
)
from cora.equipment.features import version_model
from cora.equipment.features.version_model import VersionModel

_NOW = datetime(2026, 6, 1, 12, 0, tzinfo=UTC)


def _model(
    *,
    status: ModelStatus = ModelStatus.DEFINED,
    version: str | None = None,
) -> Model:
    return Model(
        id=uuid4(),
        name=ModelName("Aerotech ANT130-L"),
        manufacturer=Manufacturer(name=ManufacturerName("Aerotech")),
        part_number=PartNumber("ANT130-L"),
        declared_families=frozenset({uuid4()}),
        status=status,
        version=version,
    )


def _command(
    model_id: object,
    *,
    name: str = "Aerotech ANT130-L rev-B",
    part_number: str = "ANT130-L-B",
    version_tag: str = "v2",
    declared_families: frozenset[object] | None = None,
) -> VersionModel:
    return VersionModel(
        model_id=model_id,  # type: ignore[arg-type]
        name=name,
        manufacturer=Manufacturer(name=ManufacturerName("Aerotech")),
        part_number=part_number,
        declared_families=declared_families  # type: ignore[arg-type]
        if declared_families is not None
        else frozenset({uuid4()}),
        version_tag=version_tag,
    )


@pytest.mark.unit
@pytest.mark.parametrize(
    "source",
    [ModelStatus.DEFINED, ModelStatus.VERSIONED],
)
def test_decide_emits_model_versioned_for_each_allowed_source_status(
    source: ModelStatus,
) -> None:
    """Both Defined and Versioned are valid sources; the emitted event
    carries the same wholesale-replacement payload regardless of which
    one preceded."""
    state = _model(status=source)
    new_families = frozenset({uuid4(), uuid4()})
    events = version_model.decide(
        state=state,
        command=_command(
            state.id,
            name="Aerotech ANT130-L rev-B",
            part_number="ANT130-L-B",
            version_tag="v2",
            declared_families=new_families,
        ),
        now=_NOW,
    )
    assert events == [
        ModelVersioned(
            model_id=state.id,
            name="Aerotech ANT130-L rev-B",
            manufacturer=Manufacturer(name=ManufacturerName("Aerotech")),
            part_number="ANT130-L-B",
            declared_families=new_families,
            version_tag="v2",
            occurred_at=_NOW,
        )
    ]


@pytest.mark.unit
def test_decide_raises_model_not_found_when_state_is_none() -> None:
    target_id = uuid4()
    with pytest.raises(ModelNotFoundError) as exc_info:
        version_model.decide(
            state=None,
            command=_command(target_id),
            now=_NOW,
        )
    assert exc_info.value.model_id == target_id


@pytest.mark.unit
def test_decide_raises_cannot_version_for_deprecated_status() -> None:
    """Deprecated is the only disallowed source state. Re-versioning a
    deprecated model raises (would otherwise un-deprecate via side
    effect)."""
    state = _model(status=ModelStatus.DEPRECATED, version="v1")
    with pytest.raises(ModelCannotVersionError) as exc_info:
        version_model.decide(
            state=state,
            command=_command(state.id),
            now=_NOW,
        )
    assert exc_info.value.model_id == state.id
    assert exc_info.value.current_status is ModelStatus.DEPRECATED


@pytest.mark.unit
def test_decide_rejects_empty_declared_families() -> None:
    state = _model()
    with pytest.raises(InvalidDeclaredFamiliesError):
        version_model.decide(
            state=state,
            command=_command(state.id, declared_families=frozenset()),
            now=_NOW,
        )


@pytest.mark.unit
def test_decide_rejects_invalid_name() -> None:
    state = _model()
    with pytest.raises(InvalidModelNameError):
        version_model.decide(
            state=state,
            command=_command(state.id, name="   "),
            now=_NOW,
        )


@pytest.mark.unit
def test_decide_rejects_invalid_part_number() -> None:
    state = _model()
    with pytest.raises(InvalidPartNumberError):
        version_model.decide(
            state=state,
            command=_command(state.id, part_number=""),
            now=_NOW,
        )


@pytest.mark.unit
def test_decide_rejects_invalid_version_tag_for_whitespace_only() -> None:
    state = _model()
    with pytest.raises(InvalidModelVersionTagError):
        version_model.decide(
            state=state,
            command=_command(state.id, version_tag="   "),
            now=_NOW,
        )


@pytest.mark.unit
def test_decide_allows_versioning_with_same_tag_for_re_attestation() -> None:
    """Deliberate divergence from strict-not-idempotent: calling
    version_model with a tag that already matches state.version
    succeeds rather than raising. Re-attestation is a legitimate audit
    moment, mirroring the version_family precedent."""
    state = _model(status=ModelStatus.VERSIONED, version="v2")
    events = version_model.decide(
        state=state,
        command=_command(state.id, version_tag="v2"),
        now=_NOW,
    )
    assert len(events) == 1
    assert events[0].version_tag == "v2"
