"""ModelUsageLookup port: which Decisions' recorded LLM calls touched a model?

Consumed by the Agent BC's `list_at_risk_results` read slice, the
catalog's flagship question: when a vendor announces a model's
retirement, enumerate every Decision whose recorded LLM calls used
that model, so the slice can grade each result by whether it stays
re-executable (the entry's `ArchivabilityTier` axis).

## Convention

Same shape as the `SpendLookup` / `LanguageModelLookup` family: a
consumer-shaped Protocol + frozen result VO + an always-empty test
stub, living in `cora.infrastructure.ports` for neutral access. The
Decision BC ships the production adapter
(`cora.decision.adapters.PostgresModelUsageLookup`) because it owns
the durable usage fact: `entries_decision_inferences`, where each LLM
call's provenance row carries `decision_id`, `occurred_at`,
`provider_name`, `request_model`, `response_model`, and `agent_id`.
The Agent BC may not read that table directly (the
port-mediated-integration rule `test_no_cross_bc_projection_sql_reads`
pins at the SQL layer), so this port is how the catalog reaches the
usage facts.

## Match semantics

A row touches the model identity `(provider, model)` when
`provider_name = provider` AND (`request_model = model` OR
`response_model = model` OR `response_model LIKE model || '-%'`).
The LIKE arm exists because providers resolve an alias onto dated
snapshots: a request for `claude-sonnet-4-5` answers as
`claude-sonnet-4-5-20250929`, and those calls are equally at risk
when the alias retires; the caller never pinned the snapshot, so the
alias's retirement takes the identity they recorded out of service.

The result carries ONE row per Decision (the newest touching call),
because the consumer enumerates affected Decisions, not raw calls.
"""

from dataclasses import dataclass
from datetime import datetime
from typing import Protocol
from uuid import UUID


@dataclass(frozen=True)
class ModelTouchedDecision:
    """One Decision whose recorded LLM calls touched the queried model.

    Field values come from the Decision's NEWEST touching inference
    row: `request_model` / `response_model` show which arm matched
    (alias asked for vs snapshot answered with), and `agent_id` is the
    OTel string identity of the recording agent (None for
    operator-attributed rows).
    """

    decision_id: UUID
    occurred_at: datetime
    request_model: str
    response_model: str | None
    agent_id: str | None


class ModelUsageLookup(Protocol):
    """Cross-BC port: enumerate the Decisions whose LLM calls touched a model."""

    async def find_decisions_touching_model(
        self,
        *,
        provider: str,
        model: str,
    ) -> tuple[ModelTouchedDecision, ...]:
        """Return one row per touching Decision, newest call first.

        A Decision touches the model when any of its inference rows
        matches `provider_name = provider` AND (`request_model = model`
        OR `response_model = model` OR `response_model` is a dated
        snapshot of it, the `model || '-%'` LIKE arm; see the module
        docstring for why snapshot answers count). No touching rows
        returns the empty tuple, never None.
        """
        ...


class EmptyModelUsageLookup:
    """Test-default stub: no recorded call ever touched any model.

    Mirrors `AlwaysZeroSpendLookup`'s role: tests and deployments
    without an inference logbook see an empty at-risk list rather than
    an error, so the read slice stays inert until real usage facts
    exist. Slice-specific tests override with an in-test fake returning
    seeded rows or with the real adapter (`PostgresModelUsageLookup`).
    """

    async def find_decisions_touching_model(
        self,
        *,
        provider: str,
        model: str,
    ) -> tuple[ModelTouchedDecision, ...]:
        return ()


__all__ = [
    "EmptyModelUsageLookup",
    "ModelTouchedDecision",
    "ModelUsageLookup",
]
