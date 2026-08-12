"""Redact `entries_*` rows: a hand-authored disposition table per kind.

Transcribed from `project_record_export_v3.md` F5's three tables (28
`text` columns across 8 tables, split PROVED CLOSED / JUDGED LOW RISK /
DROPPED; the 5 jsonb columns, 4 BY_VALUE + 1 dropped-whole). Unlike
tier 1, there is no generator here: F5 itself says tier 2 is small
enough (103 columns total) to hand-enumerate, and that hand-enumeration
is exactly what a fitness test elsewhere
(`test_record_export_registry_completeness.py`-style AST discovery does
not cover, since this table has no source annotation to derive from)
makes `test_redact_tier2.py` responsible for keeping honest against
`_registry.py`'s own table list.

`BY_VALUE` reuses the exact string tier 1's locked, generated vocabulary
already uses for the same dispatch (`_dispositions.py`'s `"by-value"`):
both name the same operation (apply the generic leaf rule), and tier 2
is the side free to conform since it is hand-authored, not generated.

`kind` here is the Step 1 registry's kind (`"activity"`, `"verdict"`,
...), matching `_registry.EntriesTableSpec.kind`, not the raw table name.
"""

from typing import Any

from cora.infrastructure.record_export._leaf_rule import OMITTED, apply_leaf_rule
from cora.infrastructure.record_export._tokens import TokenMap

KEEP = "keep"
TOKEN = "token"
DROP = "drop"
BY_VALUE = "by-value"

# Every column of every kind's entries table. `BY_VALUE` columns are
# jsonb and are handled via TIER2_JSONB_CLEARED_POINTERS /
# TIER2_JSONB_DROPPED_COLUMNS below, never via this dict's own value.
TIER2_DISPOSITIONS: dict[str, dict[str, str]] = {
    "verdict": {
        "event_id": TOKEN,
        "conduit_id": TOKEN,
        "logbook_id": TOKEN,
        "actor_id": TOKEN,
        "command_name": KEEP,  # judged low risk: written from code literals
        "decision": KEEP,  # proved closed: DB CHECK (decision IN ('Allow','Deny'))
        "reason": DROP,  # P0-4: builds f"Principal {principal_id} not in policy..."
        "correlation_id": TOKEN,
        "causation_id": TOKEN,
        "occurred_at": KEEP,
        "recorded_at": KEEP,
    },
    "inference": {
        "event_id": TOKEN,
        "decision_id": TOKEN,
        "logbook_id": TOKEN,
        "correlation_id": TOKEN,
        "causation_id": TOKEN,
        "occurred_at": KEEP,
        "duration": KEEP,
        "operation_name": KEEP,  # judged low risk: names an operation, not a person
        "provider_name": KEEP,
        "request_model": KEEP,
        "response_id": DROP,  # correlator into an external vendor's records
        "response_model": KEEP,
        "request_temperature": KEEP,
        "request_top_p": KEEP,
        "request_max_tokens": KEEP,
        "output_type": KEEP,
        "finish_reasons": DROP,  # text[]: array of str, drop-unless-cleared
        "input_tokens": KEEP,
        "output_tokens": KEEP,
        "agent_id": DROP,  # OTel gen_ai.agent.id; correlator, fail closed
        "agent_name": DROP,  # operator-authored free text
        "agent_description": DROP,
        "conversation_id": DROP,
        "tool_name": KEEP,  # judged low risk: names a tool, not a person
        "tool_call_id": DROP,
        "tool_type": KEEP,
        "messages": BY_VALUE,  # dropped whole, see TIER2_JSONB_DROPPED_COLUMNS
        "recorded_at": KEEP,
        "cost_usd": KEEP,
    },
    "activity": {
        "event_id": TOKEN,
        "procedure_id": TOKEN,
        "logbook_id": TOKEN,
        "actor_id": TOKEN,
        "command_name": KEEP,  # judged low risk (3-of-8 group)
        "step_kind": KEEP,  # proved closed: Literal + STEP_KIND_VALUES
        "payload": BY_VALUE,
        "sampled_at": KEEP,
        "occurred_at": KEEP,
        "correlation_id": TOKEN,
        "causation_id": TOKEN,
        "recorded_at": KEEP,
    },
    "diagnostic": {
        "event_id": TOKEN,
        "procedure_id": TOKEN,
        "logbook_id": TOKEN,
        "iteration_index": KEEP,
        "model_ref": KEEP,  # judged low risk: fed from advice.model_ref, "unknown" fallback
        "payload": BY_VALUE,
        "sampled_at": KEEP,
        "occurred_at": KEEP,
        "correlation_id": TOKEN,
        "causation_id": TOKEN,
        "recorded_at": KEEP,
    },
    "outcome": {
        "event_id": TOKEN,
        "procedure_id": TOKEN,
        "logbook_id": TOKEN,
        "iteration_index": KEEP,
        "point": BY_VALUE,
        "measurements": BY_VALUE,
        "succeeded": KEEP,
        "actuation_kind": KEEP,  # judged low risk: rehearsal-vs-live gate, closed by its writers
        "sampled_at": KEEP,
        "occurred_at": KEEP,
        "correlation_id": TOKEN,
        "causation_id": TOKEN,
        "recorded_at": KEEP,
    },
    "observation": {
        "event_id": TOKEN,
        "run_id": TOKEN,
        "logbook_id": TOKEN,
        "actor_id": TOKEN,
        "command_name": KEEP,  # judged low risk (3-of-8 group)
        "channel_name": KEEP,  # EPICS channel address, facility-fixed, already public
        "value": KEEP,
        "units": KEEP,  # judged low risk: unvalidated, low risk, not closed
        "sampling_procedure": KEEP,  # proved closed: Literal + SAMPLING_PROCEDURE_VALUES
        "sampled_at": KEEP,
        "occurred_at": KEEP,
        "correlation_id": TOKEN,
        "causation_id": TOKEN,
        "recorded_at": KEEP,
        "is_simulated": KEEP,
    },
    "heartbeat": {
        "event_id": TOKEN,
        "run_id": TOKEN,
        "source_id": KEEP,  # EPICS channel address, facility-fixed, already public
        "heartbeat_at": KEEP,
        "recorded_at": KEEP,
    },
    "probe": {
        "event_id": TOKEN,
        "enclosure_id": TOKEN,
        "source_kind": KEEP,  # judged low risk, same standard as heartbeat.source_id
        "source_id": DROP,  # NOT cleared alongside its heartbeat twin, deliberately:
        # pairing a reachability failure with the exact substrate address is
        # closer to a security disclosure about a safety system than to science.
        "reach_tier": KEEP,  # proved closed: ReachTier StrEnum
        "status_claimed": KEEP,  # grouped with reach_tier; needs its own human pass (watch item)
        "recorded_at": KEEP,
    },
}

# (kind, column) -> the set of string-leaf json-pointers cleared inside
# that jsonb column. Absent entries default to an empty set (every
# string leaf drops). Pointers use "*" for "any list element", matching
# F5's own notation (`outcomes.measurements/*/name`).
TIER2_JSONB_CLEARED_POINTERS: dict[tuple[str, str], frozenset[str]] = {
    ("activity", "payload"): frozenset({"channel", "action_name", "units"}),
    ("outcome", "measurements"): frozenset({"*/name", "*/units", "*/kind", "*/quality"}),
}

# (kind, column) pairs whose jsonb value drops WHOLE rather than recursing.
TIER2_JSONB_DROPPED_COLUMNS: frozenset[tuple[str, str]] = frozenset({("inference", "messages")})


def redact_tier2_row(
    kind: str,
    row: dict[str, Any],
    *,
    token_map: TokenMap,
    fired_pointers: dict[tuple[str, str], set[str]],
) -> dict[str, Any]:
    """Redact one entries row of the given registry `kind`."""
    column_dispositions = TIER2_DISPOSITIONS[kind]
    result: dict[str, Any] = {}
    for column, value in row.items():
        disposition = column_dispositions.get(column)
        if disposition is None:
            # An entries column not enumerated above. Fail closed rather
            # than silently pass it through: this is this file's own
            # drift-detection surface (see test_redact_tier2.py).
            continue
        if disposition == KEEP:
            result[column] = value
        elif disposition == TOKEN:
            result[column] = token_map.token_uuid(value)
        elif disposition == DROP:
            continue
        elif disposition == BY_VALUE:
            if (kind, column) in TIER2_JSONB_DROPPED_COLUMNS:
                continue
            cleared = TIER2_JSONB_CLEARED_POINTERS.get((kind, column), frozenset())
            fired = fired_pointers.setdefault((kind, column), set())
            redacted = apply_leaf_rule(
                value, token_map=token_map, cleared_pointers=cleared, fired_pointers=fired
            )
            if redacted is not OMITTED:
                result[column] = redacted
    return result


def unfired_clearances(
    fired_pointers: dict[tuple[str, str], set[str]], *, kinds_present: frozenset[str]
) -> frozenset[tuple[str, str, str]]:
    """Every declared tier-2 jsonb clearance that never matched a row,
    scoped to kinds actually present in this export.

    CORRECTED 2026-08-12. An earlier version of this function
    (`ensure_all_clearances_fired`) raised here, reasoning from F5's
    Rejections list: "an unfired rule inside a type that was exported is
    a leak-shaped gap." That reasoning is right for a DENYLIST, where a
    rule that fails to fire means the thing it should have hidden got
    published. It is backwards for tier 2's ALLOWLIST: a clearance that
    never fires means a field was published LESS often than the profile
    permits, never more. There is no mechanism by which that leaks
    anything, so treating it as fatal was importing a denylist-shaped
    fear into an allowlist-shaped mechanism.

    The practical failure this produced: `activity/payload`'s three
    cleared pointers (`channel`, `action_name`, `units`) live on
    different step kinds, two of them optional, so no small export --
    including a first rehearsal bundle -- reliably fires all three. The
    export would abort with an error reading like a broken disposition
    table rather than "this export was too narrow to exercise every
    clearance."

    Callers now record the result on the manifest
    (`Manifest.unfired_tier2_clearances`) instead of treating it as a
    reason to refuse. The genuine worry this WAS reaching for --a
    misspelled pointer in `TIER2_JSONB_CLEARED_POINTERS` that can never
    fire against any real payload-- is a fact about this file's code,
    not about any one export, and belongs in a build-time check against
    the real key space (the same shape as step 0's generated disposition
    table), not in a per-export runtime gate. That check does not exist
    yet; this function no longer stands in for it.
    """
    result: set[tuple[str, str, str]] = set()
    for (kind, column), cleared in TIER2_JSONB_CLEARED_POINTERS.items():
        if kind not in kinds_present:
            continue
        fired = fired_pointers.get((kind, column), set())
        result.update((kind, column, pointer) for pointer in cleared - fired)
    return frozenset(result)


__all__ = [
    "TIER2_DISPOSITIONS",
    "TIER2_JSONB_CLEARED_POINTERS",
    "TIER2_JSONB_DROPPED_COLUMNS",
    "redact_tier2_row",
    "unfired_clearances",
]
