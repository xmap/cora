"""LanguageModelLookup port: is this model identity in the approved catalog?

Consumed by the define_agent gate (an operator cannot register an agent
on a model the facility has not approved). The shipped fleet's own
defaults are covered by a unit consistency test that pins the fleet
constants against the seed entries; no runtime consumer walks the
fleet at startup. The query shape is by model identity, not by entry
id, because that is the only key the consumer holds: an
`Agent.model_ref` carries provider + model.

## Convention

Same neutral-port shape as `SpendLookup` and the start_run lookup
family: a consumer-shaped Protocol + frozen result VO + an always-pass
test stub here, with the production adapter shipped by the BC that owns
the fact (the agent BC's `PostgresLanguageModelLookup` over
`proj_agent_language_model_summary`). The port lives in infrastructure
even though today's consumers share the agent BC, because the catalog's
next consumers (the conduct seam's degrade path, the pricing bridge) do
not.

## Failure direction

The kernel default is the always-approved stub, so tests and
deployments that have not stood up a catalog are unaffected (the same
opt-in posture as every lookup in the family: declaring a catalog is
what arms the gate). The Postgres adapter answers with the newest
APPROVED entry only; None means "nothing currently approved for this
identity" (never cataloged, or every entry for it is Defined or
terminal), which the gate treats as refusal once a catalog exists.
"""

from dataclasses import dataclass
from typing import Protocol
from uuid import UUID


@dataclass(frozen=True)
class LanguageModelLookupResult:
    """The catalog's answer for one (provider, model) identity."""

    language_model_id: UUID
    status: str
    data_tier: str
    archivability: str
    snapshot_pin: str | None


class LanguageModelLookup(Protocol):
    """Cross-cutting port: resolve a model identity to its approved catalog entry."""

    async def find_by_model(
        self,
        *,
        provider: str,
        model: str,
    ) -> LanguageModelLookupResult | None:
        """Return the newest APPROVED entry for `(provider, model)`, or None.

        None means "nothing currently approved for this identity":
        the identity was never cataloged, or every entry for it is
        Defined or terminal. Approved-only on purpose: the gate's
        question is whether an approval currently stands, so an
        unapproved or deprecated newer entry can never shadow an
        older Approved one, and deprecating a mistaken duplicate
        restores the previous Approved entry.
        """
        ...


class AlwaysApprovedLanguageModelLookup:
    """Test-default stub: every model identity is an Approved entry.

    Mirrors `AlwaysZeroSpendLookup`'s role: the kernel default keeps
    every existing test and catalog-less deployment permissive (the
    approved-only contract is trivially satisfied because every answer
    IS an Approved entry). The synthetic entry id is the nil-adjacent
    constant below, never a real stream id.
    """

    _SYNTHETIC_ID = UUID("00000000-0000-0000-0000-00000000a11a")

    async def find_by_model(
        self,
        *,
        provider: str,
        model: str,
    ) -> LanguageModelLookupResult | None:
        return LanguageModelLookupResult(
            language_model_id=self._SYNTHETIC_ID,
            status="Approved",
            data_tier="Internal",
            archivability="Alias",
            snapshot_pin=None,
        )


__all__ = [
    "AlwaysApprovedLanguageModelLookup",
    "LanguageModelLookup",
    "LanguageModelLookupResult",
]
