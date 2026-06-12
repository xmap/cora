"""Signer port — cryptographic attestation for AI-agent-produced events.

`Signer` is the hexagonal port for signing event payloads. Implementations
plug in at the handler tier post-decider / pre-INSERT per
[[project_signed_events_design]]. Today: the in-memory Ed25519 adapter
`InMemorySigner` ships (wired by default for dev and tests); the
verification path uses the same canonicalization helper from
[[project_content_addressed_identity_design]] and a directly-resolved
public key. The port exists so the choice of signing backend stays
swappable: a production iteration swaps in one of these backends without
touching the handlers that call `Signer.sign`:

  - Sigstore keyless OIDC (Fulcio short-lived cert bound to a workload
    OIDC identity; Rekor transparency log)
  - SPIFFE / SPIRE workload identity with embedded SVID
  - Cloud KMS-backed Ed25519 (AWS KMS / GCP KMS / Azure Key Vault) with
    a private Rekor or alternative transparency log
  - Local in-memory keystore for tests / dev

The signature bytes are produced over PAE-wrapped canonical body bytes
(the same input Candidate A hashes for content identity), so swapping
signing backends does NOT change the canonicalization profile or the
verification-side bytes.

## What `sign` returns

A tuple `(signature, kid, signing_version)`. `signature` is the raw
64-byte Ed25519 output (`alg=EdDSA` per the design lock); `kid` is
the key identifier that lets the verifier resolve the matching public
key; `signing_version` is the signing-recipe identifier per
[[project_canonicalization_port_design]] (the v1 default is
`"cora/v1"`), recorded so the verifier can dispatch to the matching
ByteSigner adapter via the SigningRegistry. The semantics of `kid`
vary by adapter:

  - Sigstore Fulcio: cert serial of the short-lived OIDC-bound cert
  - SPIFFE / SVID: the SVID's SPIFFE ID
  - Cloud KMS: the KMS key resource name / version
  - Local keystore: an opaque string the keystore maps to a key

The verification path takes the same `kid` plus a public-key resolver
to recover the verifying key; see `verify_signature` in
`cora.infrastructure.signing`.

## What is NOT here

  - The verify path lives in `cora.infrastructure.signing` (a function,
    not a port, because verification is pure given the public key).
  - The PUBLIC-key resolution mechanism is intentionally NOT on this
    port. Resolvers are call-site-specific (read-time verification can
    use a different cache than write-time signing); the verify function
    takes a resolver callable so callers compose.
  - `SIGNED_EVENT_TYPES` (the closed set of event-type names that MUST
    be signed at write time) lives in `cora.infrastructure.signing`, not
    here, because it is the verification side's invariant.

## Error model

Three adapter-tier errors. Each maps to an HTTP status when surfaced
through the route layer; the handler tier MAY catch and retry under
specific patterns (for example transient Fulcio outage retried under a
configured fallback).

  - `SignerKeyNotFoundError` (HTTP 500): the `actor_id` does not resolve
    to any signing key in the adapter's keystore. System misconfiguration;
    never expected at runtime.
  - `SignerKeyInactiveError` (HTTP 503): the resolved key is retired
    (rotation in progress). Caller retries against current key.
  - `SignerUnavailableError` (HTTP 503): the signing backend itself is
    unreachable (Sigstore Fulcio outage, KMS network blip, etc.). Caller
    retries; non-blocking when a fallback adapter is configured.
"""

from collections.abc import Mapping
from typing import Any, Protocol
from uuid import UUID


class SignerKeyNotFoundError(Exception):
    """The `actor_id` does not resolve to a signing key in the adapter's keystore.

    System misconfiguration. Surfaces as HTTP 500 at the route layer
    because no caller retry will help: the key was never registered
    for this actor or the Agent BC's bootstrap missed a registration
    step.
    """

    def __init__(self, actor_id: UUID, detail: str = "") -> None:
        super().__init__(
            f"No signing key resolved for actor {actor_id}" + (f": {detail}" if detail else "")
        )
        self.actor_id = actor_id
        self.detail = detail


class SignerKeyInactiveError(Exception):
    """The resolved signing key is retired or inactive (rotation in progress).

    Surfaces as HTTP 503 because the caller can retry once the rotation
    has settled and the new `kid` is the active one.
    """

    def __init__(self, kid: str, detail: str = "") -> None:
        super().__init__(f"Signing key {kid!r} is inactive" + (f": {detail}" if detail else ""))
        self.kid = kid
        self.detail = detail


class SignerUnavailableError(Exception):
    """The signing backend cannot be reached.

    Surfaces as HTTP 503 with `Retry-After`. Transient by definition;
    callers retry. Adapters with a configured fallback (for example local
    keystore behind Sigstore Fulcio) may catch this internally and
    re-route before it reaches the caller.
    """

    def __init__(self, backend: str, detail: str = "") -> None:
        super().__init__(
            f"Signing backend {backend!r} unavailable" + (f": {detail}" if detail else "")
        )
        self.backend = backend
        self.detail = detail


class Signer(Protocol):
    """Cryptographic signer for event payloads.

    Implementations (none ship today; see module docstring for the
    planned set) resolve a private key for the actor, canonicalize the
    payload using the shared content-hash pipeline, wrap with DSSE PAE,
    and sign. Return value is `(signature, kid, signing_version)` for
    the handler to persist alongside the event row.

    Every method is async because the production adapters (Sigstore
    Fulcio, KMS) are network-bound. In-process adapters (local
    keystore) trivially wrap their sync work as `async`.
    """

    async def sign(
        self,
        *,
        event_type: str,
        payload: Mapping[str, Any],
        actor_id: UUID,
    ) -> tuple[bytes, str, str]:
        """Produce a signature over the canonicalized + PAE-wrapped payload.

        `event_type` is the unbracketed event-type name (for example
        `"DecisionRegistered"`, the sole entry in `SIGNED_EVENT_TYPES`
        today); the implementation MUST resolve it to the
        full payloadType URI via
        `cora.infrastructure.signing.event_type_to_payload_type` and
        canonicalize the payload via
        `cora.shared.content_hash.canonical_body_bytes` +
        `cora.shared.content_hash.pae_bytes`. Rolling a custom
        canonicalization here is the dominant footgun: it desyncs from
        `verify_signature` and breaks every signed event silently.
        `payload` is the event-payload dict that will land in
        `events.payload` jsonb.

        `actor_id` identifies WHO is signing (in CORA: an Agent.id that
        shares a row with an Actor.id per [[project_agent_bc_design]]).
        The adapter uses this to look up the private key.

        Returns `(signature, kid, signing_version)`. `signature` is raw
        bytes (64 bytes for Ed25519). `kid` is the adapter-specific key
        identifier the verifier passes to its public-key resolver.
        `signing_version` is the signing-recipe identifier
        (`"cora/v1"` for the shipped Ed25519-over-DSSE-PAE recipe);
        the verifier dispatches to the matching ByteSigner adapter
        via the SigningRegistry. Adapters MUST return the version
        string that names their signing recipe; the matched-pair
        invariant is enforced row-by-row by an architecture-fitness
        test.

        Failure modes:
          - `SignerKeyNotFoundError`: actor has no registered key
          - `SignerKeyInactiveError`: resolved key is retired
          - `SignerUnavailableError`: signing backend unreachable
        """
        ...


__all__ = [
    "Signer",
    "SignerKeyInactiveError",
    "SignerKeyNotFoundError",
    "SignerUnavailableError",
]
