"""Unit tests for the entries-tier registry: `kind -> (table, order key, reader)`.

See `cora.infrastructure.record_export._registry` for the design: ten
entries, six resolved from a `*LogbookOpened` envelope's `kind` and four
(`heartbeat`, `permit_probe`, `capture_probe`, `supply_probe`) declared
explicitly because they have no envelope. `permit_probe` was renamed
from the bare `probe` (slice 16) once a second, unrelated probe kind
existed.
"""

import pytest

from cora.infrastructure.record_export import (
    UnknownLogbookKindError,
    all_specs,
    registered_envelope_classes,
    resolve,
)
from cora.infrastructure.record_export._redact_tier2 import TIER2_DISPOSITIONS

_ENVELOPE_DRIVEN_KINDS = (
    "verdict",
    "inference",
    "activity",
    "diagnostic",
    "outcome",
    "observation",
)
_DECLARED_KINDS = ("heartbeat", "permit_probe", "capture_probe", "supply_probe")


def test_registry_has_ten_entries_not_six() -> None:
    assert len(all_specs()) == 10


@pytest.mark.parametrize("kind", [*_ENVELOPE_DRIVEN_KINDS, *_DECLARED_KINDS])
def test_resolve_finds_every_registered_kind(kind: str) -> None:
    spec = resolve(kind)
    assert spec.kind == kind


@pytest.mark.parametrize("kind", _ENVELOPE_DRIVEN_KINDS)
def test_envelope_driven_kinds_carry_their_envelope_class(kind: str) -> None:
    spec = resolve(kind)
    assert spec.envelope_class is not None
    assert spec.envelope_class.endswith("LogbookOpened")
    assert spec.scope_column == "logbook_id"


@pytest.mark.parametrize("kind", _DECLARED_KINDS)
def test_declared_kinds_have_no_envelope_class(kind: str) -> None:
    spec = resolve(kind)
    assert spec.envelope_class is None
    assert spec.scope_column != "logbook_id"


def test_registered_envelope_classes_has_exactly_the_six_logbook_kinds() -> None:
    assert registered_envelope_classes() == {
        "ConduitLogbookOpened",
        "DecisionLogbookOpened",
        "ProcedureActivitiesLogbookOpened",
        "ProcedureDiagnosticLogbookOpened",
        "ProcedureOutcomeLogbookOpened",
        "RunObservationLogbookOpened",
    }


def test_unknown_kind_refuses_loudly_instead_of_returning_none() -> None:
    with pytest.raises(UnknownLogbookKindError) as excinfo:
        resolve("steps")  # the pre-rename name; must not silently resurrect it
    assert excinfo.value.kind == "steps"


def test_order_by_uses_sampled_at_on_exactly_the_four_tables_that_have_it() -> None:
    with_sampled_at = {spec.kind for spec in all_specs() if spec.order_by[0] == "sampled_at"}
    assert with_sampled_at == {"activity", "diagnostic", "outcome", "observation"}
    without_sampled_at = {spec.kind for spec in all_specs() if spec.order_by == ("event_id",)}
    assert without_sampled_at == {
        "verdict",
        "inference",
        "heartbeat",
        "permit_probe",
        "capture_probe",
        "supply_probe",
    }


def test_table_names_are_unique_across_the_registry() -> None:
    tables = [spec.table for spec in all_specs()]
    assert len(tables) == len(set(tables))


def test_every_registered_kind_has_a_tier2_disposition_entry() -> None:
    """Unit-level cross-check of the `_registry.py` <-> `_redact_tier2.py`
    kind name agreement: a half-done rename (like `probe` -> `permit_probe`)
    would otherwise only surface via an integration test
    (`test_tier2_disposition_table_columns_match_live_schema`), which
    needs a live Postgres and would not run in a unit-only pass."""
    assert set(TIER2_DISPOSITIONS) == {spec.kind for spec in all_specs()}
