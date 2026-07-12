"""Application-handler tests for the `define_agent` slice.

Focuses on the cross-BC atomic write: every successful `define_agent`
call writes ONE `AgentDefined` event on the Agent stream AND ONE
`ActorRegistered(kind=agent)` event on the Access stream with the
SAME id, via `EventStore.append_streams`.
"""

from datetime import UTC, datetime
from uuid import UUID

import pytest

from cora.access.aggregates.actor import ActorKind
from cora.agent.aggregates.agent import ModelRef
from cora.agent.aggregates.language_model import LanguageModelNotApprovedError
from cora.agent.errors import UnauthorizedError
from cora.agent.features import define_agent
from cora.agent.features.define_agent import DefineAgent
from cora.infrastructure.adapters.in_memory_event_store import InMemoryEventStore
from cora.infrastructure.kernel import Kernel
from cora.infrastructure.ports import LanguageModelLookupResult
from tests.unit._helpers import build_deps as _build_deps_shared
from tests.unit._helpers import make_profile_store

_NOW = datetime(2026, 5, 16, 12, 0, 0, tzinfo=UTC)
_NEW_ID = UUID("01900000-0000-7000-8000-00000000a001")
_AGENT_EVENT_ID = UUID("01900000-0000-7000-8000-00000000a002")
_ACTOR_EVENT_ID = UUID("01900000-0000-7000-8000-00000000a003")
_PRINCIPAL_ID = UUID("01900000-0000-7000-8000-000000000099")
_CORRELATION_ID = UUID("01900000-0000-7000-8000-0000000000aa")


class _FixedLanguageModelLookup:
    """Gate stub: answers every identity with one fixed catalog result
    and records the identities it was asked about."""

    def __init__(self, result: LanguageModelLookupResult | None) -> None:
        self._result = result
        self.calls: list[tuple[str, str]] = []

    async def find_by_model(
        self,
        *,
        provider: str,
        model: str,
    ) -> LanguageModelLookupResult | None:
        self.calls.append((provider, model))
        return self._result


def _build_deps(
    *,
    event_store: InMemoryEventStore | None = None,
    deny: bool = False,
    language_model_lookup: _FixedLanguageModelLookup | None = None,
) -> Kernel:
    return _build_deps_shared(
        # define_agent consumes 3 ids: new agent_id + 1 event_id per stream.
        ids=[_NEW_ID, _AGENT_EVENT_ID, _ACTOR_EVENT_ID],
        now=_NOW,
        event_store=event_store,
        deny=deny,
        language_model_lookup=language_model_lookup,
    )


def _command(**overrides: object) -> DefineAgent:
    base: dict[str, object] = {
        "kind": "RunDebriefer",
        "name": "Run Debrief",
        "version": "v1",
        "model_ref": ModelRef(provider="anthropic", model="claude-sonnet-4-6"),
    }
    base.update(overrides)
    return DefineAgent(**base)  # type: ignore[arg-type]


@pytest.mark.unit
async def test_handler_returns_generated_agent_id() -> None:
    deps = _build_deps()
    handler = define_agent.bind(deps, profile_store=make_profile_store())
    result = await handler(
        _command(),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )
    assert result == _NEW_ID


@pytest.mark.unit
async def test_handler_appends_to_both_agent_and_actor_streams() -> None:
    """Cross-BC atomic write: AgentDefined on Agent stream AND
    ActorRegistered on Actor stream with the SAME id."""
    store = InMemoryEventStore()
    deps = _build_deps(event_store=store)
    handler = define_agent.bind(deps, profile_store=make_profile_store())
    await handler(
        _command(),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )

    agent_events, agent_version = await store.load("Agent", _NEW_ID)
    actor_events, actor_version = await store.load("Actor", _NEW_ID)

    assert agent_version == 1
    assert actor_version == 1
    assert len(agent_events) == 1
    assert len(actor_events) == 1
    assert agent_events[0].event_type == "AgentDefined"
    # PII vault: post-vault writes use the V2 discriminator
    # (legacy "ActorRegistered" string lives only in `from_stored`).
    assert actor_events[0].event_type == "ActorRegisteredV2"


@pytest.mark.unit
async def test_handler_writes_kind_agent_on_actor_event() -> None:
    """The co-written Actor MUST be kind=agent (not human)."""
    store = InMemoryEventStore()
    deps = _build_deps(event_store=store)
    handler = define_agent.bind(deps, profile_store=make_profile_store())
    await handler(
        _command(),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )
    actor_events, _ = await store.load("Actor", _NEW_ID)
    assert actor_events[0].payload["kind"] == ActorKind.AGENT.value


@pytest.mark.unit
async def test_handler_actor_display_name_mirrors_agent_name_via_pii_vault() -> None:
    """At genesis the co-registered Actor's display name (in the
    actor_profile vault) matches the trimmed Agent display name.

    PII vault: the ActorRegistered event itself carries no name;
    the handler upserts the validated AgentName into actor_profile
    before append_streams. Verified via the InMemoryProfileStore.
    """
    store = InMemoryEventStore()
    profile_store = make_profile_store()
    deps = _build_deps(event_store=store)
    handler = define_agent.bind(deps, profile_store=profile_store)
    await handler(
        _command(name="  Run Debrief  "),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )

    actor_events, _ = await store.load("Actor", _NEW_ID)
    assert "name" not in actor_events[0].payload  # PII not on the event

    profile = await profile_store.get(_NEW_ID)
    assert profile is not None
    assert profile.name == "Run Debrief"  # trimmed via AgentName VO


@pytest.mark.unit
async def test_handler_agent_event_carries_full_command() -> None:
    store = InMemoryEventStore()
    deps = _build_deps(event_store=store)
    handler = define_agent.bind(deps, profile_store=make_profile_store())
    await handler(
        _command(
            description="Synthesises terminal Runs.",
            canonical_uri="https://example.org/agents/run-debrief",
            capabilities=frozenset({"summarize"}),
        ),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )
    agent_events, _ = await store.load("Agent", _NEW_ID)
    payload = agent_events[0].payload
    assert payload["kind"] == "RunDebriefer"
    assert payload["name"] == "Run Debrief"
    assert payload["version"] == "v1"
    assert payload["description"] == "Synthesises terminal Runs."
    assert payload["canonical_uri"] == "https://example.org/agents/run-debrief"
    assert payload["capabilities"] == ["summarize"]
    assert payload["model_ref"] == {
        "provider": "anthropic",
        "model": "claude-sonnet-4-6",
        "snapshot_pin": None,
    }


@pytest.mark.unit
async def test_handler_propagates_envelope_fields_to_both_streams() -> None:
    store = InMemoryEventStore()
    deps = _build_deps(event_store=store)
    handler = define_agent.bind(deps, profile_store=make_profile_store())
    await handler(
        _command(),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )
    agent_events, _ = await store.load("Agent", _NEW_ID)
    actor_events, _ = await store.load("Actor", _NEW_ID)
    for events in (agent_events, actor_events):
        stored = events[0]
        assert stored.correlation_id == _CORRELATION_ID
        assert stored.causation_id is None


@pytest.mark.unit
async def test_handler_denies_via_authorize_port() -> None:
    deps = _build_deps(deny=True)
    handler = define_agent.bind(deps, profile_store=make_profile_store())
    with pytest.raises(UnauthorizedError):
        await handler(
            _command(),
            principal_id=_PRINCIPAL_ID,
            correlation_id=_CORRELATION_ID,
        )


@pytest.mark.unit
async def test_handler_denied_does_not_write_either_stream() -> None:
    """Authorize-denial MUST NOT leave events on either stream."""
    store = InMemoryEventStore()
    deps = _build_deps(event_store=store, deny=True)
    handler = define_agent.bind(deps, profile_store=make_profile_store())
    with pytest.raises(UnauthorizedError):
        await handler(
            _command(),
            principal_id=_PRINCIPAL_ID,
            correlation_id=_CORRELATION_ID,
        )
    agent_events, agent_version = await store.load("Agent", _NEW_ID)
    actor_events, actor_version = await store.load("Actor", _NEW_ID)
    assert agent_version == 0
    assert actor_version == 0
    assert agent_events == []
    assert actor_events == []


@pytest.mark.unit
async def test_handler_gate_queries_exactly_the_commands_model_identity() -> None:
    """The gate resolves the command's own model_ref (provider, model),
    once: a drift to a hardcoded identity or a double lookup fails here."""
    lookup = _FixedLanguageModelLookup(
        LanguageModelLookupResult(
            language_model_id=UUID("01900000-0000-7000-8000-00000000d002"),
            status="Approved",
            data_tier="Internal",
            archivability="Alias",
            snapshot_pin=None,
        )
    )
    deps = _build_deps(language_model_lookup=lookup)
    handler = define_agent.bind(deps, profile_store=make_profile_store())
    await handler(
        _command(),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )
    assert lookup.calls == [("anthropic", "claude-sonnet-4-6")]


@pytest.mark.unit
async def test_handler_uncataloged_model_raises_not_approved() -> None:
    """A lookup miss (identity absent from the catalog) refuses the
    registration with status None on the error."""
    deps = _build_deps(language_model_lookup=_FixedLanguageModelLookup(None))
    handler = define_agent.bind(deps, profile_store=make_profile_store())
    with pytest.raises(LanguageModelNotApprovedError) as exc_info:
        await handler(
            _command(),
            principal_id=_PRINCIPAL_ID,
            correlation_id=_CORRELATION_ID,
        )
    assert exc_info.value.provider == "anthropic"
    assert exc_info.value.model == "claude-sonnet-4-6"
    assert exc_info.value.status is None


@pytest.mark.unit
async def test_handler_defined_but_unapproved_model_raises_not_approved() -> None:
    """A Defined entry is registered but not yet usable: the gate
    requires Approved, mirroring the bootstrap-then-promote ceremony."""
    entry = LanguageModelLookupResult(
        language_model_id=UUID("01900000-0000-7000-8000-00000000d001"),
        status="Defined",
        data_tier="Internal",
        archivability="Alias",
        snapshot_pin=None,
    )
    deps = _build_deps(language_model_lookup=_FixedLanguageModelLookup(entry))
    handler = define_agent.bind(deps, profile_store=make_profile_store())
    with pytest.raises(LanguageModelNotApprovedError) as exc_info:
        await handler(
            _command(),
            principal_id=_PRINCIPAL_ID,
            correlation_id=_CORRELATION_ID,
        )
    assert exc_info.value.status == "Defined"


@pytest.mark.unit
async def test_handler_gate_refusal_writes_neither_stream_nor_vault() -> None:
    """The gate runs BEFORE the vault upsert and the atomic append, so a
    refused registration leaves no orphan profile row and no events."""
    store = InMemoryEventStore()
    profile_store = make_profile_store()
    deps = _build_deps(
        event_store=store,
        language_model_lookup=_FixedLanguageModelLookup(None),
    )
    handler = define_agent.bind(deps, profile_store=profile_store)
    with pytest.raises(LanguageModelNotApprovedError):
        await handler(
            _command(),
            principal_id=_PRINCIPAL_ID,
            correlation_id=_CORRELATION_ID,
        )
    agent_events, _ = await store.load("Agent", _NEW_ID)
    actor_events, _ = await store.load("Actor", _NEW_ID)
    assert agent_events == []
    assert actor_events == []
    assert await profile_store.get(_NEW_ID) is None
