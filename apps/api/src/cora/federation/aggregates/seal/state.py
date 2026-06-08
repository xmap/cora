"""Seal aggregate state, status enum, and domain errors.

A `Seal` is the per-facility singleton that signs the head
pointer over this facility's published registry tree. It pairs two
Credential references with distinct purposes:

  - `online_credential_id` references a Credential whose purpose is
    `SealOnlineSigning` (warm key used to sign every head pointer).
  - `offline_credential_id` references a Credential whose purpose is
    `SealOfflineRoot` (cold root used only to authorize online-key
    rotation and to attest a full republish).

Key invariants per [[project_federation_port_design]]:

  - Singleton identity: `facility_id` (str). One Seal stream
    per facility; the stream's UUID is deterministic per facility
    (the handler mints it via UUID5 with the federation namespace).
  - Key separation: `online_credential_id` and `offline_credential_id` MUST
    differ at every transition. Helper `verify_key_separation` at
    `cora.federation.aggregates.seal._key_separation` is called by
    every transition decider per the sec-4 AH#15 strengthening.
  - Purpose binding: each ref is the Credential.id of a Credential
    whose `purpose` matches the slot. Cross-purpose installation
    raises `SealKeyPurposeMismatchError` at the decider, which reads
    the referenced Credential's purpose.
  - Sequence monotonicity: `current_sequence_number` strictly
    increases with each `SealPointerSigned` and with each
    `SealRepublishingCompleted`. Regression raises
    `SealSequenceNumberRegressionError`.

## FSM

`Live -> Republishing -> Live'` (singleton). Republishing is the
window during which the offline root is republishing the full
registry tree against a new head shape; during this window the
online key continues to sign pointers but consumers may use the
`Republishing` indicator to defer trust until the republish
completes.

## Path C lifecycle timestamps

Per [[project_template_aggregate_timestamps]], lifecycle bookkeeping
timestamps (`initialized_at`, `last_signed_at`) do NOT live on
aggregate state; they are derived at projection-apply time from each
event's envelope `occurred_at` (and from the `signed_at` payload field
for the most-recent signing). The `SealLifecycleTimestamps`
view in `read.py` exposes them to read-side surfaces, mirroring
`CalibrationLifecycleTimestamps`. Closest precedent: Calibration is
the append-only-revision FSM analog to Seal's append-only-
snapshot pattern.

The fields that DO stay on state:

  - `online_credential_id` / `offline_credential_id` (decider reads these for the
    key-separation invariant and for cross-purpose binding checks).
  - `current_head_hash` / `current_sequence_number` (decider reads
    these for monotonicity invariants).
  - `initialized_by` (genesis identity denorm; folds into the
    aggregate alongside `initialized_at` per fold-symmetry).
  - `initialized_at` (genesis envelope `occurred_at`; paired with
    `initialized_by` per [[project_fold_symmetry_design]]).
  - `status` (the FSM state).
"""

from dataclasses import dataclass
from datetime import datetime
from enum import StrEnum
from uuid import UUID

from cora.shared.identity import ActorId


class SealStatus(StrEnum):
    """The Seal singleton's lifecycle posture.

    Two values locked day one per [[project_federation_port_design]]:

      - `Live`: normal posture; the online key signs each new head
        pointer; consumers trust the pointer chain.
      - `Republishing`: the offline root is republishing the full
        registry tree against a new head shape; consumers may defer
        trust on new pointers until republish completes (the indicator
        lets them decide, the head still signs).

    The mini-FSM keeps the singleton legible: republishing is a
    bounded window that ends with `SealRepublishingCompleted`.
    """

    LIVE = "Live"
    REPUBLISHING = "Republishing"


# Domain validation errors


class InvalidSealFacilityIdError(ValueError):
    """The supplied `facility_id` is empty or whitespace-only.

    The aggregate keys the per-facility singleton on `facility_id`;
    accepting an empty or whitespace-only handle would bind the
    singleton to nothing. Surfaced as HTTP 400 by the federation
    routes (mirrors `InvalidPermitScopeError` /
    `InvalidCredentialSecretRefError` precedent).
    """

    def __init__(self, value: str) -> None:
        super().__init__(
            f"Seal facility_id must be a non-empty string after trimming (got: {value!r})"
        )
        self.value = value


class InvalidSealHeadHashError(ValueError):
    """Structural problem with the head-pointer fields.

    Covers three head-hash structural rejections, all surfaced as
    HTTP 400 by the federation routes:

      - `new_head_hash` empty or whitespace-only after trim
        (sign_seal_pointer).
      - On complete_seal_republishing, `new_head_hash` and
        `new_sequence_number` supplied as a half-pair (must be
        supplied together or omitted together).
      - On complete_seal_republishing with the pair omitted, the
        Seal has no prior `current_head_hash` to reuse (a
        republish-without-fresh-head only makes sense after at
        least one signing).
    """

    def __init__(self, reason: str) -> None:
        super().__init__(f"Seal head_hash invalid: {reason}")
        self.reason = reason


class SealAlreadyExistsError(Exception):
    """Attempted to initialize the Seal twice for the same facility.

    The singleton invariant: exactly one Seal per facility.
    Per [[project_genesis_error_classes]] this stays un-hoisted per BC.
    """

    def __init__(self, facility_id: str) -> None:
        super().__init__(f"Seal for facility {facility_id!r} already exists")
        self.facility_id = facility_id


class SealNotFoundError(Exception):
    """Attempted an operation on a Seal whose stream has no events."""

    def __init__(self, facility_id: str) -> None:
        super().__init__(f"Seal for facility {facility_id!r} not found")
        self.facility_id = facility_id


class SealKeyCollisionError(Exception):
    """`online_credential_id` and `offline_credential_id` are equal.

    Per sec-4 AH#15 strengthening, the online (warm) signing key and
    the offline (cold) root MUST be distinct credentials. Equality
    collapses the cold-root attestation guarantee: an attacker
    compromising the warm key would also gain root authority.
    Enforced at every transition by the `_key_separation` helper.
    """

    def __init__(self, facility_id: str, shared_credential_id: UUID) -> None:
        super().__init__(
            f"Seal for facility {facility_id!r}: online_credential_id and "
            f"offline_credential_id must differ (both equal {shared_credential_id})"
        )
        self.facility_id = facility_id
        self.shared_credential_id = shared_credential_id


class SealKeyPurposeMismatchError(Exception):
    """A key ref points at a Credential whose purpose does not match the slot.

    `online_credential_id` MUST reference a Credential with purpose
    `SealOnlineSigning`; `offline_credential_id` MUST reference a
    Credential with purpose `SealOfflineRoot`. The decider performs
    this cross-aggregate purpose check before commit; raising this
    error keeps the wrong-purpose case distinguishable from the
    equality-collision case above.
    """

    def __init__(
        self,
        facility_id: str,
        slot: str,
        credential_id: UUID,
        expected_purpose: str,
        actual_purpose: str,
    ) -> None:
        super().__init__(
            f"Seal for facility {facility_id!r}: {slot} credential "
            f"{credential_id} has purpose {actual_purpose!r}, expected "
            f"{expected_purpose!r}"
        )
        self.facility_id = facility_id
        self.slot = slot
        self.credential_id = credential_id
        self.expected_purpose = expected_purpose
        self.actual_purpose = actual_purpose


class SealCredentialNotTrustAnchorError(Exception):
    """A key ref points at a Credential id that is not in the Facility's trust anchors.

    Structural defense against cross-tenant key-mounting (Slice 6
    Sub-Slice C): replaces the deleted `SealCrossFacilityBindingError`
    string-equality three-way check with set-membership against
    `Facility.trust_anchor_credential_ids`. An operator binds a
    Credential as a trust anchor via `add_facility_trust_anchor_credential`
    before the Seal can use it as `online_credential_id` or
    `offline_credential_id`.

    Both `initialize_seal` and `rotate_seal_online_key` raise this when
    the candidate credential id is absent from the bound Facility's
    trust-anchor set. Surfaced as HTTP 409 by the federation routes
    (mirrors `SealCannotRotateWithInactiveCredentialError`; the binding
    is structurally valid but operationally conflicting).

    `key_ref_role` is `"online"` or `"offline"`; the deleted error's
    `"online_vs_offline"` third defense collapses entirely because
    set-membership against the same Facility makes the cross-check
    structurally redundant.
    """

    def __init__(
        self,
        facility_id: str,
        credential_id: UUID,
        key_ref_role: str,
    ) -> None:
        super().__init__(
            f"Seal {key_ref_role} credential {credential_id} is not a "
            f"trust anchor for facility {facility_id!r}"
        )
        self.facility_id = facility_id
        self.credential_id = credential_id
        self.key_ref_role = key_ref_role


class SealCannotRotateWithInactiveCredentialError(Exception):
    """A key ref points at a Credential whose status is not Active.

    Rotation MUST bind only Active Credentials; Rotating or Revoked
    status indicates the secret material is in a lifecycle window
    where signing-authority is not stable. The decider performs this
    cross-aggregate status check before commit (mirrors the purpose
    check in `SealKeyPurposeMismatchError`).
    """

    def __init__(
        self,
        facility_id: str,
        slot: str,
        credential_id: UUID,
        actual_status: str,
    ) -> None:
        super().__init__(
            f"Seal for facility {facility_id!r}: {slot} credential "
            f"{credential_id} has status {actual_status!r}, expected 'Active'"
        )
        self.facility_id = facility_id
        self.slot = slot
        self.credential_id = credential_id
        self.actual_status = actual_status


class SealCannotInitializeWithInactiveCredentialError(Exception):
    """A key ref points at a Credential whose status is not Active at initialize time.

    Initialization MUST bind only Active Credentials in BOTH slots;
    Rotating or Revoked status indicates the secret material is in a
    lifecycle window where signing authority is not stable. The
    decider performs this cross-aggregate status check on both
    `online_credential_id` and `offline_credential_id` before commit (mirrors the
    rotation-time check in
    `SealCannotRotateWithInactiveCredentialError`).
    """

    def __init__(
        self,
        facility_id: str,
        slot: str,
        credential_id: UUID,
        actual_status: str,
    ) -> None:
        super().__init__(
            f"Seal for facility {facility_id!r}: {slot} credential "
            f"{credential_id} has status {actual_status!r}, expected 'Active'"
        )
        self.facility_id = facility_id
        self.slot = slot
        self.credential_id = credential_id
        self.actual_status = actual_status


class SealCannotSignError(Exception):
    """Attempted `sign_seal_pointer` from a disqualifying status."""

    def __init__(self, facility_id: str, current_status: "SealStatus") -> None:
        super().__init__(
            f"Seal for facility {facility_id!r} cannot sign pointer: "
            f"currently in status {current_status.value}, sign requires "
            f"{SealStatus.LIVE.value}"
        )
        self.facility_id = facility_id
        self.current_status = current_status


class SealCannotRotateError(Exception):
    """Attempted `rotate_seal_online_key` from a disqualifying status."""

    def __init__(self, facility_id: str, current_status: "SealStatus") -> None:
        super().__init__(
            f"Seal for facility {facility_id!r} cannot rotate online key: "
            f"currently in status {current_status.value}, rotate requires "
            f"{SealStatus.LIVE.value}"
        )
        self.facility_id = facility_id
        self.current_status = current_status


class SealCannotStartRepublishingError(Exception):
    """Attempted `start_seal_republishing` from a disqualifying status."""

    def __init__(self, facility_id: str, current_status: "SealStatus") -> None:
        super().__init__(
            f"Seal for facility {facility_id!r} cannot start republishing: "
            f"currently in status {current_status.value}, start_republishing "
            f"requires {SealStatus.LIVE.value}"
        )
        self.facility_id = facility_id
        self.current_status = current_status


class SealCannotCompleteRepublishingError(Exception):
    """Attempted `complete_seal_republishing` from a disqualifying status."""

    def __init__(self, facility_id: str, current_status: "SealStatus") -> None:
        super().__init__(
            f"Seal for facility {facility_id!r} cannot complete "
            f"republishing: currently in status {current_status.value}, "
            f"complete_republishing requires {SealStatus.REPUBLISHING.value}"
        )
        self.facility_id = facility_id
        self.current_status = current_status


class SealSequenceNumberRegressionError(Exception):
    """The proposed `current_sequence_number` is not strictly greater than the prior value.

    Monotonic-sequence invariant: every signed head pointer and every
    completed republish increments the sequence number. A regression
    is either a stale write that lost a race or a contaminated event;
    both fail loud at the decider.
    """

    def __init__(
        self,
        facility_id: str,
        prior_sequence_number: int,
        proposed_sequence_number: int,
    ) -> None:
        super().__init__(
            f"Seal for facility {facility_id!r}: proposed sequence "
            f"number {proposed_sequence_number} is not strictly greater than "
            f"prior {prior_sequence_number}"
        )
        self.facility_id = facility_id
        self.prior_sequence_number = prior_sequence_number
        self.proposed_sequence_number = proposed_sequence_number


@dataclass(frozen=True)
class Seal:
    """Aggregate root: the per-facility singleton that signs the head pointer.

    Identity is `facility_id` (str). One stream per facility (the
    handler mints a deterministic stream UUID; the domain identity
    that matters is the human-readable facility string).

    `online_credential_id` and `offline_credential_id` are both Credential.id
    references and MUST never equal each other. Their referenced
    Credentials MUST carry distinct purposes (`SealOnlineSigning`
    vs `SealOfflineRoot`); cross-purpose installation is rejected
    by the decider.

    `current_head_hash` is the SHA-256 (lowercase hex) of the most
    recent signed head pointer; `None` between initialization and
    the first `SealPointerSigned`.

    `current_sequence_number` increments monotonically with each
    pointer signing and each completed republish. Seeded to 0 at
    initialization.

    `initialized_by` is the genesis identity denorm and `initialized_at`
    folds the genesis envelope `occurred_at`; the pair satisfies the
    fold-symmetry rule [[project_fold_symmetry_design]] for the genesis
    arm. Transition events (sign / rotate / start-republish /
    complete-republish) stay fold-NEITHER on state per the same
    convention: their attribution rides on the envelope and on the
    projection (`last_signed_by`), not on aggregate state.

    Per [[project_template_aggregate_timestamps]] Path C the
    transition-tier bookkeeping (`last_signed_at`) still lives on the
    projection, not on state; see `SealLifecycleTimestamps` in
    `read.py`. `initialized_at` is now folded onto state per the Path
    C reversal for the genesis arm.
    """

    facility_id: str
    online_credential_id: UUID
    offline_credential_id: UUID
    current_head_hash: str | None
    current_sequence_number: int
    initialized_by: ActorId
    initialized_at: datetime
    status: SealStatus
