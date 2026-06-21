"""Unit tests for the Equipment BC's `PersistentIdentifierMinter` bootstrap wiring.

Per [[project-asset-persistent-id-write-design]] section 13.1 + Lock 10:
`wire_equipment` reads `Settings.datacite_repository_id` and wires the
inert `StubPersistentIdentifierMinter` when the field is None (the dev / test default).
The minter is attached BC-local at `deps.equipment.persistent_identifier_minter` so the
`assign_asset_persistent_id` handler closure can read it, AND surfaced on the
returned `EquipmentHandlers.persistent_identifier_minter` so the FastAPI lifespan stashes
it on `app.state.equipment.persistent_identifier_minter` for test-override of the 502
mint-failure path. P1-7 covers the test-file naming convention.
"""

import pytest

from cora.equipment.wire import wire_equipment
from cora.infrastructure.adapters.stub_persistent_identifier_minter import (
    StubPersistentIdentifierMinter,
)
from tests.unit._helpers import build_deps as _build_deps_shared

pytestmark = pytest.mark.timeout(60, method="thread")


@pytest.mark.unit
def test_wire_equipment_datacite_none_wires_stub_minter() -> None:
    deps = _build_deps_shared(ids=[])
    handlers = wire_equipment(deps)
    assert isinstance(handlers.persistent_identifier_minter, StubPersistentIdentifierMinter)


@pytest.mark.unit
def test_wire_equipment_stores_persistent_identifier_minter_on_app_state_equipment() -> None:
    deps = _build_deps_shared(ids=[])
    handlers = wire_equipment(deps)
    bc_local = getattr(deps, "equipment", None)
    assert bc_local is not None
    assert bc_local.persistent_identifier_minter is handlers.persistent_identifier_minter
    assert isinstance(bc_local.persistent_identifier_minter, StubPersistentIdentifierMinter)


@pytest.mark.unit
@pytest.mark.skip(
    reason=(
        "DataCitePersistentIdentifierMinter wiring lands in F.2 once "
        "production credentials gate is available"
    )
)
def test_wire_equipment_with_datacite_repository_id_set_skips_stub() -> None:
    deps = _build_deps_shared(ids=[])
    deps.settings.datacite_repository_id = "test.repo"  # type: ignore[attr-defined]
    handlers = wire_equipment(deps)
    assert not isinstance(handlers.persistent_identifier_minter, StubPersistentIdentifierMinter)
