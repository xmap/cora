"""The `RequestRatification` command -- intent dataclass for this slice.

Genesis command. Caller-supplied `ratification_id` so a subscriber (the
consequence-gate decider that detects a co-signature is required) can mint a
deterministic id for replay-safe ingest, while operator-direct requests can also
supply one.

The requester (`requested_by`) is NOT a command field: it is the envelope
`principal_id`, threaded into the decider by the handler, so a caller cannot
claim a different requester than the one issuing the request. This mirrors the
`supersede_caution` author-threading convention (command surface omits the
principal; the handler supplies it).
"""

from dataclasses import dataclass
from uuid import UUID


@dataclass(frozen=True)
class RequestRatification:
    """Request a second-principal co-signature for a consequential action.

    `ratification_id`: REQUIRED caller-supplied id (genesis collision raises
    `RatificationAlreadyExistsError`).

    `target_action_id`: REQUIRED opaque id of the action being gated (e.g. the run id
    whose consequential command is held). Not existence-checked at the decider
    per the cross-BC eventual-consistency stance.

    `command_name`: REQUIRED canonical name of the gated command.

    `consequence_class`: REQUIRED declared class that triggered the requirement
    (bare-str label, 1-100 chars after trim).
    """

    ratification_id: UUID
    target_action_id: UUID
    command_name: str
    consequence_class: str
