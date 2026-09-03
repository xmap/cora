"""The set of Agents CORA ships with itself.

Every deployment gets these twenty-four at boot, seeded by the
`seed_*_agent` functions. Until this file existed the set existed only
as sequential calls in `cora.api.main`, which was enough to create them
and not enough to ask a question ABOUT them.

Four of the twenty-four are two "kind, split by which brain serves it"
pairs: `RunDebriefer`/`RunDebriefer (External)` and
`CautionDrafter`/`CautionDrafter (External)`. The bare name is the
local/in-house arm, `(External)` marks the vendor-API arm; both members
of a pair share `kind` and coexist `Versioned` (per
`aggregates/agent/state.py`'s "Multiple Versioned Agents may exist
concurrently... different `id`s sharing `kind`"). The two original
singletons (`RUN_DEBRIEFER_AGENT_ID`/`CAUTION_DRAFTER_AGENT_ID`, from
`seed.py`/`seed_caution_drafter.py`) stay in this tuple unchanged: they
are no longer the compile-time default (see `_subscribers.py`), but
per-id FOREVER-STABLE means they are retired via `deprecate_agent` on a
deployment, never removed from source.

One further identity, `RunWitness`, was renamed outright to
`RunTranslator` (`seed_run_translator.py`): not a split, a straight
rename, since `witness` named the modeling axis this runtime implements
rather than what it does. `RUN_WITNESS_AGENT_ID` (from `seed_run_witness.py`)
stays in this tuple unchanged for the same FOREVER-STABLE reason as the
pair above.

The question that needed asking: which of these can actually act? A
seeded Agent lands `Versioned` on a fresh bootstrap, but a deployment
seeded before that change carries a fleet stuck at `Defined`, and the
subscribers refuse anything less than `Versioned` without saying so. The
operator remedy is one gesture over the whole fleet, and a gesture over
a fleet needs the fleet to be a value rather than a control flow.

## Why a hand-written tuple, and why the fitness test is the real work

Nothing here derives the list, so nothing here stops the next
agent from being added without an entry. That silent-incompleteness
shape is precisely what stranded the fleet in the first place: a set
that looks complete, reports nothing, and is quietly missing a member.

`tests/architecture/test_seeded_fleet_completeness.py` closes it by
scanning the seed modules for `*_AGENT_ID` constants and refusing any
that this tuple does not carry. Adding an agent without registering it
here fails that test, which is the only reason this file can be trusted.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING, Final

from cora.agent.seed import RUN_DEBRIEFER_AGENT_ID, RUN_DEBRIEFER_AGENT_NAME
from cora.agent.seed_authority_revocation_holder import (
    AUTHORITY_REVOCATION_HOLDER_AGENT_ID,
    AUTHORITY_REVOCATION_HOLDER_AGENT_NAME,
)
from cora.agent.seed_calibration_watcher import (
    CALIBRATION_WATCHER_AGENT_ID,
    CALIBRATION_WATCHER_AGENT_NAME,
)
from cora.agent.seed_campaign_watcher import (
    CAMPAIGN_WATCHER_AGENT_ID,
    CAMPAIGN_WATCHER_AGENT_NAME,
)
from cora.agent.seed_capture_baseline_reader import (
    CAPTURE_BASELINE_READER_AGENT_ID,
    CAPTURE_BASELINE_READER_AGENT_NAME,
)
from cora.agent.seed_capture_progress_feeder import (
    CAPTURE_PROGRESS_FEEDER_AGENT_ID,
    CAPTURE_PROGRESS_FEEDER_AGENT_NAME,
)
from cora.agent.seed_capture_scan_ingestor import (
    CAPTURE_SCAN_INGESTOR_AGENT_ID,
    CAPTURE_SCAN_INGESTOR_AGENT_NAME,
)
from cora.agent.seed_caution_drafter import (
    CAUTION_DRAFTER_AGENT_ID,
    CAUTION_DRAFTER_AGENT_NAME,
)
from cora.agent.seed_caution_drafter_external import (
    CAUTION_DRAFTER_EXTERNAL_AGENT_ID,
    CAUTION_DRAFTER_EXTERNAL_AGENT_NAME,
)
from cora.agent.seed_caution_drafter_local import (
    CAUTION_DRAFTER_LOCAL_AGENT_ID,
    CAUTION_DRAFTER_LOCAL_AGENT_NAME,
)
from cora.agent.seed_caution_promoter import (
    CAUTION_PROMOTER_AGENT_ID,
    CAUTION_PROMOTER_AGENT_NAME,
)
from cora.agent.seed_clearance_expirer import (
    CLEARANCE_EXPIRER_AGENT_ID,
    CLEARANCE_EXPIRER_AGENT_NAME,
)
from cora.agent.seed_clearance_watcher import (
    CLEARANCE_WATCHER_AGENT_ID,
    CLEARANCE_WATCHER_AGENT_NAME,
)
from cora.agent.seed_durable_copy_registrar import (
    DURABLE_COPY_REGISTRAR_AGENT_ID,
    DURABLE_COPY_REGISTRAR_AGENT_NAME,
)
from cora.agent.seed_experiment_steerer import (
    EXPERIMENT_STEERER_AGENT_ID,
    EXPERIMENT_STEERER_AGENT_NAME,
)
from cora.agent.seed_procedure_watcher import (
    PROCEDURE_WATCHER_AGENT_ID,
    PROCEDURE_WATCHER_AGENT_NAME,
)
from cora.agent.seed_ratification_enforcer import (
    RATIFICATION_ENFORCER_AGENT_ID,
    RATIFICATION_ENFORCER_AGENT_NAME,
)
from cora.agent.seed_run_debriefer_external import (
    RUN_DEBRIEFER_EXTERNAL_AGENT_ID,
    RUN_DEBRIEFER_EXTERNAL_AGENT_NAME,
)
from cora.agent.seed_run_debriefer_local import (
    RUN_DEBRIEFER_LOCAL_AGENT_ID,
    RUN_DEBRIEFER_LOCAL_AGENT_NAME,
)
from cora.agent.seed_run_initiator import (
    RUN_INITIATOR_AGENT_ID,
    RUN_INITIATOR_AGENT_NAME,
)
from cora.agent.seed_run_supervisor import (
    RUN_SUPERVISOR_AGENT_ID,
    RUN_SUPERVISOR_AGENT_NAME,
)
from cora.agent.seed_run_translator import (
    RUN_TRANSLATOR_AGENT_ID,
    RUN_TRANSLATOR_AGENT_NAME,
)
from cora.agent.seed_run_witness import (
    RUN_WITNESS_AGENT_ID,
    RUN_WITNESS_AGENT_NAME,
)
from cora.agent.seed_status_publisher import (
    STATUS_PUBLISHER_AGENT_ID,
    STATUS_PUBLISHER_AGENT_NAME,
)

if TYPE_CHECKING:
    from uuid import UUID


@dataclass(frozen=True)
class SeededAgent:
    """One member of the shipped fleet: its stable id and its name."""

    agent_id: UUID
    name: str


SEEDED_FLEET: Final[tuple[SeededAgent, ...]] = (
    SeededAgent(AUTHORITY_REVOCATION_HOLDER_AGENT_ID, AUTHORITY_REVOCATION_HOLDER_AGENT_NAME),
    SeededAgent(CALIBRATION_WATCHER_AGENT_ID, CALIBRATION_WATCHER_AGENT_NAME),
    SeededAgent(CAMPAIGN_WATCHER_AGENT_ID, CAMPAIGN_WATCHER_AGENT_NAME),
    SeededAgent(CAPTURE_BASELINE_READER_AGENT_ID, CAPTURE_BASELINE_READER_AGENT_NAME),
    SeededAgent(CAPTURE_PROGRESS_FEEDER_AGENT_ID, CAPTURE_PROGRESS_FEEDER_AGENT_NAME),
    SeededAgent(CAPTURE_SCAN_INGESTOR_AGENT_ID, CAPTURE_SCAN_INGESTOR_AGENT_NAME),
    SeededAgent(CAUTION_DRAFTER_AGENT_ID, CAUTION_DRAFTER_AGENT_NAME),
    SeededAgent(CAUTION_DRAFTER_EXTERNAL_AGENT_ID, CAUTION_DRAFTER_EXTERNAL_AGENT_NAME),
    SeededAgent(CAUTION_DRAFTER_LOCAL_AGENT_ID, CAUTION_DRAFTER_LOCAL_AGENT_NAME),
    SeededAgent(CAUTION_PROMOTER_AGENT_ID, CAUTION_PROMOTER_AGENT_NAME),
    SeededAgent(CLEARANCE_EXPIRER_AGENT_ID, CLEARANCE_EXPIRER_AGENT_NAME),
    SeededAgent(CLEARANCE_WATCHER_AGENT_ID, CLEARANCE_WATCHER_AGENT_NAME),
    SeededAgent(DURABLE_COPY_REGISTRAR_AGENT_ID, DURABLE_COPY_REGISTRAR_AGENT_NAME),
    SeededAgent(EXPERIMENT_STEERER_AGENT_ID, EXPERIMENT_STEERER_AGENT_NAME),
    SeededAgent(PROCEDURE_WATCHER_AGENT_ID, PROCEDURE_WATCHER_AGENT_NAME),
    SeededAgent(RATIFICATION_ENFORCER_AGENT_ID, RATIFICATION_ENFORCER_AGENT_NAME),
    SeededAgent(RUN_DEBRIEFER_AGENT_ID, RUN_DEBRIEFER_AGENT_NAME),
    SeededAgent(RUN_DEBRIEFER_EXTERNAL_AGENT_ID, RUN_DEBRIEFER_EXTERNAL_AGENT_NAME),
    SeededAgent(RUN_DEBRIEFER_LOCAL_AGENT_ID, RUN_DEBRIEFER_LOCAL_AGENT_NAME),
    SeededAgent(RUN_INITIATOR_AGENT_ID, RUN_INITIATOR_AGENT_NAME),
    SeededAgent(RUN_SUPERVISOR_AGENT_ID, RUN_SUPERVISOR_AGENT_NAME),
    SeededAgent(RUN_TRANSLATOR_AGENT_ID, RUN_TRANSLATOR_AGENT_NAME),
    SeededAgent(RUN_WITNESS_AGENT_ID, RUN_WITNESS_AGENT_NAME),
    SeededAgent(STATUS_PUBLISHER_AGENT_ID, STATUS_PUBLISHER_AGENT_NAME),
)


__all__ = ["SEEDED_FLEET", "SeededAgent"]
