"""Smoke tests for application Settings loading."""

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
