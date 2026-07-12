"""Bootstrap-time seed for the fleet's default LanguageModel catalog entries.

One catalog entry per model the shipped agent fleet declares:
the RunDebriefer default, the CautionDrafter default, and the
ExperimentSteerer LLM-decide default. Each entry is born Defined AND
Approved (two events on the fresh stream) because seeds bypass the
handlers: the `define_agent` gate refuses any model identity without
an Approved entry, and a fresh deployment must not refuse
`define_agent` for the fleet it ships with. The seed precedent is
Safety's clearance-template seed, which likewise writes Defined +
Activated in one append (the agent-fleet seeds are NOT the precedent:
they land Defined and are gated at runtime by `Actor.active`, not
`AgentStatus`). The operator's governance lever is
`deprecate_language_model`, which withdraws the seeded approval like
any other.

Idempotent in the `_agent_seed` style: `expected_version=0` append
with `ConcurrencyError`-as-no-op, so a stream that already exists is
skipped (an operator's later transitions are never overwritten). The
skip path inspects the existing stream's first event: a stream at a
deterministic seed id whose genesis was NOT written by this seed is a
squatted stream an operator must inspect, and it logs a WARNING
instead of the routine already-present INFO.

Ids are deterministic `uuid5` values from the pinned
`LANGUAGE_MODEL_SEED_NAMESPACE`, so the same entry resolves to the
same id at every deployment (the Role / Family seed posture rather
than the per-agent literal ranges: catalog identity is derived from
the model identity, not hand-allocated).

Seeded tiers: `served_via=Direct` (CORA's own adapter holds the
provider credentials today), `data_tier=Internal` (the fleet reads
non-public working data), `archivability=Alias` (provider-hosted
identities the vendor may move or retire). TokenPricing figures are
copied from `cora.infrastructure.observability.gen_ai.PRICING`; the
consistency test pins the copies against drift.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING, Final
from uuid import UUID, uuid5

from cora.agent.aggregates.agent import ModelRef
from cora.agent.aggregates.language_model import (
    ArchivabilityTier,
    DataSensitivityTier,
    LanguageModelApproved,
    LanguageModelDefined,
    LanguageModelName,
    ServingRoute,
    TokenPricing,
    cost_basis_to_payload,
    event_type_name,
    to_payload,
)
from cora.agent.prompts.caution_drafter import DEFAULT_CAUTION_DRAFTER_MODEL
from cora.agent.prompts.run_debrief import DEFAULT_RUN_DEBRIEF_MODEL
from cora.infrastructure.logging import get_logger
from cora.infrastructure.ports import ConcurrencyError
from cora.infrastructure.routing import SYSTEM_PRINCIPAL_ID

if TYPE_CHECKING:
    from cora.infrastructure.kernel import Kernel


_log = get_logger(__name__)

_SEED_COMMAND_NAME: Final[str] = "SeedLanguageModels"


# Fixed UUID5 namespace for seeded catalog-entry ids. Generated once at
# lock-time as `uuid5(NAMESPACE_DNS, 'cora.language-model')`. Hardcoded
# so re-derivation is deterministic without requiring the uuid library
# at runtime in the seed path (mirrors `_ROLE_NAMESPACE`).
LANGUAGE_MODEL_SEED_NAMESPACE: Final[UUID] = UUID("a6c65b6f-70eb-595f-894b-eb4b9b3bde39")


def language_model_seed_id(provider: str, model: str) -> UUID:
    """Derive the deterministic catalog-entry id for one model identity."""
    return uuid5(LANGUAGE_MODEL_SEED_NAMESPACE, f"{provider}/{model}")


@dataclass(frozen=True)
class LanguageModelSeedEntry:
    """One fleet-default catalog entry's deployment-stable constants."""

    name: str
    model_ref: ModelRef
    cost_basis: TokenPricing


# The ExperimentSteerer default is `DEFAULT_LLM_DECIDE_MODEL` in
# `cora.operation.adapters._llm_decide_prompt`, mirrored here as
# literals because `cora.agent` does not depend on `cora.operation`
# (tach boundary). The consistency test in
# `tests/unit/agent/test_language_model_seed.py` imports both sides
# and pins the mirror against drift.
_LLM_DECIDE_MODEL: Final[ModelRef] = ModelRef(
    provider="anthropic",
    model="claude-sonnet-4-5",
)


# TokenPricing figures copied from
# `cora.infrastructure.observability.gen_ai.PRICING` (Anthropic public
# pricing, Jul 2026; cache writes at the 1-hour TTL tier).
SEED_LANGUAGE_MODELS: Final[tuple[LanguageModelSeedEntry, ...]] = (
    LanguageModelSeedEntry(
        name="Claude Haiku 4.5",
        # Rebuilt as the aggregate's ModelRef from the prompt module's
        # ports-level constant (the seed_caution_drafter posture).
        model_ref=ModelRef(
            provider=DEFAULT_RUN_DEBRIEF_MODEL.provider,
            model=DEFAULT_RUN_DEBRIEF_MODEL.model,
            snapshot_pin=DEFAULT_RUN_DEBRIEF_MODEL.snapshot_pin,
        ),
        cost_basis=TokenPricing(
            input_per_mtok=1.00,
            output_per_mtok=5.00,
            cache_write_per_mtok=2.00,
            cache_read_per_mtok=0.10,
        ),
    ),
    LanguageModelSeedEntry(
        name="Claude Sonnet 4.6",
        model_ref=ModelRef(
            provider=DEFAULT_CAUTION_DRAFTER_MODEL.provider,
            model=DEFAULT_CAUTION_DRAFTER_MODEL.model,
            snapshot_pin=DEFAULT_CAUTION_DRAFTER_MODEL.snapshot_pin,
        ),
        cost_basis=TokenPricing(
            input_per_mtok=3.00,
            output_per_mtok=15.00,
            cache_write_per_mtok=6.00,
            cache_read_per_mtok=0.30,
        ),
    ),
    LanguageModelSeedEntry(
        name="Claude Sonnet 4.5",
        model_ref=_LLM_DECIDE_MODEL,
        cost_basis=TokenPricing(
            input_per_mtok=3.00,
            output_per_mtok=15.00,
            cache_write_per_mtok=6.00,
            cache_read_per_mtok=0.30,
        ),
    ),
)


async def seed_language_models(kernel: Kernel) -> None:
    """Seed the fleet-default LanguageModel catalog entries (idempotent).

    Each entry is appended as `LanguageModelDefined` +
    `LanguageModelApproved` in ONE `expected_version=0` append, so the
    stream is born Approved atomically. Seeds bypass the handlers on
    purpose: a fresh deployment must not refuse `define_agent` for the
    shipped fleet, and the kernel's default lookup only stops
    approving everything once a real catalog exists. The operator
    withdraws a seeded approval via `deprecate_language_model`.

    No-op per entry when its stream already has events
    (`ConcurrencyError`-as-already-seeded); safe to call on every boot.
    """
    from cora.infrastructure.event_envelope import to_new_event

    now = kernel.clock.now()

    for entry in SEED_LANGUAGE_MODELS:
        identity_key = f"{entry.model_ref.provider}/{entry.model_ref.model}"
        language_model_id = language_model_seed_id(entry.model_ref.provider, entry.model_ref.model)

        # Validate the constants through the same VO the decider uses so
        # a bad constant crashes at startup with a clear error.
        name = LanguageModelName(entry.name)

        defined_event = LanguageModelDefined(
            language_model_id=language_model_id,
            name=name.value,
            provider=entry.model_ref.provider,
            model=entry.model_ref.model,
            snapshot_pin=entry.model_ref.snapshot_pin,
            served_via=ServingRoute.DIRECT.value,
            endpoint_note=None,
            cost_basis=cost_basis_to_payload(entry.cost_basis),
            data_tier=DataSensitivityTier.INTERNAL.value,
            archivability=ArchivabilityTier.ALIAS.value,
            occurred_at=now,
        )
        approved_event = LanguageModelApproved(
            language_model_id=language_model_id,
            occurred_at=now,
        )

        new_events = [
            to_new_event(
                event_type=event_type_name(event),
                payload=to_payload(event),
                occurred_at=now,
                event_id=uuid5(LANGUAGE_MODEL_SEED_NAMESPACE, f"{identity_key}/{tag}"),
                command_name=_SEED_COMMAND_NAME,
                correlation_id=uuid5(LANGUAGE_MODEL_SEED_NAMESPACE, f"{identity_key}/bootstrap"),
                causation_id=None,
                principal_id=SYSTEM_PRINCIPAL_ID,
            )
            for event, tag in (
                (defined_event, "defined-event"),
                (approved_event, "approved-event"),
            )
        ]

        try:
            await kernel.event_store.append(
                stream_type="LanguageModel",
                stream_id=language_model_id,
                expected_version=0,
                events=new_events,
            )
        except ConcurrencyError:
            # A stream already sits at this deterministic seed id. If its
            # genesis was not written by this seed, an entry pre-exists
            # that bootstrap never created (a uuid5 squat), so an operator
            # must inspect it; the squatter's events are never overwritten
            # either way.
            stored, _version = await kernel.event_store.load("LanguageModel", language_model_id)
            found_command_name = stored[0].metadata.get("command") if stored else None
            if found_command_name != _SEED_COMMAND_NAME:
                _log.warning(
                    "language_model_seed.stream_squatted",
                    language_model_id=str(language_model_id),
                    provider=entry.model_ref.provider,
                    model=entry.model_ref.model,
                    found_command_name=found_command_name,
                )
            else:
                _log.info(
                    "language_model_seed.already_present",
                    language_model_id=str(language_model_id),
                    provider=entry.model_ref.provider,
                    model=entry.model_ref.model,
                )
            continue

        _log.info(
            "language_model_seed.created",
            language_model_id=str(language_model_id),
            provider=entry.model_ref.provider,
            model=entry.model_ref.model,
            name=name.value,
        )


__all__ = [
    "LANGUAGE_MODEL_SEED_NAMESPACE",
    "SEED_LANGUAGE_MODELS",
    "LanguageModelSeedEntry",
    "language_model_seed_id",
    "seed_language_models",
]
