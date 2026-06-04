"""Unit test for the bootstrap-time landing-page-template guard.

Per L12 + L17 of project_asset_persistent_id_design: the wire layer
refuses to construct `EquipmentHandlers` when
`Settings.landing_page_template` is empty. Failing here keeps the
PIDINST view assembler free of per-request guards: if the template
is missing, the process never finishes booting and the route is
unreachable.
"""

import pytest

from cora.equipment._bootstrap import check_pidinst_landing_page_template
from cora.equipment.wire import wire_equipment
from tests.unit._helpers import build_deps as _build_deps_shared


@pytest.mark.unit
@pytest.mark.timeout(60, method="thread")
def test_check_pidinst_landing_page_template_rejects_empty_string() -> None:
    """The check function itself rejects an empty template."""
    deps = _build_deps_shared(ids=[])
    deps.settings.landing_page_template = ""  # type: ignore[misc]  # pydantic-settings frozen=False default
    with pytest.raises(RuntimeError, match="landing_page_template"):
        check_pidinst_landing_page_template(deps.settings)


@pytest.mark.unit
@pytest.mark.timeout(60, method="thread")
def test_wire_equipment_rejects_empty_landing_page_template() -> None:
    """wire_equipment runs the check; empty template fails Kernel
    construction, not first-request handling."""
    deps = _build_deps_shared(ids=[])
    deps.settings.landing_page_template = "   "  # type: ignore[misc]
    with pytest.raises(RuntimeError, match="landing_page_template"):
        wire_equipment(deps)
