"""Pure-decider tests for `register_caution` slice."""

from datetime import UTC, datetime, timedelta
from uuid import UUID, uuid4

import pytest

from cora.caution.aggregates.caution import (
    AssetTarget,
    Caution,
    CautionAlreadyExistsError,
    CautionCategory,
    CautionRegistered,
    CautionSeverity,
    CautionText,
    CautionWorkaround,
    InvalidCautionExpiresAtError,
    InvalidCautionTagError,
    InvalidCautionTextError,
    InvalidCautionWorkaroundError,
    ProcedureTarget,
)
from cora.caution.features import register_caution
from cora.caution.features.register_caution import RegisterCaution
from cora.shared.identity import ActorId

_NOW = datetime(2026, 5, 16, 12, 0, 0, tzinfo=UTC)
_ASSET_ID = UUID("01900000-0000-7000-8000-00000000e001")
_AUTHOR_ID = ActorId(UUID("01900000-0000-7000-8000-00000000e002"))


def _command(**overrides: object) -> RegisterCaution:
    base: dict[str, object] = {
        "target": AssetTarget(asset_id=_ASSET_ID),
        "category": CautionCategory.WEAR,
        "severity": CautionSeverity.CAUTION,
        "text": "hexapod stalls below 0.5 mm/s",
        "workaround": "run at 0.6 mm/s",
    }
    base.update(overrides)
    return RegisterCaution(**base)  # type: ignore[arg-type]


@pytest.mark.unit
def test_decide_emits_caution_registered_when_stream_is_empty() -> None:
    new_id = uuid4()
    events = register_caution.decide(
        state=None,
        command=_command(),
        now=_NOW,
        new_id=new_id,
        authored_by=_AUTHOR_ID,
    )
    assert events == [
        CautionRegistered(
            caution_id=new_id,
            target=AssetTarget(asset_id=_ASSET_ID),
            category="Wear",
            severity="Caution",
            text="hexapod stalls below 0.5 mm/s",
            workaround="run at 0.6 mm/s",
            tags=frozenset(),
            authored_by=_AUTHOR_ID,
            expires_at=None,
            propagate_to_children=False,
            parent_id=None,
            occurred_at=_NOW,
        )
    ]


@pytest.mark.unit
def test_decide_top_level_register_has_no_parent_id() -> None:
    """Anti-hook discipline: top-level registers always have parent_id=None;
    supersession-child genesis is the only path that sets it."""
    events = register_caution.decide(
        state=None, command=_command(), now=_NOW, new_id=uuid4(), authored_by=_AUTHOR_ID
    )
    assert events[0].parent_id is None


@pytest.mark.unit
def test_decide_carries_procedure_target() -> None:
    procedure_id = uuid4()
    events = register_caution.decide(
        state=None,
        command=_command(target=ProcedureTarget(procedure_id=procedure_id)),
        now=_NOW,
        new_id=uuid4(),
        authored_by=_AUTHOR_ID,
    )
    assert events[0].target == ProcedureTarget(procedure_id=procedure_id)


@pytest.mark.unit
def test_decide_trims_text_and_workaround() -> None:
    events = register_caution.decide(
        state=None,
        command=_command(text="  stalls  ", workaround="  go faster  "),
        now=_NOW,
        new_id=uuid4(),
        authored_by=_AUTHOR_ID,
    )
    assert events[0].text == "stalls"
    assert events[0].workaround == "go faster"


@pytest.mark.unit
def test_decide_trims_tags() -> None:
    events = register_caution.decide(
        state=None,
        command=_command(tags=frozenset({"  motion  ", "  electrical  "})),
        now=_NOW,
        new_id=uuid4(),
        authored_by=_AUTHOR_ID,
    )
    assert events[0].tags == frozenset({"motion", "electrical"})


@pytest.mark.unit
def test_decide_accepts_empty_tags() -> None:
    events = register_caution.decide(
        state=None,
        command=_command(tags=frozenset[str]()),
        now=_NOW,
        new_id=uuid4(),
        authored_by=_AUTHOR_ID,
    )
    assert events[0].tags == frozenset()


@pytest.mark.unit
def test_decide_rejects_existing_state() -> None:
    existing = Caution(
        id=uuid4(),
        target=AssetTarget(asset_id=_ASSET_ID),
        category=CautionCategory.WEAR,
        severity=CautionSeverity.CAUTION,
        text=CautionText("existing"),
        workaround=CautionWorkaround("workaround"),
        authored_by=_AUTHOR_ID,
    )
    with pytest.raises(CautionAlreadyExistsError) as exc_info:
        register_caution.decide(
            state=existing, command=_command(), now=_NOW, new_id=uuid4(), authored_by=_AUTHOR_ID
        )
    assert exc_info.value.caution_id == existing.id


@pytest.mark.unit
def test_decide_rejects_empty_text() -> None:
    with pytest.raises(InvalidCautionTextError):
        register_caution.decide(
            state=None,
            command=_command(text="   "),
            now=_NOW,
            new_id=uuid4(),
            authored_by=_AUTHOR_ID,
        )


@pytest.mark.unit
def test_decide_rejects_too_long_text() -> None:
    with pytest.raises(InvalidCautionTextError):
        register_caution.decide(
            state=None,
            command=_command(text="a" * 2001),
            now=_NOW,
            new_id=uuid4(),
            authored_by=_AUTHOR_ID,
        )


@pytest.mark.unit
def test_decide_rejects_empty_workaround() -> None:
    """Anti-hook #1: workaround is REQUIRED — never optional."""
    with pytest.raises(InvalidCautionWorkaroundError):
        register_caution.decide(
            state=None,
            command=_command(workaround="   "),
            now=_NOW,
            new_id=uuid4(),
            authored_by=_AUTHOR_ID,
        )


@pytest.mark.unit
def test_decide_rejects_too_long_workaround() -> None:
    with pytest.raises(InvalidCautionWorkaroundError):
        register_caution.decide(
            state=None,
            command=_command(workaround="a" * 2001),
            now=_NOW,
            new_id=uuid4(),
            authored_by=_AUTHOR_ID,
        )


@pytest.mark.unit
def test_decide_rejects_too_long_tag() -> None:
    with pytest.raises(InvalidCautionTagError):
        register_caution.decide(
            state=None,
            command=_command(tags=frozenset({"a" * 51})),
            now=_NOW,
            new_id=uuid4(),
            authored_by=_AUTHOR_ID,
        )


@pytest.mark.unit
def test_decide_rejects_whitespace_only_tag() -> None:
    with pytest.raises(InvalidCautionTagError):
        register_caution.decide(
            state=None,
            command=_command(tags=frozenset({"   "})),
            now=_NOW,
            new_id=uuid4(),
            authored_by=_AUTHOR_ID,
        )


@pytest.mark.unit
def test_decide_rejects_past_expires_at() -> None:
    past = _NOW - timedelta(days=1)
    with pytest.raises(InvalidCautionExpiresAtError):
        register_caution.decide(
            state=None,
            command=_command(expires_at=past),
            now=_NOW,
            new_id=uuid4(),
            authored_by=_AUTHOR_ID,
        )


@pytest.mark.unit
def test_decide_rejects_expires_at_equal_to_now() -> None:
    """`expires_at <= now` is rejected; strict-future required."""
    with pytest.raises(InvalidCautionExpiresAtError):
        register_caution.decide(
            state=None,
            command=_command(expires_at=_NOW),
            now=_NOW,
            new_id=uuid4(),
            authored_by=_AUTHOR_ID,
        )


@pytest.mark.unit
def test_decide_accepts_future_expires_at() -> None:
    future = _NOW + timedelta(days=7)
    events = register_caution.decide(
        state=None,
        command=_command(expires_at=future),
        now=_NOW,
        new_id=uuid4(),
        authored_by=_AUTHOR_ID,
    )
    assert events[0].expires_at == future


@pytest.mark.unit
def test_decide_accepts_none_expires_at() -> None:
    events = register_caution.decide(
        state=None,
        command=_command(expires_at=None),
        now=_NOW,
        new_id=uuid4(),
        authored_by=_AUTHOR_ID,
    )
    assert events[0].expires_at is None


@pytest.mark.unit
def test_decide_carries_propagate_to_children_when_set() -> None:
    events = register_caution.decide(
        state=None,
        command=_command(propagate_to_children=True),
        now=_NOW,
        new_id=uuid4(),
        authored_by=_AUTHOR_ID,
    )
    assert events[0].propagate_to_children is True


@pytest.mark.unit
def test_decide_is_pure_same_inputs_same_outputs() -> None:
    new_id = uuid4()
    command = _command()
    first = register_caution.decide(
        state=None, command=command, now=_NOW, new_id=new_id, authored_by=_AUTHOR_ID
    )
    second = register_caution.decide(
        state=None, command=command, now=_NOW, new_id=new_id, authored_by=_AUTHOR_ID
    )
    assert first == second
