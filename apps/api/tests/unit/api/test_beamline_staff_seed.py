"""beamline_staff_seed's pure parts: pinned identity, fail-loud name
validation, report semantics, and the CLI.

The database-touching flow lives in the integration tier
(test_beamline_staff_seed_postgres); this tier pins what must never
drift without ceremony: the three pinned actor ids (a re-pin orphans
every deployment that already ran this ceremony), the loud refusal to
seed a blank display name, and the CLI/env-var defaulting.

Every name literal here is invented ("Test Operator A/B"); the real
2-BM staff names are personal data and never appear in this
repository, including in tests.
"""

from uuid import UUID

import pytest

from cora.api.beamline_staff_seed import (
    ADMIN_ACTOR_ID,
    BEAMLINE_STAFF_SLOTS,
    GROUP_MANAGER_ACTOR_ID,
    STAFF_ACTOR_ID,
    _BeamlineStaffNameMissingError,  # pyright: ignore[reportPrivateUsage]
    _Report,  # pyright: ignore[reportPrivateUsage]
    _require_all_names_configured,  # pyright: ignore[reportPrivateUsage]
    build_parser,
)

pytestmark = pytest.mark.unit


def test_role_actor_ids_are_the_locked_constants() -> None:
    """The ids outlive the labels.

    `2-bm-admin` became `2-bm-admin` without minting anything: the
    id IS the person as far as the record is concerned, and every grant
    already made hangs off it. A re-pin here would orphan those and
    create a second actor for the same human, which has already happened
    once at this deployment and took an hour to find.
    """
    assert UUID("02900000-0000-7000-9000-0000000a0010") == ADMIN_ACTOR_ID
    assert UUID("02900000-0000-7000-9000-0000000b0010") == GROUP_MANAGER_ACTOR_ID
    assert UUID("02900000-0000-7000-9000-0000000c0010") == STAFF_ACTOR_ID


def test_operator_actor_ids_are_distinct_from_the_seeded_agent_range() -> None:
    """Seeded agents live under `01900000-0000-7000-8000-...`; a human
    staff id must never fall in that range, or a UUID alone can no
    longer tell a human actor from a seeded agent."""
    for actor_id in (ADMIN_ACTOR_ID, GROUP_MANAGER_ACTOR_ID, STAFF_ACTOR_ID):
        assert str(actor_id).startswith("02900000-")
        assert "-8000-" not in str(actor_id)


def test_beamline_staff_slots_has_one_slot_per_role_with_distinct_ids() -> None:
    assert len(BEAMLINE_STAFF_SLOTS) == 3
    actor_ids = {slot.actor_id for slot in BEAMLINE_STAFF_SLOTS}
    event_ids = {slot.event_id for slot in BEAMLINE_STAFF_SLOTS}
    correlation_ids = {slot.correlation_id for slot in BEAMLINE_STAFF_SLOTS}
    # Against the slot count, not a literal. Two slots sharing an id is
    # the failure worth catching, and a hardcoded 2 stops catching it the
    # moment a third slot is added -- which is exactly when the risk of a
    # copied-and-not-edited id is highest.
    assert len(actor_ids) == len(BEAMLINE_STAFF_SLOTS)
    assert len(event_ids) == len(BEAMLINE_STAFF_SLOTS)
    assert len(correlation_ids) == len(BEAMLINE_STAFF_SLOTS)


def test_beamline_staff_slots_env_vars_are_distinct() -> None:
    env_vars = {slot.env_var for slot in BEAMLINE_STAFF_SLOTS}
    assert len(env_vars) == len(BEAMLINE_STAFF_SLOTS)


def test_require_all_names_configured_passes_when_every_slot_is_named() -> None:
    """Built from the slot tuple, so a new slot cannot pass this by default.

    A hand-written dict of names would keep passing after a fourth slot
    arrived, and the ceremony would then refuse at deploy time against a
    green suite.
    """
    _require_all_names_configured({slot.slot: f"Test {slot.slot}" for slot in BEAMLINE_STAFF_SLOTS})


def test_require_all_names_configured_rejects_missing_slot() -> None:
    with pytest.raises(_BeamlineStaffNameMissingError):
        _require_all_names_configured({"2-bm-admin": "Test Admin"})


def test_require_all_names_configured_rejects_blank_name() -> None:
    with pytest.raises(_BeamlineStaffNameMissingError):
        _require_all_names_configured({"2-bm-admin": "Test Admin", "2-bm-group-manager": "   "})


def test_require_all_names_configured_rejects_none_name() -> None:
    with pytest.raises(_BeamlineStaffNameMissingError):
        _require_all_names_configured({"2-bm-admin": "Test Admin", "2-bm-group-manager": None})


def test_require_all_names_configured_error_names_every_missing_slot() -> None:
    """A config mistake should surface every unconfigured slot at once,
    not just the first, so an operator fixes it in one pass."""
    with pytest.raises(_BeamlineStaffNameMissingError) as excinfo:
        _require_all_names_configured({})
    message = str(excinfo.value)
    assert "2-bm-admin" in message
    assert "2-bm-group-manager" in message
    assert "BEAMLINE_STAFF_ADMIN_NAME" in message
    assert "BEAMLINE_STAFF_GROUP_MANAGER_NAME" in message


def test_require_all_names_configured_error_never_carries_a_name() -> None:
    """The error is safe to print or log precisely because it names
    slots and env vars, never a value; assert the one name that WAS
    supplied does not leak into the message about the other slot."""
    with pytest.raises(_BeamlineStaffNameMissingError) as excinfo:
        _require_all_names_configured({"2-bm-admin": "Test Admin"})
    assert "Test Admin" not in str(excinfo.value)


def test_report_all_exists_leaves_seeded_and_failed_unset() -> None:
    report = _Report(lines=[])
    report.note("exists", "actor 2-bm-admin")
    report.note("exists", "actor 2-bm-group-manager")
    assert report.seeded is False
    assert report.failed is False


def test_report_any_seed_marks_seeded() -> None:
    report = _Report(lines=[])
    report.note("exists", "actor 2-bm-admin")
    report.note("seeded", "actor 2-bm-group-manager")
    assert report.seeded is True
    assert report.failed is False


def test_report_any_error_marks_failed() -> None:
    report = _Report(lines=[])
    report.note("seeded", "actor 2-bm-admin")
    report.note("error", "ceremony", "synthetic failure")
    assert report.failed is True


def test_parser_defaults_read_from_environment(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("BEAMLINE_STAFF_ADMIN_NAME", "Test Admin")
    monkeypatch.setenv("BEAMLINE_STAFF_GROUP_MANAGER_NAME", "Test Manager")
    from importlib import reload

    from cora.api import beamline_staff_seed

    reload(beamline_staff_seed)
    args = beamline_staff_seed.build_parser().parse_args([])
    assert args.admin_name == "Test Admin"
    assert args.group_manager_name == "Test Manager"
    reload(beamline_staff_seed)


def test_parser_defaults_are_none_without_environment(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("BEAMLINE_STAFF_ADMIN_NAME", raising=False)
    monkeypatch.delenv("BEAMLINE_STAFF_GROUP_MANAGER_NAME", raising=False)
    from importlib import reload

    from cora.api import beamline_staff_seed

    reload(beamline_staff_seed)
    args = beamline_staff_seed.build_parser().parse_args([])
    assert args.admin_name is None
    assert args.group_manager_name is None
    assert args.dry_run is False


def test_parser_accepts_cli_overrides() -> None:
    args = build_parser().parse_args(
        [
            "--admin-name",
            "Test Admin",
            "--group-manager-name",
            "Test Manager",
            "--staff-name",
            "Test Staff",
            "--dry-run",
        ]
    )
    assert args.admin_name == "Test Admin"
    assert args.group_manager_name == "Test Manager"
    assert args.staff_name == "Test Staff"
    assert args.dry_run is True


def test_main_parses_argv_and_returns_the_ceremony_exit_code(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from cora.api import beamline_staff_seed

    received: dict[str, object] = {}

    async def fake_ceremony(**kwargs: object) -> int:
        received.update(kwargs)
        return 2

    monkeypatch.setattr(beamline_staff_seed, "seed_beamline_staff", fake_ceremony)

    exit_code = beamline_staff_seed.main(
        [
            "--admin-name",
            "Test Admin",
            "--group-manager-name",
            "Test Manager",
            "--staff-name",
            "Test Staff",
            "--dry-run",
        ]
    )

    assert exit_code == 2
    assert received["names_by_slot"] == {
        "2-bm-admin": "Test Admin",
        "2-bm-group-manager": "Test Manager",
        "2-bm-staff": "Test Staff",
    }
    assert received["dry_run"] is True
