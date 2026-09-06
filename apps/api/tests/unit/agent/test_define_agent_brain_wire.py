"""The wire lets a caller name a brain that is not a language model.

Before this, `define_agent` required an LLM-shaped `model_ref`, so the only
way to define a rule-brained Agent over the wire was to invent a model name
it would never call. That is the sentinel eighteen seeds carried, and the
wire was the last place still forcing it.

Exactly one of `model_ref` / `brain` must be supplied. Not "brain wins":
two declarations that disagree mean the caller believes something the record
would not say, and silently picking one makes the wire lie about what was
asked for.
"""

import pytest
from pydantic import ValidationError

from cora.agent._brain_wire import brain_from_body
from cora.agent.aggregates.agent import (
    BrainKind,
    BrainRef,
    InvalidBrainRefError,
    ModelRef,
)
from cora.agent.features.define_agent.route import (
    BrainRequest,
    DefineAgentRequest,
    ModelRefRequest,
)

_MODEL = ModelRefRequest(provider="anthropic", model="claude-sonnet-4-6")


def _body(**overrides: object) -> dict[str, object]:
    base: dict[str, object] = {"kind": "RunDebriefer", "name": "Run Debrief", "version": "v1"}
    base.update(overrides)
    return base


@pytest.mark.unit
def test_a_rule_brain_needs_no_model_ref() -> None:
    request = DefineAgentRequest(
        **_body(brain=BrainRequest(kind="Rule", rule="ExperimentCoordinator:v1"))  # type: ignore[arg-type]
    )

    brain = brain_from_body(request.brain)

    assert brain == BrainRef.for_rule("ExperimentCoordinator:v1")


@pytest.mark.unit
def test_a_language_model_brain_carries_its_model() -> None:
    request = DefineAgentRequest(
        **_body(brain=BrainRequest(kind="LanguageModel", model_ref=_MODEL))  # type: ignore[arg-type]
    )

    brain = brain_from_body(request.brain)

    assert brain is not None
    assert brain.kind is BrainKind.LANGUAGE_MODEL
    assert brain.model_ref == ModelRef(provider="anthropic", model="claude-sonnet-4-6")


@pytest.mark.unit
def test_legacy_model_ref_body_still_defines_an_agent() -> None:
    """Callers that predate `brain` keep working, and the command records
    what they said rather than a translation of it."""
    request = DefineAgentRequest(**_body(model_ref=_MODEL))  # type: ignore[arg-type]

    assert request.brain is None
    assert request.model_ref is not None


@pytest.mark.unit
def test_naming_neither_is_rejected() -> None:
    with pytest.raises(ValidationError, match="exactly one"):
        DefineAgentRequest(**_body())  # type: ignore[arg-type]


@pytest.mark.unit
def test_naming_both_is_rejected() -> None:
    """The ambiguity is the point: a body carrying both could disagree with
    itself, and resolving that quietly would record a brain nobody asked for."""
    with pytest.raises(ValidationError, match="exactly one"):
        DefineAgentRequest(
            **_body(  # type: ignore[arg-type]
                model_ref=_MODEL,
                brain=BrainRequest(kind="Rule", rule="ExperimentCoordinator:v1"),
            )
        )


@pytest.mark.unit
def test_a_kind_that_disagrees_with_its_payload_is_refused() -> None:
    """The wire cannot express kind-consistency on its own, so the payload
    goes to the VO. A Rule body carrying a model_ref is not coerced."""
    with pytest.raises(InvalidBrainRefError):
        brain_from_body(BrainRequest(kind="Rule", rule="X:v1", model_ref=_MODEL))

    with pytest.raises(InvalidBrainRefError):
        brain_from_body(BrainRequest(kind="LanguageModel"))


@pytest.mark.unit
def test_rule_name_is_bounded_and_non_empty() -> None:
    """Unbounded was tolerable while only seeds wrote it; it is wire-supplied
    now, so it takes the same bound as every sibling identity field."""
    with pytest.raises(ValidationError):
        BrainRequest(kind="Rule", rule="")

    with pytest.raises(ValidationError):
        BrainRequest(kind="Rule", rule="x" * 201)

    with pytest.raises(InvalidBrainRefError, match="non-empty after trim"):
        BrainRef.for_rule("   ")
