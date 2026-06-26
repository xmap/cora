# Governance

*Who would act at i19 and the trust shape that would gate it. This is CORA's governance design landing on the beamline, not a description of the beamline's current controls authority. Not yet instantiated (scaffold).*

Governance at i19 follows the same model as the other Diamond beamlines: people and autonomous agents are facility principals at the [Diamond Site](../diamond/index.md#who-acts-here), and on the beamline they surface through the actions they take. Their commands are gated by a trust shape: a Zone grouping the beamline's resources, a Conduit binding the surfaces that may issue commands, and Policies that say who may do what. The human roster is not in the dodal module (GOV-1), so the principals below are the design shape, not a registered list.

Because i19 is a scaffold, the concrete trust shape is not instantiated. What is already settled is the boundary: clearances (the safety state that must be active to start) are issued at the Diamond Site, not on the beamline, and the beamline links up to them.

## Who acts

The Diamond operator pool runs an i19 beamtime, with a beamline scientist and a safety reviewer in the facility-wide review chain. These are the Diamond facility principals, carried pending at the [Diamond Site page](../diamond/index.md#who-acts-here); i19 inherits them rather than coining its own (GOV-1). The Diamond proposal and cycle are a fact CORA's Campaign uses for custody.

## The trust boundary

i19's boundary is shaped by the Trust BC aggregates (Zone, Conduit, Policy); the [Trust module](../../architecture/modules/trust/index.md) defines what each one is. This page records only the intended i19 instances, all pending until the beamline approaches real scope.

| Zone | Conduit | Endpoints |
| --- | --- | --- |
| `i19 Zone` | `i19 Local Conduit` | `i19 Zone` -> `i19 Zone` |

A Policy governs who may issue which command across a Conduit.

| Policy | Permitted principals | Permitted commands |
| --- | --- | --- |
| `i19 Operations Policy` | Diamond operator pool (GOV-1) | Operator-driven commands (Equipment, Recipe, Operation, Run, Subject, Dataset, Caution, Clearance, Supply, Campaign) |
| `i19 Agent Policy` | Diamond agent principals (GOV-1) | Decision family: `RegisterDecision`, `RateDecision`, `AppendInferences` |

## The safety envelope

i19 inherits the Diamond [safety envelope](../diamond/index.md#the-safety-envelope). The one safety signal CORA can name today is the dodal interlocked optics shutter (`OpticsShutter`, BL19I-PS-SHTR-01), which is PSS-interlocked and bound to the Shutter family. Beyond that, the PSS search-and-secure permit signals per hutch are pending and are not invented (PSS-1). Clearances are issued at the Diamond Site and the beamline links up to them.

## The active-hutch permit (ACCESS-1)

i19 has two experiment hutches in series, EH1 (`i19-1`) and EH2 (`i19-2`), that share one optics line (`i19-optics`, the shared BL19I optics). This is the i19-specific governance element, and it is the genuine novelty of the deployment: only the **active** hutch may drive the shared optics. A non-active hutch may still observe the shared optics state, but it may not move them.

dodal expresses this with a central arbiter, the i19-blueapi optics service. A hutch reads the shared-optics state directly over EPICS, but its writes (change the energy, operate the experiment shutter, move the attenuator, set a mirror piezo) are posted to the arbiter. The arbiter compares the requesting hutch against the active-hutch readback (BL19I-OP-STAT-01:EHStatus) and runs or rejects.

CORA models this as an **Enclosure-permit plus Trust-gate** over the shared-optics Assets, not as a device family (ACCESS-1):

- The Enclosure-permit is the active-hutch state itself: of the two Enclosures `i19-1` and `i19-2`, the one currently holding the permit is the only one whose commands against the shared `i19-optics` Assets may proceed (ENC-1).
- The Trust-gate is the Policy condition layered on the shared-optics commands: a command to change energy (`BeamEnergy`, the coordinated DCM plus undulator plus mirror-stripe move, MONO-1), operate the optics shutter (PSS-1), move the attenuator (`Attenuator`, the i03 precedent, ATTN-1), or set a focusing-mirror piezo (`HorizontalFocusingMirror` / `VerticalFocusingMirror`, with its hutch-keyed coating stripe Si 5-10 / Rh 10-20 / Pt 20-30 keV, OPT-1) is admitted only from the hutch that holds the permit.
- The i19-blueapi arbiter is the **actuate-floor seam** partner, the same "EPICS is the floor" pattern the rest of the Diamond fleet follows, here a blueapi-arbiter floor. CORA's gate decides whether the command is authorized; the arbiter remains the floor that compares the requesting hutch against the active-hutch readback and runs or rejects against EPICS.

The shared-optics devices are single Assets, access-gated rather than duplicated per hutch: the monochromator (DCM, MONO-1), the two focusing mirrors (OPT-1), the attenuator (ATTN-1), the coordinated `BeamEnergy` pseudo-axis (MONO-1), and the optics shutter (PSS-1) all live in `i19-optics` and are reached through the permit. The undulator (`Undulator`, SR19I-MO-SERVC-01) is coordinated with the DCM on an energy move (SRC-1); the storage ring is observe-only machine state (MACHINE-1).

None of this is instantiated yet. The Zone, Conduit, and Policy instances, the Diamond operator pool, and the active-hutch permit gate would land if the beamline approaches real scope, following the [2-BM governance](../2-bm/governance.md) shape.
