"""Unit tests for `build_compute_port` (the ComputePort factory).

Mirror of `test_control_port_config.py`'s substrate-selection coverage,
minus the route-table cases (ComputePort has no registry yet).
"""

import pytest

from cora.operation.adapters.compute_port_config import ComputePortConfig, build_compute_port
from cora.operation.adapters.in_memory_compute_port import InMemoryComputePort
from cora.operation.adapters.local_process_compute_port import LocalProcessComputePort
from cora.operation.ports.compute_port import (
    ComputeExecutableNotPermittedError,
    ComputePort,
    ComputeSubmitRejectedError,
    JobSpec,
)


@pytest.mark.unit
def test_no_config_builds_the_in_memory_fake() -> None:
    port = build_compute_port()
    assert isinstance(port, InMemoryComputePort)
    assert isinstance(port, ComputePort)


@pytest.mark.unit
def test_in_memory_substrate_builds_the_fake() -> None:
    port = build_compute_port(ComputePortConfig(substrate="in_memory"))
    assert isinstance(port, InMemoryComputePort)


@pytest.mark.unit
def test_local_process_substrate_builds_the_subprocess_adapter() -> None:
    port = build_compute_port(ComputePortConfig(substrate="local_process", default_timeout_s=42.0))
    assert isinstance(port, LocalProcessComputePort)
    assert isinstance(port, ComputePort)


@pytest.mark.unit
def test_permitted_executables_default_to_empty() -> None:
    """Fail closed: a config that never mentions executables permits none."""
    assert ComputePortConfig().permitted_executables == frozenset()


@pytest.mark.unit
async def test_local_process_substrate_threads_the_allowlist_to_the_adapter() -> None:
    """The declared fact must survive wiring, or the gate is decorative."""
    port = build_compute_port(
        ComputePortConfig(
            substrate="local_process",
            permitted_executables=frozenset({"/opt/tomopy"}),
        )
    )
    with pytest.raises(ComputeExecutableNotPermittedError):
        await port.submit(JobSpec(command=("/usr/bin/whoami",)))


@pytest.mark.unit
async def test_local_process_substrate_with_no_declared_allowlist_runs_nothing() -> None:
    """Selecting the substrate without declaring an executable must not run one."""
    port = build_compute_port(ComputePortConfig(substrate="local_process"))
    with pytest.raises(ComputeExecutableNotPermittedError):
        await port.submit(JobSpec(command=("/bin/sh", "-c", "true")))


@pytest.mark.unit
def test_executable_not_permitted_is_a_submit_rejected_subclass() -> None:
    """Load-bearing: subclassing reaches the runtime's closed catch tuples.

    The Conductor's `_COMPUTE_ERRORS` and the EdgeConductor's inline
    tuple both name only the parent. `except` catches subclasses, so this
    relationship is what keeps an allowlist refusal a recorded step
    failure instead of an exception that strands the Procedure in
    Running. A sibling class would need hand-threading into both.
    """
    assert issubclass(ComputeExecutableNotPermittedError, ComputeSubmitRejectedError)
    error = ComputeExecutableNotPermittedError("/bin/sh")
    assert error.executable == "/bin/sh"
    assert "allowlist" in str(error)
