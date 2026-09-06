"""The back-door grant table: which in-process principal needs which command.

CORA gates every command through the `Authorize` port. Two doors reach
it: the HTTP front door (people and external agents), and
`SYSTEM_IN_PROCESS_SURFACE_ID`, the back door CORA's own background
runtimes use to act on themselves. This table is the ground truth for
the back door: for every principal that issues a command through it,
the exact set of command names a `TrustAuthorize` Policy must grant that
principal so the runtime keeps working once a deployment leaves shadow
mode and starts enforcing a real Policy instead of `AllowAllAuthorize`.

## Inert by design

Nothing in the running app imports this module. It is consumed by two
things only:

  - `tests/architecture/test_hardcoded_command_lists_track_wire_surface.py`,
    which AST-parses (never imports) this file's `IN_PROCESS_GRANTS`
    literal and checks every granted command name against the real wire
    surface, the same way it already checks every other hand-typed
    command-name list in the repo.
  - `tools/gen_policy_grants.py`, which imports this table to emit the
    `POST /policies` request body an operator pipes into the API to
    seed the deployment's real back-door Policy.

Nothing here changes what any runtime does; changing this table has no
effect until an operator re-runs the generator and posts the result. A
future sweep (out of scope here) is what will make the ~35 in-process
call sites that still pass `NIL_SENTINEL_ID` for `surface_id` actually
land on this door; today the table already reflects the commands those
sites issue, so that sweep does not have to re-derive them.

## How every entry was derived

Not copied from a design memo: each entry comes from reading the
call site itself, for every principal drawn from two populations,
`grep -rl SYSTEM_IN_PROCESS_SURFACE_ID src/cora/` and
`grep -rl "surface_id=NIL_SENTINEL_ID" src/cora/`. Every command name
below is confirmed present in the real wire surface via
`grep -rn 'command_name=' src/cora/*/wire.py`.

## Deliberate omissions

  - `cora.agent.promote_seeded_fleet.promote_seeded_fleet`: rebinds the
    kernel through `AllowAllAuthorize` before calling `version_agent`
    (see that module's own docstring, "Bypasses the deployment's
    configured gate, on purpose"). It never consults a real Policy, so
    there is nothing for a Policy to grant it.
  - Eight synthetic Decision-envelope labels (`CampaignWatcherTick`,
    `ClearanceWatcherTick`, `ClearanceExpirerTick`, `ProcedureWatcherTick`,
    `CalibrationWatcherTick`, `ExperimentCoordinatorTurn`,
    `CautionPromoterSubscriber`, `AuthorityRevocationHolderSubscriber`):
    these are `command_name=` values written directly via
    `to_new_event(...)` + `event_store.append(...)`, audit labels on a
    Decision record, never arguments to `authorize()`. They carry no
    grant because there is no gate that checks one.

## Overridable principals

`RUN_DEBRIEFER_EXTERNAL_AGENT_ID` and `CAUTION_DRAFTER_EXTERNAL_AGENT_ID` are the default
principals only: `Settings.run_debriefer_agent_id` and
`Settings.caution_drafter_agent_id` let a deployment designate a
different Agent for either LLM subscriber. A deployment that overrides
either one must grant the designated Agent the same command below
instead (or in addition).

## Not currently wired

`SIM_OBSERVATION_FEEDER_AGENT_ID` (`cora.run.adapters.sim_observation_feeder`)
is not a member of `SEEDED_FLEET` and nothing in `cora.api.main`
instantiates it; it ships as an optional sim harness a deployment can
wire in. Its entry documents what that deployment would need to grant,
not a principal already active anywhere.
"""

from __future__ import annotations

from types import MappingProxyType
from typing import TYPE_CHECKING, Final

from cora.agent.seed_authority_revocation_holder import AUTHORITY_REVOCATION_HOLDER_AGENT_ID
from cora.agent.seed_calibration_watcher import CALIBRATION_WATCHER_AGENT_ID
from cora.agent.seed_campaign_watcher import CAMPAIGN_WATCHER_AGENT_ID
from cora.agent.seed_capture_baseline_reader import CAPTURE_BASELINE_READER_AGENT_ID
from cora.agent.seed_capture_progress_feeder import CAPTURE_PROGRESS_FEEDER_AGENT_ID
from cora.agent.seed_capture_scan_ingestor import CAPTURE_SCAN_INGESTOR_AGENT_ID
from cora.agent.seed_caution_drafter_external import CAUTION_DRAFTER_EXTERNAL_AGENT_ID
from cora.agent.seed_caution_promoter import CAUTION_PROMOTER_AGENT_ID
from cora.agent.seed_clearance_expirer import CLEARANCE_EXPIRER_AGENT_ID
from cora.agent.seed_clearance_watcher import CLEARANCE_WATCHER_AGENT_ID
from cora.agent.seed_durable_copy_registrar import DURABLE_COPY_REGISTRAR_AGENT_ID
from cora.agent.seed_experiment_coordinator import EXPERIMENT_COORDINATOR_AGENT_ID
from cora.agent.seed_procedure_watcher import PROCEDURE_WATCHER_AGENT_ID
from cora.agent.seed_ratification_enforcer import RATIFICATION_ENFORCER_AGENT_ID
from cora.agent.seed_run_debriefer_external import RUN_DEBRIEFER_EXTERNAL_AGENT_ID
from cora.agent.seed_run_initiator import RUN_INITIATOR_AGENT_ID
from cora.agent.seed_run_supervisor import RUN_SUPERVISOR_AGENT_ID
from cora.agent.seed_run_translator import RUN_TRANSLATOR_AGENT_ID
from cora.agent.seed_status_publisher import STATUS_PUBLISHER_AGENT_ID
from cora.run.adapters.sim_observation_feeder import SIM_OBSERVATION_FEEDER_AGENT_ID

if TYPE_CHECKING:
    from collections.abc import Mapping
    from uuid import UUID


IN_PROCESS_GRANTS: Final[Mapping[UUID, frozenset[str]]] = MappingProxyType(
    {
        AUTHORITY_REVOCATION_HOLDER_AGENT_ID: frozenset({"HoldRun"}),
        CALIBRATION_WATCHER_AGENT_ID: frozenset({"ListCalibrations"}),
        CAMPAIGN_WATCHER_AGENT_ID: frozenset({"ListCampaigns"}),
        CAPTURE_BASELINE_READER_AGENT_ID: frozenset({"AppendObservations"}),
        CAPTURE_PROGRESS_FEEDER_AGENT_ID: frozenset({"AppendObservations"}),
        CAPTURE_SCAN_INGESTOR_AGENT_ID: frozenset({"IngestScan"}),
        CAUTION_DRAFTER_EXTERNAL_AGENT_ID: frozenset({"AppendInferences"}),
        CAUTION_PROMOTER_AGENT_ID: frozenset({"PromoteCautionProposal"}),
        CLEARANCE_EXPIRER_AGENT_ID: frozenset({"ListClearances", "ExpireClearance"}),
        CLEARANCE_WATCHER_AGENT_ID: frozenset({"ListClearances", "GetClearance"}),
        DURABLE_COPY_REGISTRAR_AGENT_ID: frozenset({"RegisterDistribution"}),
        EXPERIMENT_COORDINATOR_AGENT_ID: frozenset({"HoldProcedure", "AppendInferences"}),
        PROCEDURE_WATCHER_AGENT_ID: frozenset({"ListProcedures"}),
        RATIFICATION_ENFORCER_AGENT_ID: frozenset({"HoldRun", "ResumeRun"}),
        RUN_DEBRIEFER_EXTERNAL_AGENT_ID: frozenset({"AppendInferences"}),
        RUN_INITIATOR_AGENT_ID: frozenset({"StartRun", "ListRuns", "ListSubjects"}),
        RUN_SUPERVISOR_AGENT_ID: frozenset(
            {"HoldRun", "ResumeRun", "TruncateRun", "AbortRun", "StopRun", "ListRuns"}
        ),
        RUN_TRANSLATOR_AGENT_ID: frozenset(
            {"RecordWitnessedRun", "TruncateRun", "RecordWitnessedRunOutcome", "ListRuns"}
        ),
        SIM_OBSERVATION_FEEDER_AGENT_ID: frozenset({"AppendObservations"}),
        STATUS_PUBLISHER_AGENT_ID: frozenset(
            {
                "ListPlans",
                "ListRuns",
                "GetRunHistory",
                "ListSubjects",
                "ListCampaigns",
                "ListDatasets",
                "ListProcedures",
                "ListClearances",
                "ListEnclosures",
                "GetEnclosureHistory",
                "ListDecisions",
            }
        ),
    }
)


__all__ = ["IN_PROCESS_GRANTS"]
