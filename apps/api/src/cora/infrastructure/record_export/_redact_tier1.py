"""Redact `events` rows: fixed columns plus disposition-table-driven payload.

Per `project_record_export_build_brief.md` step 6 and
`project_record_export_v3.md` F5.

Two DIFFERENT failure modes, easy to conflate (the brief's own step-6
notes and its terser Rejections list read ambiguously against each
other on this point; this resolves it the way that keeps schema
evolution possible):

- `event_type` absent from `_dispositions.DISPOSITIONS` entirely ->
  ABORT (`UnknownEventTypeError`). Step 0's generator is exhaustive
  over every currently-declared event class; a stream carrying a type
  the table has never heard of means the table is stale relative to
  the code, which is a build problem, not a per-row one.
- A payload KEY present on a row but absent from
  `DISPOSITIONS[event_type]`'s own field list -> DROP (omit the key).
  This is what makes schema evolution survivable: an OLDER
  `schema_version`'s row can carry a field the CURRENT dataclass no
  longer declares (removed in a later version), and dropping it rather
  than aborting the whole export is the graceful path. This is also
  exactly what "a bare str on a NEW event drops with nobody editing a
  list" is really about at the OTHER end: Step 0's generator
  auto-classifies every new bare `str` field as `drop:text` the moment
  it is generated, so the field already has a rule (drop) with no
  manual list-editing required; it is not the "missing key" case.
"""

# pyright: reportUnknownMemberType=false, reportUnknownVariableType=false, reportUnknownArgumentType=false
# Dispatches on `Any`-typed disposition values and already-rendered
# JSON payloads; suppressed the same way cora.shared.content_hash is.

from typing import Any

from cora.infrastructure.record_export._dispositions import DISPOSITIONS
from cora.infrastructure.record_export._leaf_rule import OMITTED, apply_leaf_rule
from cora.infrastructure.record_export._tokens import TokenMap

FIXED_KEEP_COLUMNS = (
    "schema_version",
    "stream_type",
    "event_type",
    "occurred_at",
    "recorded_at",
)
FIXED_TOKEN_COLUMNS = (
    "stream_id",
    "correlation_id",
    "causation_id",
    "event_id",
    "principal_id",
)
FIXED_DROP_COLUMNS = ("metadata", "signature", "signature_kid", "signature_version")


class UnknownEventTypeError(LookupError):
    """`event_type` has no entry in `_dispositions.DISPOSITIONS` at all.

    Refuses loudly: the disposition table is exhaustive over every
    currently-declared event class, so this means the table is stale
    relative to the code, not that this one row should be skipped.
    """

    def __init__(self, event_type: str) -> None:
        super().__init__(
            f"event_type {event_type!r} has no entry in DISPOSITIONS; the "
            "table is stale relative to the code (run `make record-dispositions`)."
        )
        self.event_type = event_type


def _apply_field_disposition(disposition: Any, value: Any, *, token_map: TokenMap) -> Any:
    if isinstance(disposition, dict):
        # `None` on a dict-shaped (nested-VO or fixed-tuple) disposition is
        # the field's own declared absence (e.g. `SafetyEnvelopeVerdict |
        # None = None`, `CaptureProgressSnapshot | None = None`), not a
        # malformed value: preserve it as an explicit null, matching the
        # "present-as-null, not omit-when-None" convention every optional
        # scalar field on these same events already gets (see
        # `RunCompleted.observed_at`'s `to_payload` comment). Falling
        # through to the OMITTED branch below would silently drop the key
        # for the COMMON case (a Conducted Run's `safety_envelope_verdict`,
        # a driven or operator-terminal's `capture_progress_snapshot`),
        # making "this stream predates the field" and "this stream has the
        # field, unset" indistinguishable in the exported record.
        if value is None:
            return None
        if "[*]" in disposition:
            # A COLLECTION of value objects. The table states the cardinality
            # HERE, so this branch does not read it off the payload: a stored
            # shape that is not a collection is a disagreement between table
            # and payload, and stays fail-closed. The scalar arms below still
            # infer cardinality from the value, which is safe for them because
            # a scalar rule publishes the same value class either way.
            element = disposition["[*]"]
            if not isinstance(value, (list, tuple)):
                return OMITTED
            redacted_items = [
                _apply_field_disposition(element, item, token_map=token_map) for item in value
            ]
            # A withheld element becomes an explicit null, exactly as a
            # withheld slot does in the positional branch below and for the
            # same reason: removing it would shrink the collection, and a
            # populated field that exports as `[]` is not a withheld field, it
            # is a positive claim that there was nothing there. That claim is
            # the whole defect this rule exists to remove, and filtering would
            # reintroduce it one level down. OMITTED must not survive either:
            # it is an internal sentinel no JSON encoder can write, so one
            # escaping into a list aborts the entire export.
            return [None if item is OMITTED else item for item in redacted_items]
        if "[]" in disposition:
            # Fixed-length heterogeneous tuple: one disposition per position.
            per_position = disposition["[]"]
            if not isinstance(value, (list, tuple)):
                return OMITTED
            redacted_positions = [
                _apply_field_disposition(pos_disposition, item, token_map=token_map)
                for pos_disposition, item in zip(per_position, value, strict=True)
            ]
            # A withheld slot becomes an explicit null, never a removed entry:
            # this is a POSITIONAL record, so dropping one slot would silently
            # renumber the rest and make the survivors unreadable. OMITTED also
            # must not escape, being an internal sentinel that no JSON encoder
            # can write.
            return [None if item is OMITTED else item for item in redacted_positions]
        # A recursed value object: apply this same per-key logic one level down.
        if not isinstance(value, dict):
            return OMITTED
        result: dict[str, Any] = {}
        for key, sub_disposition in disposition.items():
            if key not in value:
                continue
            redacted = _apply_field_disposition(sub_disposition, value[key], token_map=token_map)
            if redacted is not OMITTED:
                result[key] = redacted
        return result

    if disposition == "by-value":
        return apply_leaf_rule(value, token_map=token_map)
    if disposition.startswith("keep:"):
        return value
    if disposition == "token:uuid":
        # A UUID-collection field (e.g. `target_asset_ids`) carries
        # `token:uuid` too, per Step 0's census: the disposition names
        # the ELEMENT type, not the field's own cardinality.
        if isinstance(value, (list, tuple)):
            return [token_map.token_uuid(item) for item in value]
        return token_map.token_uuid(value)
    if disposition.startswith("drop:"):
        return OMITTED
    return OMITTED


def redact_tier1_payload(
    event_type: str,
    payload: dict[str, Any],
    *,
    token_map: TokenMap,
    fired_fields: dict[str, set[str]] | None = None,
) -> dict[str, Any]:
    """Redact one event's `payload`, iterating the STORED payload's own
    keys (never the disposition table's), per F5's fail-closed property.

    `fired_fields`, when given, records which of `DISPOSITIONS[event_type]`'s
    DECLARED field keys were actually present on this row -- the tier-1
    completeness twin to tier-2's `fired_pointers`. A field can be
    declared but never fire within one export's event types if every row
    of that type in this export happens to come from an older
    `schema_version` that predates the field; `redact_record` uses this
    to report the fact on the manifest, mirroring
    `Manifest.unfired_tier2_clearances`.
    """
    if event_type not in DISPOSITIONS:
        raise UnknownEventTypeError(event_type)
    field_dispositions = DISPOSITIONS[event_type]

    result: dict[str, Any] = {}
    for key, value in payload.items():
        disposition = field_dispositions.get(key)
        if disposition is None:
            continue  # known event type, unlisted field: schema-evolution DROP
        if fired_fields is not None:
            fired_fields.setdefault(event_type, set()).add(key)
        redacted = _apply_field_disposition(disposition, value, token_map=token_map)
        if redacted is not OMITTED:
            result[key] = redacted
    return result


class Tier1Redactor:
    """Stateful per-export redactor for `events` rows.

    Must be fed rows in the SAME order `export_record` produced them
    (`(transaction_id, position)`): `position`/`transaction_id`
    re-indexing depends on that order, and `version` re-indexing depends
    on rows for one `stream_id` arriving in stream order (already true
    of the exporter's global order).
    """

    def __init__(self, token_map: TokenMap) -> None:
        self._token_map = token_map
        self._next_position = 1
        self._next_version_by_stream: dict[str, int] = {}
        self._transaction_id_index: dict[str, int] = {}
        self._next_transaction_id = 1
        self._fired_fields: dict[str, set[str]] = {}

    @property
    def fired_fields(self) -> dict[str, frozenset[str]]:
        """Per event type redacted so far, the declared field keys that
        actually appeared on at least one row. A copy; callers cannot
        mutate the accumulator this instance still writes to."""
        return {event_type: frozenset(keys) for event_type, keys in self._fired_fields.items()}

    def _dense_version(self, raw_stream_id: str) -> int:
        version = self._next_version_by_stream.get(raw_stream_id, 1)
        self._next_version_by_stream[raw_stream_id] = version + 1
        return version

    def _dense_transaction_id(self, raw_transaction_id: object) -> int:
        key = str(raw_transaction_id)
        if key not in self._transaction_id_index:
            self._transaction_id_index[key] = self._next_transaction_id
            self._next_transaction_id += 1
        return self._transaction_id_index[key]

    def redact_row(self, row: dict[str, Any]) -> dict[str, Any]:
        raw_stream_id = row["stream_id"]
        redacted: dict[str, Any] = {
            "position": self._next_position,
            "version": self._dense_version(raw_stream_id),
            "transaction_id": self._dense_transaction_id(row["transaction_id"]),
        }
        self._next_position += 1

        for column in FIXED_KEEP_COLUMNS:
            redacted[column] = row[column]
        for column in FIXED_TOKEN_COLUMNS:
            redacted[column] = self._token_map.token_uuid(row[column])
        # FIXED_DROP_COLUMNS (metadata, signature*) intentionally absent.

        redacted["payload"] = redact_tier1_payload(
            row["event_type"],
            row["payload"],
            token_map=self._token_map,
            fired_fields=self._fired_fields,
        )
        return redacted


__all__ = [
    "FIXED_DROP_COLUMNS",
    "FIXED_KEEP_COLUMNS",
    "FIXED_TOKEN_COLUMNS",
    "Tier1Redactor",
    "UnknownEventTypeError",
    "redact_tier1_payload",
]
