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
        "cache_creation_input_tokens": KEEP,  # token count, same posture as input/output_tokens
        "cache_read_input_tokens": KEEP,  # token count, same posture as input/output_tokens
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
        "gpu_seconds": KEEP,  # raw seconds primitive, same posture as cost_usd
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
        "categorical_value": KEEP,  # facility's own enum label (e.g. 'Fly'), same
        # standard as channel_name/value: substrate vocabulary, not PII
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
    "permit_probe": {
        # Renamed from "probe" (slice 16): disambiguates from the new
        # "capture_probe" kind below; no data migration needed, this
        # key never lands in a stored payload (see _registry.py).
        "event_id": TOKEN,
        "enclosure_id": TOKEN,  # weak at a two-enclosure facility: see status_claimed's
        # comment below for the residual re-identification risk this leaves open.
        "source_kind": KEEP,  # judged low risk, same standard as heartbeat.source_id
        "source_id": DROP,  # NOT cleared alongside its heartbeat twin, deliberately:
        # pairing a reachability failure with the exact substrate address is
        # closer to a security disclosure about a safety system than to science.
        "reach_tier": KEEP,  # proved closed: ReachTier StrEnum
        "status_claimed": DROP,  # watch item RESOLVED at S5c. This table has no
        # observed_at column, so S5b's "not redundant with observed_at" argument for
        # capture_probe.phase_claimed does not transfer; the case here is independent.
        # The real assignment is enclosure._monitor.record_observation's
        # status_claimed=observation.observed_status is not None, where observation
        # comes from api._enclosure_permit_observer.ControlPortEnclosureObserver: its
        # _pump sets observed_status (not None) on every push delivery (a real reading
        # OR a disconnect flattened to "Unknown" via _unknown) and its _poll leaves
        # observed_status None on every tick (a periodic reaffirmation CORA itself
        # schedules, carrying no status, via _probe_only). So the bit does not track reach
        # (reach_tier already does that; all four (reach_tier, status_claimed) pairs are
        # live, confirmed by reading _pump/_poll/_unknown/_probe_only directly, so neither
        # axis derives from the other) -- it tracks whether a row came from the PSS PV's
        # OWN push traffic or from CORA's separately-configured polling clock. That is a
        # fact about the safety substrate's own behavior, not about CORA's reach to it,
        # which is exactly the line source_id's own DROP above already draws for this
        # table ("closer to a security disclosure about a safety system than to
        # science").
        #
        # Adversary (per feedback_claims_need_a_threat_model.md): a reader holding the
        # published bundle plus the facility's public beamtime schedule, who wants to
        # attribute a specific PSS reach/coverage event to a proposal or PI. enclosure_id
        # is TOKEN, not cleartext like capture_probe's capture_code, but at a
        # two-enclosure facility that tokenization is weak: schedule correlation
        # plausibly reattaches a token to a physical hutch regardless, an accepted
        # residual risk this DROP does not resolve and is not trying to. Once that
        # reattachment is made, an exact push/poll label on every row -- which
        # status_claimed would have supplied for free -- lets that adversary isolate the
        # PSS's OWN traffic (real readings and disconnects) from CORA's self-scheduled
        # polling noise, which is a finer-grained view of that specific safety system's
        # behavior than the trail's stated purpose (S4: when was CORA not watching,
        # carried in full by reach_tier + recorded_at) ever needed to publish.
        #
        # This DROP raises the cost of that reconstruction; it does not prove the
        # reconstruction impossible, and the comment does not claim otherwise. `_poll`
        # runs on a fixed `tick_seconds` cadence per PV while `_pump` deliveries are
        # change-only and irregular, so a sophisticated reader could still approximate
        # the same push/poll split from KEPT `recorded_at` inter-arrival timing grouped
        # by `(enclosure_id, source_kind)`, if they also knew or guessed this
        # deployment's `tick_seconds`. Dropping the column removes the free, certain,
        # zero-effort version of that classification; it does not close the timing side
        # channel, which is a property of `recorded_at`'s own KEEP, not of this field,
        # and is not resolved here. Same DROP shape as phase_claimed's S5b reversal,
        # reached independently from this table's own shape rather than by carrying that
        # reasoning over.
        "recorded_at": KEEP,
    },
    "capture_probe": {
        "event_id": TOKEN,
        "capture_code": KEEP,  # deployment-declared watch code, not PII; same standard
        # as observation.channel_name -- an instrument identifier, not a person.
        "source_kind": KEEP,  # judged low risk, same standard as heartbeat.source_id
        "source_id": KEEP,  # UNLIKE permit_probe.source_id: a TomoScan status/abort PV
        # is experiment instrumentation, not a PSS/interlock safety system, so the
        # security-disclosure reasoning that justifies DROP there does not carry
        # over here. Same standard as heartbeat.source_id. Rests on TomoScan's own PV
        # naming being already public (same premise as observation.channel_name);
        # inherited, not freshly reverified against 2bm-docs at S5b.
        "reach_tier": KEEP,  # proved closed: ReachTier StrEnum
        "phase_claimed": DROP,  # watch item RESOLVED at S5b, reversed to DROP: the
        # producer (`_run_witness.py`'s `phase_claimed=observation.phase is not None,
        # observed_at=observation.observed_at`) sets this from a field independent of
        # observed_at, not correlated with it as the compressed aggregate docstring
        # implied, so keeping it would disclose a real, distinct "genuine status/abort
        # observation vs background reaffirmation" cadence signal that was never
        # threat-modeled. Same reversal shape as `ActionStep.name`/`capture_name` above:
        # the first KEEP argument (bool, two values) was field-by-field and missed the
        # joint signal with observed_at; dropping costs nothing against this table's
        # actual purpose (reach/coverage, carried by reach_tier/observed_at/recorded_at).
        "observed_at": KEEP,  # substrate timestamp, same standard as sampled_at/occurred_at
        "recorded_at": KEEP,
    },
    "supply_probe": {
        "event_id": TOKEN,
        "supply_id": TOKEN,  # same standard as permit_probe.enclosure_id, and the
        # residual re-identification risk is at least as strong: a 2-BM deployment
        # registers exactly two BLEPS-observed Supplies (cooling water, vacuum), the
        # same small cardinality permit_probe's comment names for a two-enclosure
        # facility, so schedule correlation plausibly reattaches this token too.
        "source_kind": KEEP,  # judged low risk, same standard as heartbeat.source_id
        "source_id": DROP,  # Adversary (per feedback_claims_need_a_threat_model.md): a
        # reader holding the published bundle plus the facility's public beamtime
        # schedule, wanting to learn the interlock's own channel topology. Follows
        # permit_probe.source_id's DROP, not capture_probe.source_id's KEEP: BLEPS is
        # explicitly an equipment-protection interlock (docs/deployments/2-bm/
        # operations.md, "Equipment protection"), the same system CLASS as the PSS
        # permit_probe protects against, not experiment instrumentation like
        # TomoScan. If anything the case for DROP is stronger here: a BLEPS channel
        # PV name (e.g. "2bmBLEPS:BLEPS:FLOW2_BELOW_SET_POINT_TRIP") embeds which
        # physical circuit it protects directly in the string, so it discloses more
        # of the interlock's own topology than a bare SecureM permit PV does.
        "reach_tier": KEEP,  # proved closed: ReachTier StrEnum
        "status_claimed": DROP,  # same class-wide reasoning as permit_probe.
        # status_claimed, not reargued from scratch: both tables sit on the same
        # equipment-protection interlock class, and the bit distinguishes the
        # substrate's own push cadence from CORA's self-scheduled polling clock for
        # that system either way. permit_probe's comment carries the full argument
        # (source_id's DROP above already draws the same line for this table); this
        # entry does not repeat it, only confirms it applies unchanged.
        "recorded_at": KEEP,
    },
}

# (kind, column) -> the set of string-leaf json-pointers cleared inside
# that jsonb column. Absent entries default to an empty set (every
# string leaf drops). Pointers use "*" for "any list element", matching
# F5's own notation (`outcomes.measurements/*/name`).
#
# `activity/payload`'s set below replaces one transcribed from a route
# docstring that named no key the real Conductor ever writes (slice 6 of
# project_record_publishing_campaign.md). Every pointer matches a real,
# closed-in-practice string leaf `conductor.py` writes on some step kind;
# see the detailed rationale AND the scope note (a second, un-addressed
# `activity/payload` writer exists) in the comment following this dict.
TIER2_JSONB_CLEARED_POINTERS: dict[tuple[str, str], frozenset[str]] = {
    ("activity", "payload"): frozenset(
        {
            "address",
            "result",
            "error_class",
            "criterion/kind",
            "reading/kind",
            "reading/quality",
            "post_reading/kind",
            "post_reading/quality",
            "post_read_error/error_class",
            "measurements/*/name",
            "measurements/*/units",
            "measurements/*/kind",
            "measurements/*/quality",
        }
    ),
    ("outcome", "measurements"): frozenset({"*/name", "*/units", "*/kind", "*/quality"}),
}

# `activity/payload`'s clearance rationale, per pointer. `address` is a
# facility-fixed PV, same posture as `observation.channel_name`. `result`
# is closed to 3 module constants (verified against every `result=` call
# site). `error_class`/`post_read_error/error_class` are `type(exc).__name__`
# for exceptions this module catches by tuple membership or explicit
# subclass (e.g. `ComputeExecutableNotPermittedError`); CORA-defined
# literals either way, never third-party or input-varying. `criterion/kind`
# is closed to "equals"/"within_tolerance". The `kind`/`quality` fields of
# every `Measurement` projection (`reading`, `post_reading`,
# `measurements/*`) match the outcome/measurements precedent above; unlike
# the control-path readings (closed by a real ACL,
# `epics_ca_control_port.py`'s quality translation), `measurements/*` from
# a COMPUTE step is closed only by there being no real value-arm
# ComputePort adapter yet (`Measurement` itself has no runtime validation
# on these fields) -- re-verify this clearance the day one lands.
#
# `criterion/expected`, `criterion/tolerance`, and the uncleared setpoint
# `value` need no pointer entry ONLY when their leaf is numeric, which is
# the common case but not the type: all three are typed as
# `int | float | bool | str | tuple[Any, ...]` unions, so a categorical
# check/setpoint (a string or tuple expected/value) silently drops today.
# Fails closed, not a leak, but means "what was checked/written" is
# incomplete for exactly the non-numeric case this slice is partly about;
# a real per-kind typed payload (Step 3, project_record_export_build_brief.md)
# is what would let this clear correctly instead of silently.
#
# Deliberately NOT cleared: `message`/`post_read_error/message` (free
# text, same shape as `verdict.reason`'s DROP); `quality_detail` and any
# `sampled_at`/`produced_at` timestamp (same non-clearance as
# outcome/measurements, and the timestamp-linkage lesson in
# feedback-claims-need-a-threat-model); `command`/`input_uris`/
# `output_uri`/`input_refs`/`artifacts` (locator-shaped; a 2-BM path
# carries a PI surname and a proposal number); `parameters`/`params`/
# `result_data`/compute `job_id`/`status` (arbitrary or unverified-closed
# shapes, watch items rather than asserted safe); and, DECIDED AND
# REVERSED during this slice's own gate review, `name` (ActionStep) plus
# `capture_name`/`capture_ref`/`steering_ref`/`output_ref_name` (Setpoint/
# Capture/Compute ref-and-slot names). The first draft cleared these five
# by analogy to `command_name`/`tool_name` ("code-literal, not a
# person"). Both the analogy and the closure claim were wrong: none of
# the five is type- or registry-closed (`capture_name`/`output_ref_name`/
# the ref names are plain `str` fields on Setpoint/Capture/Compute steps
# with no character-class validation anywhere in the recipe/body
# machinery), and `ActionStep.name` specifically is recorded on the
# PRE-LOOKUP in-flight marker and on the `UnknownActionError` failure arm
# -- both before or instead of the registry check that would have closed
# it, so an unregistered, arbitrary operator-authored string reaches the
# payload. The correct precedent in this same file is `agent_name`/
# `agent_description`: DROP, "operator-authored free text". Per
# feedback-claims-need-a-threat-model, withdrawing this overclaim costs
# nothing: `address`+`result`+`criterion`+`reading` already carry the
# core "what did the Conductor do" evidence this slice exists for.
#
# SCOPE: `redact_tier2_row` dispatches on `kind` alone (`redact_tier2_row`,
# below) -- it does not know or care which code path wrote a row, so
# EVERY pointer above governs EVERY `("activity", "payload")` row
# regardless of writer. `entries_operation_procedure_activities.payload`
# has a SECOND real writer besides the Conductor: `append_activities`'s
# route and MCP tool accept an arbitrary caller-submitted payload
# (`payload: dict[str, Any]`, Pydantic does not constrain its shape), and
# 16 `tests/integration/scenarios/test_2bm_*.py` files modeling genuine
# 2-BM procedures submit activities this way directly, using the OLDER
# `channel`/`target_value`/`units`/`ramp_rate` (setpoint), `action_name`/
# `params` (action), `channel`/`passed`/`expected`/`actual`/`tolerance`
# (check) shape this file used to (uselessly) clear. This slice's real,
# observable effect on that writer: the three old dead pointers
# (`channel`, `action_name`, `units`) tighten to DROP for it too, and any
# of its rows that happen to use `address`/`result`/`criterion`/`reading`-
# shaped keys would newly clear under the pointers above -- neither
# effect was decided FOR that writer, both are a side effect of one
# shared dispatch-on-`kind` mechanism with no writer discrimination.
# Verified no scenario test's fixture currently collides with the new
# pointer names, so nothing changes in practice today; that is
# incidental, not structural. That writer's own threat-modeled pass is a
# separate, un-briefed follow-up slice; do not assume it is covered by
# the pointers above just because they live in the same dict. This is
# the ONE authoritative copy of this note -- do not restate it in a
# docstring elsewhere, only cross-reference it.

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

    The practical failure this produced: `activity/payload`'s cleared
    pointers live on different step kinds (setpoint, action, check,
    compute), several of them optional or failure-arm-only, so no small
    export -- including a first rehearsal bundle -- reliably fires every
    one. The export would abort with an error reading like a broken
    disposition table rather than "this export was too narrow to
    exercise every clearance."

    Callers now record the result on the manifest
    (`Manifest.unfired_tier2_clearances`) instead of treating it as a
    reason to refuse. The genuine worry this WAS reaching for --a
    misspelled pointer in `TIER2_JSONB_CLEARED_POINTERS` that can never
    fire against any real payload-- is a fact about this file's code,
    not about any one export, and belongs in a build-time check against
    the real key space (the same shape as step 0's generated disposition
    table), not in a per-export runtime gate. That check now exists,
    shipped the same day as this correction:
    `tests/architecture/test_tier2_jsonb_clearances_are_real_keys.py`.
    This function no longer stands in for it.
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
