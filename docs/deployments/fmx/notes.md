# Notes

## Techniques

*What CORA would run at FMX: macromolecular crystallography, each a [Catalog](../../catalog/methods.md) Method. FMX is CORA's second MX beamline (after Diamond i03) and follows the same Method-deferral discipline.*

FMX's science is protein crystallography: rotate a cryo-cooled crystal in a focused microbeam and read the diffraction on the Eiger, locate crystals with fast grid scans, and exchange samples with a robot. These are the MX Methods i03 brought to CORA; FMX is their second consumer. The Methods below render unlinked and stay pending until the owner-scope decision (TECH-1) brings them into the catalog.

| Technique | Beam | Detector | Status in CORA |
| --- | --- | --- | --- |
| Rotation (oscillation) data collection | monochromatic, microfocused | `AreaDetector` (Eiger, Detector Role) | the i03 `mx_data_collection` Method binding Goniometer + Eiger + vector + Zebra, pending; 2nd consumer (TECH-1) |
| Grid scan / sample location | monochromatic, microfocused | `AreaDetector` + `SampleCamera` | the i03 `grid_scan` Method over the Zebra-triggered goniometer raster, pending; 2nd consumer (TECH-1) |
| Autonomous sample exchange | n/a | n/a | the i03 `sample_exchange` Method: a Procedure over the spine + a Subject custody thread, pending; 2nd consumer (ROBOT-1) |
| Anomalous element ID (fluorescence) | monochromatic, energy-swept | `FluorescenceDetector` (Mercury, Sensor) | the edge scan picks the energy for SAD / MAD; reuses the energy axis (DET-1) |
| Fixed-target serial (chip) | monochromatic, microfocused | `AreaDetector` | the chip-scanner raster; reuses the `serial_crystallography` Method (i24 / LCLS-MFX), deferred (SERIAL-1) |

### Why the Methods stay pending

FMX reuses the three MX Methods Diamond i03 left pending. Unlike a loose device *Family* (which a second sighting promotes on a mechanical rule-of-three, as ISS did for the emission spectrometer), a pending *Method* has no automatic promotion: it is coined by deliberate decision when a conduct-path needs it, the same discipline that keeps `energy_scan` deferred even across several consumers. FMX makes each of `mx_data_collection`, `grid_scan`, and `sample_exchange` a two-consumer Method (i03 + FMX), which strengthens the eventual case to coin them but does not force it in a descriptor scaffold (TECH-1). The device Roles already exist (the graduated `Goniometer` presents Positioner, the Eiger presents Detector), so what is pending is the recipe, not a device shape.

The autonomous sample-exchange loop is the genuinely non-obvious modelling: the unattended sequence (load pin, centre, collect, unmount, next) is a Procedure over the spine, threaded through the `Subject` custody lifecycle (Received to mounted to measured to Returned) and gated by a Clearance issued after a safety review. The robot itself is just a Positioner Asset; the workflow is the modelling (ROBOT-1). The per-experiment recipes (oscillation ranges, exposure, grid parameters, the exchange sequence) are calibration the deployment must supply.

## Governance

*Who may act at FMX and the trust shape CORA applies. This is CORA's governance design landing on the beamline, not a description of the beamline's current controls authority.*

People and agents are facility principals at the [NSLS-II Site](../nsls2/index.md#safety-and-governance); on the beamline they surface through the actions they take. The human roster is not known from the profile collection (GOV-1), so the principals are the design shape, not a registered list.

### Who acts

CORA brings its own Access model: a small set of facility roles (operator, beamline scientist, safety reviewer, and the autonomous-agent and service principals) scoped at the NSLS-II Site. An FMX beamtime is run by an operator or beamline scientist Actor; a safety reviewer holds the clearance authority.

### The trust boundary

CORA's Trust BC (Zone, Conduit, Policy) gates every command by who is acting and what the beamline state allows: who may set the energy, move the goniometer, start a rotation data collection or a grid scan, drive the robot, override a caution, or commit a beam-centre calibration. This authority is CORA's own, expressed per Actor, not inherited from the beamline's controls layer (the LSDC Governor). The NSLS-II proposal and cycle are a fact CORA's Campaign uses for custody.

### The autonomous loop under custody

FMX's defining governance wrinkle is the unattended robot sample-exchange loop. CORA's Campaign, Trust, and Subject shapes are where that resolves: the robot loading a crystal is a command the trust boundary gates, and the crystal is a `Subject` whose custody (Received to mounted-on-goniometer to measured to Returned / Stored) is the record of record. The autonomous loop is gated by a `Clearance` issued after a safety review, exactly the i03 pattern. An autonomous Agent driving the load-centre-collect-unmount cycle would be a facility principal scoped at the Site, governed by the same trust boundary, with each choice recorded as a [Decision](../../architecture/modules/decision/index.md). None is declared yet; the autonomous-loop lifecycle is deferred (ROBOT-1).

## Model

*The developer's by-kind index: where each CORA aggregate's FMX content lives. It hosts no content of its own. Design-phase scaffold.*

For the aggregate shapes see the [architecture model](../../architecture/model.md) and the per-BC
[modules](../../architecture/modules/index.md).

| Aggregate (BC) | Where at FMX |
| --- | --- |
| Asset (Equipment) | the stage pages: [Source](source.md), [Sample](sample.md), [Detector](detector.md) |
| Computed / virtual axes (Equipment) | [Source](source.md) (EnergyAxis) |
| Capability, Method (Recipe) | [Techniques](#techniques) |
| Enclosure (Enclosure) | [The beamline](index.md#enclosures) (17-ID-A optics, 17-ID-C experiment) |
| Zone, Conduit, Policy (Trust); Actor (Access) | [Governance](#governance) |
| Subject (the crystal custody thread) | [Governance](#the-autonomous-loop-under-custody) (deferred, ROBOT-1) |
| Procedure, Recipe, Caution, Supply, Run, Campaign, Dataset, Decision | deferred (design-phase; see below) |

### What this deployment graduates: nothing (and that is the finding)

FMX is a clean **pure-reuse** deployment. As CORA's second MX beamline (after i03), its finding is that the MX vocabulary i03 earned generalizes to a second, independent facility with no new modelling: the graduated `Goniometer` (the single-omega micro-goniometer), the `Camera` (the Eiger), the graduated `Transfocator` (the CRL), the `Monochromator`, the `Mirror` (HFM + KB), the `Filter` (the BCU / RI attenuators), the `BeamStop`, the `FluxMonitor`, the catalog `Backlight` (graduated across the MX / imaging fleet), and the graduated catalog `PositionMonitor` (presenting `Sensor`, distinct from `FluxMonitor` by measuring beam position rather than flux) all bind unchanged. The robot is one Positioner-presenting Asset, not a new Family (the i03 / 19-BM precedent). The one small modelling step beyond i03 is binding the Mercury fluorescence detector to the catalog `EnergyDispersiveSpectrometer` (i03 deferred its fluorescence detector); no new Family is coined.

### Deliberately not here yet

This is a design-phase scaffold (descriptor + docs), mirroring i03 and the other NSLS-II beamlines. Left out on purpose:

- **No catalog change.** FMX graduates nothing and coins nothing. The three MX Methods (`mx_data_collection`, `grid_scan`, `sample_exchange`) stay pending: FMX is their second consumer (after i03), which strengthens but does not force coining (Methods have no mechanical promotion, the `energy_scan` deferral discipline; TECH-1). The `Backlight` (i03 + i24 + FMX) has graduated to the catalog across the MX / imaging fleet (DET-1).
- **The robot is not a Family.** The sample-changing robot is one Positioner-presenting Asset, gated by a Clearance, loading a `Subject`, vendor in a bound Model; not a new SampleChanger Family (the i03 / 19-BM precedent, adversarially verified there; ROBOT-1).
- **The autonomous loop and the Subject custody thread.** The unattended exchange loop is a Procedure over the spine threaded through the `Subject` aggregate; it is the genuinely non-obvious MX modelling, deferred with i03 (ROBOT-1).
- **Sample cryo-cooling.** The cold-gas cryostream is not exposed in the profile collection (an annealer / thaw-air actuator is), so it is deferred (CRYO-1); it would bind `TemperatureController` (the i03 cryostream precedent) when its PV is supplied.
- **The fixed-target serial mode.** The chip-scanner serial-crystallography raster is named but not modelled; it would reuse the `serial_crystallography` Method (i24 / LCLS-MFX), deferred (SERIAL-1).
- **Operations and experiment views, integration scenarios, vendor Models.** A runbook and registered Assets for a beamline CORA does not yet drive would be invention; they land when the design firms and the team confirms.

## Open questions

*What CORA needs the FMX team to confirm. This model is reverse-engineered from public open source (the `NSLS2/fmx-profile-collection` bluesky / ophyd startup files; the MX acquisition logic lives in the `lsdc` / `mxtools` libraries): the EPICS PVs are read from the `startup/*.py` device classes, but the goniometer / robot / detector vendor identities, the crystal cut, and physical positions are not. Each row is a fact the beamline team owns. It is a delete-on-answer queue.*

Priorities: `Blocks-build`, `Blocks-go-live`, `Nice-to-have`.

### Source and safety

| ID | Priority | Question | CORA assumes | Resolves |
| --- | --- | --- | --- | --- |
| SRC-1 | Nice-to-have | The IVU21 undulator period, gap range, and gap-to-energy curve. The device (`SR:C17-ID:G1{IVU21:2}`) is in source; the parameters are not. | An in-vacuum undulator on the 3 GeV ring, identity-only. | The InsertionDevice settings. |
| TOPO-1 | Nice-to-have | FMX (17-ID-2) shares the IVU21 undulator and the 17-ID straight with AMX (17-ID-1). Is the straight canted (two beams), and is one root Unit per branch the right model? | One root Unit feeding the 17-ID-2 branch (the CSX / 32-ID canted precedent); AMX is the sibling branch. | The sector topology and the AMX relationship. |
| PSS-1 | Blocks-go-live | The PSS search-and-secure permit-leaf PVs. Only the shutters (`XF:17ID-PPS:FAMX{Sh:FE}`, `XF:17IDA-PPS:FMX{PSh}`) are in source. | The permit signal is a confirm note, not a guessed PV. | The Enclosure permit signals. |

### Optics

| ID | Priority | Question | CORA assumes | Resolves |
| --- | --- | --- | --- | --- |
| DCM-1 | Nice-to-have | The HDCM crystal cut, d-spacing, and energy range. The monochromator (`Mono:DCM`) and its axes are in source. | One Monochromator Asset, crystal settings blank. | The Monochromator settings. |
| KB-1 | Nice-to-have | The HFM and KB mirror coatings, the bimorph calibration, and the CRL transfocator lens count and focal configuration. The mirrors (`Mir:HFM`, `Mir:KBH/KBV`) and the CRL (`CRL:`) are in source. | The mirror / CRL internals are per-Asset settings on the existing Mirror / Transfocator Families. | The focusing-optic settings. |

### Sample and detectors

| ID | Priority | Question | CORA assumes | Resolves |
| --- | --- | --- | --- | --- |
| GONIO-1 | Blocks-go-live | The goniometer axis decomposition (single omega + GX / GY / GZ centring + PY / PZ pin + PI fine) and the centre-of-rotation calibration. The stack (`Gon:1`) is in source. | A `Goniometer` Asset (catalog Family, graduated on the i03 Smargon); per-axis decomposition to confirm. | The goniometer model. |
| ROBOT-1 | Blocks-go-live | The sample-changing robot model, the dewar / puck layout, the exchange workflow, and the Subject custody lifecycle. The Governor state machine (`Gov:Robot`) and the dewar interlock (`DewarSwitch`) are in source. | One Positioner-presenting `Robot` Asset (not a new Family); the autonomous loop is a Procedure + a Subject custody thread, gated by a Clearance. | The robot model and the autonomous-loop modelling. |
| DET-1 | Blocks-go-live | The Eiger model and beam centre, and the Mercury fluorescence detector element count and ROI map. The Eiger (`Det:Eig16M`) and the Mercury (`Det:Mer`) are in source. | An Eiger 16M (`Camera`) and a Mercury (`EnergyDispersiveSpectrometer`); model / ROIs to confirm. | The detector roster. |
| DIAG-1 | Nice-to-have | The beam-position channel map (the Prosilica BPM cameras, the sector XBPM); the `PositionMonitor` Family is graduated (catalog, presenting `Sensor`), only the per-Asset channel map stays pending. | Read-only beam-position (graduated catalog `PositionMonitor`) probes; channel map blank. | The PositionMonitor bindings. |
| CRYO-1 | Nice-to-have | The sample cryo-cooling (cold-gas cryostream) and the annealer / thaw-air actuator. The annealer (`Wago:`) is in source; the cryostream IOC is not. | Sample cooling deferred; the annealer named, the cryostream a `TemperatureController` when its PV is supplied. | The sample-environment Assets. |

### Controls and technique scope

| ID | Priority | Question | CORA assumes | Resolves |
| --- | --- | --- | --- | --- |
| DRIVE-1 | Blocks-go-live | The motion-controller box models, firmware, and IPs (the PowerBrick / PPMAC vector controller `Gon:1-Vec` / `MC17:Sender`, the Zebra `Zeb:3`, and the EPICS motor records). | Families bound (MotionController, TimingController), specifics blank. | The MotionController Models. |
| TECH-1 | Blocks-go-live | Do the MX Methods (rotation `mx_data_collection`, `grid_scan`, `sample_exchange`) enter CORA's catalog, or stay pending? FMX is the second consumer after i03. | The three Methods reused pending (no mechanical promotion for Methods; the energy_scan deferral discipline); no new Method coined. | The MX Method scope. |
| SERIAL-1 | Nice-to-have | The fixed-target chip-scanner serial-crystallography mode (the Oxford chip raster, a PPMAC on-the-fly motion). Is it modelled, and does it reuse the `serial_crystallography` Method (i24 / LCLS-MFX)? | Deferred; FMX's primary mode is rotation MX, the chip-scanner mode is named here. | The serial-mode Assets and Method. |
