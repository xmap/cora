"""Golden-payload corpus pinning every live legacy upcaster arm.

Whenever an aggregate's `from_stored` carries a legacy `event_type`
arm (the Marten / Axon canonical-rename pattern), the only thing
keeping pre-rename payloads replayable is that exact arm. Inline
Hypothesis property tests cover the happy-path round trip but they
do not freeze a realistic golden payload that mirrors what a real
prior deployment would have stored, so a future refactor that
collapses or renames the legacy arm could silently break replay
without a single test going red.

This fitness function walks `tests/fixtures/event_corpus/` and, for
every fixture it finds, calls the matching BC's `from_stored` and
asserts the rebuilt dataclass matches the fixture's `expected`
section. Adding a new legacy arm means dropping one JSON file into
the corpus tree; no new test file required.

## Fixture shape

Each fixture is a self-describing record at
`event_corpus/<bc>/<aggregate>/<event_type>_v<N>[_<variant>].json`:

```json
{
  "event_type": "<wire discriminator>",
  "payload": { ... },
  "expected": {
    "class": "<dataclass name from the <Aggregate>Event union>",
    "<field>": <value>
  }
}
```

The walker pulls the BC + aggregate from the path, looks up the
right `from_stored` in `_BC_REGISTRY`, and the expected dataclass
constructor in `_EVENT_CLASSES`. Add a new BC by extending both
registries; the meta-test below guards against silent walker
breakage (zero-fixture pass).
"""

from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path
from typing import TYPE_CHECKING, Any
from uuid import UUID

import pytest

from cora.access.aggregates.actor import (
    ActorDeactivated,
    ActorKind,
    ActorProfileForgotten,
    ActorRegistered,
)
from cora.access.aggregates.actor import from_stored as actor_from_stored
from cora.agent.aggregates.agent import AgentDefined, ModelRef
from cora.agent.aggregates.agent import from_stored as agent_from_stored
from tests._strategies import make_stored_event

if TYPE_CHECKING:
    from collections.abc import Callable

    from cora.infrastructure.ports.event_store import StoredEvent

_CORPUS_ROOT = Path(__file__).resolve().parents[1] / "fixtures" / "event_corpus"

_BC_REGISTRY: dict[tuple[str, str], tuple[Callable[[StoredEvent], Any], str]] = {
    ("access", "actor"): (actor_from_stored, "Actor"),
    ("agent", "agent"): (agent_from_stored, "Agent"),
}

_EVENT_CLASSES: dict[str, type] = {
    "ActorRegistered": ActorRegistered,
    "ActorDeactivated": ActorDeactivated,
    "ActorProfileForgotten": ActorProfileForgotten,
    "AgentDefined": AgentDefined,
}

_FIELD_COERCERS: dict[str, Callable[[Any], Any]] = {
    "actor_id": lambda v: UUID(v),
    "occurred_at": lambda v: datetime.fromisoformat(v),
    "agent_id": lambda v: UUID(v),
    "model_ref": lambda v: ModelRef(**v),
    "capabilities": lambda v: frozenset(v),
    "prompt_template_id": lambda v: None if v is None else UUID(v),
}

# Keyed by (bc, field) and consulted before `_FIELD_COERCERS`, because a field
# name is only unique within a BC: Actor's `kind` is an enum and Agent's is a
# plain string, so a single global entry for it would coerce one of them wrong.
_BC_FIELD_COERCERS: dict[tuple[str, str], Callable[[Any], Any]] = {
    ("access", "kind"): lambda v: ActorKind(v),
}


def _fixture_files() -> list[Path]:
    return sorted(_CORPUS_ROOT.rglob("*.json"))


def _fixture_id(p: Path) -> str:
    return "/".join(p.relative_to(_CORPUS_ROOT).parts)


def _bc_and_aggregate(p: Path) -> tuple[str, str]:
    rel = p.relative_to(_CORPUS_ROOT).parts
    if len(rel) < 3:
        msg = (
            f"Fixture {p} must live at event_corpus/<bc>/<aggregate>/<file>.json; "
            f"got depth {len(rel)}"
        )
        raise AssertionError(msg)
    return rel[0], rel[1]


def _coercer_for(bc: str, field: str) -> Callable[[Any], Any]:
    scoped = _BC_FIELD_COERCERS.get((bc, field))
    if scoped is not None:
        return scoped
    return _FIELD_COERCERS.get(field, lambda v: v)


def _build_expected(expected: dict[str, Any], bc: str) -> Any:
    class_name = expected["class"]
    if class_name not in _EVENT_CLASSES:
        msg = (
            f"Fixture references unknown dataclass {class_name!r}; "
            f"extend _EVENT_CLASSES in {__file__}"
        )
        raise AssertionError(msg)
    cls = _EVENT_CLASSES[class_name]
    kwargs = {
        field: _coercer_for(bc, field)(value)
        for field, value in expected.items()
        if field != "class"
    }
    return cls(**kwargs)


@pytest.mark.architecture
@pytest.mark.parametrize("fixture_path", _fixture_files(), ids=_fixture_id)
def test_legacy_event_corpus_upcasts_to_current_dataclass(fixture_path: Path) -> None:
    record = json.loads(fixture_path.read_text())
    bc, aggregate = _bc_and_aggregate(fixture_path)
    if (bc, aggregate) not in _BC_REGISTRY:
        msg = (
            f"Fixture {_fixture_id(fixture_path)}: ({bc!r}, {aggregate!r}) "
            f"is not in _BC_REGISTRY. Wire the BC's from_stored before "
            "landing fixtures under that path."
        )
        raise AssertionError(msg)
    from_stored, stream_type = _BC_REGISTRY[(bc, aggregate)]

    stored = make_stored_event(
        stream_type=stream_type,
        event_type=record["event_type"],
        payload=record["payload"],
    )
    actual = from_stored(stored)
    expected = _build_expected(record["expected"], bc)
    assert actual == expected, (
        f"{_fixture_id(fixture_path)}: upcaster produced {actual!r}, expected {expected!r}"
    )


@pytest.mark.architecture
def test_event_corpus_walker_actually_finds_fixtures() -> None:
    """Meta-guard: if the walker silently stops discovering files (corpus
    moved, glob pattern broken, future filesystem refactor), the
    parametrize above degenerates to zero tests and passes vacuously.
    Lock a floor matching the live upcaster arms covered today.
    """
    found = _fixture_files()
    assert len(found) >= 4, (
        f"Expected at least 4 corpus fixtures under {_CORPUS_ROOT}, "
        f"found {len(found)}: {[_fixture_id(p) for p in found]}"
    )
