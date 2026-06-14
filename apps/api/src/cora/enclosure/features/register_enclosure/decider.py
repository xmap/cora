"""Pure decider for the `RegisterEnclosure` command.

Pure function: given the current Enclosure state (None for a fresh
stream) and a `RegisterEnclosure` command, returns the events to
append. No I/O, no awaits, no side effects.

`now`, `new_id`, and `registered_by` are injected by the application
handler from the Clock and IdGenerator ports and from the route /
tool boundary (the non-determinism principle: capture, don't
recompute). Registration is operator-only today; `registered_by` is
typed `ActorId` directly, not the trigger-aware union, matching the
genesis-event payload shape in `cora.enclosure.aggregates.enclosure`.

## Validation

  - State must be None (genesis-only) -> `EnclosureAlreadyExistsError`
  - `facility_lookup_result` must be non-None
    -> `EnclosureFacilityNotFoundError`
  - `name` is wrapped via `EnclosureName(...)` which validates 1-200
    chars in `__post_init__` -> `InvalidEnclosureNameError`.

## Facility binding

`command.facility_code` is the cross-deployment convergent slug for the
containing Facility (the Site / Area the enclosure sits within). The
handler resolves it via `FacilityLookup.lookup_by_code` and threads the
resulting `FacilityLookupResult | None` into the decider. LOAD lives in
the handler; REJECTION lives in the decider: a `None` result means no
Facility with that code is visible in the Federation projection and the
registration is rejected with `EnclosureFacilityNotFoundError`
(HTTP 404). The lookup-result's `.code` field is folded onto the event
so the event's `facility_code` reflects the projection's canonical typed
VO, not a command-echo (mirrors the Asset / Supply handler/decider
split). The decider does NOT partition on Facility status: every status
(Active, Decommissioned) is a valid containing geography.

Initial permit-status is implicit `Unknown` and initial lifecycle is
implicit `Active`; the evolver seeds both from the genesis event
type. Per the universal industrial + cloud-native consensus on
registration-time defaults (Tango UNKNOWN, EPICS UDF, Azure Resource
Health Unknown, k8s Pending).

Cross-stream uniqueness of the `(facility_code, name)` address
tuple is NOT enforced here: the decider cannot see other Enclosure
streams without DCB. The projection's partial UNIQUE INDEX (active
rows only) is the cross-stream guard; this decider's pre-state-None
check is the genesis collision guard against same-stream double
registration.
"""

from datetime import datetime

from cora.enclosure.aggregates.enclosure import (
    Enclosure,
    EnclosureAlreadyExistsError,
    EnclosureFacilityNotFoundError,
    EnclosureId,
    EnclosureName,
    EnclosureRegistered,
)
from cora.enclosure.features.register_enclosure.command import RegisterEnclosure
from cora.infrastructure.ports.facility_lookup import FacilityLookupResult
from cora.shared.identity import ActorId


def decide(
    state: Enclosure | None,
    command: RegisterEnclosure,
    *,
    now: datetime,
    new_id: EnclosureId,
    registered_by: ActorId,
    facility_lookup_result: FacilityLookupResult | None,
) -> list[EnclosureRegistered]:
    """Decide the events produced by registering a new Enclosure.

    Invariants:
      - State must be None (genesis-only)
        -> EnclosureAlreadyExistsError
      - facility_lookup_result must be non-None
        -> EnclosureFacilityNotFoundError
      - Name must be valid -> InvalidEnclosureNameError
        (via EnclosureName VO)

    `registered_by` is the operator's `ActorId` (registration is
    always operator-driven; no Monitor or Auto counterpart). Folded
    onto the event payload as the fold-symmetric genesis attribution
    per [[project_fold_symmetry_design]].

    `facility_lookup_result.code` is the canonical Facility slug
    threaded onto the event payload, replacing direct echo of
    `command.facility_code` so the cross-BC convergent identity is the
    single source of truth for the wire value.
    """
    if state is not None:
        raise EnclosureAlreadyExistsError(state.id)

    if facility_lookup_result is None:
        raise EnclosureFacilityNotFoundError(command.facility_code)

    name = EnclosureName(command.name)

    return [
        EnclosureRegistered(
            enclosure_id=new_id,
            name=name.value,
            facility_code=facility_lookup_result.code,
            registered_by=registered_by,
            occurred_at=now,
        )
    ]


__all__ = ["decide"]
