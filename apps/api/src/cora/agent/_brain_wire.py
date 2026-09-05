"""Build a typed `BrainRef` from a wire body, for every front door that takes one.

Four call sites want this: `define_agent`'s route and MCP tool, and
`restate_agent_definition`'s route and MCP tool. Hoisted rather than copied
because a per-kind mapping copied four ways is the hand-maintained field list
that [[project_field_drop_bug_class]] is about: add a `BrainKind` and three
of the four copies keep compiling while quietly refusing the new kind.

The payload is handed to the VO rather than re-validated here, so a body whose
payload disagrees with its `kind` surfaces as `InvalidBrainRefError` instead of
being coerced into something the caller did not ask for. One home for the
invariant.

The protocol is structural on purpose: each slice declares its own request
model with its own field descriptions and bounds, and they only have to agree
on shape.
"""

from typing import Protocol, assert_never

from cora.agent.aggregates.agent import (
    BrainKind,
    BrainRef,
    InvalidBrainRefError,
    ModelRef,
)


class ModelRefBody(Protocol):
    """Structural shape of any slice's ModelRef sub-body."""

    @property
    def provider(self) -> str: ...
    @property
    def model(self) -> str: ...
    @property
    def snapshot_pin(self) -> str | None: ...


class BrainBody(Protocol):
    """Structural shape of any slice's Brain sub-body."""

    @property
    def kind(self) -> str: ...
    @property
    def model_ref(self) -> ModelRefBody | None: ...
    @property
    def rule(self) -> str | None: ...


def model_ref_from_body(body: ModelRefBody | None) -> ModelRef | None:
    """Carry a wire ModelRef body across to the typed VO."""
    if body is None:
        return None
    return ModelRef(provider=body.provider, model=body.model, snapshot_pin=body.snapshot_pin)


def brain_from_body(body: BrainBody | None) -> BrainRef | None:
    """Build the typed BrainRef a wire body names, or None when it names none.

    Every field the body carries is passed through, including ones that do not
    belong to the stated kind, so `BrainRef.__post_init__` is what rejects a
    mismatch. Filtering them out here would silently accept a body that
    contradicts itself.
    """
    if body is None:
        return None
    model_ref = model_ref_from_body(body.model_ref)
    match BrainKind(body.kind):
        case BrainKind.LANGUAGE_MODEL:
            if model_ref is None:
                raise InvalidBrainRefError("a LanguageModel brain carries model_ref and no rule")
            return BrainRef(kind=BrainKind.LANGUAGE_MODEL, model_ref=model_ref, rule=body.rule)
        case BrainKind.RULE:
            return BrainRef(kind=BrainKind.RULE, rule=body.rule, model_ref=model_ref)
        case _:  # pragma: no cover - exhaustive over a closed enum
            assert_never(BrainKind(body.kind))


__all__ = ["BrainBody", "ModelRefBody", "brain_from_body", "model_ref_from_body"]
