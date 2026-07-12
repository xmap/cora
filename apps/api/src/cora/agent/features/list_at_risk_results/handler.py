"""Application handler for the `list_at_risk_results` query slice.

The catalog's flagship read: when a vendor announces a model's
retirement, enumerate every Decision whose recorded LLM calls used
that model, graded by whether the result stays re-executable.

Workflow:

    1. authorize(principal_id, query_name, conduit_id) -> Allow | Deny
    2. load_language_model(...)  -> LanguageModel
                                    (raises LanguageModelNotFoundError
                                     when absent; the route's registered
                                     handler maps it to 404)
    3. deps.model_usage_lookup.find_decisions_touching_model(
           provider=entry.model_ref.provider,
           model=entry.model_ref.model)
    4. grade + return AtRiskResultsView

## Grading

`reproducibility_grade` follows the entry's `ArchivabilityTier`:
`Pinned` (the facility holds the weights and can serve them
indefinitely) grades `ReExecutable`; `Alias` (an identity the provider
may move or retire) grades `AttributableOnly`, because provenance
survives a retirement but re-execution does not.

`at_risk` is true only when the grade is `AttributableOnly` AND the
entry's status is RetirementAnnounced or Retired: risk is the
conjunction of a fragile identity and a vendor lifecycle event.

## Why the endpoint answers for ANY status

An operator may ask what WOULD be at risk before any announcement
(catalog triage: how exposed are we if the vendor retires this alias
tomorrow?). The slice therefore never gates on status; the `at_risk`
flag carries the lifecycle judgment and the Decision list is always
returned.
"""

from dataclasses import dataclass
from typing import Protocol
from uuid import UUID

from cora.agent.aggregates.language_model import (
    ArchivabilityTier,
    LanguageModelNotFoundError,
    LanguageModelStatus,
    load_language_model,
)
from cora.agent.errors import UnauthorizedError
from cora.agent.features.list_at_risk_results.query import ListAtRiskResults
from cora.infrastructure.kernel import Kernel
from cora.infrastructure.logging import get_logger
from cora.infrastructure.ports import Deny, ModelUsageLookupResult
from cora.infrastructure.routing import NIL_SENTINEL_ID

_QUERY_NAME = "ListAtRiskResults"

GRADE_RE_EXECUTABLE = "ReExecutable"
GRADE_ATTRIBUTABLE_ONLY = "AttributableOnly"

# The vendor lifecycle events that turn a fragile identity into live
# risk; Deprecated is excluded because the FACILITY ending an entry's
# service life does not take the provider-side identity out of service.
_AT_RISK_STATUSES = frozenset(
    {LanguageModelStatus.RETIREMENT_ANNOUNCED, LanguageModelStatus.RETIRED}
)

_log = get_logger(__name__)


@dataclass(frozen=True)
class AtRiskResultsView:
    """Read-side bundle: the entry's grading axes plus the touched
    Decisions the usage lookup returned (newest call first). `results`
    is populated for ANY status and archivability; `at_risk` alone
    carries the lifecycle judgment."""

    language_model_id: UUID
    status: LanguageModelStatus
    archivability: ArchivabilityTier
    reproducibility_grade: str
    at_risk: bool
    results: tuple[ModelUsageLookupResult, ...]


class Handler(Protocol):
    """Callable interface every list_at_risk_results handler implements."""

    async def __call__(
        self,
        query: ListAtRiskResults,
        *,
        principal_id: UUID,
        correlation_id: UUID,
        surface_id: UUID = NIL_SENTINEL_ID,
    ) -> AtRiskResultsView: ...


def bind(deps: Kernel) -> Handler:
    """Build a list_at_risk_results handler closed over the shared deps."""

    async def handler(
        query: ListAtRiskResults,
        *,
        principal_id: UUID,
        correlation_id: UUID,
        surface_id: UUID = NIL_SENTINEL_ID,
    ) -> AtRiskResultsView:
        _log.info(
            "list_at_risk_results.start",
            query_name=_QUERY_NAME,
            language_model_id=str(query.language_model_id),
            principal_id=str(principal_id),
            correlation_id=str(correlation_id),
        )

        decision = await deps.authz.authorize(
            principal_id=principal_id,
            command_name=_QUERY_NAME,
            conduit_id=NIL_SENTINEL_ID,
            surface_id=surface_id,
        )
        if isinstance(decision, Deny):
            _log.info(
                "list_at_risk_results.denied",
                query_name=_QUERY_NAME,
                language_model_id=str(query.language_model_id),
                principal_id=str(principal_id),
                correlation_id=str(correlation_id),
                reason=decision.reason,
            )
            raise UnauthorizedError(decision.reason)

        entry = await load_language_model(deps.event_store, query.language_model_id)
        if entry is None:
            _log.info(
                "list_at_risk_results.not_found",
                query_name=_QUERY_NAME,
                language_model_id=str(query.language_model_id),
                principal_id=str(principal_id),
                correlation_id=str(correlation_id),
            )
            raise LanguageModelNotFoundError(query.language_model_id)

        results = await deps.model_usage_lookup.find_decisions_touching_model(
            provider=entry.model_ref.provider,
            model=entry.model_ref.model,
        )
        grade = (
            GRADE_RE_EXECUTABLE
            if entry.archivability is ArchivabilityTier.PINNED
            else GRADE_ATTRIBUTABLE_ONLY
        )
        at_risk = grade == GRADE_ATTRIBUTABLE_ONLY and entry.status in _AT_RISK_STATUSES

        _log.info(
            "list_at_risk_results.success",
            query_name=_QUERY_NAME,
            language_model_id=str(query.language_model_id),
            principal_id=str(principal_id),
            correlation_id=str(correlation_id),
            status=entry.status.value,
            reproducibility_grade=grade,
            at_risk=at_risk,
            result_count=len(results),
        )
        return AtRiskResultsView(
            language_model_id=entry.id,
            status=entry.status,
            archivability=entry.archivability,
            reproducibility_grade=grade,
            at_risk=at_risk,
            results=results,
        )

    return handler
