"""Unit tests for shared `cora.shared.logbook` types.

`LogbookSchema` + `LogbookFieldSpec` carry the schema declaration on
`<Aggregate>ChannelOpened` event payloads. Round-trip through
to_dict / from_dict is the core invariant — payloads land in jsonb
and need to rebuild faithfully.
"""

import pytest

from cora.shared.logbook import LogbookFieldSpec, LogbookSchema


@pytest.mark.unit
def test_field_spec_to_dict_minimal_fields_only() -> None:
    spec = LogbookFieldSpec(type="string")
    assert spec.to_dict() == {"type": "string"}


@pytest.mark.unit
def test_field_spec_to_dict_includes_units_and_description_when_set() -> None:
    spec = LogbookFieldSpec(type="float", units="deg", description="rotation angle")
    assert spec.to_dict() == {
        "type": "float",
        "units": "deg",
        "description": "rotation angle",
    }


@pytest.mark.unit
def test_field_spec_from_dict_round_trips() -> None:
    original = LogbookFieldSpec(type="float", units="C", description="sample temp")
    assert LogbookFieldSpec.from_dict(original.to_dict()) == original


@pytest.mark.unit
def test_field_spec_from_dict_handles_missing_optionals() -> None:
    rebuilt = LogbookFieldSpec.from_dict({"type": "uuid"})
    assert rebuilt == LogbookFieldSpec(type="uuid")


@pytest.mark.unit
def test_schema_default_is_empty_fields() -> None:
    schema = LogbookSchema()
    assert schema.fields == {}
    assert schema.description is None


@pytest.mark.unit
def test_schema_to_dict_excludes_description_when_none() -> None:
    schema = LogbookSchema(fields={"x": LogbookFieldSpec(type="int")})
    assert schema.to_dict() == {"fields": {"x": {"type": "int"}}}


@pytest.mark.unit
def test_schema_to_dict_includes_description_when_set() -> None:
    schema = LogbookSchema(
        fields={"angle": LogbookFieldSpec(type="float", units="deg")},
        description="rotation positions",
    )
    assert schema.to_dict() == {
        "fields": {"angle": {"type": "float", "units": "deg"}},
        "description": "rotation positions",
    }


@pytest.mark.unit
def test_schema_from_dict_round_trips() -> None:
    original = LogbookSchema(
        fields={
            "actor_id": LogbookFieldSpec(type="uuid"),
            "command_name": LogbookFieldSpec(type="string"),
            "decision": LogbookFieldSpec(type="string"),
        },
        description="auth audit log",
    )
    assert LogbookSchema.from_dict(original.to_dict()) == original


@pytest.mark.unit
def test_schema_from_dict_handles_missing_fields_key() -> None:
    """Defensive: a stored schema with no fields rebuilds as empty."""
    rebuilt = LogbookSchema.from_dict({"description": "no columns yet"})
    assert rebuilt.fields == {}
    assert rebuilt.description == "no columns yet"
