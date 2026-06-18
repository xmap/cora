"""Timing box registration at APS 2-BM (the trigger-source foundation).

cluster: Commissioning
archetype: setup
bc_primary: Equipment
bc_touches: Equipment

Registers the 2-BM softGlueZynq timing box as a CORA Asset so its identity
and gateware version become reproducibility provenance a Run can answer
against ("did the trigger logic change between Run X and Run Y").

The timing box is the first `TimingController` Asset at 2-BM. Unlike a
`MotionController`, it is itself the actor: it generates the camera trigger
pulse train, so the `Pulsing` affordance is its own (carried via the
`Controller` Role), not a driven device's. Being a controller, it carries
no `controller_id` back-reference, exactly as `FrontEndDrive` does in
test_2bm_front_end_optics_setup.py. The durable trigger wiring (the box's
output ports and the Plan wires that route them to the camera and the
NV200D piezo) is modeled in test_2bm_trigger_wiring.py; only the per-scan
routing values (the MUX2-1 select, the trigILF pulse subset, the GateDly
width / delay) stay Plan / Method configuration. This slice registers the
box's identity only.

## Asset stack

```
2-BM (Unit)
+-- Timing (Device)   Family: TimingController   softGlueZynq trigger box (2bmbMZ1:SG:)
```
"""

# pyright: reportUnknownMemberType=false, reportUnknownVariableType=false, reportUnknownArgumentType=false

from datetime import UTC, datetime
from uuid import UUID, uuid4

import asyncpg
import pytest

from cora.equipment.aggregates.family import FamilyName, family_stream_id
from tests.integration._helpers import build_postgres_deps, make_pg_profile_store
from tests.integration.scenarios._facility_fixture import (
    DeviceSpec,
    facility_id_prefix,
    install_aps_unit,
    operator_for,
)

_NOW = datetime(2026, 6, 16, 12, 0, 0, tzinfo=UTC)
_PRINCIPAL_ID = operator_for(__file__)
_CORRELATION_ID = UUID("01900000-0000-7000-8000-000000490cc1")

# Scenario tag: 490 (timing box registration).

_2BM_UNIT_ID = UUID("01900000-0000-7000-8000-000000490a01")

# TimingController is the second <Domain>Controller leaf after
# MotionController; the install defines it (empty affordances in the
# fixture; the real Pulsing affordance lives in the catalog seed).
_CAP_TIMING_CONTROLLER_ID = family_stream_id(FamilyName("TimingController"))

_TIMING_ID = UUID("01900000-0000-7000-8000-000000490a11")

# The timing box is a controller, so it carries no controller_id (no
# sibling drives it). This mirrors how FrontEndDrive registers.
_DEVICES = (DeviceSpec("Timing", _TIMING_ID, "TimingController", _CAP_TIMING_CONTROLLER_ID),)


def _id_queue() -> list[UUID]:
    """FixedIdGenerator queue: the facility prefix (which covers the install
    of the timing box + its Family) plus a small slack tail."""
    return [
        *facility_id_prefix(unit_id=_2BM_UNIT_ID, devices=_DEVICES),
        *[uuid4() for _ in range(10)],
    ]


@pytest.mark.integration
async def test_timing_box_registers_as_a_controller_without_controller_id(
    db_pool: asyncpg.Pool,
) -> None:
    """Register the softGlueZynq timing box as a TimingController Asset.
    Assert its genesis + Family, that it carries no controller_id (it is
    itself the actor, not a driven device), and that the TimingController
    Family was defined by the install ceremony."""
    deps = build_postgres_deps(db_pool, now=_NOW, ids=_id_queue())

    await install_aps_unit(
        deps,
        profile_store=make_pg_profile_store(db_pool),
        correlation_id=_CORRELATION_ID,
        unit_id=_2BM_UNIT_ID,
        devices=_DEVICES,
    )

    # ----- Timing: genesis + Family, parented to the Unit, no controller_id. -----
    events, _ = await deps.event_store.load("Asset", _TIMING_ID)
    assert [e.event_type for e in events] == [
        "AssetRegistered",
        "AssetFamilyAdded",
    ], f"Timing: unexpected event sequence {[e.event_type for e in events]}"
    genesis = events[0].payload
    assert genesis["parent_id"] == str(_2BM_UNIT_ID), "Timing: expected Unit parent"
    assert "controller_id" not in genesis, (
        "Timing: a TimingController is itself the actor and carries no controller_id"
    )
    assert events[1].payload["family_id"] == str(_CAP_TIMING_CONTROLLER_ID), (
        "Timing: wrong Family bound"
    )

    # ----- The TimingController Family was defined by the install ceremony. -----
    fam_events, _ = await deps.event_store.load("Family", _CAP_TIMING_CONTROLLER_ID)
    assert [e.event_type for e in fam_events] == ["FamilyDefined"], (
        "TimingController: expected a single FamilyDefined"
    )
