"""A seeded Agent's language model is checked against the approved catalog.

`define_agent` applies this check to an operator. Until now no seeded Agent
passed it: `seed_agent` builds its events and calls `append_streams` itself
rather than going through that handler, so of twenty seeded Agents, zero were
gated, including the two that think with real models.

## What "armed" means here, and what it does not

The Kernel's default `language_model_lookup` is
`AlwaysApprovedLanguageModelLookup`, a permissive stub, and this gate inherits
that exactly as `define_agent`'s does: it bites where the composition root
binds `PostgresLanguageModelLookup`, and passes everything where it does not.
That default predates this gate and is deliberate, so it is not changed here,
but it does mean the check is armed by the deployment rather than by the code.
These tests inject a refusing lookup so the behaviour is asserted rather than
assumed from a stub that says yes to everything.
"""

from datetime import UTC, datetime
from uuid import UUID, uuid4

import pytest

from cora.agent._agent_seed import AgentSeedIdentity, seed_agent
from cora.agent.aggregates.agent import BrainRef, ModelRef, load_agent
from cora.agent.aggregates.language_model import (
    LanguageModelNotApprovedError,
    LanguageModelStatus,
)
from cora.infrastructure.config import Settings
from cora.infrastructure.deps import make_inmemory_kernel
from cora.infrastructure.kernel import Kernel
from cora.infrastructure.ports import AllowAllAuthorize, FakeClock, FixedIdGenerator
from cora.infrastructure.ports.language_model_lookup import LanguageModelLookupResult

_AGENT_ID = UUID("01900000-0000-7000-8000-0000abcd0001")
_MODEL = ModelRef(provider="anthropic", model="claude-sonnet-4-6")


class _RefusingLookup:
    """Nothing is approved. The shape a fresh deployment's catalog has."""

    async def find_by_model(self, *, provider: str, model: str) -> LanguageModelLookupResult | None:
        return None


class _DefinedNotApprovedLookup:
    """The entry exists but was never approved, which is not the same thing."""

    async def find_by_model(self, *, provider: str, model: str) -> LanguageModelLookupResult | None:
        return LanguageModelLookupResult(
            language_model_id=uuid4(),
            status=LanguageModelStatus.DEFINED.value,
            data_tier="Tier1",
            archivability="Archivable",
            snapshot_pin=None,
        )


def _kernel(lookup: object) -> Kernel:
    settings = Settings()  # type: ignore[call-arg]
    kernel = make_inmemory_kernel(
        settings=settings,
        clock=FakeClock(datetime(2026, 5, 17, 14, 0, 0, tzinfo=UTC)),
        id_generator=FixedIdGenerator([]),
        authz=AllowAllAuthorize(),
    )
    object.__setattr__(kernel, "language_model_lookup", lookup)
    return kernel


def _identity(brain: BrainRef) -> AgentSeedIdentity:
    return AgentSeedIdentity(
        agent_id=_AGENT_ID,
        name="Gated Agent",
        kind="RunDebriefer",
        version="1.0.0",
        description="Seeded for the approval-gate tests.",
        brain=brain,
        prompt_template_id=None,
        agent_event_id=UUID("01900000-0000-7000-8000-0000abcd0002"),
        actor_event_id=UUID("01900000-0000-7000-8000-0000abcd0003"),
        correlation_id=UUID("01900000-0000-7000-8000-0000abcd0004"),
        command_name="SeedGatedAgent",
    )


@pytest.mark.unit
async def test_uncataloged_model_refuses_to_seed() -> None:
    kernel = _kernel(_RefusingLookup())

    with pytest.raises(LanguageModelNotApprovedError):
        await seed_agent(kernel, _identity(BrainRef.for_model(_MODEL)))

    assert await load_agent(kernel.event_store, _AGENT_ID) is None


@pytest.mark.unit
async def test_cataloged_but_unapproved_model_refuses_to_seed() -> None:
    """Present is not approved. A Defined entry means the facility has looked
    at the model and not yet said yes."""
    kernel = _kernel(_DefinedNotApprovedLookup())

    with pytest.raises(LanguageModelNotApprovedError):
        await seed_agent(kernel, _identity(BrainRef.for_model(_MODEL)))

    assert await load_agent(kernel.event_store, _AGENT_ID) is None


@pytest.mark.unit
async def test_a_rule_brained_agent_seeds_against_a_refusing_catalog() -> None:
    """Eighteen of the twenty seeded agents are rule-brained. A rule runs no
    external model and spends nothing, so there is no catalog decision for it
    to be subject to, and gating it would refuse boot for no reason."""
    kernel = _kernel(_RefusingLookup())

    await seed_agent(kernel, _identity(BrainRef.for_rule("ProcedureWatcher:v1")))

    assert await load_agent(kernel.event_store, _AGENT_ID) is not None


@pytest.mark.unit
async def test_an_already_seeded_agent_survives_the_model_losing_approval() -> None:
    """The gate covers a FIRST write only.

    The append is optimistically idempotent, so an unconditional gate would
    re-run every boot: a facility that later retires a model would find its
    already-seeded deployment refusing to start. That is catalog curation, not
    a definition error, and it must not be a boot hazard.
    """
    permissive = _kernel(_RefusingLookup())
    object.__setattr__(permissive, "language_model_lookup", _ApprovingLookup())
    await seed_agent(permissive, _identity(BrainRef.for_model(_MODEL)))
    assert await load_agent(permissive.event_store, _AGENT_ID) is not None

    # Same event store, catalog now refuses: a restart must still be a no-op.
    object.__setattr__(permissive, "language_model_lookup", _RefusingLookup())
    await seed_agent(permissive, _identity(BrainRef.for_model(_MODEL)))

    assert await load_agent(permissive.event_store, _AGENT_ID) is not None


class _ApprovingLookup:
    async def find_by_model(self, *, provider: str, model: str) -> LanguageModelLookupResult | None:
        return LanguageModelLookupResult(
            language_model_id=uuid4(),
            status=LanguageModelStatus.APPROVED.value,
            data_tier="Tier1",
            archivability="Archivable",
            snapshot_pin=None,
        )
