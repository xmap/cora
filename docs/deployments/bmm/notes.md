# Notes

## Techniques

*What CORA would run at BMM: X-ray absorption spectroscopy, bound through an NSLS-II [Practice](../nsls2/index.md#the-techniques-adapted-here). BMM raises the spectroscopy Capability question CORA has not yet had to answer.*

BMM does transmission and fluorescence XAS / EXAFS: sweep the beam energy across an element's absorption edge, record the per-energy detector readings, and fit the absorption spectrum downstream.

| BMM technique | CORA expression | Earn-the-abstraction call |
| --- | --- | --- |
| Transmission XAS / EXAFS | an energy sweep reading I0/It/Ir | the live question (ENERGY-1): coin `energy_scan`, or hold under `characterization`? |
| Fluorescence XAS | the same sweep reading the `EnergyDispersiveSpectrometer` | same Capability, different detector in the slot |
| Energy calibration | reference foil + `Ir` channel each scan | a Calibration, not a separate technique |
| Alignment | beam-finding and slit/mirror tuning | reuse [`alignment`](../../catalog/methods.md) |

### The energy_scan Capability question (ENERGY-1)

BMM is the first CORA deployment whose measurement *is* an energy scan. The catalog already anticipates this: alongside `cora.capability.energy_change` (a coordinated *setpoint* move to one energy), a note records `cora.capability.energy_scan` as **pending in code**, and describes energy_change as "distinct from a future energy_scan sweep." BMM is that future consumer.

Per the design-phase discipline (Diamond i03/i22, 32-ID, and HXN all coined no new Capability at scaffold time), this scaffold **defers** coining `energy_scan`: an XAS scan is mapped to `characterization` plus `energy_change` for now, and the Capability is coined when a conduct-path actually sweeps the energy. The argument to coin is strong (the sweep is the measurement, exactly the in-kind case), and the catalog already reserved the name; it is held open deliberately, not because it is weak, but because a Capability is coined when a conduct-path forces it, not at scaffold time.

EXAFS data reduction (background subtraction, normalization, the chi(k) transform) is a `ComputePort` leg, not a beamline Method, the same way tomographic and ptychographic reconstruction are.

## Governance

*Who may act at BMM and the trust shape CORA applies. This is CORA's governance design landing on the beamline, not a description of the beamline's current controls authority.*

People and agents are facility principals at the [NSLS-II Site](../nsls2/index.md#safety-and-governance); on the beamline they surface through the actions they take. The human roster is not known from the profile collection (GOV-1), so the principals are the design shape, not a registered list.

### Who acts

CORA brings its own Access model: a small set of facility roles (operator, beamline scientist, safety reviewer, and the autonomous-agent and service principals) scoped at the NSLS-II Site. A BMM beamtime is run by an operator or beamline scientist Actor; a safety reviewer holds the clearance authority.

### The trust boundary

CORA's Trust BC (Zone, Conduit, Policy) gates every command by who is acting and what the beamline state allows: who may start a scan, override a caution, or commit a calibration. This authority is CORA's own, expressed per Actor, not inherited from the beamline's controls layer. The NSLS-II proposal and cycle are a fact CORA's Campaign uses for custody.

### Batch automation and agents

BMM's batch XAS, a wheel of many samples scanned unattended, is a natural place for an autonomous Agent: choosing the next sample, deciding when a spectrum has enough signal-to-noise, flagging a bad scan. If such an agent were added, it would be a facility principal scoped at the Site, governed by the same trust boundary, and each decision (which sample, rescan-or-advance) would be a [Decision](../../architecture/modules/decision/index.md) recorded in the run provenance. None is declared for BMM yet; the unattended wheel loop is conducted, not agent-driven, in this scaffold.

## Model

*The developer's by-kind index: where each CORA aggregate's BMM content lives. It hosts no content of its own. Design-phase scaffold.*

For the aggregate shapes see the [architecture model](../../architecture/model.md) and the per-BC
[modules](../../architecture/modules/index.md).

| Aggregate (BC) | Where at BMM |
| --- | --- |
| Asset (Equipment) | the stage pages: [Source](source.md), [Sample](sample.md), [Detector](detector.md) |
| Computed / virtual axes (Equipment) | [Source](source.md) (EnergyAxis) |
| Capability, Method (Recipe) | [Techniques](#techniques) |
| Enclosure (Enclosure) | [The beamline](index.md#enclosures) (6-BM-A optics, 6-BM-B endstation) |
| Zone, Conduit, Policy (Trust); Actor (Access) | [Governance](#governance) |
| Procedure, Recipe, Caution, Supply, Subject, Run, Campaign, Dataset, Decision | deferred (design-phase; see below) |

### Deliberately not here yet

This is a design-phase scaffold (descriptor + docs), mirroring HXN and the Diamond beamlines. Left out on purpose:

- **The `energy_scan` Capability.** BMM is the first real consumer of the energy-scan sweep the catalog already anticipates (pending in code), but a Capability is coined when a conduct-path consumes it, not at scaffold time (see [Techniques](#techniques), ENERGY-1). This is the live earn-the-abstraction question BMM surfaces.
- **No new Family.** BMM reuses existing catalog Families: the ion chambers reuse `FluxMonitor` (graduated in #353), the fluorescence detector the catalog `EnergyDispersiveSpectrometer`, plus the catalog `Screen` Family (FLAG-1) for the diagnostic screens. The sample wheel reuses `RotaryStage`; whether a sample-changer Family is earned across BMM and the Diamond robots is open (WHEEL-1).
- **Operations and experiment views, integration scenarios, vendor Models.** A runbook and registered Assets for a beamline CORA does not yet drive would be invention; they land when the design firms and the team confirms.

## Open questions

*What CORA needs the BMM team to confirm. This model is reverse-engineered from public open source (the [`NSLS2/bmm-profile-collection`](https://github.com/NSLS2/bmm-profile-collection) profile collection): the EPICS PVs are read from it, but vendor identities, physical positions, and the detector configuration are not. Each row is a fact the beamline team owns. It is a delete-on-answer queue.*

Priorities: `Blocks-build` (changes the model structure), `Blocks-go-live` (needed before CORA controls or observes the hardware), `Nice-to-have`.

### Source and safety

| ID | Priority | Question | CORA assumes | Resolves |
| --- | --- | --- | --- | --- |
| SRC-1 | Nice-to-have | The 6-BM bending-magnet source parameters (critical energy, fan). The source is confirmed a bending magnet (`SR:C06`), not an insertion device. | A bending-magnet PhotonBeam Supply, identity-only. | The Source Supply settings. |
| PSS-1 | Blocks-go-live | The PSS search-and-secure permit-leaf PVs. Only the front-end and photon shutters (`XF:06BM-PPS{Sh:FE}`, `{Sh:A}`) are in source. | The permit signal is a confirm note, not a guessed PV. | The Enclosure permit signals. |
| ENC-1 | Nice-to-have | Is the endstation a distinct hutch (6-BM-B) from the optics hutch (6-BM-A)? | Two enclosures, optics + experiment. | The Enclosure set and roles. |

### Optics

| ID | Priority | Question | CORA assumes | Resolves |
| --- | --- | --- | --- | --- |
| DCM-1 | Nice-to-have | The DCM crystal sets available (Si(111) confirmed; a Si(311) set?) and the energy range. | Si(111), range blank. | The Monochromator settings. |
| OPTIC-1 | Nice-to-have | The mirror coatings / stripes on M1 and M2 (harmonic rejection). | Two mirrors, coatings blank. | The Mirror settings. |

### Sample and detectors

| ID | Priority | Question | CORA assumes | Resolves |
| --- | --- | --- | --- | --- |
| WHEEL-1 | Blocks-go-live | The sample wheel: how many sample positions, and is batch sample-changing a CORA-modelled automation or operator-driven? Should a dedicated sample-changer Family be earned across BMM and the Diamond robots, or does the wheel stay a `RotaryStage`? | A `RotaryStage` indexing samples; sample-changer behaviour is a Method/automation concern, not a new Family. | The sample-wheel model and the sample-changer abstraction. |
| DET-1 | Blocks-go-live | The fluorescence detector configuration: which Xspress3 element count (1, 4, or 7) is the installed/default, and the vendor (Quantum Detectors?). Source carries all three configurations. | One `EnergyDispersiveSpectrometer` Asset presenting the Sensor Role; element count blank. | The detector Model and element count. |
| DIAG-1 | Blocks-go-live | The ion chambers (`I0`/`It`/`Ir`) gas fill and the per-channel PV bindings. | The quad electrometer binds the catalog `FluxMonitor` Family (graduated in #353); gas fill and per-channel detail unconfirmed. | The I0/It/Ir bindings and gas fill. |

### Controls and techniques

| ID | Priority | Question | CORA assumes | Resolves |
| --- | --- | --- | --- | --- |
| DRIVE-1 | Blocks-go-live | The motion-controller box models, firmware, serials, IPs. The endstation controller PV (`MC:09`) is in source; vendor detail is not. | A `MotionController`, specifics blank. | The MotionController Models. |
| ENERGY-1 | Blocks-build | Should CORA coin the `energy_scan` Capability (the catalog anticipates it as pending) now that BMM is its first real consumer, or keep XAS under `characterization` + `energy_change` until a conduct-path forces it? An XAS scan sweeps the energy axis and reads the detectors per point, distinct from the `beamline_energy_change` setpoint move. | XAS mapped to existing Capabilities for now; `energy_scan` deferred per the design-phase discipline. | The spectroscopy Capability decision. |
