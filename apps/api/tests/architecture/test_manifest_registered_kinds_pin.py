"""Pins the registered logbook kind SET against `MANIFEST_SCHEMA_VERSION`.

Per `project_record_completeness_design.md`'s "Two authorities, two
times": `registered_kinds_hash` lets a reader tell whether their own
checkout's registry has grown a kind a bundle's manifest never had a
slot for, but only if the kind set and the schema version move
together. Sibling to `test_record_export_registry_completeness.py`'s
`test_exactly_six_logbook_opened_classes_exist`, which pins the six
envelope classes; this pins the full nine-kind registry (`_registry.py`
already pins the bare count in `tests/unit/infrastructure/record_export/
test_registry.py::test_registry_has_nine_entries_not_six`, but not the
SET, and not against the manifest's own version).

A tenth `EntriesTableSpec` changes `_REGISTERED_KINDS` below, which is a
deliberate, reviewed edit -- exactly the point: nothing here should
change silently.
"""

import pytest

from cora.infrastructure.record_export import MANIFEST_SCHEMA_VERSION, all_specs

_REGISTERED_KINDS = (
    "activity",
    "capture_probe",
    "diagnostic",
    "heartbeat",
    "inference",
    "observation",
    "outcome",
    "permit_probe",
    "verdict",
)


@pytest.mark.architecture
def test_registered_kinds_pin_forces_a_deliberate_schema_version_bump() -> None:
    assert tuple(sorted(spec.kind for spec in all_specs())) == _REGISTERED_KINDS, (
        "the registered logbook kind set has changed; bump MANIFEST_SCHEMA_VERSION "
        "in _manifest.py, update _REGISTERED_KINDS here, and update the S4 "
        "membership decision in project_record_completeness_design.md together"
    )
    assert MANIFEST_SCHEMA_VERSION == 1, (
        "MANIFEST_SCHEMA_VERSION moved without updating this pin's expected "
        "value; update _REGISTERED_KINDS above in the same commit"
    )
