"""LanguageModel's update-handler factory (thin wrapper).

Mirrors `cora.agent._agent_update_handler` per the per-aggregate
factory convention: that file's docstring kept its module shape lined
up with the cross-BC factory precisely so a future second aggregate
in the BC would slot in cleanly, and LanguageModel is that aggregate.
Four transition slices bind through here (`approve_language_model`,
`announce_language_model_retirement`, `retire_language_model`,
`deprecate_language_model`).

Thin variant only: none of the catalog's transition deciders takes
the acting principal (the approving / retiring actor's identity lives
on the event envelope, `StoredEvent.principal_id`), so the
actor-stamping `make_agent_actor_update_handler` sibling stays
Agent-only until a fold-symmetry LanguageModel slice needs one.

## LanguageModel-side knobs closed over

  - `stream_type = "LanguageModel"`.
  - `target_id_attr = "language_model_id"` -- every LanguageModel
    transition command exposes `language_model_id: UUID`.
  - `unauthorized_error = UnauthorizedError` from the Agent BC (both
    aggregates share the BC's application-error namespace, so an
    Agent-BC 403 stays one class in log search).
  - The four codec functions imported from
    `cora.agent.aggregates.language_model`.

`extra_log_fields` is a per-slice optional extractor for command-
specific fields the structured log should emit, same contract as the
Agent factory.
"""

from collections.abc import Callable, Sequence
from typing import Any

from cora.agent.aggregates.language_model import (
    LanguageModelEvent,
    event_type_name,
    fold,
    from_stored,
    to_payload,
)
from cora.agent.errors import UnauthorizedError
from cora.infrastructure.kernel import Kernel
from cora.infrastructure.update_handler import make_update_handler

_STREAM_TYPE = "LanguageModel"
_TARGET_ID_ATTR = "language_model_id"


def make_language_model_update_handler(
    deps: Kernel,
    *,
    command_name: str,
    log_prefix: str,
    decide_fn: Callable[..., Sequence[LanguageModelEvent]],
    extra_log_fields: Callable[[Any], dict[str, Any]] | None = None,
):
    """Build an update-style handler for one LanguageModel slice (fold-NEITHER posture)."""
    return make_update_handler(
        deps,
        stream_type=_STREAM_TYPE,
        target_id_attr=_TARGET_ID_ATTR,
        from_stored=from_stored,
        to_payload=to_payload,
        event_type_name=event_type_name,
        fold=fold,
        unauthorized_error=UnauthorizedError,
        command_name=command_name,
        log_prefix=log_prefix,
        decide_fn=decide_fn,
        extra_log_fields=extra_log_fields,
    )


__all__ = ["make_language_model_update_handler"]
