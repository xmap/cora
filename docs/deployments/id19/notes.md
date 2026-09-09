# Notes

## Techniques

*What CORA would run at ID19: hard X-ray parallel-beam microtomography, radiography, and propagation phase-contrast imaging, a [Catalog](../../catalog/methods.md) Method bound through an [ESRF Practice](../esrf/index.md#the-techniques-adapted-here). The technique is plain tomography reuse; the genuine novelty at ID19 is the control floor, not the science.*

| Technique | Catalog method | Notes |
| --- | --- | --- |
| Parallel-beam microtomography / radiography / phase-contrast imaging | `tomography` | the sample is spun through the beam while an area detector records a stack of projection radiographs; a real-space volume is reconstructed downstream. The existing Method the 2-BM pilot and MAX IV TomoWise carry; ID19 is a further consumer (TECH-1) |

The technique is recorded as a pending [Practice](../esrf/index.md#the-techniques-adapted-here) on the ESRF Site, `ID19_microtomography_practice` (TECH-1).

### The acquisition shape

Microtomography is an acquisition shape CORA already models. The [rotation stage](sample.md) spins the sample through the beam; the [detector](detector.md) records a projection radiograph at each angle; and the stack of projections, together with the known rotation angles, is enough to reconstruct a real-space volume of the sample. ID19's long source-to-sample distance gives the beam high spatial coherence, so a settable sample-to-detector distance turns the same acquisition into propagation phase-contrast imaging (DET-1). The reconstruction, turning the projection stack into a volume, is `ComputePort` work, not a beamline device, the same reconstruction leg the other imaging beamlines carry.

ID19 runs this acquisition at two endstations sharing one source and optics: the micro-resolution (MR) station for large-field, high-throughput tomography, and the high-resolution (HR) station for small-field, high-resolution tomography. Both are the same Method; the difference is the stage stack and the magnification optic, a Practice-and-settings difference, not a new technique.

So the parts are a `RotaryStage` (the tomographic spin, the master motion, SAMPLE-1), a `LinearStage` for sample centring (SAMPLE-1), a `Camera` as the area detector (interchangeable Frelon / PCO / Basler Lima cameras, DET-1), and a `LinearStage` setting the detector propagation distance (DET-1). None is new; ID19 reuses the existing tomography device shapes exactly.

### Why the technique is not the novelty

ID19 is a microtomography beamline, and CORA already models microtomography at the 2-BM operational pilot and the MAX IV TomoWise design scaffold. The `tomography` Method, its Capability, and the device families it binds are all in place. ID19 is a further consumer of that Method, not a new technique, so the Practice is carried pending only because ID19 is not yet driven by CORA, not because the Method is new (TECH-1).

The genuine novelty at ID19 is one layer down, in the control plane: ESRF runs BLISS (a Tango-based control system), not EPICS, and ID19 is the first to bring that BLISS floor to tomographic imaging (its ESRF sibling ID32 opened it for soft X-ray RIXS). That is a [Controls](controls.md) and seam concern, not a technique concern. Holding the technique constant is the point: it isolates the control-plane axis so the BLISS / Tango floor is the only thing that is new (see [Model](#model)).

### Not modelled yet

This cut models the source, the optics, and the two main tomography endstations (MR and HR). The further endstations present in the ID19 config are noted but not modelled:

- The MH and MED tomography endstations, their own BLISS sessions with their own stage stacks (ENDSTATION-1).
- The LATOMO laminography endstation, which runs a MicosAnka controller over TCP plus a tilt-transformation pusher, a distinct acquisition geometry (ENDSTATION-1).
- The RADIO (radiography) and PCOTOMO (PCO high-speed tomography) sessions (ENDSTATION-1).
- The SmarAct multi-tower sample stack and the FalconX / Mercury fluorescence MCAs (ENDSTATION-1).

Each is named on the [Open questions](#open-questions) page rather than modelled speculatively. The source walk that grounds what is and is not present is the generated [beamline](source.md) view.

## Governance

*Who may act at ID19 and the trust shape CORA applies. This is CORA's governance design landing on the beamline, not a description of the beamline's current controls authority. Scaffold, not yet instantiated.*

People and autonomous agents are facility principals at the [ESRF Site](../esrf/index.md#safety-and-governance); on the beamline they surface through the actions they take. The human roster is not in the BLISS config (GOV-1), so the principals are the design shape, not a registered list. This page follows the same model as the other beamlines.

### Who acts

CORA brings its own Access model: a small set of facility roles (operator, beamline scientist, safety reviewer, and the autonomous-agent and service principals) scoped at the ESRF Site. An ID19 beamtime is run by an operator or beamline scientist Actor; a safety reviewer holds the clearance authority. The ESRF operator pool and review structure are site-level and shared across the beamlines, so they are not instantiated per beamline; they are carried pending on the [ESRF Site page](../esrf/index.md#safety-and-governance) (GOV-1). None of this is in the BLISS config, which is a controls device database, not an organizational record.

### The trust boundary

CORA's Trust BC (Zone, Conduit, Policy) gates every command by who is acting and what the beamline state allows: who may drive a [rotation stage](sample.md) through a tomographic scan, arm a [detector](detector.md) to record the projection stack, move the monochromator or open a shutter, override a caution, or commit an alignment. This authority is CORA's own, expressed per Actor, not inherited from the beamline's controls layer. The ESRF proposal and cycle are a fact CORA's Campaign uses for custody.

Because ID19 is a reverse-engineered scaffold rather than a pilot, the concrete trust shape (the Zones grouping the optics and endstation resources, the Conduit binding the surfaces that may issue commands, and the Policies that say who may do what) is named here, not built. It would land, following the [2-BM governance](../2-bm/governance.md) shape, if and when the deployment approaches real scope.

### The Enclosures ID19 gates

This cut covers two enclosures, the grouping CORA's Zones would follow (ENC-1):

| Enclosure | Role | What it holds |
| --- | --- | --- |
| `id19-optics` | optics hutch | the insertion-device source, the TripleMono, the primary / secondary slits, the transfocator, the attenuators, and the front-end / beam shutters |
| `id19-experiment` | experiment hutch | the MR and HR tomographic rotation stages, their sample positioning stacks, the Lima area detectors, and the detector propagation stages |

A shared optics hutch feeding two tomography endstations in one experiment hutch is the governance shape: which endstation is taking beam, and who may drive the shared optics, is the kind of question the Zone and Policy answer.

### The safety tier behind the beam

The safety tier behind the beam is the personnel safety system. The leaves that must be satisfied before the beam can enter an enclosure are the PSS search-and-secure permit signals, and the shutters are what those leaves gate. The shutter handles are known from the config (`frontend`, `id19/bsh/1`, `id19/bsh/2`, all TangoShutters), but the PSS permit signals behind them are not in the config, so CORA does not name them and does not invent them: the Enclosure permit signals are carried pending (PSS-1). When staff confirm the permit signal handles, they bind to the Enclosure as the permit leaves the way the operating siblings carry theirs. No interlock or PSS tier is invented in the meantime.

Clearances (the safety forms that must be active to start) are issued at the ESRF Site, not on the beamline, and the beamline links up to them rather than restating them (GOV-1). The ESRF PSS clearance is carried pending because its form names are not confirmed (PSS-1).

### Microtomography under custody

ID19's reason for existing is microtomography: a tomographic acquisition spins the sample through the beam and records a stack of projection radiographs, and a real-space volume is reconstructed from that stack. In CORA's model this is the existing `tomography` Method, not a new technique (TECH-1); the devices it gates are `RotaryStage`, `LinearStage`, and `Camera` Assets (SAMPLE-1, DET-1), and the reconstruction is `ComputePort` work, not a beamline device. That makes the repeated tomographic acquisition the place CORA's custody and trust shapes would earn their keep: the trust boundary bounds who may drive the rotation and arm the detector, and the Campaign and Subject shapes carry the sample's custody and the projection record.

The governance shape is the same CORA brings to every beamline; what is different at ID19 is one layer down, in the control floor (BLISS / Tango, not EPICS, see [Controls](controls.md)). The trust boundary is control-floor-agnostic: it gates commands by Actor and state regardless of whether the floor underneath is EPICS or BLISS.

If an autonomous Agent were added (for example to centre the sample or decide when a scan is complete), it would be a facility principal scoped at the Site, governed by the same trust boundary, with each choice recorded as a [Decision](../../architecture/modules/decision/index.md). None is declared yet; this stays design intent.

### What is deliberately not modelled

- **The PSS permit signals (PSS-1).** The shutter handles are known; the permit signals behind them are not in the config, carried pending, not invented.
- **The ESRF operator pool and review structure (GOV-1).** Site-level and shared across the beamlines, carried pending on the ESRF Site, not instantiated per beamline.
- **The further endstations (ENDSTATION-1).** MH, MED, laminography, radiography, and PCO are noted, not modelled in this cut.
- **The concrete Zone, Conduit, and Policy instances.** Named as the trust shape, not built; they would land if and when the deployment approaches real scope, following the [2-BM governance](../2-bm/governance.md) shape.

The full delete-on-answer queue is on [Open questions](#open-questions); where each device and Method lands is on [Model](#model).

## Model

*The developer's by-kind index: where each CORA aggregate's ID19 content lives, why this BLISS-floor imaging deployment coins no new family, and the record of what is deliberately deferred. Design-phase scaffold.*

For the aggregate shapes see the [architecture model](../../architecture/model.md) and the per-BC [modules](../../architecture/modules/index.md).

| Aggregate (BC) | Where at ID19 |
| --- | --- |
| Asset (Equipment) | the stage pages: [Source](source.md), [Sample](sample.md) |
| Capability, Method (Recipe) | [Techniques](#techniques) |
| Enclosure (Enclosure) | [the index](index.md#enclosures) |
| Zone, Conduit, Policy (Trust); Actor (Access) | [Governance](#governance) |
| Procedure, Recipe, Caution, Supply, Subject, Run, Campaign, Dataset, Decision | deferred (design-phase; see below) |

### What makes ID19 new

ID19 is CORA's first imaging beamline on a **non-EPICS control floor**. Most of the fleet is EPICS (APS, Diamond, NSLS-II, SLAC, all ophyd / bluesky / dodal / pcdshub). ESRF runs BLISS, a Tango-based control system; its soft X-ray sibling ID32 opened the BLISS floor for CORA, and ID19 is the first to bring it to tomographic imaging. That is the novelty, and it is a **control-plane** concern, not a device or technique concern.

The seam model that today reads "EPICS is the floor" generalizes at ID19 to "BLISS / Tango is the floor". CORA's edge conducts the tomographic scan over its `ControlPort` against BLISS scan procedures and Lima detector servers, rather than EPICS IOCs. The test ID19 poses is that the `ControlPort` and the conduct-versus-drive-through seam are genuinely control-system-agnostic, not secretly EPICS-shaped (see [Controls](controls.md), CTRL-1).

### No new families, no new methods

ID19 is a microtomography beamline, and CORA already models microtomography. So holding the device families and the technique constant is deliberate: it isolates the control-plane axis as the only new thing.

- **The rotation stages bind the catalog `RotaryStage`.** `mrsrot` (MR) and `hrsrot` (HR) are the tomographic spins, the master motions of each scan, expected to clock the detector triggering (SAMPLE-1).
- **The sample and detector positioning stages bind the catalog `LinearStage`.** Sample centring (with the `XYOnRotation` pseudo-axis keeping the sample on the rotation axis) and the detector propagation distance are plain linear motion (SAMPLE-1, DET-1).
- **The detectors bind the catalog `Camera`, which presents the Detector Role.** ID19's indirect-detection area detectors (interchangeable Frelon CCD, PCO 4k, PCO Dimax high-speed, and Basler Lima cameras) are thin `Camera` instances (DET-1).
- **The optics bind existing Families.** `Monochromator` (the TripleMono), `Slit` (primary / secondary), `Transfocator` (the white-beam Be-lens transfocator), `Filter` (the attenuator banks, folding in per the i03 precedent rather than a new `Attenuator` Family), `Shutter` (front-end and beam shutters), and `InsertionDevice` (the undulator / wiggler set).
- **The technique is the existing `tomography` Method.** ID19 is a further consumer of the Method the 2-BM pilot and TomoWise carry; the Practice `ID19_microtomography_practice` is carried pending only because ID19 is not yet driven by CORA (TECH-1).

ID19 coins no new Family, nothing graduates, and the catalog is unchanged.

### Two endstations

MR (micro-resolution) and HR (high-resolution) are distinct BLISS sessions (`MRTOMO`, `HRTOMO`) sharing the source and optics. CORA models each as its own sample and detection group under the shared experiment hutch: same Families, same `tomography` Method, different stage stack and magnification optic. This is a Practice-and-settings difference, not new vocabulary.

### Deliberately not here yet

- **The further endstations (`ENDSTATION-1`).** The config carries MH, MED, laminography (LATOMO, a MicosAnka-over-TCP controller with a tilt-transformation pusher), RADIO, PCOTOMO, the SmarAct multi-tower stack, and the FalconX / Mercury fluorescence MCAs. This cut models MR and HR, the two main tomography stations; the rest are noted, not modelled.
- **The PSS permit signals (`PSS-1`).** The TangoShutter handles (`frontend`, `id19/bsh/1`, `id19/bsh/2`) are known, but the personnel-safety permit signals behind them are not in the config; carried pending, not invented.
- **Vendor models, serials, and physical positions.** Not in the config; carried confirm.
- **The simulated devices and full asset-tree scenarios.** No `test_id19_*.py` registers the asset tree, and no vendor Models are bound.
- **Operations and experiment views.** A runbook and live experiment view for a beamline CORA does not yet drive would be invention; see the note on the [index](index.md#not-yet-documented).

## Open questions

*What CORA needs the ID19 team to confirm before the model can be trusted.*

ID19 was reverse-engineered from the beamline's own public BLISS Beacon device database ([`gitlab.esrf.fr/id19/beamline_configuration`](https://gitlab.esrf.fr/id19/beamline_configuration)), so the control handles on the [device pages](index.md) are the beamline's real BLISS object and Tango device names, read from the config rather than confirmed by staff. Each row below is a fact the beamline team owns, not a CORA modelling choice (those are on [Model](#deliberately-not-here-yet)). It is a delete-on-answer queue. Priorities are `Blocks-build`, `Blocks-go-live`, and `Nice-to-have`.

### Control and the BLISS / Tango floor

| ID | Priority | Question | CORA assumes | Resolves |
| --- | --- | --- | --- | --- |
| CTRL-1 | Blocks-go-live | Are the BLISS object and Tango device handles read from the public config current and correct against the live system? | The handles in the descriptor are taken from the config and carried confirm. | Verifying each Asset's control handle on the BLISS floor. |
| CTRL-2 | Nice-to-have | Which BLISS scan procedure(s) ID19 uses per endstation (continuous / fly versus step), and which the CORA edge drives through versus replaces. | A continuous-rotation scan clocked by the rotation stage; the conduct-versus-replace split is per routine. | The orchestration seam over the `ControlPort`. |

### Topology and scope

| ID | Priority | Question | CORA assumes | Resolves |
| --- | --- | --- | --- | --- |
| ENC-1 | Blocks-go-live | The hutch grouping: one optics hutch and one experiment hutch holding both endstations, or a finer split? | One `id19-optics` and one `id19-experiment` enclosure. | The Enclosure grouping. |
| ENDSTATION-1 | Nice-to-have | The further endstations in the config (MH, MED, laminography LATOMO, RADIO, PCOTOMO, the SmarAct towers, the fluorescence MCAs): are they distinct endstations CORA should model? | Noted, not modelled in this cut; MR and HR are the two main tomography stations. | The remaining endstation roster. |

### Source and optics

| ID | Priority | Question | CORA assumes | Resolves |
| --- | --- | --- | --- | --- |
| SRC-1 | Blocks-go-live | Which insertion device(s) feed which endstation / mode, and the energy reach. | The undulators (u13a/u32a/u17-6c/u32c) and the w150b wiggler, selected per mode; the wiggler drives white-beam tomography. | The source Asset and mode mapping. |
| OPT-1 | Blocks-go-live | The TripleMono crystal-pair / Laue / multilayer mode mapping, the transfocator lens recipe per energy, and the attenuator foil set. | TripleMono Bragg 17-99 keV plus Laue / multilayer; 8 Be transfocator lenses; Cu/Al attenuator banks folding into Filter. | The optics modelling. |

### Endstations

| ID | Priority | Question | CORA assumes | Resolves |
| --- | --- | --- | --- | --- |
| SAMPLE-1 | Blocks-go-live | The operative rotation and sample-positioning axis set per endstation (the config carries spare / commented axes). | MR: mrsrot + mrsx/mrsy/mrxc/mryc; HR: hrsrot + hrsx/hrsy/hrsz/hrz0; XYOnRotation centring on each. | The sample-stage modelling. |
| DET-1 | Blocks-go-live | The operative Lima detector(s) and the indirect-detection optics per endstation, and the propagation-stage axes. | Interchangeable Frelon / PCO / Basler Lima cameras bound to `Camera`; the propagation stage binds `LinearStage`. | The detector modelling. |

### Safety and resources

| ID | Priority | Question | CORA assumes | Resolves |
| --- | --- | --- | --- | --- |
| PSS-1 | Blocks-go-live | The ESRF PSS search-and-secure permit signals behind the frontend / bsh shutters (not in the config). | Permit leaves to be named; the TangoShutter handles are known, the permit signals are not. | The Enclosure permit signals and the safety tier. |
| SUP-1 | Nice-to-have | The vacuum extent of the beam path and the cooling-water / beam supplies a run draws on. | Photon beam, cooling water, and vacuum, carried pending. | The Supply observations. |
| GOV-1 | Nice-to-have | The ESRF operator pool and safety-review structure (site-level, shared across beamlines). | Carried pending on the ESRF Site, not instantiated per beamline. | The governance principals. |

### Technique

| ID | Priority | Question | CORA assumes | Resolves |
| --- | --- | --- | --- | --- |
| TECH-1 | Blocks-go-live | Does ID19 microtomography map cleanly onto the existing `tomography` Method, or does parallel-beam / phase-contrast imaging want a distinct Method? | The existing `tomography` Method, a further consumer; carried as a pending Practice. | The microtomography Practice. |
