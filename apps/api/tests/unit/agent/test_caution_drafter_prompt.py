"""Unit tests for the CautionDrafter prompt builder."""

import json
from datetime import UTC, datetime
from uuid import UUID, uuid4

import pytest

from cora.agent.prompts.caution_drafter import (
    CAUTION_DRAFTER_OUTPUT_SCHEMA,
    CAUTION_DRAFTER_PROMPT_TEMPLATE_ID,
    CAUTION_DRAFTER_SYSTEM_PROMPT,
    DEFAULT_CAUTION_DRAFTER_MODEL,
    CandidateTarget,
    CautionDrafterPayload,
    ExistingCaution,
    build_caution_drafter_chat_request,
)
from cora.decision.aggregates.decision import (
    CAUTION_PROPOSAL_CHOICES,
    DECISION_CONTEXT_CAUTION_PROPOSAL,
)

_NOW = datetime(2026, 5, 17, 12, 0, 0, tzinfo=UTC)


def _payload(**overrides: object) -> CautionDrafterPayload:
    defaults: dict[str, object] = {
        "terminal_event_type": "RunAborted",
        "terminal_event_reason": "encoder offline",
        "terminal_event_occurred_at": _NOW.isoformat(),
        "run_id": uuid4(),
        "run_name": "Test Run",
        "run_status": "Aborted",
        "plan_id": uuid4(),
        "subject_id": None,
        "campaign_id": None,
        "effective_parameters": {"exposure_seconds": 0.5},
        "adjustment_count": 0,
        "last_adjusted_at": None,
        "interrupted_at": None,
    }
    defaults.update(overrides)
    return CautionDrafterPayload(**defaults)  # type: ignore[arg-type]


@pytest.mark.unit
def test_prompt_template_id_is_pinned() -> None:
    """The template id is forever-stable; pin the constant."""
    assert UUID("01900000-0000-7000-8000-0000bbbb0001") == CAUTION_DRAFTER_PROMPT_TEMPLATE_ID


@pytest.mark.unit
def test_system_prompt_meets_cache_minimum() -> None:
    """System prompt must exceed Anthropic's 1024-token cache minimum.

    Conservative byte-count proxy: 1024 tokens ~= 4000 bytes.
    Iter-3 prompt targets ~2000 tokens (~8000 bytes).
    """
    assert len(CAUTION_DRAFTER_SYSTEM_PROMPT) > 4000


@pytest.mark.unit
def test_default_model_is_sonnet() -> None:
    """Per design memo: sonnet-4-6 (vs RunDebriefer's haiku-4-5)."""
    assert DEFAULT_CAUTION_DRAFTER_MODEL.provider == "anthropic"
    assert DEFAULT_CAUTION_DRAFTER_MODEL.model == "claude-sonnet-4-6"


@pytest.mark.unit
def test_output_schema_choice_enum_matches_decision_constant_minus_conflicted() -> None:
    """The prompt's `choice` enum MUST equal Decision BC's canonical set
    minus `CautionDraftConflicted`, which is an audit-only outcome the
    subscriber writes on lease loss and the LLM must never produce.
    Per [[project-run-debriefer-lease-design]]."""
    schema_enum = set(CAUTION_DRAFTER_OUTPUT_SCHEMA["properties"]["choice"]["enum"])
    assert schema_enum == set(CAUTION_PROPOSAL_CHOICES) - {"CautionDraftConflicted"}


@pytest.mark.unit
def test_output_schema_lists_all_five_choices() -> None:
    """Closed 5-value set per design memo."""
    schema_enum = set(CAUTION_DRAFTER_OUTPUT_SCHEMA["properties"]["choice"]["enum"])
    assert schema_enum == {
        "NoAction",
        "ProposeNotice",
        "ProposeCaution",
        "ProposeWarning",
        "ProposeSupersede",
    }


@pytest.mark.unit
def test_output_schema_requires_confidence_band() -> None:
    """Confidence band always-emit per FDA + OpenAI agentic best-practices."""
    required = set(CAUTION_DRAFTER_OUTPUT_SCHEMA["required"])
    assert "confidence_band" in required


@pytest.mark.unit
def test_output_schema_confidence_band_is_closed_3value() -> None:
    band_enum = set(CAUTION_DRAFTER_OUTPUT_SCHEMA["properties"]["confidence_band"]["enum"])
    assert band_enum == {"low", "medium", "high"}


@pytest.mark.unit
def test_build_request_returns_cacheable_system_prompt() -> None:
    """The system block must carry a cache breakpoint at 1h TTL."""
    request = build_caution_drafter_chat_request(_payload())
    assert len(request.system.blocks) == 1
    block = request.system.blocks[0]
    assert block.cache is not None
    assert block.cache.ttl == "1h"


@pytest.mark.unit
def test_build_request_user_message_carries_payload_as_json() -> None:
    """Payload travels in user message as JSON (prompt-injection isolation)."""
    payload = _payload(run_name="Test Specimen Run")
    request = build_caution_drafter_chat_request(payload)
    user_text = request.user_message.text
    assert "Test Specimen Run" in user_text
    # The user-message body contains a JSON object after the label.
    json_start = user_text.index("{")
    json_blob = user_text[json_start:]
    parsed = json.loads(json_blob)
    assert parsed["run_name"] == "Test Specimen Run"
    assert parsed["terminal_event_type"] == "RunAborted"


@pytest.mark.unit
def test_build_request_includes_candidate_targets_and_existing_cautions() -> None:
    """The two new payload fields v1 added must travel into the user message."""
    target_id = uuid4()
    caution_id = uuid4()
    payload = _payload(
        candidate_targets=(
            CandidateTarget(
                target_kind="Asset",
                target_id=target_id,
                target_name="Aerotech ABRS",
            ),
        ),
        existing_cautions=(
            ExistingCaution(
                caution_id=caution_id,
                category="Wear",
                severity="Caution",
                text_excerpt="encoder drift",
                workaround_excerpt="re-home before scan",
            ),
        ),
    )
    request = build_caution_drafter_chat_request(payload)
    user_text = request.user_message.text
    assert str(target_id) in user_text
    assert str(caution_id) in user_text
    assert "Aerotech ABRS" in user_text


@pytest.mark.unit
def test_payload_with_no_candidate_targets_serialises_empty_list() -> None:
    """Empty defaults must round-trip as JSON-empty (not missing)."""
    request = build_caution_drafter_chat_request(_payload())
    json_blob = request.user_message.text[request.user_message.text.index("{") :]
    parsed = json.loads(json_blob)
    assert parsed["candidate_targets"] == []
    assert parsed["existing_cautions"] == []


@pytest.mark.unit
def test_decision_context_constant_matches_design_lock() -> None:
    """The context value used by the subscriber is `CautionProposal`."""
    assert DECISION_CONTEXT_CAUTION_PROPOSAL == "CautionProposal"


# ---------------------------------------------------------------------------
# Cross-BC enum drift pins
# ---------------------------------------------------------------------------
# The prompt's severity / category / target_kind enums are sourced from
# Caution BC at module-import time. If Caution BC adds a 7th category
# (or renames a severity tier), the prompt picks it up SILENTLY and
# ships an un-anchored vocabulary to the LLM. These pin tests fail loudly
# on drift so the prompt's anchoring is reviewed when the source-of-
# truth changes.


@pytest.mark.unit
def test_output_schema_severity_enum_matches_caution_bc_z535() -> None:
    """Severity must equal Caution BC's Z535-downshifted 3-tier ladder."""
    severity_enum = set(
        CAUTION_DRAFTER_OUTPUT_SCHEMA["properties"]["proposed_caution"]["properties"]["severity"][
            "enum"
        ]
    )
    # Hard-coded copy of Caution BC's day-one Z535 lock; if Caution BC
    # adds Danger (or restores it), this test forces a prompt review.
    assert severity_enum == {"Notice", "Caution", "Warning"}


@pytest.mark.unit
def test_output_schema_category_enum_matches_caution_bc_day_one_six() -> None:
    """Category must equal Caution BC's closed 6-value day-one lock."""
    category_enum = set(
        CAUTION_DRAFTER_OUTPUT_SCHEMA["properties"]["proposed_caution"]["properties"]["category"][
            "enum"
        ]
    )
    # Hard-coded copy of Caution BC's day-one closed vocabulary; if
    # Caution BC adds a 7th category, this test forces a prompt review
    # (the LLM needs explicit anchor + example narrative for new tiers).
    assert category_enum == {
        "Wear",
        "Calibration",
        "Wiring",
        "OperationalWindow",
        "InterlockQuirk",
        "ProcedureGotcha",
    }


@pytest.mark.unit
def test_output_schema_target_kind_is_closed_two_values() -> None:
    """Target kind covers Caution BC's polymorphic union (Asset+Procedure)."""
    target_kind_enum = set(
        CAUTION_DRAFTER_OUTPUT_SCHEMA["properties"]["proposed_caution"]["properties"][
            "target_kind"
        ]["enum"]
    )
    assert target_kind_enum == {"Asset", "Procedure"}
