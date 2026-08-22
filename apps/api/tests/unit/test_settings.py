"""Smoke tests for application Settings loading."""

from uuid import UUID

import pytest

from cora.infrastructure.config import Settings


@pytest.mark.unit
def test_settings_has_defaults(monkeypatch: pytest.MonkeyPatch) -> None:
    """Settings should load with defaults when env vars are unset."""
    monkeypatch.delenv("APP_ENV", raising=False)
    monkeypatch.delenv("LOG_LEVEL", raising=False)

    settings = Settings()

    assert settings.app_env == "local"
    assert settings.log_level == "INFO"
    assert settings.database_url.startswith("postgresql://")


@pytest.mark.unit
def test_settings_reads_env(monkeypatch: pytest.MonkeyPatch) -> None:
    """Env vars should override defaults."""
    monkeypatch.setenv("APP_ENV", "test")
    monkeypatch.setenv("LOG_LEVEL", "DEBUG")
    monkeypatch.setenv("DATABASE_URL", "postgresql://test:test@host/db")

    settings = Settings()

    assert settings.app_env == "test"
    assert settings.log_level == "DEBUG"
    assert settings.database_url == "postgresql://test:test@host/db"


@pytest.mark.unit
def test_settings_accepts_postgres_scheme(monkeypatch: pytest.MonkeyPatch) -> None:
    """Asyncpg accepts both 'postgresql://' and 'postgres://'."""
    monkeypatch.setenv("DATABASE_URL", "postgres://test:test@host/db")
    settings = Settings()
    assert settings.database_url == "postgres://test:test@host/db"


@pytest.mark.unit
def test_settings_rejects_malformed_database_url(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Catch typos at startup, not on first connection attempt."""
    import pydantic

    monkeypatch.setenv("DATABASE_URL", "psql://test:test@host/db")
    with pytest.raises(pydantic.ValidationError):
        Settings()


@pytest.mark.unit
def test_settings_rejects_sqlalchemy_style_url(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """SQLAlchemy-style 'postgresql+psycopg2://' URLs aren't supported by asyncpg."""
    import pydantic

    monkeypatch.setenv("DATABASE_URL", "postgresql+psycopg2://test:test@host/db")
    with pytest.raises(pydantic.ValidationError):
        Settings()


@pytest.mark.unit
def test_settings_trust_policy_id_defaults_to_none(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Default unset → AllowAllAuthorize wired by build_kernel.
    Permissive default; matches dev/test."""
    monkeypatch.delenv("TRUST_POLICY_ID", raising=False)
    settings = Settings()
    assert settings.trust_policy_id is None


@pytest.mark.unit
def test_settings_trust_policy_id_parses_uuid_from_env(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from uuid import UUID

    policy_id = UUID("01900000-0000-7000-8000-000000000601")
    monkeypatch.setenv("TRUST_POLICY_ID", str(policy_id))
    settings = Settings()
    assert settings.trust_policy_id == policy_id


@pytest.mark.unit
def test_settings_rejects_malformed_trust_policy_id(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Pydantic UUID validation catches typos at startup."""
    import pydantic

    monkeypatch.setenv("TRUST_POLICY_ID", "not-a-uuid")
    with pytest.raises(pydantic.ValidationError):
        Settings()


@pytest.mark.unit
def test_settings_run_initiator_enabled_defaults_to_false(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Default off: deployments opt the autonomous run-initiator in explicitly."""
    monkeypatch.delenv("RUN_INITIATOR_ENABLED", raising=False)
    settings = Settings()
    assert settings.run_initiator_enabled is False


@pytest.mark.unit
def test_settings_run_initiator_tick_seconds_defaults_and_rejects_tight_loop(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    import pydantic

    monkeypatch.delenv("RUN_INITIATOR_TICK_SECONDS", raising=False)
    assert Settings().run_initiator_tick_seconds == 30.0

    monkeypatch.setenv("RUN_INITIATOR_TICK_SECONDS", "0.1")  # floor accepted
    assert Settings().run_initiator_tick_seconds == 0.1

    monkeypatch.setenv("RUN_INITIATOR_TICK_SECONDS", "0.05")  # below floor rejected
    with pytest.raises(pydantic.ValidationError):
        Settings()


@pytest.mark.unit
def test_settings_run_initiator_max_in_flight_defaults_and_rejects_below_one(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    import pydantic

    monkeypatch.delenv("RUN_INITIATOR_MAX_IN_FLIGHT", raising=False)
    assert Settings().run_initiator_max_in_flight == 1

    monkeypatch.setenv("RUN_INITIATOR_MAX_IN_FLIGHT", "1")  # floor accepted
    assert Settings().run_initiator_max_in_flight == 1

    monkeypatch.setenv("RUN_INITIATOR_MAX_IN_FLIGHT", "0")  # below floor rejected
    with pytest.raises(pydantic.ValidationError):
        Settings()


@pytest.mark.unit
def test_settings_run_initiator_plan_id_defaults_none_and_parses_uuid(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from uuid import UUID

    import pydantic

    monkeypatch.delenv("RUN_INITIATOR_PLAN_ID", raising=False)
    assert Settings().run_initiator_plan_id is None

    plan_id = UUID("01900000-0000-7000-8000-000000464d21")
    monkeypatch.setenv("RUN_INITIATOR_PLAN_ID", str(plan_id))
    assert Settings().run_initiator_plan_id == plan_id

    monkeypatch.setenv("RUN_INITIATOR_PLAN_ID", "not-a-uuid")  # typo caught at startup
    with pytest.raises(pydantic.ValidationError):
        Settings()


@pytest.mark.unit
def test_settings_subscriber_agent_designations_default_to_none(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Unset means the seeded singleton for both LLM subscribers, so
    nothing changes on upgrade."""
    monkeypatch.delenv("RUN_DEBRIEFER_AGENT_ID", raising=False)
    monkeypatch.delenv("CAUTION_DRAFTER_AGENT_ID", raising=False)
    settings = Settings()
    assert settings.run_debriefer_agent_id is None
    assert settings.caution_drafter_agent_id is None


@pytest.mark.unit
def test_settings_require_authenticated_principal_defaults_to_false(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Phase-1 dev / test posture: SYSTEM_PRINCIPAL_ID fallback for
    header-less requests is convenient. Production deployments
    explicitly turn this on."""
    monkeypatch.delenv("REQUIRE_AUTHENTICATED_PRINCIPAL", raising=False)
    settings = Settings()
    assert settings.require_authenticated_principal is False


@pytest.mark.unit
def test_settings_require_authenticated_principal_reads_env(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("REQUIRE_AUTHENTICATED_PRINCIPAL", "true")
    settings = Settings()
    assert settings.require_authenticated_principal is True


@pytest.mark.unit
def test_settings_projection_use_listen_notify_default_true(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.delenv("PROJECTION_USE_LISTEN_NOTIFY", raising=False)
    settings = Settings()
    assert settings.projection_use_listen_notify is True


@pytest.mark.unit
def test_settings_projection_use_listen_notify_can_disable(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Per `project_deferred.md` NATS trigger: flip to False as an
    interim mitigation before the full NATS bridge ships."""
    monkeypatch.setenv("PROJECTION_USE_LISTEN_NOTIFY", "false")
    settings = Settings()
    assert settings.projection_use_listen_notify is False


@pytest.mark.unit
def test_settings_projection_poll_interval_default(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.delenv("PROJECTION_POLL_INTERVAL_SECONDS", raising=False)
    settings = Settings()
    assert settings.projection_poll_interval_seconds == 5.0


@pytest.mark.unit
def test_settings_projection_poll_interval_rejects_tight_loop(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Floor of 0.1s prevents accidental tight-loop misconfiguration."""
    import pydantic

    monkeypatch.setenv("PROJECTION_POLL_INTERVAL_SECONDS", "0.05")
    with pytest.raises(pydantic.ValidationError):
        Settings()


# ---------------------------------------------------------------------------
# Field validators that enforce numeric bounds
# ---------------------------------------------------------------------------


@pytest.mark.unit
@pytest.mark.parametrize("bad_value", ["-0.01", "1.01", "2.0", "-1.0"])
def test_settings_otel_sampler_ratio_rejects_out_of_range(
    monkeypatch: pytest.MonkeyPatch, bad_value: str
) -> None:
    """Sampler ratio outside [0.0, 1.0] is meaningless and rejected."""
    import pydantic

    monkeypatch.setenv("OTEL_SAMPLER_RATIO", bad_value)
    with pytest.raises(pydantic.ValidationError, match="otel_sampler_ratio must be in"):
        Settings()


@pytest.mark.unit
@pytest.mark.parametrize("boundary_value", ["0.0", "1.0", "0.5"])
def test_settings_otel_sampler_ratio_accepts_in_range(
    monkeypatch: pytest.MonkeyPatch, boundary_value: str
) -> None:
    """Boundaries inclusive: 0.0 and 1.0 are both valid."""
    monkeypatch.setenv("OTEL_SAMPLER_RATIO", boundary_value)
    settings = Settings()
    assert settings.otel_sampler_ratio == float(boundary_value)


@pytest.mark.unit
def test_settings_idempotency_ttl_hours_accepts_zero_to_disable_pruner(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """0 is the documented sentinel that disables the pruner."""
    monkeypatch.setenv("IDEMPOTENCY_TTL_HOURS", "0")
    assert Settings().idempotency_ttl_hours == 0


@pytest.mark.unit
def test_settings_idempotency_ttl_hours_rejects_negative(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Negative TTL would invert the window (always-prune-everything)."""
    import pydantic

    monkeypatch.setenv("IDEMPOTENCY_TTL_HOURS", "-1")
    with pytest.raises(pydantic.ValidationError, match="idempotency_ttl_hours must be >= 0"):
        Settings()


@pytest.mark.unit
def test_settings_idempotency_lock_stale_seconds_rejects_below_one(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Floor of 1s prevents a tight stale-lock recovery loop."""
    import pydantic

    monkeypatch.setenv("IDEMPOTENCY_LOCK_STALE_SECONDS", "0")
    with pytest.raises(
        pydantic.ValidationError, match="idempotency_lock_stale_seconds must be >= 1"
    ):
        Settings()


# ---------------------------------------------------------------------------
# capture_status_phases: the deployment-declared literal-to-CapturePhase map
# ---------------------------------------------------------------------------


@pytest.mark.unit
def test_settings_capture_watch_defaults_are_empty_and_off(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A generic boot declares no capture PVs and runs no watcher."""
    monkeypatch.delenv("CAPTURE_WATCH_PVS", raising=False)
    monkeypatch.delenv("CAPTURE_STATUS_PHASES", raising=False)
    monkeypatch.delenv("RUN_WITNESS_ENABLED", raising=False)

    settings = Settings()

    assert settings.capture_watch_pvs == {}
    assert settings.capture_status_phases == {}
    assert settings.capture_watch_probe_tick_seconds is None
    assert settings.run_witness_enabled is False


@pytest.mark.unit
def test_settings_capture_watch_pvs_reads_role_keyed_json(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Outer key is the capture code, inner dict is role -> PV."""
    monkeypatch.setenv(
        "CAPTURE_WATCH_PVS",
        '{"2bmb-tomoscan": {"status": "2bmb:TomoScan:ScanStatus"}}',
    )
    settings = Settings()
    assert settings.capture_watch_pvs == {"2bmb-tomoscan": {"status": "2bmb:TomoScan:ScanStatus"}}


@pytest.mark.unit
def test_settings_capture_status_phases_accepts_every_real_capture_phase_value(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Every non-UNRECOGNIZED CapturePhase value is a legal mapping target."""
    monkeypatch.setenv(
        "CAPTURE_STATUS_PHASES",
        '{"Beginning scan": "Begun", "Collecting projections": "Progressing", '
        '"Scan complete": "Ended", "Scan aborted": "Aborted"}',
    )
    settings = Settings()
    assert settings.capture_status_phases == {
        "Beginning scan": "Begun",
        "Collecting projections": "Progressing",
        "Scan complete": "Ended",
        "Scan aborted": "Aborted",
    }


@pytest.mark.unit
def test_settings_capture_status_phases_rejects_a_value_outside_capture_phase(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A typo in the mapped-to phase must fail at boot, not classify
    silently as UNRECOGNIZED until someone reads the log."""
    import pydantic

    monkeypatch.setenv("CAPTURE_STATUS_PHASES", '{"Scan complete": "Endedd"}')
    with pytest.raises(pydantic.ValidationError, match="capture_status_phases has values"):
        Settings()


@pytest.mark.unit
def test_settings_capture_status_phases_rejects_explicit_unrecognized(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """UNRECOGNIZED is what an absent literal already means; mapping a
    literal to it explicitly would be a second way to say the same
    thing, so it is rejected rather than silently accepted."""
    import pydantic

    monkeypatch.setenv("CAPTURE_STATUS_PHASES", '{"Weird status": "Unrecognized"}')
    with pytest.raises(pydantic.ValidationError, match="capture_status_phases has values"):
        Settings()


# ---------------------------------------------------------------------------
# capture_baseline_pvs: the genesis-baseline PV set (slice 12)
# ---------------------------------------------------------------------------


@pytest.mark.unit
def test_settings_capture_baseline_defaults_are_empty_and_off(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A generic boot declares no baseline PVs and reads nothing at genesis."""
    monkeypatch.delenv("CAPTURE_BASELINE_PVS", raising=False)
    monkeypatch.delenv("CAPTURE_BASELINE_RECORDING_ENABLED", raising=False)

    settings = Settings()

    assert settings.capture_baseline_pvs == {}
    assert settings.capture_baseline_recording_enabled is False


@pytest.mark.unit
def test_settings_capture_baseline_pvs_reads_channel_keyed_json(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Outer key is the capture code, inner key is the observation's
    channel_name (not a role), matching the sibling `capture_watch_pvs`
    shape but with an open, deployment-chosen inner vocabulary."""
    monkeypatch.setenv(
        "CAPTURE_BASELINE_PVS",
        '{"2bmb-tomoscan": {"ExposureTime": "2bmb:TomoScan:ExposureTime"}}',
    )
    settings = Settings()
    assert settings.capture_baseline_pvs == {
        "2bmb-tomoscan": {"ExposureTime": "2bmb:TomoScan:ExposureTime"}
    }


@pytest.mark.unit
def test_settings_capture_baseline_recording_enabled_reads_env(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("CAPTURE_BASELINE_RECORDING_ENABLED", "true")
    settings = Settings()
    assert settings.capture_baseline_recording_enabled is True


# ---------------------------------------------------------------------------
# capture_experiment_identity_pvs: proposal / ESAF / ESAF-DOI (slice 14a)
# ---------------------------------------------------------------------------


@pytest.mark.unit
def test_settings_capture_experiment_identity_defaults_are_empty_and_off(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A generic boot declares no experiment-identity PVs and vaults nothing."""
    monkeypatch.delenv("CAPTURE_EXPERIMENT_IDENTITY_PVS", raising=False)
    monkeypatch.delenv("CAPTURE_EXPERIMENT_IDENTITY_RECORDING_ENABLED", raising=False)

    settings = Settings()

    assert settings.capture_experiment_identity_pvs == {}
    assert settings.capture_experiment_identity_recording_enabled is False


@pytest.mark.unit
def test_settings_capture_experiment_identity_pvs_reads_role_keyed_json(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Outer key is the capture code, inner dict is the closed role ->
    PV vocabulary (`proposal_number` / `esaf_number` / `esaf_doi_number`)."""
    monkeypatch.setenv(
        "CAPTURE_EXPERIMENT_IDENTITY_PVS",
        '{"2bmb-tomoscan": {'
        '"proposal_number": "2bmb:TomoScan:ProposalNumber", '
        '"esaf_number": "2bmb:TomoScan:ESAFNumber", '
        '"esaf_doi_number": "2bmb:TomoScan:ESAFDOINumber"'
        "}}",
    )
    settings = Settings()
    assert settings.capture_experiment_identity_pvs == {
        "2bmb-tomoscan": {
            "proposal_number": "2bmb:TomoScan:ProposalNumber",
            "esaf_number": "2bmb:TomoScan:ESAFNumber",
            "esaf_doi_number": "2bmb:TomoScan:ESAFDOINumber",
        }
    }


@pytest.mark.unit
def test_settings_capture_experiment_identity_pvs_rejects_unrecognized_role(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A typo'd role must fail at boot: the reader dispatches on exactly
    the three closed role names and would otherwise silently never read
    an unrecognized one, with no error anywhere."""
    import pydantic

    monkeypatch.setenv(
        "CAPTURE_EXPERIMENT_IDENTITY_PVS",
        '{"2bmb-tomoscan": {"proposal_numberr": "2bmb:TomoScan:ProposalNumber"}}',
    )
    with pytest.raises(pydantic.ValidationError, match="capture_experiment_identity_pvs has roles"):
        Settings()


@pytest.mark.unit
def test_settings_capture_experiment_identity_recording_enabled_reads_env(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("CAPTURE_EXPERIMENT_IDENTITY_RECORDING_ENABLED", "true")
    settings = Settings()
    assert settings.capture_experiment_identity_recording_enabled is True


# ---------------------------------------------------------------------------
# capture_probe_recording_enabled (slice 16, the SEVENTH kill switch)
# ---------------------------------------------------------------------------


@pytest.mark.unit
def test_settings_capture_probe_recording_enabled_defaults_off(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.delenv("CAPTURE_PROBE_RECORDING_ENABLED", raising=False)
    settings = Settings()
    assert settings.capture_probe_recording_enabled is False


@pytest.mark.unit
def test_settings_capture_probe_recording_enabled_reads_env(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("CAPTURE_PROBE_RECORDING_ENABLED", "true")
    settings = Settings()
    assert settings.capture_probe_recording_enabled is True


# ---------------------------------------------------------------------------
# capture_scan_ingestor_* / scan_probe_* (slice 17, the EIGHTH kill switch)
# ---------------------------------------------------------------------------


@pytest.mark.unit
def test_settings_capture_scan_ingestor_defaults_are_empty_and_off(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.delenv("CAPTURE_SCAN_INGESTOR_ENABLED", raising=False)
    monkeypatch.delenv("CAPTURE_SCAN_INGESTOR_BINDINGS", raising=False)
    monkeypatch.delenv("SCAN_PROBE_REMOTE_HOST", raising=False)

    settings = Settings()

    assert settings.capture_scan_ingestor_enabled is False
    assert settings.capture_scan_ingestor_bindings == {}
    assert settings.scan_probe_remote_host is None


@pytest.mark.unit
def test_settings_capture_scan_ingestor_bindings_reads_code_keyed_json(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("POSIX_CHECKSUM_ROOTS", '["/local1/2BM"]')
    monkeypatch.setenv(
        "CAPTURE_SCAN_INGESTOR_BINDINGS",
        '{"2bmb-tomoscan": {'
        '"producing_asset_id": "01900000-0000-7000-8000-000000000001", '
        '"locations": {"/local1/2BM": {'
        '"supply_id": "01900000-0000-7000-8000-000000000002", '
        '"access_protocol": "POSIX"'
        "}}}}",
    )
    settings = Settings()
    binding = settings.capture_scan_ingestor_bindings["2bmb-tomoscan"]
    assert binding.producing_asset_id == UUID("01900000-0000-7000-8000-000000000001")
    location = binding.locations["/local1/2BM"]
    assert location.supply_id == UUID("01900000-0000-7000-8000-000000000002")
    assert location.access_protocol == "POSIX"


@pytest.mark.unit
def test_settings_capture_scan_ingestor_bindings_rejects_a_missing_required_field(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    import pydantic

    monkeypatch.setenv(
        "CAPTURE_SCAN_INGESTOR_BINDINGS",
        '{"2bmb-tomoscan": {"locations": {"/local1/2BM": {'
        '"supply_id": "01900000-0000-7000-8000-000000000002", '
        '"access_protocol": "POSIX"'
        "}}}}",
    )
    with pytest.raises(pydantic.ValidationError, match="Field required"):
        Settings()


@pytest.mark.unit
def test_settings_capture_scan_ingestor_bindings_with_two_locations_both_retrievable(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A detector's finished file lands on more than one storage location
    (the acquisition tier, and a durable APS Data Management copy under
    `/gdata`); one binding must carry one entry per location."""
    monkeypatch.setenv("POSIX_CHECKSUM_ROOTS", '["/local1/2BM"]')
    monkeypatch.setenv("SCAN_PROBE_ALLOWED_ROOTS", '["/gdata/dm/2BM"]')
    monkeypatch.setenv(
        "CAPTURE_SCAN_INGESTOR_BINDINGS",
        '{"2bmb-tomoscan": {'
        '"producing_asset_id": "01900000-0000-7000-8000-000000000001", '
        '"locations": {'
        '"/local1/2BM": {'
        '"supply_id": "01900000-0000-7000-8000-000000000002", '
        '"access_protocol": "POSIX"'
        "}, "
        '"/gdata/dm/2BM": {'
        '"supply_id": "01900000-0000-7000-8000-000000000003", '
        '"access_protocol": "NFS"'
        "}"
        "}}}",
    )
    settings = Settings()
    binding = settings.capture_scan_ingestor_bindings["2bmb-tomoscan"]

    local = binding.locations["/local1/2BM"]
    assert local.supply_id == UUID("01900000-0000-7000-8000-000000000002")
    assert local.access_protocol == "POSIX"

    durable = binding.locations["/gdata/dm/2BM"]
    assert durable.supply_id == UUID("01900000-0000-7000-8000-000000000003")
    assert durable.access_protocol == "NFS"


@pytest.mark.unit
def test_settings_capture_scan_ingestor_bindings_location_with_trailing_slash_is_normalized(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("POSIX_CHECKSUM_ROOTS", '["/local1/2BM"]')
    monkeypatch.setenv(
        "CAPTURE_SCAN_INGESTOR_BINDINGS",
        '{"2bmb-tomoscan": {'
        '"producing_asset_id": "01900000-0000-7000-8000-000000000001", '
        '"locations": {"/local1/2BM/": {'
        '"supply_id": "01900000-0000-7000-8000-000000000002", '
        '"access_protocol": "POSIX"'
        "}}}}",
    )
    settings = Settings()
    binding = settings.capture_scan_ingestor_bindings["2bmb-tomoscan"]
    assert "/local1/2BM" in binding.locations
    assert "/local1/2BM/" not in binding.locations


@pytest.mark.unit
def test_settings_capture_scan_ingestor_bindings_rejects_a_relative_root(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    import pydantic

    monkeypatch.setenv(
        "CAPTURE_SCAN_INGESTOR_BINDINGS",
        '{"2bmb-tomoscan": {'
        '"producing_asset_id": "01900000-0000-7000-8000-000000000001", '
        '"locations": {"local1/2BM": {'
        '"supply_id": "01900000-0000-7000-8000-000000000002", '
        '"access_protocol": "POSIX"'
        "}}}}",
    )
    with pytest.raises(pydantic.ValidationError, match="is not an absolute path"):
        Settings()


@pytest.mark.unit
def test_settings_capture_scan_ingestor_bindings_rejects_root_of_slash(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    import pydantic

    monkeypatch.setenv(
        "CAPTURE_SCAN_INGESTOR_BINDINGS",
        '{"2bmb-tomoscan": {'
        '"producing_asset_id": "01900000-0000-7000-8000-000000000001", '
        '"locations": {"/": {'
        '"supply_id": "01900000-0000-7000-8000-000000000002", '
        '"access_protocol": "POSIX"'
        "}}}}",
    )
    with pytest.raises(pydantic.ValidationError, match="normalizes to the empty string"):
        Settings()


@pytest.mark.unit
def test_settings_capture_scan_ingestor_bindings_rejects_empty_locations(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    import pydantic

    monkeypatch.setenv(
        "CAPTURE_SCAN_INGESTOR_BINDINGS",
        '{"2bmb-tomoscan": {'
        '"producing_asset_id": "01900000-0000-7000-8000-000000000001", '
        '"locations": {}'
        "}}",
    )
    with pytest.raises(pydantic.ValidationError, match="locations is empty"):
        Settings()


@pytest.mark.unit
def test_settings_capture_scan_ingestor_bindings_rejects_two_locations_that_collapse_to_one_root(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """`/local1/2BM` and `/local1/2BM/` normalize to the same root; silently
    keeping only one would drop a Supply/protocol pairing an operator wrote
    on purpose with no signal that it happened."""
    import pydantic

    monkeypatch.setenv(
        "CAPTURE_SCAN_INGESTOR_BINDINGS",
        '{"2bmb-tomoscan": {'
        '"producing_asset_id": "01900000-0000-7000-8000-000000000001", '
        '"locations": {'
        '"/local1/2BM": {'
        '"supply_id": "01900000-0000-7000-8000-000000000002", '
        '"access_protocol": "POSIX"'
        "}, "
        '"/local1/2BM/": {'
        '"supply_id": "01900000-0000-7000-8000-000000000003", '
        '"access_protocol": "NFS"'
        "}"
        "}}}",
    )
    with pytest.raises(pydantic.ValidationError, match="both normalize to"):
        Settings()


@pytest.mark.unit
def test_settings_capture_scan_ingestor_bindings_rejects_unknown_key_on_binding(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    import pydantic

    monkeypatch.setenv(
        "CAPTURE_SCAN_INGESTOR_BINDINGS",
        '{"2bmb-tomoscan": {'
        '"producing_asset_id": "01900000-0000-7000-8000-000000000001", '
        '"producing_asset_idd": "01900000-0000-7000-8000-000000000001", '
        '"locations": {"/local1/2BM": {'
        '"supply_id": "01900000-0000-7000-8000-000000000002", '
        '"access_protocol": "POSIX"'
        "}}}}",
    )
    with pytest.raises(pydantic.ValidationError, match="Extra inputs are not permitted"):
        Settings()


@pytest.mark.unit
def test_settings_capture_scan_ingestor_bindings_rejects_unknown_key_on_location(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv(
        "CAPTURE_SCAN_INGESTOR_BINDINGS",
        '{"2bmb-tomoscan": {'
        '"producing_asset_id": "01900000-0000-7000-8000-000000000001", '
        '"locations": {"/local1/2BM": {'
        '"supply_id": "01900000-0000-7000-8000-000000000002", '
        '"access_protocol": "POSIX", '
        '"extra_field": "x"'
        "}}}}",
    )
    import pydantic

    with pytest.raises(pydantic.ValidationError, match="Extra inputs are not permitted"):
        Settings()


@pytest.mark.unit
def test_settings_capture_scan_ingestor_bindings_rejects_a_non_uuid_asset_id(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    import pydantic

    monkeypatch.setenv(
        "CAPTURE_SCAN_INGESTOR_BINDINGS",
        '{"2bmb-tomoscan": {'
        '"producing_asset_id": "not-a-uuid", '
        '"locations": {"/local1/2BM": {'
        '"supply_id": "01900000-0000-7000-8000-000000000002", '
        '"access_protocol": "POSIX"'
        "}}}}",
    )
    with pytest.raises(pydantic.ValidationError, match="Input should be a valid UUID"):
        Settings()


@pytest.mark.unit
def test_settings_capture_scan_ingestor_bindings_rejects_an_unrecognized_access_protocol(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv(
        "CAPTURE_SCAN_INGESTOR_BINDINGS",
        '{"2bmb-tomoscan": {'
        '"producing_asset_id": "01900000-0000-7000-8000-000000000001", '
        '"locations": {"/local1/2BM": {'
        '"supply_id": "01900000-0000-7000-8000-000000000002", '
        '"access_protocol": "FTP"'
        "}}}}",
    )
    import pydantic

    with pytest.raises(pydantic.ValidationError, match="access_protocol"):
        Settings()


@pytest.mark.unit
def test_settings_capture_scan_ingestor_bindings_rejects_a_root_not_in_either_scan_allowlist(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A location neither `posix_checksum_roots` nor
    `scan_probe_allowed_roots` allowlists can never actually be read by
    the sweep; refusing at boot beats a location that sits unreachable
    forever."""
    import pydantic

    monkeypatch.delenv("POSIX_CHECKSUM_ROOTS", raising=False)
    monkeypatch.delenv("SCAN_PROBE_ALLOWED_ROOTS", raising=False)
    monkeypatch.setenv(
        "CAPTURE_SCAN_INGESTOR_BINDINGS",
        '{"2bmb-tomoscan": {'
        '"producing_asset_id": "01900000-0000-7000-8000-000000000001", '
        '"locations": {"/local1/2BM": {'
        '"supply_id": "01900000-0000-7000-8000-000000000002", '
        '"access_protocol": "POSIX"'
        "}}}}",
    )
    with pytest.raises(
        pydantic.ValidationError,
        match="is in neither posix_checksum_roots nor scan_probe_allowed_roots",
    ):
        Settings()


@pytest.mark.unit
def test_settings_capture_scan_ingestor_bindings_accepts_a_root_only_in_scan_probe_allowed_roots(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The boot check is a UNION of both allowlists, not just
    `posix_checksum_roots`: a location reachable only via the remote
    probe must still validate."""
    monkeypatch.delenv("POSIX_CHECKSUM_ROOTS", raising=False)
    monkeypatch.setenv("SCAN_PROBE_ALLOWED_ROOTS", '["/local1/2BM"]')
    monkeypatch.setenv(
        "CAPTURE_SCAN_INGESTOR_BINDINGS",
        '{"2bmb-tomoscan": {'
        '"producing_asset_id": "01900000-0000-7000-8000-000000000001", '
        '"locations": {"/local1/2BM": {'
        '"supply_id": "01900000-0000-7000-8000-000000000002", '
        '"access_protocol": "POSIX"'
        "}}}}",
    )
    settings = Settings()
    assert "/local1/2BM" in settings.capture_scan_ingestor_bindings["2bmb-tomoscan"].locations


# ---------------------------------------------------------------------------
# CaptureScanIngestorLocation.durable / .subdirectory, and the two derived reads
# ---------------------------------------------------------------------------


@pytest.mark.unit
def test_settings_capture_scan_ingestor_bindings_durable_defaults_to_false_when_absent(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("POSIX_CHECKSUM_ROOTS", '["/local1/2BM"]')
    monkeypatch.setenv(
        "CAPTURE_SCAN_INGESTOR_BINDINGS",
        '{"2bmb-tomoscan": {'
        '"producing_asset_id": "01900000-0000-7000-8000-000000000001", '
        '"locations": {"/local1/2BM": {'
        '"supply_id": "01900000-0000-7000-8000-000000000002", '
        '"access_protocol": "POSIX"'
        "}}}}",
    )
    settings = Settings()
    location = settings.capture_scan_ingestor_bindings["2bmb-tomoscan"].locations["/local1/2BM"]
    assert location.durable is False


@pytest.mark.unit
def test_settings_capture_scan_ingestor_bindings_durable_round_trips_on_the_flagged_location_only(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Only the location that sets `durable` in the env var comes back
    `True`; its sibling, which does not set it, stays `False`. Both
    assertions are needed, since a validator that ignored the field and
    always returned one fixed value would pass either assertion alone."""
    monkeypatch.setenv("POSIX_CHECKSUM_ROOTS", '["/local1/2BM"]')
    monkeypatch.setenv("SCAN_PROBE_ALLOWED_ROOTS", '["/gdata/dm/2BM"]')
    monkeypatch.setenv(
        "CAPTURE_SCAN_INGESTOR_BINDINGS",
        '{"2bmb-tomoscan": {'
        '"producing_asset_id": "01900000-0000-7000-8000-000000000001", '
        '"locations": {'
        '"/local1/2BM": {'
        '"supply_id": "01900000-0000-7000-8000-000000000002", '
        '"access_protocol": "POSIX"'
        "}, "
        '"/gdata/dm/2BM": {'
        '"supply_id": "01900000-0000-7000-8000-000000000003", '
        '"access_protocol": "NFS", '
        '"durable": true'
        "}"
        "}}}",
    )
    settings = Settings()
    binding = settings.capture_scan_ingestor_bindings["2bmb-tomoscan"]

    assert binding.locations["/local1/2BM"].durable is False
    assert binding.locations["/gdata/dm/2BM"].durable is True


@pytest.mark.unit
def test_settings_capture_scan_ingestor_bindings_rejects_two_durable_locations_under_one_code(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Two durable locations would leave the sweep no way to choose
    between them; refusing at boot beats discovering the ambiguity on
    the first sweep tick."""
    import pydantic

    monkeypatch.setenv("POSIX_CHECKSUM_ROOTS", '["/local1/2BM"]')
    monkeypatch.setenv("SCAN_PROBE_ALLOWED_ROOTS", '["/gdata/dm/2BM"]')
    monkeypatch.setenv(
        "CAPTURE_SCAN_INGESTOR_BINDINGS",
        '{"2bmb-tomoscan": {'
        '"producing_asset_id": "01900000-0000-7000-8000-000000000001", '
        '"locations": {'
        '"/local1/2BM": {'
        '"supply_id": "01900000-0000-7000-8000-000000000002", '
        '"access_protocol": "POSIX", '
        '"durable": true'
        "}, "
        '"/gdata/dm/2BM": {'
        '"supply_id": "01900000-0000-7000-8000-000000000003", '
        '"access_protocol": "NFS", '
        '"durable": true'
        "}"
        "}}}",
    )
    with pytest.raises(
        pydantic.ValidationError, match="At most one location per capture code may be durable"
    ):
        Settings()


@pytest.mark.unit
def test_settings_capture_scan_ingestor_bindings_allows_one_durable_location_per_code_across_codes(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The one-durable-per-code rule is scoped to a single binding: two
    DIFFERENT capture codes each naming their own durable location is
    not the ambiguity the validator guards against."""
    monkeypatch.setenv("POSIX_CHECKSUM_ROOTS", '["/local1/2BM", "/local2/2BMB"]')
    monkeypatch.setenv(
        "CAPTURE_SCAN_INGESTOR_BINDINGS",
        '{"2bmb-tomoscan": {'
        '"producing_asset_id": "01900000-0000-7000-8000-000000000001", '
        '"locations": {"/local1/2BM": {'
        '"supply_id": "01900000-0000-7000-8000-000000000002", '
        '"access_protocol": "POSIX", '
        '"durable": true'
        "}}}, "
        '"2bmb-pco": {'
        '"producing_asset_id": "01900000-0000-7000-8000-000000000004", '
        '"locations": {"/local2/2BMB": {'
        '"supply_id": "01900000-0000-7000-8000-000000000005", '
        '"access_protocol": "POSIX", '
        '"durable": true'
        "}}}}",
    )
    settings = Settings()

    assert settings.capture_scan_ingestor_bindings["2bmb-tomoscan"].locations["/local1/2BM"].durable
    assert settings.capture_scan_ingestor_bindings["2bmb-pco"].locations["/local2/2BMB"].durable


@pytest.mark.unit
def test_capture_scan_ingestor_durable_roots_and_supply_ids_span_capture_codes_and_skip_others(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Both derived reads union across every capture code, and both
    exclude a location that is present but NOT marked durable: a
    read that returned every configured root or supply id regardless
    of the flag would still pass a same-code-only assertion, so the
    non-durable sibling location has to be there to catch it."""
    from cora.infrastructure.capture_scan_ingestor_binding import (
        durable_roots,
        durable_supply_ids,
    )

    monkeypatch.setenv("POSIX_CHECKSUM_ROOTS", '["/local1/2BM", "/local2/2BMB"]')
    monkeypatch.setenv("SCAN_PROBE_ALLOWED_ROOTS", '["/gdata/dm/2BM"]')
    monkeypatch.setenv(
        "CAPTURE_SCAN_INGESTOR_BINDINGS",
        '{"2bmb-tomoscan": {'
        '"producing_asset_id": "01900000-0000-7000-8000-000000000001", '
        '"locations": {'
        '"/local1/2BM": {'
        '"supply_id": "01900000-0000-7000-8000-000000000002", '
        '"access_protocol": "POSIX"'
        "}, "
        '"/gdata/dm/2BM": {'
        '"supply_id": "01900000-0000-7000-8000-000000000003", '
        '"access_protocol": "NFS", '
        '"durable": true'
        "}"
        "}}, "
        '"2bmb-pco": {'
        '"producing_asset_id": "01900000-0000-7000-8000-000000000004", '
        '"locations": {"/local2/2BMB": {'
        '"supply_id": "01900000-0000-7000-8000-000000000005", '
        '"access_protocol": "POSIX", '
        '"durable": true'
        "}}}}",
    )
    settings = Settings()
    bindings = settings.capture_scan_ingestor_bindings

    assert durable_roots(bindings) == frozenset({"/gdata/dm/2BM", "/local2/2BMB"})
    assert durable_supply_ids(bindings) == frozenset(
        {
            UUID("01900000-0000-7000-8000-000000000003"),
            UUID("01900000-0000-7000-8000-000000000005"),
        }
    )


@pytest.mark.unit
def test_capture_scan_ingestor_durable_roots_and_supply_ids_are_empty_when_none_are_durable(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from cora.infrastructure.capture_scan_ingestor_binding import (
        durable_roots,
        durable_supply_ids,
    )

    monkeypatch.setenv("POSIX_CHECKSUM_ROOTS", '["/local1/2BM"]')
    monkeypatch.setenv(
        "CAPTURE_SCAN_INGESTOR_BINDINGS",
        '{"2bmb-tomoscan": {'
        '"producing_asset_id": "01900000-0000-7000-8000-000000000001", '
        '"locations": {"/local1/2BM": {'
        '"supply_id": "01900000-0000-7000-8000-000000000002", '
        '"access_protocol": "POSIX"'
        "}}}}",
    )
    settings = Settings()
    bindings = settings.capture_scan_ingestor_bindings

    assert durable_roots(bindings) == frozenset()
    assert durable_supply_ids(bindings) == frozenset()


@pytest.mark.unit
def test_settings_capture_scan_ingestor_bindings_subdirectory_defaults_to_none(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("POSIX_CHECKSUM_ROOTS", '["/local1/2BM"]')
    monkeypatch.setenv(
        "CAPTURE_SCAN_INGESTOR_BINDINGS",
        '{"2bmb-tomoscan": {'
        '"producing_asset_id": "01900000-0000-7000-8000-000000000001", '
        '"locations": {"/local1/2BM": {'
        '"supply_id": "01900000-0000-7000-8000-000000000002", '
        '"access_protocol": "POSIX"'
        "}}}}",
    )
    settings = Settings()
    location = settings.capture_scan_ingestor_bindings["2bmb-tomoscan"].locations["/local1/2BM"]
    assert location.subdirectory is None


@pytest.mark.unit
def test_settings_capture_scan_ingestor_bindings_subdirectory_round_trips_on_one_location(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The location that sets `subdirectory` comes back with that exact
    segment; its sibling, which does not set it, stays `None` rather
    than inheriting the value."""
    monkeypatch.setenv("POSIX_CHECKSUM_ROOTS", '["/local1/2BM"]')
    monkeypatch.setenv("SCAN_PROBE_ALLOWED_ROOTS", '["/gdata/dm/2BM"]')
    monkeypatch.setenv(
        "CAPTURE_SCAN_INGESTOR_BINDINGS",
        '{"2bmb-tomoscan": {'
        '"producing_asset_id": "01900000-0000-7000-8000-000000000001", '
        '"locations": {'
        '"/local1/2BM": {'
        '"supply_id": "01900000-0000-7000-8000-000000000002", '
        '"access_protocol": "POSIX"'
        "}, "
        '"/gdata/dm/2BM": {'
        '"supply_id": "01900000-0000-7000-8000-000000000003", '
        '"access_protocol": "NFS", '
        '"durable": true, '
        '"subdirectory": "data"'
        "}"
        "}}}",
    )
    settings = Settings()
    binding = settings.capture_scan_ingestor_bindings["2bmb-tomoscan"]

    assert binding.locations["/local1/2BM"].subdirectory is None
    assert binding.locations["/gdata/dm/2BM"].subdirectory == "data"


@pytest.mark.unit
@pytest.mark.parametrize(
    "subdirectory",
    ["", "..", "sub/dir", "sub\\dir"],
    ids=["empty", "traversal", "separator", "backslash"],
)
def test_settings_capture_scan_ingestor_bindings_rejects_an_unsafe_subdirectory(
    monkeypatch: pytest.MonkeyPatch, subdirectory: str
) -> None:
    import json

    import pydantic

    monkeypatch.setenv("POSIX_CHECKSUM_ROOTS", '["/local1/2BM"]')
    monkeypatch.setenv(
        "CAPTURE_SCAN_INGESTOR_BINDINGS",
        json.dumps(
            {
                "2bmb-tomoscan": {
                    "producing_asset_id": "01900000-0000-7000-8000-000000000001",
                    "locations": {
                        "/local1/2BM": {
                            "supply_id": "01900000-0000-7000-8000-000000000002",
                            "access_protocol": "POSIX",
                            "subdirectory": subdirectory,
                        }
                    },
                }
            }
        ),
    )
    with pytest.raises(pydantic.ValidationError, match="is not one safe path segment"):
        Settings()


@pytest.mark.unit
def test_settings_scan_probe_remote_host_without_remote_python_is_rejected(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """`scan_probe_remote_host` with no interpreter path would otherwise
    surface only as `ssh ... None -m ...` at the first sweep tick."""
    import pydantic

    monkeypatch.setenv("SCAN_PROBE_REMOTE_HOST", "tomdet")
    monkeypatch.delenv("SCAN_PROBE_REMOTE_PYTHON", raising=False)
    with pytest.raises(pydantic.ValidationError, match="scan_probe_remote_python is not"):
        Settings()


@pytest.mark.unit
def test_settings_scan_probe_remote_host_with_remote_python_is_accepted(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("SCAN_PROBE_REMOTE_HOST", "tomdet")
    monkeypatch.setenv("SCAN_PROBE_REMOTE_PYTHON", "/venv/bin/python3")
    settings = Settings()
    assert settings.scan_probe_remote_host == "tomdet"
    assert settings.scan_probe_remote_python == "/venv/bin/python3"


@pytest.mark.unit
def test_settings_scan_probe_remote_host_rejects_empty_string(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """`SCAN_PROBE_REMOTE_HOST=""` used to pass validation and then
    `active_scan_transport` (`is not None`) treated it as a configured
    remote host, failing the vault's CHECK constraint on first upsert
    instead of at boot."""
    import pydantic

    monkeypatch.setenv("SCAN_PROBE_REMOTE_HOST", "")
    with pytest.raises(pydantic.ValidationError, match="scan_probe_remote_host is set to"):
        Settings()


@pytest.mark.unit
def test_settings_scan_probe_remote_host_rejects_whitespace_only(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    import pydantic

    monkeypatch.setenv("SCAN_PROBE_REMOTE_HOST", "   ")
    with pytest.raises(pydantic.ValidationError, match="scan_probe_remote_host is set to"):
        Settings()


# ---------------------------------------------------------------------------
# posix_checksum_roots / scan_probe_allowed_roots: absolute-path boot checks
# ---------------------------------------------------------------------------


@pytest.mark.unit
def test_settings_posix_checksum_roots_accepts_trailing_slash(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Normalization (`cora.shared.storage_root`) handles the trailing
    slash; the validator must not reject what normalization already fixes."""
    monkeypatch.setenv("POSIX_CHECKSUM_ROOTS", '["/local1/2BM/"]')
    settings = Settings()
    assert settings.posix_checksum_roots == ("/local1/2BM/",)


@pytest.mark.unit
def test_settings_posix_checksum_roots_rejects_relative_path(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    import pydantic

    monkeypatch.setenv("POSIX_CHECKSUM_ROOTS", '["local1/2BM"]')
    with pytest.raises(pydantic.ValidationError, match="is not an absolute path"):
        Settings()


@pytest.mark.unit
def test_settings_posix_checksum_roots_rejects_bare_root(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A bare "/" normalizes to the empty string, which the
    run_capture_path vault's CHECK constraint forbids; refuse it at
    boot instead of at the first write."""
    import pydantic

    monkeypatch.setenv("POSIX_CHECKSUM_ROOTS", '["/"]')
    with pytest.raises(pydantic.ValidationError, match="normalizes to the empty string"):
        Settings()


@pytest.mark.unit
def test_settings_scan_probe_allowed_roots_accepts_trailing_slash(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("SCAN_PROBE_ALLOWED_ROOTS", '["/local1/2BM/"]')
    settings = Settings()
    assert settings.scan_probe_allowed_roots == ("/local1/2BM/",)


@pytest.mark.unit
def test_settings_scan_probe_allowed_roots_rejects_relative_path(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    import pydantic

    monkeypatch.setenv("SCAN_PROBE_ALLOWED_ROOTS", '["local1/2BM"]')
    with pytest.raises(pydantic.ValidationError, match="is not an absolute path"):
        Settings()


@pytest.mark.unit
def test_settings_scan_probe_allowed_roots_rejects_bare_root(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    import pydantic

    monkeypatch.setenv("SCAN_PROBE_ALLOWED_ROOTS", '["/"]')
    with pytest.raises(pydantic.ValidationError, match="normalizes to the empty string"):
        Settings()
