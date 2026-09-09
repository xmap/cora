# Notes

## Techniques

*What CORA would run at ID16B: KB-focused hard X-ray nano-tomography and nano-XRF (fluorescence) mapping, two [Catalog](../../catalog/methods.md) Methods bound through [ESRF Practices](../esrf/index.md#the-techniques-adapted-here). Both are reused, not new; ID16B's novelty is the nanoprobe-on-BLISS combination, not the techniques.*

| Technique | Catalog method | Notes |
| --- | --- | --- |
| KB-focused nano-tomography | `tomography` | the sample is spun through the nanofocused beam while an area detector records a projection stack; a real-space volume is reconstructed downstream. The existing Method ID19 / 2-BM / TomoWise carry; ID16B is a further consumer (TECH-1) |
| Nano-XRF mapping (incl. fluorescence-tomography) | `scanning_fluorescence_microscopy` | the sample is rastered through the nanoprobe on a piezo scanner while an energy-dispersive detector reads a fluorescence spectrum per point, building an element map; fluorescence-tomography adds a rotation axis. The pending Method 2-ID / XFM / LIX carry; ID16B is a further consumer (METHOD-1) |

The techniques are recorded as pending [Practices](../esrf/index.md#the-techniques-adapted-here) on the ESRF Site: `ID16B_nanotomography_practice` and `ID16B_scanning_fluorescence_microscopy_practice` (TECH-1, METHOD-1).

### The two acquisition shapes

Both are acquisition shapes CORA already models; ID16B runs them through one KB nanofocus.

- **Nano-tomography.** The [rotation stage](sample.md) spins the sample through the nanofocused beam; the [area detector](detector.md) records a projection at each angle; the projection stack reconstructs to a volume. Same shape as ID19, at nanoscale resolution.
- **Nano-XRF mapping.** The [piezo raster scanner](sample.md) steps the sample through the nanoprobe point by point; at each point the [fluorescence detector](detector.md) reads an energy-dispersive spectrum, and the element maps are fit downstream. Adding the rotation axis turns this into fluorescence-tomography (a 3D element map).

The parts are a `RotaryStage` (the tomo spin / fluo-tomo rotation), `LinearStage`s (coarse positioning and the PI piezo raster scanner), `Mirror`s (the KB nanofocus), an `EnergyDispersiveSpectrometer` (the FalconX XRF detector), and a `Camera` (the area detector). None is new. The reconstructions, both the tomographic volume and the XRF map fitting, are `ComputePort` work, not beamline devices.

### Why the techniques are not the novelty

CORA already models tomography (ID19, 2-BM) and scanning fluorescence microscopy (2-ID, XFM, LIX). ID16B is a further consumer of both, so the Practices are carried pending only because ID16B is not yet driven by CORA, not because the Methods are new.

The novelty at ID16B is the combination and the floor: it is the fleet's first KB nanoprobe with an energy-dispersive fluorescence detector, and a further beamline on the BLISS / Tango control floor. Both are device-and-control concerns ([Model](#model), [Controls](controls.md)), not technique concerns. Holding the Methods constant is the point: it isolates what is genuinely new.

### Not modelled yet

This cut models the source, optics, KB nanofocus, sample stack, and detection. The sample environments present in the config are noted, not modelled:

- The cryostream, furnace, and xeol sample environments (`EH/cryo`, `EH/furnace`, `EH/xeol`) and their Eurotherm / nanodac regulation. A `Cryostat` Family is not yet in the catalog, so the sample environment is deferred to keep this cut vocabulary-neutral (ENV-1).
- The `mapping` / `oda` / `taurus` / `webui` software layers (not beamline devices).

Each is named on the [Open questions](#open-questions) page rather than modelled speculatively. The source walk that grounds what is and is not present is the generated [beamline](source.md) view.

## Governance

*Who may act at ID16B and the trust shape CORA applies. This is CORA's governance design landing on the beamline, not a description of the beamline's current controls authority. Scaffold, not yet instantiated.*

People and autonomous agents are facility principals at the [ESRF Site](../esrf/index.md#safety-and-governance); on the beamline they surface through the actions they take. The human roster is not in the BLISS config (GOV-1), so the principals are the design shape, not a registered list. This page follows the same model as ID19 and the other beamlines.

### Who acts

CORA brings its own Access model: a small set of facility roles (operator, beamline scientist, safety reviewer, and the autonomous-agent and service principals) scoped at the ESRF Site. An ID16B beamtime is run by an operator or beamline scientist Actor; a safety reviewer holds the clearance authority. The ESRF operator pool and review structure are site-level and shared across the beamlines (ID19 and ID16B both inherit them), so they are not instantiated per beamline; they are carried pending on the [ESRF Site page](../esrf/index.md#safety-and-governance) (GOV-1).

### The trust boundary

CORA's Trust BC (Zone, Conduit, Policy) gates every command by who is acting and what the beamline state allows: who may drive the [sample rotation](sample.md) through a tomographic scan, raster the [piezo scanner](sample.md) for an XRF map, arm the [FalconX detector](detector.md) or an area detector, move the KB nanofocus or the monochromator, override a caution, or commit an alignment. This authority is CORA's own, expressed per Actor, not inherited from the beamline's controls layer. The ESRF proposal and cycle are a fact CORA's Campaign uses for custody.

Because ID16B is a reverse-engineered scaffold rather than a pilot, the concrete trust shape (the Zones grouping the optics and endstation resources, the Conduit binding the surfaces that may issue commands, and the Policies that say who may do what) is named here, not built. It would land, following the [2-BM governance](../2-bm/governance.md) shape, if and when the deployment approaches real scope.

### The Enclosures ID16B gates

This cut covers two enclosures, the grouping CORA's Zones would follow (ENC-1):

| Enclosure | Role | What it holds |
| --- | --- | --- |
| `id16b-optics` | optics hutch | the U205 undulator source, the Kohzu DCM, the primary / secondary slits, the beam monitors, and the shutters |
| `id16b-experiment` | experiment hutch | the KB nanofocus mirrors, the sample-side slits, the sample rotation / coarse / piezo-scanner stack, the FalconX XRF detector, the optical spectrometer, and the area detectors |

### The safety tier behind the beam

The safety tier behind the beam is the personnel safety system. The leaves that must be satisfied before the beam can enter an enclosure are the PSS search-and-secure permit signals, and the shutters are what those leaves gate. The shutter handles are known from the config (the front-end and `fshut` fast shutter), but the PSS permit signals behind them are not in the config, so CORA does not name them and does not invent them: the Enclosure permit signals are carried pending (PSS-1). When staff confirm the permit signal handles, they bind to the Enclosure as the permit leaves. No interlock or PSS tier is invented in the meantime.

Clearances (the safety forms that must be active to start) are issued at the ESRF Site, not on the beamline, and the beamline links up to them rather than restating them (GOV-1). The ESRF PSS clearance is carried pending because its form names are not confirmed (PSS-1).

### Nano-analysis under custody

ID16B's reason for existing is nano-analysis: KB-focused nano-tomography and nano-XRF mapping. In CORA's model these are the existing `tomography` and `scanning_fluorescence_microscopy` Methods, not new techniques (TECH-1, METHOD-1); the devices they gate are `RotaryStage`, `LinearStage`, `Mirror`, `EnergyDispersiveSpectrometer`, and `Camera` Assets (SAMPLE-1, DET-1), and the reconstructions (the tomographic volume and the XRF map fitting) are `ComputePort` work, not beamline devices. That makes the repeated nano-acquisition the place CORA's custody and trust shapes would earn their keep: the trust boundary bounds who may drive the nanofocus and arm the detectors, and the Campaign and Subject shapes carry the sample's custody and the data record.

The governance shape is the same CORA brings to every beamline; what is different at ID16B is the control floor (BLISS / Tango, not EPICS, see [Controls](controls.md)) and the nanoprobe device set. The trust boundary is control-floor-agnostic and device-agnostic: it gates commands by Actor and state regardless.

If an autonomous Agent were added (for example to centre the sample on the nanoprobe or decide when an XRF map is complete), it would be a facility principal scoped at the Site, governed by the same trust boundary, with each choice recorded as a [Decision](../../architecture/modules/decision/index.md). None is declared yet; this stays design intent.

### What is deliberately not modelled

- **The PSS permit signals (PSS-1).** The shutter handles are known; the permit signals behind them are not in the config, carried pending, not invented.
- **The ESRF operator pool and review structure (GOV-1).** Site-level and shared across the beamlines, carried pending on the ESRF Site.
- **The sample environments (ENV-1).** The cryostream, furnace, and xeol environments are noted, not modelled in this cut.
- **The concrete Zone, Conduit, and Policy instances.** Named as the trust shape, not built; they would land if and when the deployment approaches real scope, following the [2-BM governance](../2-bm/governance.md) shape.

The full delete-on-answer queue is on [Open questions](#open-questions); where each device and Method lands is on [Model](#model).

## Model

*The developer's by-kind index: where each CORA aggregate's ID16B content lives, why this nanoprobe deployment coins no new family, and the record of what is deliberately deferred. Design-phase scaffold.*

For the aggregate shapes see the [architecture model](../../architecture/model.md) and the per-BC [modules](../../architecture/modules/index.md).

| Aggregate (BC) | Where at ID16B |
| --- | --- |
| Asset (Equipment) | the stage pages: [Source](source.md), [Sample](sample.md) |
| Capability, Method (Recipe) | [Techniques](#techniques) |
| Enclosure (Enclosure) | [the index](index.md#enclosures) |
| Zone, Conduit, Policy (Trust); Actor (Access) | [Governance](#governance) |
| Procedure, Recipe, Caution, Supply, Subject, Run, Campaign, Dataset, Decision | deferred (design-phase; see below) |

### What makes ID16B new

ID16B is CORA's **third non-EPICS deployment** (after ID32 and ID19) and the fleet's **first KB nanoprobe with XRF**. The novelty sits on two axes, both below the technique layer:

- **A second BLISS / Tango floor.** ID16B confirms the ID19 seam pattern is repeatable: motion stages are BLISS axes (IcePAP racks, PI piezo scanners, etel Tango motors), the fluorescence detector is a MOSCA / FalconX Tango device, the area detectors are Lima device servers, and CORA's edge conducts over the `ControlPort` against that floor (CTRL-1, see [Controls](controls.md)).
- **The first KB nanoprobe with XRF.** The Kirkpatrick-Baez mirror pair focuses the beam to a nanoprobe, and an energy-dispersive fluorescence detector reads a spectrum per raster point. This device combination is new to the fleet, but every part binds an existing Family.

### No new families, two reused methods

ID16B holds the vocabulary constant; that is deliberate, so the new axes (floor, nanoprobe device set) are isolated.

- **The KB mirrors bind the catalog `Mirror`.** The Kirkpatrick-Baez focusing pair is the nanoprobe; a focusing mirror is what `Mirror` is (OPT-1).
- **The fluorescence detector binds the catalog `EnergyDispersiveSpectrometer`.** ID16B's FalconX silicon-drift detector reads a per-point energy spectrum, a Sensor not a 2D Frame, the same shape as the XFM Xspress3 and the 2-ID / SRX detectors (DET-1). The optical spectrometer (QEPro / Hamamatsu) reuses the same Family (DET-2).
- **The area detectors bind the catalog `Camera`, which presents the Detector Role.** The PCO and Zyla indirect-detection cameras for nano-tomography are thin `Camera` instances (DET-1).
- **The stages bind `RotaryStage` and `LinearStage`.** Sample rotation (the tomo / fluo-tomo master motion), coarse positioning, and the PI piezo raster scanner (the nano-XRF mapping motion) (SAMPLE-1).
- **The optics bind existing Families.** `Monochromator` (the Kohzu DCM), `Slit` (primary / secondary / sample-side), `FluxMonitor` (the EBV beam monitors), `Shutter` (the fast shutter), `InsertionDevice` (the U205 undulator).
- **The Methods are reused.** Nano-tomography is the existing `tomography` Method; nano-XRF mapping is the pending `scanning_fluorescence_microscopy` Method (2-ID / XFM / LIX). ID16B is a further consumer of each (TECH-1, METHOD-1).

ID16B coins no new Family, nothing graduates, and the catalog is unchanged.

### Deliberately not here yet

- **The sample environments (`ENV-1`).** The config carries a cryostream, a furnace, and a xeol environment with Eurotherm / nanodac regulation. A `Cryostat` Family is not yet in the catalog; the sample environment is deferred to keep this cut vocabulary-neutral. It is the natural first candidate for a future cut (and a rule-of-three watch for a sample-environment Family across ID16B, the 4-ID magnet / temperature stack, and others).
- **The PSS permit signals (`PSS-1`).** The shutter handles are known; the permit signals behind them are not in the config; carried pending, not invented.
- **Vendor models, serials, focal-spot sizes, and physical positions.** Not in the config; carried confirm.
- **The simulated devices and full asset-tree scenarios.** No `test_id16b_*.py` registers the asset tree, and no vendor Models are bound.
- **Operations and experiment views.** A runbook and live experiment view for a beamline CORA does not yet drive would be invention; see the note on the [index](index.md#not-yet-documented).

## Open questions

*What CORA needs the ID16B team to confirm before the model can be trusted.*

ID16B was reverse-engineered from the beamline's own public BLISS Beacon device database ([`gitlab.esrf.fr/id16b/beamline_configuration`](https://gitlab.esrf.fr/id16b/beamline_configuration)), so the control handles on the [device pages](index.md) are the beamline's real BLISS object and Tango device names, read from the config rather than confirmed by staff. Each row below is a fact the beamline team owns, not a CORA modelling choice (those are on [Model](#deliberately-not-here-yet)). It is a delete-on-answer queue. Priorities are `Blocks-build`, `Blocks-go-live`, and `Nice-to-have`.

### Control and the BLISS / Tango floor

| ID | Priority | Question | CORA assumes | Resolves |
| --- | --- | --- | --- | --- |
| CTRL-1 | Blocks-go-live | Are the BLISS object and Tango device handles read from the public config current and correct against the live system? | The handles in the descriptor are taken from the config and carried confirm. | Verifying each Asset's control handle. |
| CTRL-2 | Nice-to-have | Which BLISS scan procedures ID16B uses per mode (daiquiri_tomo vs daiquiri_fluo / fluo3d), and which the CORA edge drives through versus replaces. | A continuous-rotation tomo scan and a piezo raster fluo scan; the conduct-versus-replace split is per routine. | The orchestration seam over the `ControlPort`. |

### Topology and scope

| ID | Priority | Question | CORA assumes | Resolves |
| --- | --- | --- | --- | --- |
| ENC-1 | Blocks-go-live | The hutch grouping: one optics hutch and one experiment hutch holding the nanofocus and sample? | One `id16b-optics` and one `id16b-experiment` enclosure. | The Enclosure grouping. |
| ENV-1 | Nice-to-have | The sample environments (cryostream, furnace, xeol) in the config: do they enter a later cut, and as which Family? | Noted, not modelled in this cut; no `Cryostat` Family yet. | The sample-environment roster. |

### Source and optics

| ID | Priority | Question | CORA assumes | Resolves |
| --- | --- | --- | --- | --- |
| SRC-1 | Blocks-go-live | The U205 undulator energy reach and gap mapping. | An undulator source feeding the DCM; energy reach to confirm. | The source Asset. |
| OPT-1 | Blocks-go-live | The Kohzu crystal-pair selection per energy, and the KB focal spot / working distance. | Kohzu Si111 / Si333 / Si311; KB mirrors as the nanofocus. | The optics and nanofocus modelling. |

### Sample and detection

| ID | Priority | Question | CORA assumes | Resolves |
| --- | --- | --- | --- | --- |
| SAMPLE-1 | Blocks-go-live | The operative rotation / coarse / piezo-scanner axis set per mode (tomo vs fluo). | Rotation (srot) + coarse (sx/sy/sz) + PI piezo scanner (sampy/sampz); rotation is the tomo master motion, the piezo scanner the fluo raster. | The sample-stage modelling. |
| DET-1 | Blocks-go-live | The operative XRF detector and area detector per mode, and the detector-stage axes. | FalconX silicon-drift for nano-XRF (EnergyDispersiveSpectrometer); PCO / Zyla for nano-tomography (Camera). | The detector modelling. |
| DET-2 | Nice-to-have | The role of the optical spectrometer (QEPro / Hamamatsu): xeol, beam diagnostics, or a science channel? | An optical-emission spectrometer reusing EnergyDispersiveSpectrometer. | The optical-spectrometer modelling. |

### Safety and resources

| ID | Priority | Question | CORA assumes | Resolves |
| --- | --- | --- | --- | --- |
| PSS-1 | Blocks-go-live | The ESRF PSS permit signals behind the front-end / fast shutters (not in the config). | Permit leaves to be named; the shutter handles are known, the permit signals are not. | The Enclosure permit signals and the safety tier. |
| SUP-1 | Nice-to-have | The vacuum extent of the beam path and the cooling-water / beam supplies a run draws on. | Photon beam, cooling water, and vacuum, carried pending. | The Supply observations. |
| GOV-1 | Nice-to-have | The ESRF operator pool and safety-review structure (site-level, shared across beamlines). | Carried pending on the ESRF Site, not instantiated per beamline. | The governance principals. |

### Technique

| ID | Priority | Question | CORA assumes | Resolves |
| --- | --- | --- | --- | --- |
| TECH-1 | Blocks-go-live | Do nano-tomography and nano-XRF map cleanly onto the existing `tomography` and `scanning_fluorescence_microscopy` Methods? | Both reused as pending Practices; ID16B is a further consumer of each. | The two Practices. |
