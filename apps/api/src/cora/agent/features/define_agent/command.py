"""The `DefineAgent` command -- intent dataclass for this slice.

Carries the caller-controlled fields: kind, name, version, model_ref
(required at definition time so 8f-b's LLM has model identity
available immediately), and optional description / canonical_uri /
prompt_template_id / capabilities.

The Agent's `id` is generated server-side by the handler (UUIDv7
via the injected IdGenerator port) and SHARED with Access BC's
Actor.id via the cross-BC atomic `EventStore.append_streams` write
in the handler. Callers do NOT supply the id.

Per the design lock, fields explicitly NOT on the command:
  - `id` (handler-generated)
  - `tools` (deferred to 8f-c ToolGrant slices)
  - `provider_org` / `acts_on_behalf_of` / `card_signature` (deferred
    to A2A trigger)
"""

from dataclasses import dataclass, field
from uuid import UUID

from cora.agent.aggregates.agent import BrainRef, ModelRef


@dataclass(frozen=True)
class DefineAgent:
    """Define a new Agent (lands in Defined; co-registers an Actor with kind=agent)."""

    kind: str
    name: str
    version: str
    model_ref: ModelRef
    description: str | None = None
    canonical_uri: str | None = None
    prompt_template_id: UUID | None = None
    capabilities: frozenset[str] = field(default_factory=frozenset[str])
    # The brain to run on. Optional during the migration only: omitting it
    # means "the LanguageModel named by model_ref", which is what every caller
    # meant before brains had kinds. A caller that names a Rule brain does not
    # have to invent a sentinel ModelRef to satisfy the older field.
    brain: BrainRef | None = None
