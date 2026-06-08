"""Signature verification + signed-event-type registry.

Implementation of Candidate F (signed events) per
[[project_signed_events_design]]. Ships the verification path and
the closed registry of event types that must be signed at write
time; the `Signer` port lives next door at
`cora.infrastructure.ports.signer`.

No production signer adapter ships in this iteration. The verification
function works against any future adapter (Sigstore Fulcio, SPIFFE / SVID,
cloud KMS, local keystore) because the signature input is the same DSSE
PAE wrapper used by [[project_content_addressed_identity_design]] for
content hashing. One canonicalization profile, two consumers.

## Algorithm

EdDSA over Ed25519. Picked per the corpus survey: modal across
modern attestation ecosystems (Sigstore, in-toto, SLSA, age, Tailscale),
smaller signatures (64 bytes) than RSA-2048 (256 bytes), faster sign
(~50us) and verify (~150us) than RSA at typical CORA append rates.

## Signature input

`PAE(payload_type, canonical_body_bytes(payload))`, computed via the
shared helper in `cora.shared.content_hash`. The payloadType
URI binds the event type into the signature so a `DecisionRegistered`
signature can never collide with a different Agent-emitted event of a
future type even when their bodies happen to serialize to the same
bytes.

## What is NOT here

  - The `Signer` Protocol lives in `cora.infrastructure.ports.signer`.
  - Production signing adapters are deferred; iteration 3 lands one.
  - The verification function takes an explicit public-key resolver
    callable rather than depending on a kernel-wide registry. Resolvers
    are call-site-specific (read-time verify can use a different cache
    than write-time signing); composition stays explicit.
"""

from collections.abc import Awaitable, Callable, Mapping, Sequence
from typing import Any

from cryptography.exceptions import InvalidSignature
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PublicKey

from cora.infrastructure.ports.event_store import StoredEvent
from cora.shared.content_hash import canonical_body_bytes, pae_bytes

EVENT_TYPE_PAYLOAD_TYPE_PREFIX = "application/vnd.cora."
EVENT_TYPE_PAYLOAD_TYPE_SUFFIX = "+json"


SIGNED_EVENT_TYPES: frozenset[str] = frozenset({"DecisionRegistered"})
"""Closed set of event-type names that MUST be signed at write time.

Initial set per [[project_signed_events_design]] (errata 2026-05-24):

  - `DecisionRegistered`: produced by Agents AND by humans. Per the
    design lock the signing requirement applies only to the Agent-
    produced rows; the subscriber tier (CautionDrafter and
    RunDebriefer today) checks `actor_id` against the Agent BC's
    stable-id rule before invoking `Signer.sign`. Human-actor
    `DecisionRegistered` rows from the operator-driven
    `register_decision` slice stay unsigned. Both AI-agent
    subscribers route through this single entry: CautionDrafter
    emits `DecisionRegistered` with `context="CautionProposal"`
    (the Caution aggregate itself is created later via the
    operator-driven `promote_caution_proposal` slice), and
    RunDebriefer emits `DecisionRegistered` with its own context.

Errata note: an earlier draft listed `CautionProposed` as a separate
entry on the assumption that CautionDrafter emitted a dedicated
Caution-aggregate event. It does not: the actual Caution-aggregate
events are `CautionRegistered`, `CautionSuperseded`, and
`CautionRetired`, none of which are AI-emitted directly. The
single `DecisionRegistered` entry above covers the CautionDrafter
signing case via the Agent-actor discriminator.

Future Agent-BC event types land here by default. Expansion to
human-actor events requires a deliberate design lock per the
scientific-data corpus verdict.
"""


def event_type_to_payload_type(event_type: str) -> str:
    """Map an event-type name to its payloadType URI.

    `"DecisionRegistered"` -> `"application/vnd.cora.decision-registered+json"`.

    Single source of truth shared between sign-side and verify-side so
    the PAE input is provably the same bytes on both paths. The
    function is event-type-agnostic; any CamelCase event-type name
    maps cleanly, including hypothetical future entries to
    SIGNED_EVENT_TYPES.
    """
    kebab = _camel_to_kebab(event_type)
    return f"{EVENT_TYPE_PAYLOAD_TYPE_PREFIX}{kebab}{EVENT_TYPE_PAYLOAD_TYPE_SUFFIX}"


def _camel_to_kebab(name: str) -> str:
    """Convert CamelCase event-type names to kebab-case payloadType slugs.

    Internal helper. CORA event-type names are CamelCase by convention
    (`DecisionRegistered`, `RunStarted`, etc.); payloadType URIs follow
    the IANA media-type kebab-case convention. Acronym-aware: insert
    a dash before an uppercase letter when the previous char is
    lowercase (CamelCase boundary) OR when the next char is lowercase
    and the previous char was uppercase (last-letter-of-acronym
    boundary). So `MCPSessionOpened` becomes `mcp-session-opened`,
    not `m-c-p-session-opened`.
    """
    if not name:
        return ""
    out: list[str] = [name[0].lower()]
    for i in range(1, len(name)):
        ch = name[i]
        prev = name[i - 1]
        nxt = name[i + 1] if i + 1 < len(name) else ""
        if ch.isupper() and (prev.islower() or (nxt != "" and nxt.islower())):
            out.append("-")
        out.append(ch.lower())
    return "".join(out)


class SignatureInvalidError(Exception):
    """The recorded signature does not verify against the recomputed bytes.

    Critical: surfaces tampering, schema-evolution-without-payloadType
    bump, or key compromise. Surfaces as HTTP 422 at API boundary
    (read-time verify mode) or HTTP 500 in internal audit paths.
    """

    def __init__(self, event_type: str, kid: str, detail: str = "") -> None:
        super().__init__(
            f"Signature invalid for event_type {event_type!r}, kid {kid!r}"
            + (f": {detail}" if detail else "")
        )
        self.event_type = event_type
        self.kid = kid
        self.detail = detail


class SignatureMissingError(Exception):
    """A signed-event-type row was read with no signature.

    Distinct from `SignatureInvalidError` so monitoring can distinguish
    "tampered" from "never signed" (the latter expected for pre-rollout
    events, suspicious for new events of a SIGNED_EVENT_TYPES type).
    """

    def __init__(self, event_type: str) -> None:
        super().__init__(f"Event {event_type!r} is in SIGNED_EVENT_TYPES but has no signature")
        self.event_type = event_type


async def verify_signature(
    *,
    event_type: str,
    payload: Mapping[str, Any],
    signature: bytes,
    kid: str,
    resolve_public_key: Callable[[str], Awaitable[bytes]],
) -> None:
    """Verify a signature over an event payload. Raise on failure.

    Recomputes the canonical-body-bytes from `payload` via the shared
    helper in `content_hash`, wraps in PAE with the payloadType derived
    from `event_type`, resolves the public key for `kid`, and verifies
    using Ed25519. Same bytes the signer signed; deterministic
    canonicalization profile guaranteed by the shared helper.

    `resolve_public_key` is an async callable taking the `kid` and
    returning the raw 32 bytes of the Ed25519 public key. Call-site
    chooses the resolver (in-memory cache for hot verify paths,
    JWKS-backed for federated paths, etc.).

    Raises:
      - `SignatureInvalidError`: signature does not verify
    """
    payload_type = event_type_to_payload_type(event_type)
    body_bytes = canonical_body_bytes(payload)
    pae = pae_bytes(payload_type, body_bytes)
    public_key_bytes = await resolve_public_key(kid)
    try:
        public_key = Ed25519PublicKey.from_public_bytes(public_key_bytes)
    except ValueError as exc:
        raise SignatureInvalidError(event_type, kid, f"public key malformed: {exc}") from exc
    try:
        public_key.verify(signature, pae)
    except InvalidSignature as exc:
        raise SignatureInvalidError(event_type, kid) from exc


async def verify_stream(
    events: Sequence[StoredEvent],
    *,
    resolve_public_key: Callable[[str], Awaitable[bytes]],
    strict: bool = False,
) -> None:
    """Verify every signed event in a loaded stream. Raise on first failure.

    Audit-mode opt-in verification for callers reading from any
    `EventStore` adapter. The function takes the loaded sequence and a
    public-key resolver and walks the stream in order:

      - When `event.signature_kid is not None`, calls `verify_signature`
        with the event's payload, signature, and kid. Raises
        `SignatureInvalidError` on the first row that fails.
      - When `event.signature_kid is None` AND `event.event_type` is in
        `SIGNED_EVENT_TYPES` AND `strict=True`, raises
        `SignatureMissingError` (audit-mode "no signed event went
        unsigned" check).
      - When `event.signature_kid is None` and either the event type
        is NOT in `SIGNED_EVENT_TYPES` or `strict=False`, the event is
        skipped silently. Pre-rollout events and human-actor rows are
        legitimately unsigned per the design lock's "AI-agent events
        signed, human-actor events not" stance.

    The function is event-type-agnostic at the call signature; the
    `SIGNED_EVENT_TYPES` check is the registry-lookup that determines
    which rows must carry a signature.

    Kept as a standalone helper rather than an `EventStore.load` flag
    so the port stays signing-unaware. Callers wanting opt-in
    verification compose: `events, _ = await store.load(...);
    await verify_stream(events, resolve_public_key=...)`.

    `strict=True` is the audit-sweep default; production read paths
    that just need bytes (projection rebuilds, decider folds) leave it
    `False` so they don't pay the verify cost per row.

    Raises:
      - `SignatureInvalidError`: a signed event's signature failed
        verification (tampering, key rotation drift, key compromise).
      - `SignatureMissingError`: only with `strict=True`, an event
        whose type is in SIGNED_EVENT_TYPES has no signature.
    """
    for event in events:
        if event.signature_kid is not None:
            assert event.signature is not None, (
                "events_signature_kid_consistency CHECK constraint guarantees "
                "both-or-neither; signature_kid set implies signature set"
            )
            await verify_signature(
                event_type=event.event_type,
                payload=event.payload,
                signature=event.signature,
                kid=event.signature_kid,
                resolve_public_key=resolve_public_key,
            )
        elif strict and event.event_type in SIGNED_EVENT_TYPES:
            raise SignatureMissingError(event.event_type)


__all__ = [
    "EVENT_TYPE_PAYLOAD_TYPE_PREFIX",
    "EVENT_TYPE_PAYLOAD_TYPE_SUFFIX",
    "SIGNED_EVENT_TYPES",
    "SignatureInvalidError",
    "SignatureMissingError",
    "event_type_to_payload_type",
    "verify_signature",
    "verify_stream",
]
