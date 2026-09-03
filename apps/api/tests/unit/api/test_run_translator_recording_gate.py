# pyright: reportPrivateUsage=false
"""Unit tests for the RunTranslator recording boot guard.

`_enforce_run_witness_recording_gate` refuses to boot with
`run_witness_recording_enabled=True` unless both `run_witness_enabled`
and `capture_watch_plan_id` are also set: promotion has no shadow
observer to promote from, or no Plan to bind the promoted Run to,
without both. Unlike the production signing/principal guards, this one
is not keyed on `app_env`: a half-configured recording gate is a
misconfiguration in every environment.

Slice 10 adds a THIRD gate: `capture_progress_recording_enabled=True`
requires `run_witness_recording_enabled=True`, checked ahead of (and
independent of) the first gate's own prerequisites.

Slice 12 adds a FOURTH gate, same shape: `capture_baseline_recording_enabled=True`
requires `run_witness_recording_enabled=True`.

Slice 13 adds a FIFTH gate, same shape: `capture_path_recording_enabled=True`
requires `run_witness_recording_enabled=True`.

Slice 14a adds a SIXTH gate, same shape:
`capture_experiment_identity_recording_enabled=True` requires
`run_witness_recording_enabled=True`.

Slice 16 adds a SEVENTH gate, a DIFFERENT shape from the four above:
`capture_probe_recording_enabled=True` requires `run_witness_enabled=True`
only, NOT `run_witness_recording_enabled` -- the capture-probe trail
scopes on `capture_code`, not a promoted Run, so its value is realized
specifically while recording is off. See `Settings.capture_probe_recording_enabled`'s
own docstring for the full argument.

Slice 17 adds an EIGHTH gate, same shape as the four `run_witness_recording_enabled`
gates but keyed on a DIFFERENT prerequisite: `capture_scan_ingestor_enabled=True`
requires `capture_path_recording_enabled=True` -- the sweep's only
candidate signal is a resolved `run_capture_path` row, so with path
recording off no run ever becomes a candidate.

The durable-distribution sweep adds a NINTH gate, keyed on FOUR
prerequisites: `durable_distribution_sweep_enabled=True` requires
`capture_path_recording_enabled=True` (same reasoning as the eighth
gate); `scan_probe_remote_host` to be set (`SshLocateProbe` is the only
`LocateProbe` this codebase ships, so with no remote host there is no
way to find a durable copy at all); at least one location marked
durable across `capture_scan_ingestor_bindings`; and every durable root
present in `scan_probe_allowed_roots` SPECIFICALLY -- not merely the
union with `posix_checksum_roots` that `CaptureScanIngestorBinding`'s
own validator checks, which would let a durable root reachable only by
the local pair pass boot and then make every `SshLocateProbe` call
refuse.

The orchestrator-ref join adds a TENTH gate, same shape as the four
`run_witness_recording_enabled` gates: `capture_orchestrator_ref_recording_enabled=True`
requires `run_witness_recording_enabled=True` -- the attachment happens
at promotion (a second `external_refs` entry on the genesis), so with
no promoted Run there is no genesis to attach it to.
"""

from uuid import UUID, uuid4

import pytest

from cora.api.main import _enforce_run_witness_recording_gate
from cora.infrastructure.capture_scan_ingestor_binding import (
    CaptureScanIngestorBinding,
    CaptureScanIngestorLocation,
)
from cora.infrastructure.config import Settings

_ACQUISITION_ROOT = "/local1/2BM"
_DURABLE_ROOT = "/gdata/dm/2BM"


def _durable_bindings(
    *, durable_root: str = _DURABLE_ROOT
) -> dict[str, CaptureScanIngestorBinding]:
    return {
        "2bmb-tomoscan": CaptureScanIngestorBinding(
            producing_asset_id=uuid4(),
            locations={
                _ACQUISITION_ROOT: CaptureScanIngestorLocation(
                    supply_id=uuid4(), access_protocol="POSIX"
                ),
                durable_root: CaptureScanIngestorLocation(
                    supply_id=uuid4(), access_protocol="NFS", durable=True
                ),
            },
        )
    }


def _settings(
    *,
    run_witness_enabled: bool = False,
    capture_watch_plan_id: UUID | None = None,
    run_witness_recording_enabled: bool = False,
    capture_progress_recording_enabled: bool = False,
    capture_baseline_recording_enabled: bool = False,
    capture_path_recording_enabled: bool = False,
    capture_experiment_identity_recording_enabled: bool = False,
    capture_probe_recording_enabled: bool = False,
    capture_orchestrator_ref_recording_enabled: bool = False,
    capture_scan_ingestor_enabled: bool = False,
    durable_distribution_sweep_enabled: bool = False,
    capture_scan_ingestor_bindings: dict[str, CaptureScanIngestorBinding] | None = None,
    posix_checksum_roots: tuple[str, ...] = (),
    scan_probe_allowed_roots: tuple[str, ...] = (),
    scan_probe_remote_host: str | None = None,
    scan_probe_remote_python: str | None = None,
) -> Settings:
    return Settings(  # type: ignore[call-arg]
        run_witness_enabled=run_witness_enabled,
        capture_watch_plan_id=capture_watch_plan_id,
        run_witness_recording_enabled=run_witness_recording_enabled,
        capture_progress_recording_enabled=capture_progress_recording_enabled,
        capture_baseline_recording_enabled=capture_baseline_recording_enabled,
        capture_path_recording_enabled=capture_path_recording_enabled,
        capture_experiment_identity_recording_enabled=(
            capture_experiment_identity_recording_enabled
        ),
        capture_probe_recording_enabled=capture_probe_recording_enabled,
        capture_orchestrator_ref_recording_enabled=capture_orchestrator_ref_recording_enabled,
        capture_scan_ingestor_enabled=capture_scan_ingestor_enabled,
        durable_distribution_sweep_enabled=durable_distribution_sweep_enabled,
        capture_scan_ingestor_bindings=capture_scan_ingestor_bindings or {},
        posix_checksum_roots=posix_checksum_roots,
        scan_probe_allowed_roots=scan_probe_allowed_roots,
        scan_probe_remote_host=scan_probe_remote_host,
        scan_probe_remote_python=scan_probe_remote_python,
    )


def test_recording_disabled_is_always_a_no_op() -> None:
    for run_witness_enabled in (True, False):
        for capture_watch_plan_id in (None, uuid4()):
            _enforce_run_witness_recording_gate(
                _settings(
                    run_witness_enabled=run_witness_enabled,
                    capture_watch_plan_id=capture_watch_plan_id,
                    run_witness_recording_enabled=False,
                )
            )


def test_recording_enabled_without_witness_enabled_refuses_boot() -> None:
    with pytest.raises(RuntimeError, match="RUN_WITNESS_ENABLED=true"):
        _enforce_run_witness_recording_gate(
            _settings(
                run_witness_enabled=False,
                capture_watch_plan_id=uuid4(),
                run_witness_recording_enabled=True,
            )
        )


def test_recording_enabled_without_plan_id_refuses_boot() -> None:
    with pytest.raises(RuntimeError, match="CAPTURE_WATCH_PLAN_ID"):
        _enforce_run_witness_recording_gate(
            _settings(
                run_witness_enabled=True,
                capture_watch_plan_id=None,
                run_witness_recording_enabled=True,
            )
        )


def test_recording_enabled_missing_both_refuses_boot_naming_both_vars() -> None:
    with pytest.raises(RuntimeError) as exc:
        _enforce_run_witness_recording_gate(
            _settings(
                run_witness_enabled=False,
                capture_watch_plan_id=None,
                run_witness_recording_enabled=True,
            )
        )
    message = str(exc.value)
    assert "RUN_WITNESS_ENABLED=true" in message
    assert "CAPTURE_WATCH_PLAN_ID" in message


def test_recording_enabled_with_both_prerequisites_passes() -> None:
    _enforce_run_witness_recording_gate(
        _settings(
            run_witness_enabled=True,
            capture_watch_plan_id=uuid4(),
            run_witness_recording_enabled=True,
        )
    )


def test_progress_recording_enabled_without_run_witness_recording_refuses_boot() -> None:
    with pytest.raises(RuntimeError, match="RUN_WITNESS_RECORDING_ENABLED=true"):
        _enforce_run_witness_recording_gate(
            _settings(
                run_witness_enabled=True,
                capture_watch_plan_id=uuid4(),
                run_witness_recording_enabled=False,
                capture_progress_recording_enabled=True,
            )
        )


def test_progress_recording_enabled_checked_before_the_first_gates_prerequisites() -> None:
    """The third gate's own message must appear even when the FIRST
    gate's prerequisites are also missing: the two checks are
    independent, not layered."""
    with pytest.raises(RuntimeError, match="RUN_WITNESS_RECORDING_ENABLED=true"):
        _enforce_run_witness_recording_gate(
            _settings(
                run_witness_enabled=False,
                capture_watch_plan_id=None,
                run_witness_recording_enabled=False,
                capture_progress_recording_enabled=True,
            )
        )


def test_progress_recording_enabled_with_run_witness_recording_passes() -> None:
    _enforce_run_witness_recording_gate(
        _settings(
            run_witness_enabled=True,
            capture_watch_plan_id=uuid4(),
            run_witness_recording_enabled=True,
            capture_progress_recording_enabled=True,
        )
    )


def test_baseline_recording_enabled_without_run_witness_recording_refuses_boot() -> None:
    with pytest.raises(RuntimeError, match="RUN_WITNESS_RECORDING_ENABLED=true"):
        _enforce_run_witness_recording_gate(
            _settings(
                run_witness_enabled=True,
                capture_watch_plan_id=uuid4(),
                run_witness_recording_enabled=False,
                capture_baseline_recording_enabled=True,
            )
        )


def test_baseline_recording_enabled_checked_before_the_first_gates_prerequisites() -> None:
    """Same independence property as the progress gate: the baseline
    gate's own message must appear even when the FIRST gate's
    prerequisites are also missing."""
    with pytest.raises(RuntimeError, match="RUN_WITNESS_RECORDING_ENABLED=true"):
        _enforce_run_witness_recording_gate(
            _settings(
                run_witness_enabled=False,
                capture_watch_plan_id=None,
                run_witness_recording_enabled=False,
                capture_baseline_recording_enabled=True,
            )
        )


def test_baseline_recording_enabled_with_run_witness_recording_passes() -> None:
    _enforce_run_witness_recording_gate(
        _settings(
            run_witness_enabled=True,
            capture_watch_plan_id=uuid4(),
            run_witness_recording_enabled=True,
            capture_baseline_recording_enabled=True,
        )
    )


def test_path_recording_enabled_without_run_witness_recording_refuses_boot() -> None:
    with pytest.raises(RuntimeError, match="RUN_WITNESS_RECORDING_ENABLED=true"):
        _enforce_run_witness_recording_gate(
            _settings(
                run_witness_enabled=True,
                capture_watch_plan_id=uuid4(),
                run_witness_recording_enabled=False,
                capture_path_recording_enabled=True,
            )
        )


def test_path_recording_enabled_checked_before_the_first_gates_prerequisites() -> None:
    """Same independence property as the progress / baseline gates: the
    path gate's own message must appear even when the FIRST gate's
    prerequisites are also missing."""
    with pytest.raises(RuntimeError, match="RUN_WITNESS_RECORDING_ENABLED=true"):
        _enforce_run_witness_recording_gate(
            _settings(
                run_witness_enabled=False,
                capture_watch_plan_id=None,
                run_witness_recording_enabled=False,
                capture_path_recording_enabled=True,
            )
        )


def test_path_recording_enabled_with_run_witness_recording_passes() -> None:
    _enforce_run_witness_recording_gate(
        _settings(
            run_witness_enabled=True,
            capture_watch_plan_id=uuid4(),
            run_witness_recording_enabled=True,
            capture_path_recording_enabled=True,
        )
    )


def test_experiment_identity_recording_enabled_without_run_witness_recording_refuses_boot() -> None:
    with pytest.raises(RuntimeError, match="RUN_WITNESS_RECORDING_ENABLED=true"):
        _enforce_run_witness_recording_gate(
            _settings(
                run_witness_enabled=True,
                capture_watch_plan_id=uuid4(),
                run_witness_recording_enabled=False,
                capture_experiment_identity_recording_enabled=True,
            )
        )


def test_experiment_identity_recording_enabled_checked_before_the_first_gates_prerequisites() -> (
    None
):
    """Same independence property as the progress / baseline / path
    gates: this gate's own message must appear even when the FIRST
    gate's prerequisites are also missing."""
    with pytest.raises(RuntimeError, match="RUN_WITNESS_RECORDING_ENABLED=true"):
        _enforce_run_witness_recording_gate(
            _settings(
                run_witness_enabled=False,
                capture_watch_plan_id=None,
                run_witness_recording_enabled=False,
                capture_experiment_identity_recording_enabled=True,
            )
        )


def test_experiment_identity_recording_enabled_with_run_witness_recording_passes() -> None:
    _enforce_run_witness_recording_gate(
        _settings(
            run_witness_enabled=True,
            capture_watch_plan_id=uuid4(),
            run_witness_recording_enabled=True,
            capture_experiment_identity_recording_enabled=True,
        )
    )


def test_orchestrator_ref_recording_enabled_without_run_witness_recording_refuses_boot() -> None:
    with pytest.raises(RuntimeError, match="RUN_WITNESS_RECORDING_ENABLED=true"):
        _enforce_run_witness_recording_gate(
            _settings(
                run_witness_enabled=True,
                capture_watch_plan_id=uuid4(),
                run_witness_recording_enabled=False,
                capture_orchestrator_ref_recording_enabled=True,
            )
        )


def test_orchestrator_ref_recording_enabled_checked_before_the_first_gates_prerequisites() -> None:
    """Same independence property as the progress / baseline / path /
    experiment-identity gates: this gate's own message must appear even
    when the FIRST gate's prerequisites are also missing."""
    with pytest.raises(RuntimeError, match="RUN_WITNESS_RECORDING_ENABLED=true"):
        _enforce_run_witness_recording_gate(
            _settings(
                run_witness_enabled=False,
                capture_watch_plan_id=None,
                run_witness_recording_enabled=False,
                capture_orchestrator_ref_recording_enabled=True,
            )
        )


def test_orchestrator_ref_recording_enabled_with_run_witness_recording_passes() -> None:
    _enforce_run_witness_recording_gate(
        _settings(
            run_witness_enabled=True,
            capture_watch_plan_id=uuid4(),
            run_witness_recording_enabled=True,
            capture_orchestrator_ref_recording_enabled=True,
        )
    )


def test_capture_probe_recording_enabled_without_run_witness_enabled_refuses_boot() -> None:
    with pytest.raises(RuntimeError, match="RUN_WITNESS_ENABLED=true"):
        _enforce_run_witness_recording_gate(
            _settings(
                run_witness_enabled=False,
                run_witness_recording_enabled=False,
                capture_probe_recording_enabled=True,
            )
        )


def test_capture_probe_recording_enabled_does_not_require_run_witness_recording() -> None:
    """The point of the seventh gate's divergence: recording stays OFF,
    no Plan is configured, and the boot still passes -- as long as the
    shadow observer runs. This is the live 2-BM state this slice exists
    for (three days of a dead IOC, run_witness_enabled=True, recording
    still off)."""
    _enforce_run_witness_recording_gate(
        _settings(
            run_witness_enabled=True,
            capture_watch_plan_id=None,
            run_witness_recording_enabled=False,
            capture_probe_recording_enabled=True,
        )
    )


def test_capture_scan_ingestor_enabled_without_path_recording_refuses_boot() -> None:
    with pytest.raises(RuntimeError, match="CAPTURE_PATH_RECORDING_ENABLED=true"):
        _enforce_run_witness_recording_gate(
            _settings(
                capture_path_recording_enabled=False,
                capture_scan_ingestor_enabled=True,
            )
        )


def test_capture_scan_ingestor_enabled_with_path_recording_passes() -> None:
    """The eighth gate's own prerequisite only; it does not additionally
    require `run_witness_recording_enabled` (implied by
    `capture_path_recording_enabled` already requiring it)."""
    _enforce_run_witness_recording_gate(
        _settings(
            run_witness_enabled=True,
            capture_watch_plan_id=uuid4(),
            run_witness_recording_enabled=True,
            capture_path_recording_enabled=True,
            capture_scan_ingestor_enabled=True,
        )
    )


def test_durable_distribution_sweep_enabled_without_path_recording_refuses_boot() -> None:
    with pytest.raises(RuntimeError, match="CAPTURE_PATH_RECORDING_ENABLED=true"):
        _enforce_run_witness_recording_gate(
            _settings(
                capture_path_recording_enabled=False,
                durable_distribution_sweep_enabled=True,
                capture_scan_ingestor_bindings=_durable_bindings(),
                scan_probe_allowed_roots=(_ACQUISITION_ROOT, _DURABLE_ROOT),
            )
        )


def test_durable_distribution_sweep_enabled_without_remote_host_refuses_boot() -> None:
    """`SshLocateProbe` is the only `LocateProbe` this codebase ships;
    with no remote host there is no way to find a durable copy at all,
    regardless of how the roots are configured."""
    with pytest.raises(RuntimeError, match="SCAN_PROBE_REMOTE_HOST"):
        _enforce_run_witness_recording_gate(
            _settings(
                run_witness_enabled=True,
                capture_watch_plan_id=uuid4(),
                run_witness_recording_enabled=True,
                capture_path_recording_enabled=True,
                durable_distribution_sweep_enabled=True,
                capture_scan_ingestor_bindings=_durable_bindings(),
                scan_probe_allowed_roots=(_ACQUISITION_ROOT, _DURABLE_ROOT),
                scan_probe_remote_host=None,
            )
        )


def test_durable_distribution_sweep_enabled_without_any_durable_location_refuses_boot() -> None:
    """A binding may exist for scan ingest without any location marked
    durable yet; the sweep has nothing to find in that case."""
    non_durable_bindings = {
        "2bmb-tomoscan": CaptureScanIngestorBinding(
            producing_asset_id=uuid4(),
            locations={
                _ACQUISITION_ROOT: CaptureScanIngestorLocation(
                    supply_id=uuid4(), access_protocol="POSIX"
                )
            },
        )
    }
    with pytest.raises(RuntimeError, match="CAPTURE_SCAN_INGESTOR_BINDINGS"):
        _enforce_run_witness_recording_gate(
            _settings(
                run_witness_enabled=True,
                capture_watch_plan_id=uuid4(),
                run_witness_recording_enabled=True,
                capture_path_recording_enabled=True,
                durable_distribution_sweep_enabled=True,
                capture_scan_ingestor_bindings=non_durable_bindings,
                posix_checksum_roots=(_ACQUISITION_ROOT,),
                scan_probe_remote_host="tomdet",
                scan_probe_remote_python="/venv/bin/python3",
            )
        )


def test_durable_sweep_root_only_in_posix_checksum_roots_refuses_boot() -> None:
    """The trap this gate exists to catch: the durable root satisfies
    `CaptureScanIngestorBinding`'s own UNION validator (it is in
    `posix_checksum_roots`) but is absent from `scan_probe_allowed_roots`
    specifically, which is what `SshLocateProbe` actually checks against."""
    with pytest.raises(RuntimeError, match="SCAN_PROBE_ALLOWED_ROOTS"):
        _enforce_run_witness_recording_gate(
            _settings(
                run_witness_enabled=True,
                capture_watch_plan_id=uuid4(),
                run_witness_recording_enabled=True,
                capture_path_recording_enabled=True,
                durable_distribution_sweep_enabled=True,
                capture_scan_ingestor_bindings=_durable_bindings(),
                posix_checksum_roots=(_ACQUISITION_ROOT, _DURABLE_ROOT),
                scan_probe_allowed_roots=(),
                scan_probe_remote_host="tomdet",
                scan_probe_remote_python="/venv/bin/python3",
            )
        )


def test_durable_sweep_root_in_scan_probe_allowed_roots_passes() -> None:
    _enforce_run_witness_recording_gate(
        _settings(
            run_witness_enabled=True,
            capture_watch_plan_id=uuid4(),
            run_witness_recording_enabled=True,
            capture_path_recording_enabled=True,
            durable_distribution_sweep_enabled=True,
            capture_scan_ingestor_bindings=_durable_bindings(),
            scan_probe_allowed_roots=(_ACQUISITION_ROOT, _DURABLE_ROOT),
            scan_probe_remote_host="tomdet",
            scan_probe_remote_python="/venv/bin/python3",
        )
    )
