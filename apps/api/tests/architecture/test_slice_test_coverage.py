"""Every vertical slice has the test files its shape requires.

Sibling to `test_slice_contract.py`. That test enforces *source-code*
shape (every command slice has command/decider/handler/route/tool);
this one enforces *test* shape (every command slice has the matching
test files in unit/contract/integration). Together they pin both
sides of the convention so drift in either direction fails CI.

## The pyramid (per slice shape)

For COMMAND slices (those with `command.py` + `decider.py`):
  - unit:        test_<slice>_decider.py
  - unit:        test_<slice>_handler.py
  - contract:    test_<slice>_endpoint.py   (REST surface)
  - contract:    test_<slice>_mcp_tool.py   (MCP surface)

For ENTRY-APPEND slices (per `_ENTRY_APPEND_SLICES` in
`test_slice_contract.py`): same as command MINUS the decider test.

For QUERY slices (those with `query.py`):
  - unit:        test_<slice>_handler.py
  - contract:    test_<slice>_endpoint.py
  - contract:    test_<slice>_mcp_tool.py

For CREATE-STYLE command slices (verbs `define`, `register`, `add`),
ALSO required: integration test_<slice>_handler_postgres.py. This pins
the jsonb round-trip + ON CONFLICT + unique-constraint behavior for
every new aggregate-creating slice; state-transition slices
(abort/complete/resume/hold/etc.) lean on cross-BC scenario coverage
in `tests/integration/scenarios/` instead.

## Detection

A slice is considered covered for a given tier+suffix if EITHER:
  - the 1:1 file `test_<slice>_<suffix>.py` exists in that tier
    (the canonical naming), OR
  - any other test file in that tier mentions the slice name as a
    substring (catches resource-plural grouped files like
    `test_actors_endpoint.py` covering `register_actor`, or MCP
    bundles like `test_iter2_mcp_tools.py` covering all 5 agent
    lifecycle slices).

When neither matches, the slice may be listed in one of the
EXEMPT_FROM_* allowlists below, with a comment citing the file that
provides equivalent coverage (for example, URL-only FSM-walk tests that
don't mention slice names at all). New allowlist entries WITHOUT a
citation should be rejected at review.

Stub slices (no command.py AND no query.py) are skipped automatically,
matching the source-side `test_slice_contract.py` behavior.
"""

# Shared sibling-module helpers from `test_slice_contract` are
# underscore-prefixed; pyright would otherwise flag the import.
# pyright: reportPrivateUsage=false

from pathlib import Path

import pytest

from tests.architecture.conftest import CORA_ROOT, tracked_python_files, tracked_test_files
from tests.architecture.test_slice_contract import (
    _ENTRY_APPEND_SLICES,
    WIP_SLICES,
    _all_slices,
    _qualified,
)

# tests/architecture/test_slice_test_coverage.py -> apps/api/
_TESTS_ROOT = Path(__file__).resolve().parents[1]

# Verbs whose slices create new aggregates and therefore need a
# per-slice integration test (jsonb round-trip + ON CONFLICT).
_CREATE_VERBS: frozenset[str] = frozenset({"define", "register", "add"})


# ---------------------------------------------------------------------------
# Allowlists
#
# Each entry MUST be accompanied by a comment naming the file that
# provides equivalent coverage. Reviewers should reject additions that
# lack a citation. As convention drift gets fixed, prune entries here.
# ---------------------------------------------------------------------------


EXEMPT_FROM_ENDPOINT_CONTRACT: frozenset[str] = frozenset(
    {
        # Safety clearance lifecycle: covered by URL-only FSM-walk tests
        # in `test_clearance_fsm_walk_endpoints.py`, which walks the full
        # FSM via HTTP calls (no slice-name imports or string mentions).
        "cora.safety.features.activate_clearance",
        "cora.safety.features.amend_clearance",
        "cora.safety.features.append_clearance_review_step",
        "cora.safety.features.approve_clearance",
        "cora.safety.features.expire_clearance",
        "cora.safety.features.reject_clearance",
        "cora.safety.features.start_clearance_review",
        "cora.safety.features.submit_clearance",
        # Supply monitor trigger (Port B): in-process-only slice per
        # [[project_supply_monitor_trigger_design]] design lock. No REST
        # endpoint by design ("operators have buttons; machines have ports").
        # In-process adapters call via SupplyHandlers.observe_supply_status.
        "cora.supply.features.observe_supply_status",
        # Frame slices: contract tests deferred to a follow-up commit
        # so the Frame + Mount REST + MCP suite can be authored together
        # against the shared PlacementBody surface. Decider tests +
        # event round-trip + idempotency-via-decider already pin
        # behavior; OpenAPI snapshot pins wire shape. Remove from this
        # allowlist when the contract suite lands.
        "cora.equipment.features.decommission_frame",
        "cora.equipment.features.register_frame",
        "cora.equipment.features.update_frame_placement",
        # Mount slices: same deferral. The 5 Mount slices ship with
        # decider tests but no REST/MCP contract suite; backfill
        # together with Frame's once the integration scenario lands.
        "cora.equipment.features.decommission_mount",
        "cora.equipment.features.install_asset",
        "cora.equipment.features.register_mount",
        "cora.equipment.features.uninstall_asset",
        "cora.equipment.features.update_mount_placement",
        # register_facility (Session 5 Slice 5 Sub-Slice B): REST contract
        # test deferred to a follow-up commit. Sub-Slice B ships the
        # decider + handler unit tests + projection-metadata pin; the
        # OpenAPI snapshot locks the wire shape. Backfill the dedicated
        # endpoint contract test alongside register_facility's first
        # integration test or after Sub-Slice C ships decommission_facility.
        "cora.federation.features.register_facility",
        # decommission_facility (Session 5 Slice 5 Sub-Slice C): same
        # deferral as register_facility's REST contract test. Decider +
        # handler unit tests + projection apply test (FacilityDecommissioned
        # branch) + OpenAPI snapshot cover the behavior surface.
        "cora.federation.features.decommission_facility",
        # add_facility_trust_anchor_credential (Slice 6 Sub-Slice B):
        # REST contract test deferred alongside the Facility-family
        # contract suite. Decider + PBT + handler unit tests + projection
        # apply test + OpenAPI snapshot cover the behavior surface.
        "cora.federation.features.add_facility_trust_anchor_credential",
        # remove_facility_trust_anchor_credential (Slice 6 Sub-Slice B):
        # same deferral as the add sibling.
        "cora.federation.features.remove_facility_trust_anchor_credential",
    }
)


EXEMPT_FROM_MCP_CONTRACT: frozenset[str] = frozenset(
    {
        # Agent lifecycle: all 5 slices covered by the bundled
        # `test_iter2_mcp_tools.py`.
        "cora.agent.features.grant_tool_to_agent",
        "cora.agent.features.resume_agent",
        "cora.agent.features.revise_agent_budget",
        "cora.agent.features.revoke_tool_from_agent",
        "cora.agent.features.suspend_agent",
        # Supply monitor trigger (Port B): in-process-only per
        # [[project_supply_monitor_trigger_design]]; no MCP tool by design.
        "cora.supply.features.observe_supply_status",
        # --- TODO: real gaps to fill -----------------------------------
        # The slice is MCP-registered in `cora.<bc>.tools.py` but no
        # contract test exercises the tool schema or call surface. Each
        # of these should grow a `test_<slice>_mcp_tool.py` so the MCP
        # wire shape is locked. Remove from this allowlist when added.
        "cora.recipe.features.list_methods",
        "cora.recipe.features.list_plans",
        "cora.recipe.features.list_practices",
        "cora.recipe.features.update_plan_default_parameters",
        "cora.safety.features.activate_clearance",
        "cora.safety.features.expire_clearance",
        # Frame slices: MCP contract tests deferred to a follow-up
        # commit so REST + MCP suite can be authored together. Remove
        # from this allowlist when the contract suite lands.
        "cora.equipment.features.decommission_frame",
        "cora.equipment.features.register_frame",
        "cora.equipment.features.update_frame_placement",
        # Mount slices: same deferral.
        "cora.equipment.features.decommission_mount",
        "cora.equipment.features.install_asset",
        "cora.equipment.features.register_mount",
        "cora.equipment.features.uninstall_asset",
        "cora.equipment.features.update_mount_placement",
        # register_facility (Session 5 Slice 5 Sub-Slice B): MCP contract
        # test deferred alongside the REST contract test. Same rationale.
        "cora.federation.features.register_facility",
        # decommission_facility (Session 5 Slice 5 Sub-Slice C): MCP
        # contract test deferred alongside REST. Same rationale.
        "cora.federation.features.decommission_facility",
        # add_facility_trust_anchor_credential (Slice 6 Sub-Slice B):
        # MCP contract test deferred alongside the REST contract test.
        "cora.federation.features.add_facility_trust_anchor_credential",
        # remove_facility_trust_anchor_credential (Slice 6 Sub-Slice B):
        # same deferral as the add sibling.
        "cora.federation.features.remove_facility_trust_anchor_credential",
    }
)


EXEMPT_FROM_HANDLER_UNIT: frozenset[str] = frozenset(
    {
        # --- TODO: real gaps to fill -----------------------------------
        # Query handlers compose the `list_query` factory and a thin
        # adapter call — they're covered transitively by integration
        # `test_<slice>_handler_postgres.py` but lack the unit-tier pin.
        # Each should grow `tests/unit/<bc>/test_<slice>_handler.py` so
        # filter/sort/pagination behavior is locked at the in-memory
        # tier. Remove from this allowlist when added.
        "cora.equipment.features.list_fixtures",
        "cora.federation.features.list_credentials",
        "cora.federation.features.list_permits",
        "cora.federation.features.list_seals",
        "cora.safety.features.list_clearances",
        "cora.trust.features.list_conduits",
        "cora.trust.features.list_policies",
        "cora.trust.features.list_zones",
    }
)


EXEMPT_FROM_INTEGRATION: frozenset[str] = frozenset(
    {
        # register_frame: integration test deferred to a follow-up
        # commit. Decider + event round-trip cover the genesis path;
        # the integration tier locks event-store version sequencing +
        # idempotency-store wrap + projection apply. Remove from this
        # allowlist when the integration suite lands.
        "cora.equipment.features.register_frame",
        # register_mount: same deferral.
        "cora.equipment.features.register_mount",
        # register_facility (Session 5 Slice 5 Sub-Slice B): integration
        # test deferred to a follow-up commit. Decider + handler unit
        # tests + projection apply tests + OpenAPI snapshot cover the
        # behavior surface; the integration tier locks event-store
        # version sequencing + projection apply against real Postgres.
        # Backfill alongside Sub-Slice C's decommission_facility or
        # after Sub-Slice D lands the bootstrap.
        "cora.federation.features.register_facility",
        # decommission_facility (Session 5 Slice 5 Sub-Slice C): same
        # deferral. Decider + handler unit tests + projection apply
        # cover the behavior surface.
        "cora.federation.features.decommission_facility",
        # add_facility_trust_anchor_credential (Slice 6 Sub-Slice B):
        # integration tier deferred alongside Facility-family integration
        # suite. Decider + PBT + handler + projection apply cover behavior.
        "cora.federation.features.add_facility_trust_anchor_credential",
        # remove_facility_trust_anchor_credential (Slice 6 Sub-Slice B):
        # same deferral as the add sibling.
        "cora.federation.features.remove_facility_trust_anchor_credential",
        # register_enclosure: integration test deferred to a follow-up.
        # Decider + PBT + handler + projection apply tests + endpoint +
        # MCP contract tests cover the behavior surface; the integration
        # tier locks event-store version sequencing + projection apply
        # against real Postgres. Backfill alongside the EnclosureLookup
        # cross-BC port (which needs Postgres-backed integration tests
        # for the lookup port's two adapters).
        "cora.enclosure.features.register_enclosure",
    }
)


# ---------------------------------------------------------------------------
# Detection helpers
# ---------------------------------------------------------------------------


def _slice_shape(slice_dir: Path) -> str:
    files = {p.name for p in tracked_python_files() if p.parent == slice_dir}
    has_command = "command.py" in files
    has_query = "query.py" in files
    if has_command:
        if _qualified(slice_dir) in _ENTRY_APPEND_SLICES:
            return "entry-append"
        return "command"
    if has_query:
        return "query"
    return "stub"


def _bc(slice_dir: Path) -> str:
    return slice_dir.relative_to(CORA_ROOT).parts[0]


def _tier_dir(tier: str, bc: str) -> Path:
    """Where to look for test files for this slice's tier."""
    if tier == "unit":
        return _TESTS_ROOT / "unit" / bc
    return _TESTS_ROOT / tier


def _is_covered(*, tier: str, bc: str, slice_name: str, suffix: str) -> bool:
    """True if either the 1:1 file exists OR the slice name appears as
    a substring in any test file in the tier directory.

    Enumeration filters ``tracked_test_files()`` so untracked WIP test
    files are invisible, matching pre-commit's stash behavior (see
    conftest module docstring).
    """
    direct = _tier_dir(tier, bc) / f"test_{slice_name}_{suffix}.py"
    tracked = tracked_test_files()
    if direct in tracked:
        return True
    search_dir = _tier_dir(tier, bc)
    for f in tracked:
        if f.parent != search_dir or not f.name.startswith("test_"):
            continue
        try:
            if slice_name in f.read_text():
                return True
        except OSError:
            continue
    return False


def _skip_if_not_applicable(slice_dir: Path, *required_shapes: str) -> str:
    qualified = _qualified(slice_dir)
    if qualified in WIP_SLICES:
        pytest.skip(f"{qualified} is in WIP_SLICES (mid-phase)")
    shape = _slice_shape(slice_dir)
    if shape == "stub":
        pytest.skip(f"{qualified} is a stub (no command.py or query.py)")
    if shape not in required_shapes:
        pytest.skip(f"{qualified} has shape {shape!r}, not in {required_shapes}")
    return shape


def _assert_or_exempt(
    slice_dir: Path,
    *,
    found: bool,
    tier: str,
    file_suffix: str,
    exempt: frozenset[str],
) -> None:
    qualified = _qualified(slice_dir)
    if qualified in exempt:
        pytest.skip(f"{qualified} is in the {file_suffix} allowlist")
    location = f"tests/{tier}/{_bc(slice_dir)}/" if tier == "unit" else f"tests/{tier}/"
    assert found, (
        f"{qualified}: no test in {location} mentions slice name {slice_dir.name!r}. "
        f"Add `test_{slice_dir.name}_{file_suffix}.py` or list this slice in the "
        f"appropriate EXEMPT_FROM_* allowlist with a citation."
    )


# ---------------------------------------------------------------------------
# COMMAND slices: full unit + contract pyramid required
# ---------------------------------------------------------------------------


@pytest.mark.architecture
@pytest.mark.parametrize("slice_dir", _all_slices(), ids=_qualified)
def test_command_slice_has_decider_test(slice_dir: Path) -> None:
    """Pure deciders are the single most-tested layer per the FCIS
    discipline; every command slice must have a dedicated decider test
    so the pure-logic contract is locked independently of the handler."""
    _skip_if_not_applicable(slice_dir, "command")
    found = _is_covered(tier="unit", bc=_bc(slice_dir), slice_name=slice_dir.name, suffix="decider")
    assert found, (
        f"{_qualified(slice_dir)}: no unit test mentions {slice_dir.name!r}. "
        f"Add tests/unit/{_bc(slice_dir)}/test_{slice_dir.name}_decider.py."
    )


@pytest.mark.architecture
@pytest.mark.parametrize("slice_dir", _all_slices(), ids=_qualified)
def test_slice_has_handler_unit_test(slice_dir: Path) -> None:
    """Every command, entry-append, and query slice needs a unit
    handler test pinning authz/idempotency/event-envelope shape."""
    _skip_if_not_applicable(slice_dir, "command", "entry-append", "query")
    found = _is_covered(tier="unit", bc=_bc(slice_dir), slice_name=slice_dir.name, suffix="handler")
    _assert_or_exempt(
        slice_dir,
        found=found,
        tier="unit",
        file_suffix="handler",
        exempt=EXEMPT_FROM_HANDLER_UNIT,
    )


@pytest.mark.architecture
@pytest.mark.parametrize("slice_dir", _all_slices(), ids=_qualified)
def test_slice_has_endpoint_contract_test(slice_dir: Path) -> None:
    """REST surface contract: schema, status codes, error mappings.
    Required for command, entry-append, and query slices."""
    _skip_if_not_applicable(slice_dir, "command", "entry-append", "query")
    found = _is_covered(
        tier="contract", bc=_bc(slice_dir), slice_name=slice_dir.name, suffix="endpoint"
    )
    _assert_or_exempt(
        slice_dir,
        found=found,
        tier="contract",
        file_suffix="endpoint",
        exempt=EXEMPT_FROM_ENDPOINT_CONTRACT,
    )


@pytest.mark.architecture
@pytest.mark.parametrize("slice_dir", _all_slices(), ids=_qualified)
def test_slice_has_mcp_tool_contract_test(slice_dir: Path) -> None:
    """MCP surface contract: tool schema + structured-output shape.
    Required for command, entry-append, and query slices."""
    _skip_if_not_applicable(slice_dir, "command", "entry-append", "query")
    found = _is_covered(
        tier="contract", bc=_bc(slice_dir), slice_name=slice_dir.name, suffix="mcp_tool"
    )
    _assert_or_exempt(
        slice_dir,
        found=found,
        tier="contract",
        file_suffix="mcp_tool",
        exempt=EXEMPT_FROM_MCP_CONTRACT,
    )


# ---------------------------------------------------------------------------
# CREATE-STYLE command slices: also integration test
# ---------------------------------------------------------------------------


@pytest.mark.architecture
@pytest.mark.parametrize("slice_dir", _all_slices(), ids=_qualified)
def test_create_style_slice_has_integration_test(slice_dir: Path) -> None:
    """Create-style slices (`define_*`, `register_*`, `add_*`) introduce
    a NEW aggregate or event stream — the jsonb round-trip, ON CONFLICT
    behavior, and any unique constraints have to be pinned against real
    Postgres before pilot. State-transition slices lean on cross-BC
    scenario coverage instead and are exempt by verb."""
    _skip_if_not_applicable(slice_dir, "command", "entry-append")
    if slice_dir.name.split("_", 1)[0] not in _CREATE_VERBS:
        pytest.skip(f"{_qualified(slice_dir)}: verb not create-style")
    found = _is_covered(
        tier="integration",
        bc=_bc(slice_dir),
        slice_name=slice_dir.name,
        suffix="handler_postgres",
    )
    _assert_or_exempt(
        slice_dir,
        found=found,
        tier="integration",
        file_suffix="handler_postgres",
        exempt=EXEMPT_FROM_INTEGRATION,
    )


# ---------------------------------------------------------------------------
# Allowlist drift catchers
# ---------------------------------------------------------------------------


@pytest.mark.architecture
@pytest.mark.parametrize(
    "allowlist_name",
    [
        "EXEMPT_FROM_ENDPOINT_CONTRACT",
        "EXEMPT_FROM_MCP_CONTRACT",
        "EXEMPT_FROM_HANDLER_UNIT",
        "EXEMPT_FROM_INTEGRATION",
    ],
)
def test_exempt_entries_actually_exist(allowlist_name: str) -> None:
    """Allowlist entries must point at real slice directories.
    Mirrors `test_wip_slices_actually_exist` from the source-contract suite."""
    allowlist = globals()[allowlist_name]
    for qualified in allowlist:
        parts = qualified.split(".")
        assert parts[0] == "cora", f"{qualified}: must start with 'cora.'"
        path = CORA_ROOT.joinpath(*parts[1:])
        assert path.is_dir(), f"{allowlist_name} entry {qualified} no longer exists; remove it"
