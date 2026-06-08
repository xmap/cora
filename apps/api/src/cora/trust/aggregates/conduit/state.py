"""Conduit aggregate state, value objects, and domain errors.

Per ISA-99, a Conduit is a governed communications path between two
Zones. Each Conduit has its own SL-T (Security Level Target) and an
agreed contract describing what may flow through it; runtime
traversal events accumulate against the Conduit's traversals
observation logbook.

Conduit is intentionally minimal: `id` + `name` + the two endpoint
zone IDs. SL-T, contract, and remaining lifecycle (`Defined → Active
→ Modified → Archived`, per BC-map) follow the same additive-state
pattern as Zone — fields default in the evolver when added.

**Logbook state**: `logbooks: dict[str, UUID]` maps logbook kind →
currently-open logbook id for each observation logbook attached to
this Conduit. The traversals logbook is opened automatically at
conduit-creation (gate-review locked: per-Conduit logbook scoping).
The state encodes the
**at-most-one-open-per-kind invariant** directly — opening a second
logbook of an existing kind raises rather than orphaning the first.
The slim-aggregate principle keeps state to invariant-relevant
fields only; logbook schemas live on the logbook-open event payloads,
not on the aggregate state.

The `dict` value is immutable by convention: the evolver returns a
fresh `Conduit` with a new dict on every logbook-open / logbook-close;
no code mutates `state.logbooks` in place. Frozen dataclass blocks
field reassignment but not mutation of the contained dict — the
codebase relies on the same evolver-purity discipline used by every
other aggregate.

**No referential integrity at command time.** `source_zone_id` and
`target_zone_id` are stored as primitives without verifying the
referenced Zones exist. This is the deliberate event-sourcing
posture: aggregate boundaries are transactional consistency
boundaries, and Conduit cannot transactionally consult Zone state.
A typo at the API layer creates a "dangling" Conduit. Two mitigations
arrive later: (1) the eventual-consistency view (a projection that
filters out conduits whose endpoints don't resolve), and (2) Policy
evaluation, which is the natural home for "is this Conduit
usable" runtime checks.

Endpoint naming (`source` / `target`) is for clarity at the API
layer; the conduit itself is undirected per ISA-99 (a comms path
between two zones, not a one-way arrow). If future use cases need
explicit directionality, add a `direction` enum field; today the
ordering is just convention, not enforced semantics.
"""

from dataclasses import dataclass, field
from typing import Final
from uuid import UUID

from cora.shared.bounded_text import bounded_name

CONDUIT_NAME_MAX_LENGTH = 200

# Logbook-kind discriminators. Each kind names a category of
# observation a Conduit can attach. Today: just traversals (per-
# decision authorization audit log). Future kinds (for example,
# rate-limit-events, schema-violations) follow the same naming
# convention: snake_case, plural noun, domain-meaningful.
LOGBOOK_KIND_TRAVERSALS: Final = "traversals"


class InvalidConduitNameError(ValueError):
    """The supplied name is empty, whitespace-only, or too long."""

    def __init__(self, value: str) -> None:
        super().__init__(
            f"Conduit name must be 1-{CONDUIT_NAME_MAX_LENGTH} chars after trimming "
            f"(got: {value!r})"
        )
        self.value = value


class ConduitAlreadyExistsError(Exception):
    """Attempted to define a conduit whose stream already has events."""

    def __init__(self, conduit_id: UUID) -> None:
        super().__init__(f"Conduit {conduit_id} already exists")
        self.conduit_id = conduit_id


class ConduitLogbookAlreadyOpenError(Exception):
    """Attempted to open a second logbook of a kind that already has one open.

    The state encodes the at-most-one-open-per-kind invariant; this
    error fires when an evolver replay tries to open a logbook of a
    kind that's already present in `state.logbooks`. Carries the
    existing logbook id so the caller can identify which logbook is
    already in the way.
    """

    def __init__(self, conduit_id: UUID, kind: str, existing_logbook_id: UUID) -> None:
        super().__init__(
            f"Conduit {conduit_id} already has a {kind!r} logbook open "
            f"(logbook_id={existing_logbook_id})"
        )
        self.conduit_id = conduit_id
        self.kind = kind
        self.existing_logbook_id = existing_logbook_id


class ConduitLogbookNotOpenError(Exception):
    """Attempted to close a logbook id that's not currently open on any kind.

    Defensive guard; close commands originate from Conduit lifecycle
    transitions (eventually conduit-archive) and should never target
    an unopened logbook.
    """

    def __init__(self, conduit_id: UUID, logbook_id: UUID) -> None:
        super().__init__(f"Conduit {conduit_id} has no open logbook {logbook_id} to close")
        self.conduit_id = conduit_id
        self.logbook_id = logbook_id


@bounded_name(max_length=CONDUIT_NAME_MAX_LENGTH, error_class=InvalidConduitNameError)
@dataclass(frozen=True)
class ConduitName:
    """Display name for a conduit. Trimmed; 1-200 chars.

    Third occurrence of the same trimmed-bounded-name VO pattern
    (after `ActorName` and `ZoneName`). Each kept distinct so
    invariants can diverge per aggregate; if all three stay
    byte-identical and a fourth appears, hoist a `BoundedName`
    factory to a cross-BC value-objects module.
    """

    value: str


@dataclass(frozen=True)
class Conduit:
    """Aggregate root: a governed comms path between two Trust zones.

    `logbooks` maps logbook kind → currently-open logbook id for each
    observation logbook attached to this Conduit. The
    dict shape encodes the at-most-one-open-per-kind invariant: the
    evolver raises `ConduitLogbookAlreadyOpenError` on any attempt to
    open a second logbook of an existing kind. Empty for newly-defined
    Conduits before any logbook-open event has been folded.
    """

    id: UUID
    name: ConduitName
    source_zone_id: UUID
    target_zone_id: UUID
    logbooks: dict[str, UUID] = field(default_factory=dict[str, UUID])
