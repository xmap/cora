# Notes

## Techniques

*What CORA would run at AMX: macromolecular crystallography, each a [Catalog](../../catalog/methods.md) Method. AMX is CORA's third MX beamline (after Diamond i03 and NSLS-II FMX) and follows the same Method-deferral discipline.*

AMX's science is high-throughput protein crystallography: rotate a cryo-cooled crystal in a focused microbeam and read the diffraction on the Eiger, locate crystals with fast grid scans, and exchange samples with an automated robot. These are the MX Methods i03 and FMX brought to CORA; AMX is their third consumer. The Methods below render unlinked and stay pending until a conduct-path coins them (TECH-1).

| Technique | Beam | Detector | Status in CORA |
| --- | --- | --- | --- |
| Rotation (oscillation) data collection | monochromatic, microfocused | `AreaDetector` (Eiger, Detector Role) | the `mx_data_collection` Method, pending; 3rd consumer (TECH-1) |
| Grid scan / sample location | monochromatic, microfocused | `AreaDetector` + `SampleCamera` | the `grid_scan` Method over the Zebra-triggered goniometer raster, pending; 3rd consumer (TECH-1) |
| Autonomous sample exchange | n/a | n/a | the `sample_exchange` Method: a Procedure over the spine + a Subject custody thread, pending; 3rd consumer (ROBOT-1) |
| Anomalous element ID (fluorescence) | monochromatic, energy-swept | `FluorescenceDetector` (Mercury, Sensor) | the edge scan picks the energy for SAD / MAD; reuses the energy axis (DET-1) |

### Why the Methods stay pending

AMX reuses the three MX Methods i03 and FMX left pending, and is the third consumer of each. This is the moment the consumer count is strongest, so it is worth being precise about why they still do not graduate: unlike a device *Family* (which a second sighting promotes on a mechanical rule-of-three, as ISS did for the emission spectrometer), a *Method* is coined on a **conduct-path**, when a deployment actually runs it (an integration scenario or operational pilot, the way `tomography` and `xpcs` were coined). i03, FMX, and AMX are all descriptor-only scaffolds with no conduct-path, so three consumers strengthen the case but do not coin the Methods, exactly the discipline that keeps `energy_scan` deferred across its consumers. The device Roles already exist (the graduated `Goniometer` presents Positioner, the Eiger presents Detector); what is pending is the recipe.

The genuine MX graduation, coining these Methods, is a follow-on that needs an MX conduct-path scenario (the event-sourced spine work), not another descriptor scaffold. The autonomous sample-exchange loop is the non-obvious modelling: an unattended Procedure over the spine, threaded through the `Subject` custody lifecycle and gated by a Clearance (ROBOT-1).

## Governance

*Who may act at AMX and the trust shape CORA applies. This is CORA's governance design landing on the beamline, not a description of the beamline's current controls authority.*

People and agents are facility principals at the [NSLS-II Site](../nsls2/index.md#safety-and-governance); on the beamline they surface through the actions they take. The human roster is not known from the profile collection (GOV-1), so the principals are the design shape, not a registered list.

### Who acts

CORA brings its own Access model: a small set of facility roles (operator, beamline scientist, safety reviewer, and the autonomous-agent and service principals) scoped at the NSLS-II Site. An AMX beamtime is run by an operator or beamline scientist Actor; a safety reviewer holds the clearance authority.

### The trust boundary

CORA's Trust BC (Zone, Conduit, Policy) gates every command by who is acting and what the beamline state allows: who may set the energy, move the goniometer, start a rotation data collection or a grid scan, drive the robot, override a caution, or commit a beam-centre calibration. This authority is CORA's own, expressed per Actor, not inherited from the beamline's controls layer (the LSDC Governor). The NSLS-II proposal and cycle are a fact CORA's Campaign uses for custody.

### The autonomous loop under custody

AMX is "highly automated": its defining governance wrinkle is the unattended EMBL-robot sample-exchange loop. CORA's Campaign, Trust, and Subject shapes are where that resolves: the robot loading a crystal is a command the trust boundary gates, and the crystal is a `Subject` whose custody (Received to mounted-on-goniometer to measured to Returned / Stored) is the record of record. The autonomous loop is gated by a `Clearance` issued after a safety review, the same pattern as i03 and FMX. An autonomous Agent driving the load-centre-collect-unmount cycle would be a facility principal scoped at the Site, governed by the same trust boundary, with each choice recorded as a [Decision](../../architecture/modules/decision/index.md). None is declared yet; the autonomous-loop lifecycle is deferred (ROBOT-1).

## Model

*The developer's by-kind index: where each CORA aggregate's AMX content lives. It hosts no content of its own. Design-phase scaffold.*

For the aggregate shapes see the [architecture model](../../architecture/model.md) and the per-BC
[modules](../../architecture/modules/index.md).

| Aggregate (BC) | Where at AMX |
| --- | --- |
| Asset (Equipment) | the stage pages: [Source](source.md), [Sample](sample.md), [Detector](detector.md) |
| Computed / virtual axes (Equipment) | [Source](source.md) (EnergyAxis) |
| Capability, Method (Recipe) | [Techniques](#techniques) |
| Enclosure (Enclosure) | [the index](index.md#enclosures) (17-ID-A optics, 17-ID-B experiment) |
| Zone, Conduit, Policy (Trust); Actor (Access) | [Governance](#governance) |
| Subject (the crystal custody thread) | [Governance](#the-autonomous-loop-under-custody) (deferred, ROBOT-1) |
| Procedure, Recipe, Caution, Supply, Run, Campaign, Dataset, Decision | deferred (design-phase; see below) |

### What this deployment graduates: nothing (and that is the finding)

AMX is a clean **pure-reuse** deployment, completing the NSLS-II MX pair as FMX's sibling. Its finding is that the MX vocabulary generalizes across a third independent beamline with no new modelling: the graduated `Goniometer` (single-omega micro-goniometer), the `Camera` (Eiger), the `Monochromator` (here vertical), the `Mirror` (tandem-deflection + KB), the `Filter` (BCU attenuator), the `BeamStop`, the `EnergyDispersiveSpectrometer` (Mercury), the `FluxMonitor` (Keithley), the `TimingController` (Zebra), and the graduated catalog `PositionMonitor` (presenting `Sensor`, distinct from `FluxMonitor` by measuring beam position rather than flux) all bind unchanged. The robot is one Positioner-presenting Asset, not a new Family (the i03 / 19-BM / FMX precedent).

#### FMX-vs-AMX differences

The 17-ID pair is not identical, and the differences exercise the modelling: AMX uses a **vertical** DCM (FMX horizontal), **tandem-deflection** mirrors (FMX a horizontal focusing mirror), an **EMBL** robot, and has **no CRL transfocator** and **no on-axis backlight** in source. Each is a per-Asset settings or device-presence difference, not a Family split; both beamlines bind the same Families.

### Deliberately not here yet

This is a design-phase scaffold (descriptor + docs), mirroring FMX and the other NSLS-II beamlines. Left out on purpose:

- **No catalog change.** AMX graduates nothing and coins nothing. The three MX Methods (`mx_data_collection`, `grid_scan`, `sample_exchange`) stay pending: AMX is their third consumer, which strengthens but does not coin them. Methods coin on a **conduct-path** (a deployment that runs them), not on a sighting count, which is why even at n=3 they defer (the `energy_scan` discipline; TECH-1). Coining them is a follow-on that needs an **MX conduct-path scenario** (event-sourced spine work), the genuine MX-graduation path.
- **The robot is not a Family.** The EMBL sample-changing robot is one Positioner-presenting Asset, gated by a Clearance, loading a `Subject`, vendor in a bound Model; not a new SampleChanger Family (the i03 / 19-BM precedent, ROBOT-1).
- **The autonomous loop and the Subject custody thread.** The unattended exchange loop is a Procedure over the spine threaded through the `Subject` aggregate; deferred with i03 / FMX (ROBOT-1).
- **Sample cryo-cooling.** The cold-gas cryostream is not exposed in the profile collection, so it is deferred (CRYO-1); it would bind `TemperatureController` (the i03 cryostream precedent) when its PV is supplied.
- **The area detector PV.** The Eiger is not exposed in the AMX profile collection; it is carried `Camera` confirm-only (DET-1).
- **Operations and experiment views, integration scenarios, vendor Models.** A runbook and registered Assets for a beamline CORA does not yet drive would be invention; they land when the design firms and the team confirms.

## Open questions

*What CORA needs the AMX team to confirm. This model is reverse-engineered from public open source (the `NSLS2/amx-profile-collection` bluesky / ophyd startup files; the MX acquisition logic lives in the `lsdc` / `mxtools` libraries): the EPICS PVs are read from the `startup/*.py` device classes, but the goniometer / robot / detector vendor identities, the crystal cut, and physical positions are not. Each row is a fact the beamline team owns. It is a delete-on-answer queue.*

Priorities: `Blocks-build`, `Blocks-go-live`, `Nice-to-have`.

### Source and safety

| ID | Priority | Question | CORA assumes | Resolves |
| --- | --- | --- | --- | --- |
| SRC-1 | Nice-to-have | The IVU21 undulator period, gap range, and gap-to-energy curve. The device (`SR:C17-ID:G1{IVU21:1}`) is in source; the parameters are not. | An in-vacuum undulator on the 3 GeV ring, identity-only. | The InsertionDevice settings. |
| TOPO-1 | Nice-to-have | AMX (17-ID-1) shares the IVU21 undulator and the 17-ID straight with FMX (17-ID-2, which uses IVU21:2). Is the straight canted (two beams), and is one root Unit per branch the right model? | One root Unit feeding the 17-ID-1 branch (the FMX / CSX canted precedent); FMX is the sibling branch. | The sector topology and the FMX relationship. |
| PSS-1 | Blocks-go-live | The PSS search-and-secure permit-leaf PVs and the front-end / photon shutter PVs (not in the profile collection; the front end is shared with FMX). | The permit signal is a confirm note, not a guessed PV. | The Enclosure permit signals. |

### Optics

| ID | Priority | Question | CORA assumes | Resolves |
| --- | --- | --- | --- | --- |
| DCM-1 | Nice-to-have | The vertical DCM crystal cut, d-spacing, and energy range. The monochromator (`Mono:DCM`) and its axes are in source. | One Monochromator Asset, crystal settings blank. | The Monochromator settings. |
| KB-1 | Nice-to-have | The tandem-deflection and KB mirror coatings and calibration. The mirrors (`Mir:TDM`, `Mir:KBH/KBV`) are in source. | The mirror internals are per-Asset settings on the existing Mirror Family. | The focusing-optic settings. |

### Sample and detectors

| ID | Priority | Question | CORA assumes | Resolves |
| --- | --- | --- | --- | --- |
| GONIO-1 | Blocks-go-live | The goniometer axis decomposition (single omega + GX / GY / GZ centring + PY / PZ pin fine) and the centre-of-rotation calibration. The stack (`Gon:1`) is in source. | A `Goniometer` Asset (catalog Family, graduated on the i03 Smargon); per-axis decomposition to confirm. | The goniometer model. |
| ROBOT-1 | Blocks-go-live | The EMBL sample-changing robot model, the dewar / puck layout, the exchange workflow, and the Subject custody lifecycle. The robot (`EMBL`) and Governor are in source. | One Positioner-presenting `Robot` Asset (not a new Family); the autonomous loop is a Procedure + a Subject custody thread, gated by a Clearance. | The robot model and the autonomous-loop modelling. |
| DET-1 | Blocks-go-live | The Eiger model and beam centre (not exposed in the profile collection), and the Mercury fluorescence detector element count and ROI map. | An Eiger (`Camera`, PV pending) and a Mercury (`EnergyDispersiveSpectrometer`); model / ROIs to confirm. | The detector roster. |
| DIAG-1 | Nice-to-have | The beam-position channel map (the four-quadrant BPMs); the `PositionMonitor` Family is graduated (catalog, presenting `Sensor`), only the per-Asset channel map stays pending. | Read-only beam-position (graduated catalog `PositionMonitor`) probes; channel map blank. | The BeamPositionMonitor bindings. |
| CRYO-1 | Nice-to-have | The sample cryo-cooling (cold-gas cryostream), not exposed in the profile collection. | Sample cooling deferred; a `TemperatureController` when its PV is supplied. | The sample-environment Assets. |

### Controls and technique scope

| ID | Priority | Question | CORA assumes | Resolves |
| --- | --- | --- | --- | --- |
| DRIVE-1 | Blocks-go-live | The motion-controller box models, firmware, and IPs (the goniometer vector controller is a PowerBrick; the profile's vector PV is misconfigured to the FMX prefix). | Family bound (MotionController), specifics blank. | The MotionController Models. |
| TECH-1 | Blocks-go-live | Do the MX Methods (rotation `mx_data_collection`, `grid_scan`, `sample_exchange`) enter CORA's catalog, or stay pending? AMX is the third consumer (after i03, FMX). | The three Methods reused pending; coining awaits a conduct-path (an MX integration scenario), not the sighting count (the energy_scan discipline). | The MX Method scope. |
