"""Unit tests for `build_compute_port` (the ComputePort factory).

Mirror of `test_control_port_config.py`'s substrate-selection coverage,
minus the route-table cases (ComputePort has no registry yet).
"""

import pytest

from cora.operation.adapters.compute_port_config import ComputePortConfig, build_compute_port
from cora.operation.adapters.in_memory_compute_port import InMemoryComputePort
from cora.operation.adapters.local_process_compute_port import LocalProcessComputePort
from cora.operation.ports.compute_port import ComputePort


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
