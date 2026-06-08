"""Construction-time tests for `FixturePidinstView` and `FixtureComponentRef`.

Section 15.1 of the design memo. The two frozen dataclasses are plain
data substrates with no logic of their own; the serializer
(`to_fixture_pidinst_record`) exercises the field semantics. These tests
pin the frozen-dataclass posture, the full-required-fields constructor
shape, and the type-system stance that `publication_year` is a required
non-optional int.
"""

from dataclasses import FrozenInstanceError
from uuid import UUID, uuid4

import pytest

from cora.equipment._pidinst_types import (
    FixtureComponentRef,
    FixturePidinstView,
    Manufacturer,
)
from cora.equipment.aggregates.asset.state import (
    AssetOwner,
    AssetOwnerName,
)
from cora.shared.identifier import (
    PersistentIdentifier,
    PersistentIdentifierScheme,
)

pytestmark = [pytest.mark.unit, pytest.mark.timeout(60, method="thread")]


def _component(
    *,
    component_id: UUID | None = None,
    scheme: PersistentIdentifierScheme | None = None,
    value: str | None = None,
    name: str = "Bound Asset A",
) -> FixtureComponentRef:
    return FixtureComponentRef(
        component_id=component_id if component_id is not None else uuid4(),
        scheme=scheme,
        value=value,
        name=name,
    )


def _view(**overrides: object) -> FixturePidinstView:
    base_kwargs: dict[str, object] = {
        "fixture_id": uuid4(),
        "name": "MCTOptics fixture",
        "persistent_id": None,
        "owners": (AssetOwner(name=AssetOwnerName(value="Advanced Photon Source")),),
        "manufacturers": (Manufacturer(name="Aerotech"),),
        "components": (_component(),),
        "publication_year": 2026,
    }
    base_kwargs.update(overrides)
    return FixturePidinstView(**base_kwargs)  # type: ignore[arg-type]


def test_fixture_pidinst_view_with_all_required_fields_constructs() -> None:
    fixture_id = uuid4()
    component = _component(name="Rotary stage")
    view = FixturePidinstView(
        fixture_id=fixture_id,
        name="MCTOptics fixture",
        persistent_id=None,
        owners=(AssetOwner(name=AssetOwnerName(value="Advanced Photon Source")),),
        manufacturers=(Manufacturer(name="Aerotech"),),
        components=(component,),
        publication_year=2026,
    )
    assert view.fixture_id == fixture_id
    assert view.name == "MCTOptics fixture"
    assert view.persistent_id is None
    assert view.owners == (AssetOwner(name=AssetOwnerName(value="Advanced Photon Source")),)
    assert view.manufacturers == (Manufacturer(name="Aerotech"),)
    assert view.components == (component,)
    assert view.publication_year == 2026


def test_fixture_pidinst_view_with_persistent_id_set_constructs() -> None:
    pid = PersistentIdentifier(
        scheme=PersistentIdentifierScheme.DOI,
        value="10.5281/zenodo.1234567",
    )
    view = _view(persistent_id=pid)
    assert view.persistent_id is pid


def test_fixture_pidinst_view_is_frozen() -> None:
    view = _view()
    with pytest.raises(FrozenInstanceError):
        view.name = "Renamed"  # type: ignore[misc]


def test_fixture_pidinst_view_without_publication_year_raises_type_error() -> None:
    with pytest.raises(TypeError):
        FixturePidinstView(  # type: ignore[call-arg]
            fixture_id=uuid4(),
            name="MCTOptics fixture",
            persistent_id=None,
            owners=(AssetOwner(name=AssetOwnerName(value="Advanced Photon Source")),),
            manufacturers=(Manufacturer(name="Aerotech"),),
            components=(_component(),),
        )


def test_fixture_pidinst_view_equality_is_value_based() -> None:
    fixture_id = uuid4()
    component_id = uuid4()
    a = _view(
        fixture_id=fixture_id,
        components=(_component(component_id=component_id, name="Stage"),),
    )
    b = _view(
        fixture_id=fixture_id,
        components=(_component(component_id=component_id, name="Stage"),),
    )
    assert a == b


def test_fixture_component_ref_with_all_required_fields_constructs() -> None:
    component_id = uuid4()
    ref = FixtureComponentRef(
        component_id=component_id,
        scheme=PersistentIdentifierScheme.DOI,
        value="10.5281/zenodo.1234567",
        name="Rotary stage",
    )
    assert ref.component_id == component_id
    assert ref.scheme is PersistentIdentifierScheme.DOI
    assert ref.value == "10.5281/zenodo.1234567"
    assert ref.name == "Rotary stage"


def test_fixture_component_ref_with_unminted_asset_constructs_with_none_scheme_and_value() -> None:
    component_id = uuid4()
    ref = FixtureComponentRef(
        component_id=component_id,
        scheme=None,
        value=None,
        name="Unminted detector",
    )
    assert ref.scheme is None
    assert ref.value is None
    assert ref.component_id == component_id
    assert ref.name == "Unminted detector"


def test_fixture_component_ref_is_frozen() -> None:
    ref = _component()
    with pytest.raises(FrozenInstanceError):
        ref.name = "Renamed"  # type: ignore[misc]


def test_fixture_component_ref_is_hashable_in_frozenset() -> None:
    a = _component(name="Stage A")
    b = _component(name="Stage B")
    members = frozenset({a, b})
    assert a in members
    assert b in members


def test_fixture_component_ref_equality_is_value_based() -> None:
    component_id = uuid4()
    a = FixtureComponentRef(
        component_id=component_id,
        scheme=PersistentIdentifierScheme.DOI,
        value="10.5281/zenodo.1234567",
        name="Rotary stage",
    )
    b = FixtureComponentRef(
        component_id=component_id,
        scheme=PersistentIdentifierScheme.DOI,
        value="10.5281/zenodo.1234567",
        name="Rotary stage",
    )
    assert a == b
