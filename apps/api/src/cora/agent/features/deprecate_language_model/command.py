"""The `DeprecateLanguageModel` command -- intent dataclass for this slice.

Ends a catalog entry's service life on the FACILITY side (`Defined |
Approved | RetirementAnnounced -> Deprecated`): the facility withdrew
its own approval (policy, security, cost), independent of the
vendor's lifecycle. Terminal: deprecated entries cannot be revived.
Distinct from `retire_language_model` because the two terminals
answer different audit questions (who ended this model's service
life, the vendor or us?).

`reason` is REQUIRED, a closed `DeprecationReason` (Superseded /
Defective / Obsolete): withdrawing approval is a policy act the
audit log must always carry context for.

The deprecating actor's identity lives on the event envelope
(`StoredEvent.principal_id`); no actor field on the command/event.
"""

from dataclasses import dataclass
from uuid import UUID

from cora.shared.deprecation import DeprecationReason


@dataclass(frozen=True)
class DeprecateLanguageModel:
    """Deprecate a LanguageModel (`Defined | Approved | RetirementAnnounced -> Deprecated`)."""

    language_model_id: UUID
    reason: DeprecationReason
