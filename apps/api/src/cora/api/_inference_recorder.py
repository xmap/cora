"""Composition-root `InferenceRecorder` that delegates to `append_inferences`.

`DelegatingInferenceRecorder` is the production implementor of the
`InferenceRecorder` capability port (`cora.infrastructure.ports`). It lives at
the composition root (`cora.api`) because it is the only place allowed to reach
a sibling BC's `features.*`: it translates an agent's neutral
`AgentInferenceTrace` into the Decision BC's `AppendInferences` command and
calls the existing, tested `append_inferences` handler. That reuse keeps the
lazy logbook-open + idempotency (DecisionLogbookOpened at-most-once +
inference-store PK dedup) in one place rather than re-implementing it in each
agent.

Fire-and-forget per the port contract: the Decision aggregate write is the
audit-grade source of truth, and inference capture is supplementary, so this
implementor never raises. An authorization denial (the agent's principal lacks
`AppendInferences` under a real Trust policy) is logged LOUDLY so a missing
operator grant is visible rather than silently dropping provenance, mirroring
the RunSupervisor `hold_unauthorized` posture. Any other failure is logged and
swallowed.
"""

from uuid import UUID

from cora.decision.errors import UnauthorizedError
from cora.decision.features.append_inferences.command import (
    AppendInferences,
    ReasoningEntryInput,
)
from cora.decision.features.append_inferences.handler import Handler
from cora.infrastructure.logging import get_logger
from cora.infrastructure.ports import AgentInferenceTrace

_log = get_logger(__name__)


class DelegatingInferenceRecorder:
    """`InferenceRecorder` that forwards traces to the `append_inferences` handler."""

    def __init__(self, append_inferences: Handler) -> None:
        self._append_inferences = append_inferences

    async def record(
        self,
        trace: AgentInferenceTrace,
        *,
        principal_id: UUID,
        correlation_id: UUID,
        causation_id: UUID | None = None,
    ) -> None:
        command = AppendInferences(
            decision_id=trace.decision_id,
            entries=(
                ReasoningEntryInput(
                    event_id=trace.event_id,
                    occurred_at=trace.occurred_at,
                    operation_name=trace.operation_name,
                    provider_name=trace.provider_name,
                    request_model=trace.request_model,
                    response_model=trace.response_model,
                    request_max_tokens=trace.request_max_tokens,
                    finish_reasons=trace.finish_reasons,
                    input_tokens=trace.input_tokens,
                    output_tokens=trace.output_tokens,
                    agent_id=trace.agent_id,
                    agent_name=trace.agent_name,
                ),
            ),
        )
        try:
            await self._append_inferences(
                command,
                principal_id=principal_id,
                correlation_id=correlation_id,
                causation_id=causation_id,
            )
        except UnauthorizedError as exc:
            # Loud, actionable: under a real Trust policy the agent principal
            # must be granted AppendInferences (as RunSupervisor is granted
            # HoldRun). Swallowing this silently would lose provenance with no
            # signal. See the inference_recorder port docstring.
            _log.warning(
                "inference_recorder.unauthorized",
                decision_id=str(trace.decision_id),
                principal_id=str(principal_id),
                reason=str(exc),
            )
        except Exception as exc:
            _log.warning(
                "inference_recorder.failed",
                decision_id=str(trace.decision_id),
                error_class=type(exc).__name__,
                error_message=str(exc)[:200],
            )


__all__ = ["DelegatingInferenceRecorder"]
