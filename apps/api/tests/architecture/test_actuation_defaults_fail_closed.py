"""The actuation defaults ship SAFE: a blank deployment cannot drive hardware.

CORA's observe-only pilot posture is not a mode an operator selects; it is
the DEFAULT. A `docker run` with only a database URL and a route table can
observe every configured PV and drive none. That property is the whole
adoption pitch ("install it, it cannot touch your hardware"), and it holds
only while all three actuation-relevant defaults stay on the safe side:

  - `control_writes_enabled` defaults False (the ControlPort write gate);
  - `compute_substrate` defaults `in_memory` (spawns no subprocess, so the
    ComputePort exec path cannot reach a control system);
  - `compute_permitted_executables` defaults empty (even if a deployment
    switches to `local_process`, an empty allowlist permits nothing).

A future edit that flips any of these defaults would silently widen every
observe-only deployment on the growth ladder at once, with zero test
failure, until a facility noticed CORA had moved something. This fitness
turns that into a build break.

## Why the DECLARED default, not an instantiated Settings

`tests/conftest.py` sets `CONTROL_WRITES_ENABLED=true` for the test
environment (observe-only is a production posture; the suite exercises the
full writable surface). So `Settings().control_writes_enabled` is True under
test and would tell us nothing about what ships. `model_fields[...].default`
reads the class's DECLARED default directly, immune to the environment, so
this asserts the property a real deployment gets, not the one the test env
overrides.
"""

import pytest

from cora.infrastructure.config import Settings


@pytest.mark.architecture
def test_control_writes_default_is_off() -> None:
    assert Settings.model_fields["control_writes_enabled"].default is False


@pytest.mark.architecture
def test_compute_substrate_default_is_in_memory() -> None:
    assert Settings.model_fields["compute_substrate"].default == "in_memory"


@pytest.mark.architecture
def test_compute_permitted_executables_default_is_empty() -> None:
    assert Settings.model_fields["compute_permitted_executables"].default == frozenset()
